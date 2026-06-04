"""
fuzzy_extractor.py — Pass 2: Token-level fuzzy matching
--------------------------------------------------------
Catches typos and spelling variants that exact alias matching misses.

Strategy:
  For each catalog skill alias, tokenise it and slide a window over the
  resume section text.  rapidfuzz.fuzz.token_sort_ratio gives a 0-100
  similarity score; we accept matches above an adaptive threshold that
  depends on alias length (short aliases need tighter matching to avoid
  false positives).

Thresholds (from config):
  < 4 chars  → exact only   (no fuzzy for "go", "r", "c")
  4-6 chars  → 85.0         (e.g. "java", "rust")
  7+ chars   → 82.0         (e.g. "pytorch", "kubernetes")
  multi-word → 88.0         (e.g. "machine learning")

Confidence is linearly scaled from the raw similarity ratio:
  ratio 82 → 0.45,  ratio 100 → 0.85

Dependencies:
  rapidfuzz (optional) — falls back to difflib SequenceMatcher.
"""

from __future__ import annotations

import re
import logging
from typing import Any

from app.config import settings
from app.schemas import ExtractedSkill, EvidenceItem

log = logging.getLogger(__name__)

# Try to import rapidfuzz; fall back to difflib
try:
    from rapidfuzz import fuzz as _rfuzz  # type: ignore
    def _similarity(a: str, b: str) -> float:
        return _rfuzz.token_sort_ratio(a, b)
    _FUZZY_BACKEND = "rapidfuzz"
except ImportError:
    import difflib
    def _similarity(a: str, b: str) -> float:  # type: ignore[misc]
        return difflib.SequenceMatcher(None, a.lower(), b.lower()).ratio() * 100
    _FUZZY_BACKEND = "difflib"

log.debug("fuzzy_extractor using backend: %s", _FUZZY_BACKEND)

# SECTION_WEIGHTS mirrors skill_extractor for consistent confidence scoring
SECTION_WEIGHTS: dict[str, float] = {
    "experience": settings.SECTION_WEIGHT_EXPERIENCE,
    "projects":   settings.SECTION_WEIGHT_PROJECTS,
    "skills":     settings.SECTION_WEIGHT_SKILLS,
    "education":  settings.SECTION_WEIGHT_EDUCATION,
}


def _threshold_for_alias(alias: str) -> float | None:
    """
    Return the fuzzy similarity threshold for this alias, or None if the alias
    is too short for fuzzy matching (should be exact-only).
    """
    words = alias.split()
    length = len(alias)

    if len(words) > 1:
        return settings.FUZZY_MULTI_THRESHOLD
    if length < 4:
        return None   # exact-only — skip fuzzy for "go", "r", "c"
    if length <= 6:
        return settings.FUZZY_SHORT_THRESHOLD   # 85.0
    return settings.FUZZY_LONG_THRESHOLD        # 82.0


def _scale_confidence(ratio: float) -> float:
    """
    Map a fuzzy similarity ratio (82-100) → confidence (0.45-0.85).
    Ratios below 82 should never reach here (already filtered by threshold).
    """
    low_ratio, high_ratio = 82.0, 100.0
    low_conf, high_conf  = 0.45, 0.85
    t = max(0.0, min(1.0, (ratio - low_ratio) / (high_ratio - low_ratio)))
    return round(low_conf + t * (high_conf - low_conf), 4)


def _window_match(alias: str, section_text: str, threshold: float) -> tuple[float, list[str]]:
    """
    Slide a token window of the same length as `alias` over `section_text`.
    Returns (best_ratio, list_of_matching_snippets).
    """
    alias_tokens = alias.lower().split()
    window_size = len(alias_tokens)
    text_tokens = re.findall(r"\b\w[\w.\-+#]*\b", section_text.lower())

    best_ratio = 0.0
    snippets: list[str] = []

    for i in range(len(text_tokens) - window_size + 1):
        window = " ".join(text_tokens[i : i + window_size])
        ratio = _similarity(alias, window)
        if ratio >= threshold:
            best_ratio = max(best_ratio, ratio)
            # grab a wider context slice from raw text for the snippet
            # (reconstruct approximately from matched tokens)
            snippets.append(window)

    return best_ratio, snippets


def _find_evidence(skill_name: str, aliases: list[str], sections: dict[str, str]) -> list[EvidenceItem]:
    """Find fuzzy evidence items for a skill across all sections."""
    evidence: list[EvidenceItem] = []
    seen_snippets: set[str] = set()

    for section_name, section_text in sections.items():
        if section_name == "header" or not section_text.strip():
            continue
        weight = SECTION_WEIGHTS.get(section_name, settings.SECTION_WEIGHT_OTHER)

        for alias in aliases:
            threshold = _threshold_for_alias(alias)
            if threshold is None:
                continue
            _, snippets = _window_match(alias, section_text, threshold)
            for snippet in snippets:
                if snippet not in seen_snippets:
                    seen_snippets.add(snippet)
                    evidence.append(EvidenceItem(
                        snippet=snippet,
                        section=section_name,
                        section_weight=weight,
                    ))
    return evidence


def extract_skills_by_fuzzy(
    sections: dict[str, str],
    catalog: dict[str, list[str]],
    already_found: set[str],
) -> list[ExtractedSkill]:
    """
    Pass 2: Fuzzy matching.

    For each skill NOT yet found by alias matching, test all aliases with an
    adaptive threshold.  Returns a list of ExtractedSkill objects sorted by
    confidence descending.

    Args:
        sections:      Dict of section_name → section_text.
        catalog:       Dict of canonical_skill_name → list[aliases].
        already_found: Set of skill names already detected in Pass 1.

    Returns:
        List of ExtractedSkill (how_found="fuzzy").
    """
    results: list[ExtractedSkill] = []

    for skill_name, aliases in catalog.items():
        if skill_name in already_found:
            continue

        best_ratio = 0.0
        best_alias: str = skill_name
        all_evidence: list[EvidenceItem] = []

        for section_name, section_text in sections.items():
            if section_name == "header" or not section_text.strip():
                continue

            for alias in [skill_name] + aliases:
                threshold = _threshold_for_alias(alias)
                if threshold is None:
                    continue

                ratio, snippets = _window_match(alias, section_text, threshold)
                if ratio >= threshold:
                    weight = SECTION_WEIGHTS.get(section_name, settings.SECTION_WEIGHT_OTHER)
                    for snippet in snippets:
                        all_evidence.append(EvidenceItem(
                            snippet=snippet,
                            section=section_name,
                            section_weight=weight,
                        ))
                    if ratio > best_ratio:
                        best_ratio = ratio
                        best_alias = alias

        if not all_evidence:
            continue

        confidence = _scale_confidence(best_ratio)

        # Hallucination guard: fuzzy match in skills-section only without
        # any tech context is suspicious — lower confidence and flag it.
        sections_hit = {e.section for e in all_evidence}
        low_conf_flag = (
            sections_hit == {"skills"} and confidence < 0.55
        )
        if low_conf_flag:
            confidence = max(0.30, confidence - 0.10)

        results.append(ExtractedSkill(
            name=skill_name,
            confidence=confidence,
            how_found="fuzzy",
            aliases_matched=[best_alias] if best_alias != skill_name else [],
            evidence=all_evidence[:5],  # keep top 5 snippets
            low_confidence_flag=low_conf_flag,
        ))

    results.sort(key=lambda s: s.confidence, reverse=True)
    log.debug("fuzzy_extractor found %d skills", len(results))
    return results
