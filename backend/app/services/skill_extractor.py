"""
skill_extractor.py — Pass 1: exact alias matching.
Fast, precise, zero ML. Handles ~80% of skills in well-written resumes.
"""
import re
import logging
from app.config import settings
from app.schemas import ExtractedSkill, EvidenceItem

log = logging.getLogger(__name__)

SECTION_WEIGHTS: dict[str, float] = {
    "experience":   settings.SECTION_WEIGHT_EXPERIENCE,
    "projects":     settings.SECTION_WEIGHT_PROJECTS,
    "skills":       settings.SECTION_WEIGHT_SKILLS,
    "education":    settings.SECTION_WEIGHT_EDUCATION,
    "summary":      settings.SECTION_WEIGHT_OTHER,
    "awards":       settings.SECTION_WEIGHT_OTHER,
    "publications": settings.SECTION_WEIGHT_OTHER,
    "header":       settings.SECTION_WEIGHT_OTHER,
}

_TECH_CONTEXT = set(settings.TECH_CONTEXT_WORDS)


def _find_snippets(term: str, text: str) -> list[str]:
    pattern = re.compile(r"\b" + re.escape(term) + r"\b", re.IGNORECASE)
    sentences = re.split(r"(?<=[.!?])\s+|\n", text)
    out = []
    for sent in sentences:
        if pattern.search(sent):
            cleaned = " ".join(sent.split())
            if len(cleaned) > 10:
                out.append(cleaned)
    return out


def _confidence(evidence: list[dict]) -> float:
    if not evidence:
        return 0.0
    base = 0.50
    count_bonus = min(0.30, 0.10 * len(evidence))
    max_weight = max(ev["section_weight"] for ev in evidence)
    factor = 1.0 + (max_weight - 1.0) * 0.5
    return round(min(1.0, (base + count_bonus) * factor), 3)


def _is_hallucination(evidence: list[dict]) -> bool:
    if not evidence:
        return False
    strong = {"experience", "projects", "publications"}
    if any(ev["section"] in strong for ev in evidence):
        return False
    combined = " ".join(ev["snippet"] for ev in evidence).lower()
    return not any(w in combined for w in _TECH_CONTEXT)


def extract_skills_by_alias(
    sections: dict[str, str],
    catalog: dict[str, list[str]],
) -> list[ExtractedSkill]:
    """
    Scan every resume section for every known alias of every skill.
    Returns list of ExtractedSkill sorted by confidence descending.
    """
    full_text = " ".join(sections.values()).lower()
    extracted: list[ExtractedSkill] = []

    for skill_name, aliases in catalog.items():
        if skill_name.startswith("_"):
            continue
        all_terms = [skill_name] + (aliases or [])

        # Quick pre-check
        if not any(
            re.search(r"\b" + re.escape(t.lower()) + r"\b", full_text)
            for t in all_terms
        ):
            continue

        evidence: list[dict] = []
        aliases_found: list[str] = []
        seen_snippets: set[str] = set()

        for section_name, section_text in sections.items():
            if not section_text.strip():
                continue
            weight = SECTION_WEIGHTS.get(section_name, settings.SECTION_WEIGHT_OTHER)
            for term in all_terms:
                for snippet in _find_snippets(term, section_text):
                    if snippet not in seen_snippets:
                        seen_snippets.add(snippet)
                        evidence.append({
                            "snippet": snippet,
                            "section": section_name,
                            "section_weight": weight,
                        })
                if re.search(r"\b" + re.escape(term) + r"\b", section_text, re.IGNORECASE):
                    if term not in aliases_found:
                        aliases_found.append(term)

        if not evidence:
            continue

        conf = _confidence(evidence)
        flagged = _is_hallucination(evidence)
        if flagged:
            conf = min(conf, 0.45)

        extracted.append(ExtractedSkill(
            name=skill_name,
            confidence=conf,
            how_found="alias",
            aliases_matched=aliases_found,
            evidence=[EvidenceItem(**e) for e in evidence[:4]],
            low_confidence_flag=flagged,
        ))

    extracted.sort(key=lambda s: s.confidence, reverse=True)
    log.info("Pass 1 (alias): %d skills found.", len(extracted))
    return extracted
