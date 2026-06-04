"""
jd_gap_analyzer.py — Compare candidate profile against JD requirements.

Produces four gap categories:
  1. skill_gaps         — skills required/preferred in JD but not detected in resume
  2. certification_gaps — certifications mentioned in JD but not in resume
  3. experience_gap     — years required vs. years implied in resume
  4. keyword_gaps       — JD key phrases absent from the resume text
Plus prioritised next_steps and an overall jd_readiness_score.
"""
from __future__ import annotations
import re
import math
import logging
from dataclasses import dataclass, field

log = logging.getLogger(__name__)

# ── Data classes ─────────────────────────────────────────────────────────────

@dataclass
class SkillGapItem:
    name: str
    importance: str          # "required" | "preferred"
    reason: str              # why it matters
    resources: list[dict]    # [{name, url, free}]


@dataclass
class CertGapItem:
    name: str
    why_relevant: str
    how_to_get: str


@dataclass
class ExperienceGap:
    required_years: int
    resume_implied_years: int   # best estimate from resume text
    gap_years: int
    verdict: str                # "sufficient" | "close" | "significant"
    advice: str


@dataclass
class KeywordGap:
    phrase: str
    suggestion: str             # how to add it to the resume


@dataclass
class NextStep:
    priority: int
    category: str               # "skill" | "cert" | "experience" | "keyword" | "resume"
    action: str
    details: str


@dataclass
class JDGapReport:
    jd_job_title: str = ""
    jd_readiness_score: float = 0.0      # 0–100
    jd_readiness_label: str = "Needs Work"
    required_skill_coverage: float = 0.0  # fraction
    preferred_skill_coverage: float = 0.0
    skill_gaps: list[SkillGapItem] = field(default_factory=list)
    certification_gaps: list[CertGapItem] = field(default_factory=list)
    experience_gap: ExperienceGap | None = None
    keyword_gaps: list[KeywordGap] = field(default_factory=list)
    matched_required: list[str] = field(default_factory=list)
    matched_preferred: list[str] = field(default_factory=list)
    next_steps: list[NextStep] = field(default_factory=list)
    processing_notes: list[str] = field(default_factory=list)


# ── Resource fallback map ─────────────────────────────────────────────────────
_RESOURCE_FALLBACK = {
    "javascript": [{"name": "javascript.info", "url": "https://javascript.info", "free": True}],
    "typescript": [{"name": "TypeScript Handbook", "url": "https://www.typescriptlang.org/docs/", "free": True}],
    "react": [{"name": "React Docs", "url": "https://react.dev", "free": True}],
    "node.js": [{"name": "Node.js Docs", "url": "https://nodejs.org/en/docs/", "free": True}],
    "docker": [{"name": "Docker Getting Started", "url": "https://docs.docker.com/get-started/", "free": True}],
    "kubernetes": [{"name": "Kubernetes Basics", "url": "https://kubernetes.io/docs/tutorials/kubernetes-basics/", "free": True}],
    "python": [{"name": "Python Docs", "url": "https://docs.python.org/3/tutorial/", "free": True}],
    "sql": [{"name": "SQLZoo", "url": "https://sqlzoo.net", "free": True}],
    "aws": [{"name": "AWS Skill Builder", "url": "https://skillbuilder.aws", "free": True}],
    "machine learning": [{"name": "fast.ai", "url": "https://www.fast.ai", "free": True}],
    "tensorflow": [{"name": "TensorFlow Tutorials", "url": "https://www.tensorflow.org/tutorials", "free": True}],
    "pytorch": [{"name": "PyTorch Tutorials", "url": "https://pytorch.org/tutorials/", "free": True}],
    "git": [{"name": "Pro Git Book", "url": "https://git-scm.com/book/en/v2", "free": True}],
    "ci/cd": [{"name": "GitHub Actions Docs", "url": "https://docs.github.com/en/actions", "free": True}],
    "graphql": [{"name": "GraphQL Docs", "url": "https://graphql.org/learn/", "free": True}],
    "redis": [{"name": "Redis University", "url": "https://university.redis.com", "free": True}],
}
_DEFAULT_RESOURCE = [{"name": "Search on Coursera (free audit)", "url": "https://www.coursera.org/search?query={skill}&price=free", "free": True}]

# ── Experience year extractor (from resume text) ──────────────────────────────
_RESUME_EXP_RE = re.compile(
    r"(\d{4})\s*[-–]\s*(\d{4}|present|current|now)",
    re.IGNORECASE,
)

def _estimate_resume_years(resume_text: str) -> int:
    """Estimate total years of professional experience from date ranges in resume."""
    import datetime
    current_year = datetime.datetime.now().year
    total = 0
    for m in _RESUME_EXP_RE.finditer(resume_text):
        start = int(m.group(1))
        end_str = m.group(2).lower()
        end = current_year if end_str in ("present", "current", "now") else int(end_str)
        if 1970 <= start <= current_year and start <= end <= current_year + 1:
            total += end - start
    return min(total, 40)   # cap at 40 years


