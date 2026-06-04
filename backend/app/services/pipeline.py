"""
pipeline.py - THE orchestrator: all 4 extraction passes + report assembly
"""

from __future__ import annotations
import logging
import uuid

from app.config import settings
from app.schemas import (
    AnalysisReport, ExtractedSkill, OtherRoleMatch, CareerPathAdvice,
)
from app.services import resume_parser
from app.services.skill_extractor       import extract_skills_by_alias
from app.services.fuzzy_extractor       import extract_skills_by_fuzzy
from app.services.ner_extractor         import extract_skills_by_ner
from app.services.semantic_matcher      import find_semantic_skills
from app.services.readiness_engine      import compute_readiness
from app.services.recommendation_engine import generate_skill_gaps
from app.services.text_utils            import redact_pii, find_spans

log = logging.getLogger(__name__)

_SENIORITY_WORDS = frozenset({
    "senior", "sr", "junior", "jr", "lead", "principal", "staff",
    "head", "manager", "director", "associate", "mid",
})


def _merge_skill_lists(*skill_lists):
    seen = {}
    for skill_list in skill_lists:
        for skill in skill_list:
            if skill.name not in seen:
                seen[skill.name] = skill
            else:
                existing = seen[skill.name]
                if skill.confidence > existing.confidence:
                    merged = ExtractedSkill(
                        name=skill.name,
                        confidence=max(skill.confidence, existing.confidence),
                        how_found="both",
                        aliases_matched=existing.aliases_matched or skill.aliases_matched,
                        evidence=existing.evidence or skill.evidence,
                        evidence_offsets=existing.evidence_offsets,
                        low_confidence_flag=existing.low_confidence_flag and skill.low_confidence_flag,
                    )
                    seen[skill.name] = merged
    return sorted(seen.values(), key=lambda s: s.confidence, reverse=True)


def _get_evidence_offsets(skill_name, aliases, text):
    terms = [skill_name] + aliases
    all_spans = []
    for term in terms:
        all_spans.extend(find_spans(text, term))
    all_spans.sort(key=lambda s: s[0])
    merged = []
    for span in all_spans:
        if merged and span[0] <= merged[-1][1]:
            merged[-1][1] = max(merged[-1][1], span[1])
        else:
            merged.append(list(span))
    return merged[:10]


