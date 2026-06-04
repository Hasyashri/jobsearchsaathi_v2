"""
rag_service.py — Retrieval-Augmented Generation (RAG) layer for skill discovery.

WHY RAG?
---------
Passes 1–4 (alias, fuzzy, BERT NER, semantic) extract skills mentioned in the resume.
RAG flips the direction: given a job description, it RETRIEVES the most semantically
relevant skills from our catalog — even if those skills appear nowhere in the resume.
This surfaces the "invisible gap": skills the JD implies but the candidate never named.

WHY FAISS?
----------
FAISS (Facebook AI Similarity Search) is the production-grade vector store used by Meta,
Spotify, and most RAG systems. Compared to alternatives:
  - ChromaDB: easier API but slower at scale, not production-battle-tested
  - Pinecone: managed cloud service, adds cost and latency for a portfolio demo
  - FAISS: runs in-process, zero network calls, sub-millisecond retrieval at our scale
  - Qdrant: excellent but heavier to self-host

WHY all-MiniLM-L6-v2?
-----------------------
Sentence-BERT (SBERT) family model from UKPLab. 384-dimensional embeddings.
  - 5x faster than bert-base at inference, similar quality for semantic similarity
  - Trained on 1B+ sentence pairs (NLI, STS, reddit, wikihow)
  - Scores 58.8 on STS benchmark — best quality-to-speed ratio for retrieval tasks
  - Used by Hugging Face, Elastic, and Weaviate in their default embedding pipelines

HOW IT WORKS:
  1. At startup — embed all skill names in the catalog → store in FAISS flat index
  2. At query time — embed JD text sentences → retrieve top-k nearest skill embeddings
  3. Return canonical skill names whose vector distance falls below a threshold
  4. These become Pass 5 candidates (added to extracted skills if not already found)
"""
from __future__ import annotations
import logging
import numpy as np

log = logging.getLogger(__name__)

# Lazy-loaded globals (loaded once, reused across requests)
_index = None           # faiss.IndexFlatIP  (inner-product = cosine on normalised vecs)
_skill_names: list[str] = []
_model = None           # SentenceTransformer


def _load():
    """Lazy-load FAISS + SBERT on first call. Thread-safe by GIL on CPython."""
    global _index, _skill_names, _model

    if _index is not None:
        return  # already loaded

    try:
        import faiss
        from sentence_transformers import SentenceTransformer

        log.info("RAG: loading all-MiniLM-L6-v2 ...")
        # WHY all-MiniLM-L6-v2: 22MB, 384-dim, fastest SBERT for retrieval
        _model = SentenceTransformer("all-MiniLM-L6-v2")
        log.info("RAG: SBERT model loaded")
    except ImportError as e:
        log.warning("RAG disabled: %s. Install: pip install faiss-cpu sentence-transformers", e)
        _index = False   # sentinel: disabled
        return


def build_index(catalog: dict[str, list[str]]) -> None:
    """
    Build a FAISS inner-product index over all skill names + their aliases.

    WHY IndexFlatIP (inner product)?
    After L2-normalising vectors, inner product == cosine similarity.
    This is the standard approach for semantic retrieval — we rank by
    semantic closeness, not Euclidean distance.

    WHY flat (not IVF or HNSW)?
    Our catalog has ~200 skills. HNSW and IVF are approximate methods
    that trade accuracy for speed at millions of vectors. At 200 vectors,
    exact search is faster than the overhead of approximate indexing.
    """
    global _index, _skill_names

    _load()
    if _index is False:  # disabled
        return

    try:
        import faiss
        from sentence_transformers import SentenceTransformer

        if _model is None:
            return

        # Collect all skill names (canonical + aliases) → map back to canonical
        name_to_canonical: dict[str, str] = {}
        for canonical, aliases in catalog.items():
            name_to_canonical[canonical] = canonical
            for alias in aliases:
                if alias and len(alias) >= 3:
                    name_to_canonical[alias.lower()] = canonical

        all_names = list(name_to_canonical.keys())
        canonicals = [name_to_canonical[n] for n in all_names]

        log.info("RAG: encoding %d skill names/aliases ...", len(all_names))
        # Batch encode all skill names
        embeddings = _model.encode(
            all_names,
            batch_size=64,
            show_progress_bar=False,
            convert_to_numpy=True,
            normalize_embeddings=True,  # L2-normalise → cosine similarity via IP
        ).astype("float32")

        dim = embeddings.shape[1]  # 384 for all-MiniLM-L6-v2

        # Build flat inner-product index
        index = faiss.IndexFlatIP(dim)
        index.add(embeddings)

        _index = index
        _skill_names = canonicals
        log.info("RAG: FAISS index built — %d vectors, dim=%d", index.ntotal, dim)

    except Exception as e:
        log.warning("RAG index build failed: %s", e)
        _index = False


def retrieve_skills_from_jd(
    jd_text: str,
    already_found: set[str],
    top_k: int = 10,
    similarity_threshold: float = 0.55,
) -> list[tuple[str, float]]:
    """
    Given raw JD text, retrieve the most semantically relevant skill names
    from the FAISS index that haven't been found yet.

    WHY threshold 0.55?
    Empirically, cosine similarity < 0.50 produces noisy false positives
    (e.g., "agile" retrieving "python"). 0.55 gives clean recall without
    over-retrieval. Adjustable via parameter.

    Returns: [(canonical_skill_name, similarity_score), ...]
    """
    if _index is None:
        _load()
    if _index is False or _index is None:
        return []

    try:
        from sentence_transformers import SentenceTransformer

        # Split JD into sentences for better granularity
        import re
        sentences = [s.strip() for s in re.split(r'[.\n•\-\*]', jd_text) if len(s.strip()) > 15]
        if not sentences:
            sentences = [jd_text[:500]]

        # Encode JD sentences
        query_embeddings = _model.encode(
            sentences,
            batch_size=32,
            show_progress_bar=False,
            convert_to_numpy=True,
            normalize_embeddings=True,
        ).astype("float32")

        # FAISS search: for each sentence, find top-k nearest skills
        distances, indices = _index.search(query_embeddings, top_k)

        # Aggregate by skill: keep max similarity per skill
        skill_scores: dict[str, float] = {}
        for row_dists, row_idxs in zip(distances, indices):
            for dist, idx in zip(row_dists, row_idxs):
                if idx < 0 or idx >= len(_skill_names):
                    continue
                skill = _skill_names[idx]
                score = float(dist)
                if score >= similarity_threshold and skill not in already_found:
                    skill_scores[skill] = max(skill_scores.get(skill, 0.0), score)

        # Sort by score descending
        results = sorted(skill_scores.items(), key=lambda x: x[1], reverse=True)
        log.info("RAG retrieval: %d candidate skills from JD (threshold=%.2f)", len(results), similarity_threshold)
        return results[:20]

    except Exception as e:
        log.warning("RAG retrieval error: %s", e)
        return []
