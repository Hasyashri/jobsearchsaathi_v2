"""
config.py — All application settings in one place.
Reads from environment variables; falls back to safe defaults for local dev.
"""
from __future__ import annotations
import os
from pathlib import Path

class Settings:
    # ── API metadata ─────────────────────────────────────────────────────────
    API_TITLE: str        = "JobSearchSaathi Pro"
    API_VERSION: str      = "2.0.0"
    API_DESCRIPTION: str  = (
        "AI-powered resume analysis: 4-pass skill detection, "
        "readiness scoring, gap recommendations, and career path intelligence."
    )

    # ── Directories ──────────────────────────────────────────────────────────
    BASE_DIR: Path   = Path(__file__).resolve().parent
    DATA_DIR: Path   = BASE_DIR / "data"
    STORAGE_DIR: Path = BASE_DIR / "storage"
    LOG_DIR: str      = os.getenv("LOG_DIR", "logs")

    # ── CORS ─────────────────────────────────────────────────────────────────
    CORS_ORIGINS: list[str] = ["*"]   # tighten in production

    # ── File upload ──────────────────────────────────────────────────────────
    ALLOWED_EXTENSIONS: set[str] = {".pdf", ".docx", ".txt"}
    MAX_FILE_SIZE_MB: float       = float(os.getenv("MAX_FILE_SIZE_MB", "5"))

    # ── ML models ────────────────────────────────────────────────────────────
    EMBED_MODEL: str    = os.getenv("EMBED_MODEL", "all-MiniLM-L6-v2")
    NER_MODEL: str      = os.getenv("NER_MODEL",   "dslim/bert-base-NER")

    # ── Detection thresholds ─────────────────────────────────────────────────
    PRESENCE_THRESHOLD: float  = float(os.getenv("PRESENCE_THRESHOLD",  "0.30"))
    SEMANTIC_THRESHOLD: float  = float(os.getenv("SEMANTIC_THRESHOLD",  "0.45"))
    NER_SCORE_THRESHOLD: float = float(os.getenv("NER_SCORE_THRESHOLD", "0.70"))
    NER_SBERT_THRESHOLD: float = float(os.getenv("NER_SBERT_THRESHOLD", "0.60"))

    # ── Fuzzy thresholds (ratio 0–100) ───────────────────────────────────────
    FUZZY_SHORT_THRESHOLD: float = 85.0   # 4–6 char terms
    FUZZY_LONG_THRESHOLD: float  = 82.0   # 7+ char terms
    FUZZY_MULTI_THRESHOLD: float = 88.0   # multi-word / hyphenated

    # ── Section weights ──────────────────────────────────────────────────────
    SECTION_WEIGHT_EXPERIENCE: float = float(os.getenv("SECTION_WEIGHT_EXPERIENCE", "1.5"))
    SECTION_WEIGHT_PROJECTS: float   = float(os.getenv("SECTION_WEIGHT_PROJECTS",   "1.3"))
    SECTION_WEIGHT_SKILLS: float     = float(os.getenv("SECTION_WEIGHT_SKILLS",     "1.0"))
    SECTION_WEIGHT_EDUCATION: float  = float(os.getenv("SECTION_WEIGHT_EDUCATION",  "0.8"))
    SECTION_WEIGHT_OTHER: float      = float(os.getenv("SECTION_WEIGHT_OTHER",      "0.6"))

    # ── Readiness score weights ──────────────────────────────────────────────
    READINESS_REQUIRED_WEIGHT: float    = 0.70
    READINESS_NICE_TO_HAVE_WEIGHT: float = 0.30

    # ── Tech context words (for hallucination guard) ─────────────────────────
    TECH_CONTEXT_WORDS: list[str] = [
        "used", "built", "developed", "deployed", "implemented", "designed",
        "created", "managed", "worked", "experience", "proficient", "expert",
        "years", "project", "system", "pipeline", "model", "trained",
    ]

settings = Settings()