def run_pipeline(raw_text, role_id, catalog, roles):
    """
    Execute the full analysis pipeline.
    Raises ValueError if role_id not found.
    Returns AnalysisReport.
    """
    processing_notes = []

    # Strip metadata keys
    catalog = {k: v for k, v in catalog.items() if not k.startswith("_") and isinstance(v, list)}

    # Step 0: Validate role
    role = roles.get(role_id)
    if role is None:
        raise ValueError(f"Role '{role_id}' not found.")

    # Step 1: Parse + redact
    cleaned_text   = resume_parser.clean_text(raw_text)
    sections_raw   = resume_parser.detect_sections(cleaned_text)
    candidate_name = resume_parser.extract_candidate_name(sections_raw)
    cleaned_text   = redact_pii(cleaned_text)
    sections       = resume_parser.detect_sections(cleaned_text)
    sections_found = [s for s in sections if s != "header"]

    log.info("Parsed: name=%s sections=%s (PII redacted)", candidate_name, sections_found)

    # Step 2: Pass 1 - Alias
    alias_skills = extract_skills_by_alias(sections, catalog)
    alias_found  = {s.name for s in alias_skills}
    log.info("Pass 1 (alias):    %d skills", len(alias_skills))

    # Step 3: Pass 2 - Fuzzy
    fuzzy_skills = extract_skills_by_fuzzy(sections, catalog, alias_found)
    fuzzy_found  = alias_found | {s.name for s in fuzzy_skills}
    log.info("Pass 2 (fuzzy):    %d new skills", len(fuzzy_skills))

    # Step 4: Pass 3 - BERT NER
    ner_skills = extract_skills_by_ner(sections, catalog, fuzzy_found)
    ner_found  = fuzzy_found | {s.name for s in ner_skills}
    log.info("Pass 3 (NER):      %d new skills", len(ner_skills))

    # Step 5: Pass 4 - Semantic
    semantic_skills = find_semantic_skills(sections, catalog, ner_found)
    log.info("Pass 4 (semantic): %d new skills", len(semantic_skills))

    # Step 6: Merge
    all_skills = _merge_skill_lists(alias_skills, fuzzy_skills, ner_skills, semantic_skills)
    log.info("Merged total: %d skills", len(all_skills))

    # Step 7: Evidence offsets
    for skill in all_skills:
        aliases = catalog.get(skill.name, [])
        skill.evidence_offsets = _get_evidence_offsets(skill.name, aliases, cleaned_text)

    # Step 8: Readiness
    readiness = compute_readiness(all_skills, role)
    log.info("Readiness: %.1f (%s)", readiness.score, readiness.label)

    # Step 9: Gaps
    skill_gaps = generate_skill_gaps(all_skills, role)
    log.info("Gaps: %d", len(skill_gaps))

    # Step 10: Multi-role scoring
    candidate_skill_names = {
        s.name for s in all_skills if s.confidence >= settings.PRESENCE_THRESHOLD
    }
    other_matches = []

    for other_id, other_role in roles.items():
        if other_id == role_id:
            continue
        other_readiness = compute_readiness(all_skills, other_role)
        other_required  = set(other_role.get("required_skills", []))
        matched         = candidate_skill_names & other_required
        missing         = other_required - candidate_skill_names
        next_steps      = [s for s in other_role.get("required_skills", []) if s in missing][:3]

        other_matches.append(OtherRoleMatch(
            role_id=other_id,
            role_title=other_role.get("title", other_id),
            score=other_readiness.score,
            label=other_readiness.label,
            required_coverage=other_readiness.required_coverage,
            skills_matched=len(matched),
            skills_gap_count=len(missing),
            next_steps=next_steps,
            seniority=other_role.get("seniority", ""),
        ))

    other_matches.sort(key=lambda r: r.score, reverse=True)
    other_matches = other_matches[:5]

    # Step 10b: Career path advice
    career_path_advice = None
    role_title_lower   = role.get("title", "").lower()
    base_keywords      = [w for w in role_title_lower.split() if w not in _SENIORITY_WORDS]

    if base_keywords:
        easier_roles  = []
        stretch_roles = []
        key_skills    = []

        for m in other_matches:
            t = m.role_title.lower()
            if not any(kw in t for kw in base_keywords):
                continue
            if m.score >= readiness.score:
                stretch_roles.append(m.role_title)
                if not key_skills:
                    key_skills = m.next_steps
            else:
                easier_roles.append(m.role_title)

        primary_missing = [
            s for s in role.get("required_skills", [])
            if s not in candidate_skill_names
        ][:3]

        career_path_advice = CareerPathAdvice(
            target_role_id=role_id,
            target_role_title=role.get("title", role_id),
            current_label=f"{readiness.label} match for {role.get('title', role_id)}",
            easier_roles=easier_roles[:3],
            stretch_roles=stretch_roles[:3],
            key_skills_to_unlock_next=key_skills or primary_missing,
        )

    # Step 11: Quality notes
    word_count = len(cleaned_text.split())
    if word_count < 50:
        processing_notes.append(
            f"Resume is very short ({word_count} words). Skill extraction may be incomplete."
        )
    elif word_count < 150:
        processing_notes.append(
            f"Resume is short ({word_count} words). Consider expanding experience descriptions."
        )

    if "experience" not in sections_found:
        processing_notes.append(
            "No 'Experience' section detected. A labelled 'Work Experience' section improves accuracy."
        )

    flagged = sum(1 for s in all_skills if s.low_confidence_flag)
    if flagged:
        processing_notes.append(
            f"{flagged} skill(s) were flagged as low-confidence. "
            "Add work-experience sentences to demonstrate these skills."
        )

    # Step 12: Assemble report
    report_id = str(uuid.uuid4())[:12]

    log.info(
        "Report %s: role=%s candidate=%s score=%.1f skills=%d gaps=%d",
        report_id, role_id, candidate_name,
        readiness.score, len(all_skills), len(skill_gaps),
    )

    return AnalysisReport(
        report_id=report_id,
        role_id=role_id,
        role_title=role.get("title", role_id),
        candidate_name=candidate_name,
        readiness=readiness,
        extracted_skills=all_skills,
        skill_gaps=skill_gaps,
        other_role_matches=other_matches,
        career_path_advice=career_path_advice,
        resume_sections_found=sections_found,
        total_skills_extracted=len(all_skills),
        total_skills_required=len(role.get("required_skills", [])),
        processing_notes=processing_notes,
    )
