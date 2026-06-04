"""
ner_extractor.py — Pass 3: BERT NER + SBERT catalog mapping
------------------------------------------------------------
Extracts named-entity phrases from each resume section using a BERT NER model
(dslim/bert-base-NER), then maps each entity to the closest catalog skill via
SBERT cosine similarity.

Why this beats a simple keyword scan:
  - BERT NER picks up multi-word technical entities in context:
    "Apache Kafka", "Google BigQuery", "AWS Lambda"
  - SBERT maps the entity to the canonical catalog name even when phrasing
    differs: "Kubernetes orchestration" → "kubernetes"
  - Section-aware: evidence carries the section name and weight.

Confidence formula:
    raw_conf = sqrt(ner_score × sbert_sim)   (geometric mean)
    confidence = scale(raw_conf, 0.60→0.50 … 1.00→0.90)

Hard thresholds (from config):
    NER token score  ≥ 0.70
    SBERT similarity ≥ 0.60

Both models are lazy-loaded on first use so the API starts fast even when
transformers / torch are installed.  If NOT installed, this pass is silently
skipped (the other three passes still run).
"""

from __future__ import annotations

import math
import logging
from typing import Any

from app.config import settings
from app.schemas import ExtractedSkill, EvidenceItem

log = logging.getLogger(__name__)

# ── Lazy-loaded model references ──────────────────────────────────────────────
_ner_pipeline: Any = None
_sbert_model: Any = None
_catalog_embeddings: dict[str, Any] = {}   # skill_name → embedding vector


def _load_models() -> bool:
    """
    Attempt to load BERT NER and SBERT models.
    Returns True if both loaded successfully, False otherwise.
    """
    global _ner_pipeline, _sbert_model

    if _ner_pipeline is not None and _sbert_model is not None:
        return True

    try:
        from transformers import pipeline as hf_pipeline  # type: ignore
        from sentence_transformers import SentenceTransformer  # type: ignore

        if _ner_pipeline is None:
            log.info("Loading NER model: %s", settings.NER_MODEL)
            _ner_pipeline = hf_pipeline(
                "ner",
                model=settings.NER_MODEL,
                aggregation_strategy="simple",
                device=-1,   # CPU
            )

        if _sbert_model is None:
            log.info("Loading SBERT model: %s", settings.EMBED_MODEL)
            _sbert_model = SentenceTransformer(settings.EMBED_MODEL)

        return True

    except Exception as exc:
        log.warning("NER pass skipped — could not load models: %s", exc)
        return False


def _get_catalog_embeddings(catalog: dict[str, list[str]]) -> dict[str, Any]:
    """
    Compute (and cache) SBERT embeddings for all canonical skill names.
    """
    global _catalog_embeddings

    if _catalog_embeddings and set(_catalog_embeddings.keys()) == set(catalog.keys()):
        return _catalog_embeddings

    log.info("Computing catalog embeddings for %d skills …", len(catalog))
    names = list(catalog.keys())
    vecs = _sbert_model.encode(names, normalize_embeddings=True, show_progress_bar=False)
    _catalog_embeddings = dict(zip(names, vecs))
    return _catalog_embeddings


def _extract_entities_from_text(text: str) -> list[dict]:
    """
    Run BERT NER on a text chunk.  Returns list of
    {"word": str, "score": float, "entity_group": str}.
    Skips PER (person names) entities.
    """
    if not text.strip():
        return []
    try:
        entities = _ner_pipeline(text[:2000])  # cap to avoid OOM on very long sections
        return [e for e in entities if e.get("entity_group") not in {"PER"}]
    except Exception as exc:
        log.debug("NER inference error: %s", exc)
        return []


def _map_entity_to_skill(
    entity_word: str,
    catalog_embeddings: dict[str, Any],
) -> tuple[str, float] | None:
    """
    Cosine-similarity map an entity phrase to the closest catalog skill.
    Returns (skill_name, similarity) or None if below threshold.
    """
    try:
        import numpy as np  # type: ignore
        entity_vec = _sbert_model.encode(entity_word, normalize_embeddings=True)
        best_skill = ""
        best_sim = 0.0
        for skill_name, skill_vec in catalog_embeddings.items():
            sim = float(np.dot(entity_vec, skill_vec))
            if sim > best_sim:
                best_sim = sim
                best_skill = skill_name
        if best_sim >= settings.NER_SBERT_THRESHOLD:
            return best_skill, best_sim
        return None
    except Exception as exc:
        log.debug("SBERT mapping error for '%s': %s", entity_word, exc)
        return None


