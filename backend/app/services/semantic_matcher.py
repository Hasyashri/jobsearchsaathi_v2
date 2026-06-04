"""
semantic_matcher.py — Pass 4: Sentence-level SBERT semantic matching
---------------------------------------------------------------------
Uses sentence-transformers (all-MiniLM-L6-v2) to find skills mentioned
conceptually in the resume even when exact keywords are absent.

Strategy:
  1. Split each section into sentences.
  2. Encode all sentences + all catalog skill names in one batch call.
  3. For each skill NOT yet found, compute max cosine similarity across
     all sentences in all sections.
  4. Accept matches above SEMANTIC_THRESHOLD (0.45 by default).

Confidence formula:
    confidence = scale(sim, 0.45→0.35 … 1.00→0.80)
    (semantic evidence is inherently weaker than direct matches, so the
     ceiling is lower than alias/fuzzy/NER)

The SBERT model is lazy-loaded and shared with ner_extractor via the
module-level singleton pattern.  If sentence-transformers is not installed
this pass is silently skipped.
"""

from __future__ import annotations

import re
import logging
from typing import Any

from app.config import settings
from app.schemas import ExtractedSkill, EvidenceItem

log = logging.getLogger(__name__)

_sbert_model: Any = None


def _load_model() -> bool:
    global _sbert_model
    if _sbert_model is not None:
        return True
    try:
        from sentence_transformers import SentenceTransformer  # type: ignore
        log.info("Loading SBERT model for semantic pass: %s", settings.EMBED_MODEL)
        _sbert_model = SentenceTransformer(settings.EMBED_MODEL)
        return True
    except Exception as exc:
        log.warning("Semantic pass skipped — could not load model: %s", exc)
        return False


def _split_sentences(text: str) -> list[str]:
    """Naïve sentence splitter (no NLTK dependency)."""
    sentences = re.split(r"(?<=[.!?])\s+", text.strip())
    return [s.strip() for s in sentences if len(s.strip()) > 15]


def _scale_confidence(sim: float) -> float:
    """Map cosine similarity (0.45-1.00) → confidence (0.35-0.80)."""
    low_sim, high_sim = 0.45, 1.00
    low_conf, high_conf = 0.35, 0.80
    t = max(0.0, min(1.0, (sim - low_sim) / (high_sim - low_sim)))
    return round(low_conf + t * (high_conf - low_conf), 4)


SECTION_WEIGHTS: dict[str, float] = {
    "experience": settings.SECTION_WEIGHT_EXPERIENCE,
    "projects":   settings.SECTION_WEIGHT_PROJECTS,
    "skills":     settings.SECTION_WEIGHT_SKILLS,
    "education":  settings.SECTION_WEIGHT_EDUCATION,
}


def find_semantic_skills(
    sections: dict[str, str],
    catalog: dict[str, list[str]],
    already_found: set[str],
) -> list[ExtractedSkill]:
    """
    Pass 4: Semantic matching via SBERT cosine similarity.

    For each catalog skill not yet found, find the most similar sentence
    in the resume (across all sections).  Accept if similarity ≥ SEMANTIC_THRESHOLD.

    Args:
        sections:      Dict of section_name → section_text.
        catalog:       Dict of canonical_skill_name → list[aliases].
        already_found: Skills already detected by passes 1–3.

    Returns:
        List of ExtractedSkill (how_found="semantic"), sorted by confidence desc.
        Empty list if sentence-transformers is not installed.
    """
    if not _load_model():
        return []

    import numpy as np  # type: ignore

    # Gather all sentences with their section metadata
    all_sentences: list[str] = []
    sentence_meta: list[tuple[str, float]] = []  # (section_name, weight)

    for section_name, section_text in sections.items():
        if section_name == "header" or not section_text.strip():
            continue
        weight = SECTION_WEIGHTS.get(section_name, settings.SECTION_WEIGHT_OTHER)
        for sent in _split_sentences(section_text):
            all_sentences.append(sent)
            sentence_meta.append((section_name, weight))

    if not all_sentences:
        return []

    # Skills to evaluate (not yet found)
    skills_to_check = [s for s in catalog if s not in already_found]
    if not skills_to_check:
        return []

    try:
        # Encode sentences and skill names in batch (much faster than one-by-one)
        sentence_vecs = _sbert_model.encode(
            all_sentences, normalize_embeddings=True, show_progress_bar=False, batch_size=64
        )
        skill_vecs = _sbert_model.encode(
            skills_to_check, normalize_embeddings=True, show_progress_bar=False, batch_size=64
        )
    except Exception as exc:
        log.warning("SBERT encode error: %s", exc)
        return []

    # sim_matrix[i, j] = cosine similarity of skills_to_check[i] with all_sentences[j]
    sim_matrix = np.dot(skill_vecs, sentence_vecs.T)  # shape: (n_skills, n_sentences)

    results: list[ExtractedSkill] = []

    for skill_idx, skill_name in enumerate(skills_to_check):
        sims = sim_matrix[skill_idx]
        max_sim = float(sims.max())

        if max_sim < settings.SEMANTIC_THRESHOLD:
            continue

        # Collect top evidence sentences (above threshold)
        evidence: list[EvidenceItem] = []
        top_indices = np.where(sims >= settings.SEMANTIC_THRESHOLD)[0]
        # Sort by similarity descending
        top_indices = sorted(top_indices, key=lambda i: sims[i], reverse=True)[:3]

        for sent_idx in top_indices:
            section_name, weight = sentence_meta[sent_idx]
            evidence.append(EvidenceItem(
                snippet=all_sentences[sent_idx][:150],
                section=section_name,
                section_weight=weight,
            ))

        confidence = _scale_confidence(max_sim)

        # Semantic-only evidence in skills section is weak — flag it
        sections_hit = {e.section for e in evidence}
        low_conf_flag = (
            confidence < 0.45 and sections_hit.issubset({"skills", "education"})
        )
        if low_conf_flag:
            confidence = max(0.25, confidence - 0.08)

        results.append(ExtractedSkill(
            name=skill_name,
            confidence=confidence,
            how_found="semantic",
            aliases_matched=[],
            evidence=evidence,
            low_confidence_flag=low_conf_flag,
        ))

    results.sort(key=lambda s: s.confidence, reverse=True)
    log.debug("semantic_matcher found %d skills", len(results))
    return results
