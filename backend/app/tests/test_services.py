"""
test_services.py - Unit tests for service modules.
"""
import pytest
from app.services.text_utils       import redact_pii, find_spans
from app.services.resume_parser    import clean_text, detect_sections, extract_candidate_name
from app.services.skill_extractor  import extract_skills_by_alias
from app.services.fuzzy_extractor  import extract_skills_by_fuzzy, _threshold_for_alias, _scale_confidence
from app.services.readiness_engine import compute_readiness
from app.schemas import ExtractedSkill, EvidenceItem


class TestRedactPii:
    def test_email_redacted(self):
        out = redact_pii("Contact me at alice@example.com please")
        assert "alice@example.com" not in out
        assert "[EMAIL]" in out

    def test_phone_redacted(self):
        out = redact_pii("Call me at +91-9876543210")
        assert "9876543210" not in out

    def test_url_redacted(self):
        out = redact_pii("Visit https://github.com/user/repo")
        assert "github.com" not in out

    def test_clean_text_unchanged(self):
        text = "I have 5 years of Python experience."
        assert redact_pii(text) == text

    def test_multiple_emails(self):
        out = redact_pii("a@b.com and c@d.com")
        assert out.count("[EMAIL]") == 2


class TestFindSpans:
    def test_exact_match(self):
        spans = find_spans("I know python well", "python")
        assert len(spans) == 1
        assert spans[0] == [7, 13]

    def test_case_insensitive(self):
        spans = find_spans("I use Python and PYTHON", "python")
        assert len(spans) == 2

    def test_no_match(self):
        assert find_spans("hello world", "java") == []


class TestCleanText:
    def test_strips_leading_trailing(self):
        out = clean_text("  hello world  ")
        assert out == out.strip()
        assert "hello" in out and "world" in out

    def test_normalises_newlines(self):
        out = clean_text("line1\r\nline2\n\n\nline3")
        assert "\r" not in out


class TestDetectSections:
    def test_detects_experience(self):
        sections = detect_sections("Work Experience\nBuilt ML models with Python")
        assert "experience" in sections

    def test_detects_skills(self):
        sections = detect_sections("Skills\nPython, SQL, Docker")
        assert "skills" in sections

    def test_always_has_header(self):
        sections = detect_sections("John Doe\njohn@example.com")
        assert "header" in sections

    def test_detects_education(self):
        sections = detect_sections("Education\nBSc Computer Science")
        assert "education" in sections

    def test_detects_projects(self):
        sections = detect_sections("Projects\nBuilt a recommendation engine")
        assert "projects" in sections


class TestExtractCandidateName:
    def test_extracts_name(self):
        sections = {"header": "John Smith\njohn@example.com"}
        name = extract_candidate_name(sections)
        assert "John" in name

    def test_unknown_when_no_header(self):
        name = extract_candidate_name({})
        assert name == "Unknown"


class TestAliasExtractor:
    def test_finds_python(self, catalog):
        sections = {"skills": "Python, SQL, Docker", "header": ""}
        skills = extract_skills_by_alias(sections, catalog)
        names = [s.name for s in skills]
        assert "python" in names

    def test_finds_alias(self, catalog):
        sections = {"experience": "Deployed using k8s on AWS", "header": ""}
        skills = extract_skills_by_alias(sections, catalog)
        names = [s.name for s in skills]
        assert "kubernetes" in names

    def test_confidence_le_1(self, catalog):
        sections = {"skills": "Python, Docker, AWS, SQL, machine learning", "header": ""}
        skills = extract_skills_by_alias(sections, catalog)
        for s in skills:
            assert 0.0 <= s.confidence <= 1.0

    def test_sorted_by_confidence(self, catalog):
        sections = {
            "experience": "Built Python and machine learning systems with Docker and Kubernetes",
            "skills": "Python, Docker",
            "header": "",
        }
        skills = extract_skills_by_alias(sections, catalog)
        confs = [s.confidence for s in skills]
        assert confs == sorted(confs, reverse=True)


class TestFuzzyThresholds:
    def test_short_returns_none(self):
        assert _threshold_for_alias("go") is None
        assert _threshold_for_alias("r") is None

    def test_medium_returns_85(self):
        assert _threshold_for_alias("java") == 85.0

    def test_long_returns_82(self):
        assert _threshold_for_alias("pytorch") == 82.0

    def test_multiword_returns_88(self):
        assert _threshold_for_alias("machine learning") == 88.0


class TestFuzzyScale:
    def test_ratio_82_maps_to_0_45(self):
        assert abs(_scale_confidence(82.0) - 0.45) < 0.01

    def test_ratio_100_maps_to_0_85(self):
        assert abs(_scale_confidence(100.0) - 0.85) < 0.01

    def test_midrange(self):
        c = _scale_confidence(91.0)
        assert 0.45 < c < 0.85