def _scale_confidence(raw: float) -> float:
    """
    Scale geometric mean (0.60-1.00) → confidence (0.50-0.90).
    """
    low_raw, high_raw = 0.60, 1.00
    low_conf, high_conf = 0.50, 0.90
    t = max(0.0, min(1.0, (raw - low_raw) / (high_raw - low_raw)))
    return round(low_conf + t * (high_conf - low_conf), 4)


SECTION_WEIGHTS: dict[str, float] = {
    "experience": settings.SECTION_WEIGHT_EXPERIENCE,
    "projects":   settings.SECTION_WEIGHT_PROJECTS,
    "skills":     settings.SECTION_WEIGHT_SKILLS,
    "education":  settings.SECTION_WEIGHT_EDUCATION,
}


def extract_skills_by_ner(
    sections: dict[str, str],
    catalog: dict[str, list[str]],
    already_found: set[str],
) -> list[ExtractedSkill]:
    """
    Pass 3: BERT NER + SBERT mapping.

    For each resume section, run BERT NER to extract named entities, then map
    each entity to the closest catalog skill via SBERT similarity.

    Only yields skills NOT already in `already_found` (from Pass 1 + Pass 2).

    Args:
        sections:      Dict of section_name → section_text.
        catalog:       Dict of canonical_skill_name → list[aliases].
        already_found: Skills already detected by alias + fuzzy passes.

    Returns:
        List of ExtractedSkill (how_found="bert_ner"), sorted by confidence desc.
        Empty list if transformers/torch are not installed.
    """
    if not _load_models():
        return []

    cat_embeddings = _get_catalog_embeddings(catalog)

    # Accumulate per-skill evidence across all sections
    skill_evidence: dict[str, list[EvidenceItem]] = {}
    skill_conf_parts: dict[str, list[float]] = {}

    for section_name, section_text in sections.items():
        if section_name == "header" or not section_text.strip():
            continue
        weight = SECTION_WEIGHTS.get(section_name, settings.SECTION_WEIGHT_OTHER)

        entities = _extract_entities_from_text(section_text)
        for ent in entities:
            word: str = ent.get("word", "").strip()
            ner_score: float = float(ent.get("score", 0.0))

            if not word or ner_score < settings.NER_SCORE_THRESHOLD:
                continue

            mapping = _map_entity_to_skill(word, cat_embeddings)
            if mapping is None:
                continue

            skill_name, sbert_sim = mapping
            if skill_name in already_found:
                continue

            # Geometric mean of NER score and SBERT similarity
            raw_conf = math.sqrt(ner_score * sbert_sim)
            if raw_conf < 0.60:
                continue

            confidence = _scale_confidence(raw_conf)

            if skill_name not in skill_evidence:
                skill_evidence[skill_name] = []
                skill_conf_parts[skill_name] = []

            skill_evidence[skill_name].append(EvidenceItem(
                snippet=word[:120],
                section=section_name,
                section_weight=weight,
            ))
            skill_conf_parts[skill_name].append(confidence)

    results: list[ExtractedSkill] = []
    for skill_name, evidence in skill_evidence.items():
        # Final confidence = average across all section detections, boosted by
        # evidence breadth (more sections = higher confidence)
        avg_conf = sum(skill_conf_parts[skill_name]) / len(skill_conf_parts[skill_name])
        breadth_bonus = min(0.05, 0.02 * (len(evidence) - 1))
        final_conf = min(0.90, round(avg_conf + breadth_bonus, 4))

        results.append(ExtractedSkill(
            name=skill_name,
            confidence=final_conf,
            how_found="bert_ner",
            aliases_matched=[],
            evidence=evidence[:5],
            low_confidence_flag=final_conf < settings.PRESENCE_THRESHOLD,
        ))

    results.sort(key=lambda s: s.confidence, reverse=True)
    log.debug("ner_extractor found %d skills", len(results))
    return results