# ── Certification detection in resume ────────────────────────────────────────
_CERT_RE_SIMPLE = re.compile(
    r"AWS\s+Certified|GCP\s+Certified|Azure\s+Certified|"
    r"Kubernetes\s+Certified|CKA|CKAD|CKS|PMP|Scrum\s+Master|CSM|PSM|"
    r"CISSP|CEH|CompTIA|Tableau\s+Certified|Databricks\s+Certified|"
    r"TensorFlow\s+Developer|Oracle\s+Certified|Salesforce\s+Certified|"
    r"PMI-?\w+|ITIL",
    re.IGNORECASE,
)

def _certs_in_resume(resume_text: str) -> set[str]:
    found = set()
    for m in _CERT_RE_SIMPLE.finditer(resume_text):
        found.add(m.group(0).strip().lower()[:20])
    return found


# ── Main function ─────────────────────────────────────────────────────────────

def analyze_jd_gaps(
    jd_result,                      # JDParseResult
    extracted_skills: list,         # list[ExtractedSkill] from pipeline
    resume_text: str,
    services_catalog: list[dict],
) -> JDGapReport:
    """
    Compare candidate's extracted skills + resume against JD requirements.
    Returns JDGapReport.
    """
    from app.config import settings

    report = JDGapReport(jd_job_title=jd_result.job_title)
    candidate_skills = {s.name for s in extracted_skills if s.confidence >= settings.PRESENCE_THRESHOLD}

    # ── 1. Skill gaps ──────────────────────────────────────────────────────
    matched_req = [s for s in jd_result.required_skills if s in candidate_skills]
    matched_pref = [s for s in jd_result.preferred_skills if s in candidate_skills]
    report.matched_required = matched_req
    report.matched_preferred = matched_pref

    n_req = len(jd_result.required_skills)
    n_pref = len(jd_result.preferred_skills)
    report.required_skill_coverage = len(matched_req) / n_req if n_req else 1.0
    report.preferred_skill_coverage = len(matched_pref) / n_pref if n_pref else 1.0

    def _resources_for(skill_name: str) -> list[dict]:
        # Try services catalog first
        for svc in services_catalog:
            if svc.get("skill", "").lower() == skill_name.lower() and svc.get("free", False):
                return [{"name": svc.get("resource_name", ""), "url": svc.get("url", ""), "free": True}]
        # Fallback
        res = _RESOURCE_FALLBACK.get(skill_name)
        if res:
            return res
        return [{"name": f"Search on Coursera (free audit)", "url": f"https://www.coursera.org/search?query={skill_name.replace(' ', '+')}&price=free", "free": True}]

    for skill in jd_result.required_skills:
        if skill not in candidate_skills:
            report.skill_gaps.append(SkillGapItem(
                name=skill,
                importance="required",
                reason=f"Listed as a required skill for the {jd_result.job_title or 'target'} role.",
                resources=_resources_for(skill),
            ))

    for skill in jd_result.preferred_skills:
        if skill not in candidate_skills:
            report.skill_gaps.append(SkillGapItem(
                name=skill,
                importance="preferred",
                reason=f"A preferred/bonus skill that will strengthen your application.",
                resources=_resources_for(skill),
            ))

    # ── 2. Certification gaps ──────────────────────────────────────────────
    resume_certs = _certs_in_resume(resume_text)
    for cert in jd_result.required_certifications:
        cert_key = cert.lower()[:20]
        if not any(cert_key[:10] in rc for rc in resume_certs):
            report.certification_gaps.append(CertGapItem(
                name=cert,
                why_relevant=f"Mentioned in the job description as a certification requirement.",
                how_to_get=f"Search the official certification page for '{cert}' to find exam details and prep resources.",
            ))

    # ── 3. Experience gap ──────────────────────────────────────────────────
    if jd_result.required_experience_years > 0:
        resume_years = _estimate_resume_years(resume_text)
        gap = max(0, jd_result.required_experience_years - resume_years)
        if gap == 0:
            verdict = "sufficient"
            advice = f"Your estimated {resume_years} years of experience meets the {jd_result.required_experience_years}+ year requirement."
        elif gap <= 1:
            verdict = "close"
            advice = (
                f"You appear to have ~{resume_years} years; the role asks for {jd_result.required_experience_years}+. "
                "Strengthen your resume by quantifying impact and expanding project descriptions."
            )
        else:
            verdict = "significant"
            advice = (
                f"The role requires {jd_result.required_experience_years}+ years; your resume implies ~{resume_years}. "
                "Consider open-source contributions, freelance projects, or Kaggle competitions to close this gap faster."
            )
        report.experience_gap = ExperienceGap(
            required_years=jd_result.required_experience_years,
            resume_implied_years=resume_years,
            gap_years=gap,
            verdict=verdict,
            advice=advice,
        )

    # ── 4. Resume keyword gaps ─────────────────────────────────────────────
    resume_lower = resume_text.lower()
    for phrase in jd_result.key_phrases:
        if phrase.replace("-", " ") not in resume_lower and phrase not in resume_lower:
            report.keyword_gaps.append(KeywordGap(
                phrase=phrase,
                suggestion=(
                    f"Add '{phrase}' naturally to your work experience or skills section "
                    "to improve ATS and recruiter keyword matching."
                ),
            ))

    # ── 5. Readiness score ─────────────────────────────────────────────────
    req_w = 0.70
    pref_w = 0.20
    kw_w  = 0.10

    kw_matched = len(jd_result.key_phrases) - len(report.keyword_gaps)
    kw_coverage = kw_matched / len(jd_result.key_phrases) if jd_result.key_phrases else 1.0

    if n_pref == 0:
        raw = report.required_skill_coverage * (req_w + pref_w) + kw_coverage * kw_w
    else:
        raw = (
            report.required_skill_coverage * req_w +
            report.preferred_skill_coverage * pref_w +
            kw_coverage * kw_w
        )
    score = round(min(100.0, max(0.0, raw * 100)), 1)
    report.jd_readiness_score = score
    report.jd_readiness_label = (
        "Excellent" if score >= 90 else
        "Good" if score >= 70 else
        "Fair" if score >= 50 else
        "Needs Work"
    )

    # ── 6. Next steps (prioritised) ────────────────────────────────────────
    priority = 1

    # Required skills first
    for gap in report.skill_gaps:
        if gap.importance == "required" and priority <= 5:
            report.next_steps.append(NextStep(
                priority=priority,
                category="skill",
                action=f"Learn {gap.name}",
                details=f"{gap.reason} Start with: {gap.resources[0]['name']} ({gap.resources[0]['url']})",
            ))
            priority += 1

    # Experience gap if significant
    if report.experience_gap and report.experience_gap.verdict == "significant":
        report.next_steps.append(NextStep(
            priority=priority,
            category="experience",
            action="Build more hands-on experience",
            details=report.experience_gap.advice,
        ))
        priority += 1

    # Certifications
    for cert_gap in report.certification_gaps[:2]:
        report.next_steps.append(NextStep(
            priority=priority,
            category="cert",
            action=f"Earn {cert_gap.name}",
            details=cert_gap.how_to_get,
        ))
        priority += 1

    # Keyword gaps
    if report.keyword_gaps:
        top_kw = [k.phrase for k in report.keyword_gaps[:5]]
        report.next_steps.append(NextStep(
            priority=priority,
            category="resume",
            action="Update resume keywords",
            details=f"Add these JD phrases to your resume: {', '.join(top_kw)}. Use the same wording as the job posting to pass ATS filters.",
        ))
        priority += 1

    # Preferred skills
    for gap in report.skill_gaps:
        if gap.importance == "preferred" and priority <= 8:
            report.next_steps.append(NextStep(
                priority=priority,
                category="skill",
                action=f"Add {gap.name} to your profile",
                details=f"Preferred but not required. {gap.resources[0]['name']} ({gap.resources[0]['url']})",
            ))
            priority += 1

    # Processing notes
    if n_req == 0:
        report.processing_notes.append("No required skills were extracted from the job description. Try pasting the full JD text.")
    if not jd_result.key_phrases:
        report.processing_notes.append("No key phrases extracted. The job description may be very short.")

    log.info(
        "JD gap analysis: score=%.1f skill_gaps=%d cert_gaps=%d kw_gaps=%d next_steps=%d",
        score, len(report.skill_gaps), len(report.certification_gaps),
        len(report.keyword_gaps), len(report.next_steps),
    )
    return report