class TestFuzzyExtractor:
    def test_catches_typo(self, catalog):
        sections = {"skills": "pyhon, SQL", "header": ""}
        skills = extract_skills_by_fuzzy(sections, catalog, set())
        names = [s.name for s in skills]
        assert "python" in names

    def test_skips_already_found(self, catalog):
        sections = {"skills": "Python, Docker", "header": ""}
        already = {"python", "docker"}
        skills = extract_skills_by_fuzzy(sections, catalog, already)
        names = [s.name for s in skills]
        assert "python" not in names
        assert "docker" not in names

    def test_all_confidences_in_range(self, catalog):
        sections = {"skills": "pyhon, scikit learn, postgress", "header": ""}
        skills = extract_skills_by_fuzzy(sections, catalog, set())
        for s in skills:
            assert 0.0 <= s.confidence <= 1.0

    def test_how_found_is_fuzzy(self, catalog):
        sections = {"skills": "pyhon", "header": ""}
        skills = extract_skills_by_fuzzy(sections, catalog, set())
        if skills:
            assert skills[0].how_found == "fuzzy"


def _make_skill(name, conf):
    return ExtractedSkill(
        name=name, confidence=conf, how_found="alias",
        aliases_matched=[], evidence=[], evidence_offsets=[],
    )


class TestReadinessEngine:
    def test_perfect_score_100(self):
        skills = [_make_skill("python", 0.9), _make_skill("sql", 0.9), _make_skill("docker", 0.9)]
        role = {"required_skills": ["python", "sql", "docker"], "nice_to_have_skills": []}
        r = compute_readiness(skills, role)
        assert r.score == 100.0
        assert r.label == "Excellent"

    def test_zero_score_empty_skills(self):
        r = compute_readiness([], {"required_skills": ["python", "sql"], "nice_to_have_skills": []})
        assert r.score == 0.0
        assert r.label == "Needs Work"

    def test_partial_required(self):
        skills = [_make_skill("python", 0.9)]
        role = {"required_skills": ["python", "sql", "docker"], "nice_to_have_skills": []}
        r = compute_readiness(skills, role)
        assert 0 < r.score < 100
        assert r.required_coverage == pytest.approx(1/3, abs=0.01)

    def test_nice_to_have_contributes(self):
        skills = [_make_skill("nice_skill", 0.9)]
        role = {"required_skills": [], "nice_to_have_skills": ["nice_skill"]}
        r = compute_readiness(skills, role)
        assert r.score > 0

    def test_ci_bounds_valid(self):
        skills = [_make_skill("python", 0.9), _make_skill("sql", 0.9)]
        role = {"required_skills": ["python", "sql", "docker"], "nice_to_have_skills": []}
        r = compute_readiness(skills, role)
        assert 0 <= r.confidence_low <= r.confidence_high <= 100

    def test_label_good_range(self):
        skills = [_make_skill(n, 0.9) for n in ["python", "sql", "docker", "ml"]]
        role = {
            "required_skills": ["python", "sql", "docker", "ml", "aws"],
            "nice_to_have_skills": []
        }
        r = compute_readiness(skills, role)
        assert r.label in ("Good", "Fair")


class TestPipeline:
    def test_ds_resume_scores_well(self, ds_resume, catalog, roles):
        from app.services.pipeline import run_pipeline
        role_id = "data_scientist_mid" if "data_scientist_mid" in roles else next(iter(roles))
        report = run_pipeline(ds_resume, role_id, catalog, roles)
        assert report.readiness.score > 30
        assert len(report.extracted_skills) > 3
        assert report.candidate_name != ""

    def test_junior_scores_lower_than_senior(self, junior_resume, ds_resume, catalog, roles):
        from app.services.pipeline import run_pipeline
        target = next(
            (r for r in roles if "senior" in r.lower() and "data" in r.lower()),
            next(iter(roles))
        )
        senior_report = run_pipeline(ds_resume,     target, catalog, roles)
        junior_report = run_pipeline(junior_resume, target, catalog, roles)
        assert senior_report.readiness.score >= junior_report.readiness.score

    def test_report_has_all_fields(self, ds_resume, catalog, roles):
        from app.services.pipeline import run_pipeline
        role_id = next(iter(roles))
        report = run_pipeline(ds_resume, role_id, catalog, roles)
        assert report.report_id
        assert report.role_id == role_id
        assert report.readiness is not None
        assert isinstance(report.extracted_skills, list)
        assert isinstance(report.skill_gaps, list)
        assert isinstance(report.other_role_matches, list)

    def test_invalid_role_raises(self, ds_resume, catalog, roles):
        from app.services.pipeline import run_pipeline
        with pytest.raises(ValueError):
            run_pipeline(ds_resume, "nonexistent_role_xyz", catalog, roles)