# ── Apply-Ready verdict (wraps llm_service) ───────────────────────────────

def get_apply_verdict(gap_report: "JDGapReport", candidate_name: str) -> dict:
    """
    Produce the 3-tier Apply-Ready verdict using the gap report + LLM.
    Called by the /analyze/jd endpoint after analyze_jd_gaps().
    """
    try:
        from app.services.llm_service import generate_apply_verdict
        missing_req = [g.name for g in gap_report.skill_gaps if g.importance == "required"]
        return generate_apply_verdict(
            score=gap_report.jd_readiness_score,
            required_coverage=gap_report.required_skill_coverage,
            missing_required=missing_req,
            job_title=gap_report.jd_job_title or "target role",
            candidate_name=candidate_name,
        )
    except Exception as e:
        log.warning("Verdict generation failed: %s", e)
        cov = gap_report.required_skill_coverage
        if cov >= 0.70:
            return {"tier": "Apply Now", "colour": "green", "icon": "check",
                    "summary": "Your profile is competitive for this role.", "required_coverage_pct": round(cov*100)}
        elif cov >= 0.40:
            return {"tier": "Apply With Prep", "colour": "amber", "icon": "lightning",
                    "summary": "Close 1-2 key gaps before submitting.", "required_coverage_pct": round(cov*100)}
        else:
            return {"tier": "Build First", "colour": "red", "icon": "target",
                    "summary": "Spend 4-8 weeks building core skills before applying.", "required_coverage_pct": round(cov*100)}
