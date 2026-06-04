"""
routers/admin.py — Admin endpoints for catalog management
----------------------------------------------------------
POST /admin/rebuild-catalog       → Build from O*NET XLSX files (primary)
POST /admin/rebuild-catalog-csv   → Build from flat CSV (legacy)
GET  /admin/catalog-stats         → Stats about the current catalog
"""

import json
import logging
from pathlib import Path

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from app.config import settings
from app.services.catalog_builder import (
    rebuild_catalog_from_onet,
    rebuild_roles_from_linkedin,
    rebuild_catalog,
)

log = logging.getLogger(__name__)
router = APIRouter(prefix="/admin", tags=["Admin"])


class RebuildResponse(BaseModel):
    status: str
    skills_count: int
    roles_count: int
    csv_rows_processed: int
    message: str


class CatalogStatsResponse(BaseModel):
    catalog_exists: bool
    roles_exists: bool
    skills_count: int
    roles_count: int
    source: str


@router.post(
    "/rebuild-catalog",
    response_model=RebuildResponse,
    summary="Rebuild catalog from O*NET XLSX files (recommended)",
)
def rebuild_onet():
    """
    Rebuild skills_catalog.json from O*NET 30.3 XLSX files.

    Reads from backend/data/raw/:
      - Software Skills.xlsx     (31,821 rows — tool names like Python, TensorFlow)
      - Essential Skills.xlsx    (17,880 rows — Reading Comprehension, Critical Thinking)
      - Transferable Skills.xlsx (44,700 rows — Communication, Problem Solving)

    Also rebuilds role_templates.json from LinkedIn job postings if available
    in backend/data/raw/linkedin/postings.csv.
    """
    raw_dir = settings.DATA_DIR / "raw"

    # Check at least one XLSX exists
    has_onet = any([
        (raw_dir / "Software Skills.xlsx").exists(),
        (raw_dir / "Essential Skills.xlsx").exists(),
        (raw_dir / "Transferable Skills.xlsx").exists(),
    ])
    if not has_onet:
        raise HTTPException(
            404,
            detail=(
                f"No O*NET XLSX files found in {raw_dir}. "
                "Place Software Skills.xlsx, Essential Skills.xlsx, "
                "Transferable Skills.xlsx in backend/data/raw/"
            ),
        )

    try:
        catalog_stats = rebuild_catalog_from_onet(
            data_dir=settings.DATA_DIR,
            raw_dir=raw_dir,
        )
    except Exception as exc:
        log.error("O*NET catalog build failed: %s", exc, exc_info=True)
        raise HTTPException(500, detail=f"Catalog rebuild failed: {exc}")

    # Try to build role templates from LinkedIn data
    roles_count = 0
    try:
        role_stats = rebuild_roles_from_linkedin(
            data_dir=settings.DATA_DIR,
            raw_dir=raw_dir,
        )
        roles_count = role_stats.get("roles_count", 0)
    except Exception as exc:
        log.warning("LinkedIn role rebuild skipped: %s", exc)
        # Count existing roles instead
        roles_path = settings.DATA_DIR / "role_templates.json"
        if roles_path.exists():
            try:
                roles_count = len(json.loads(roles_path.read_text(encoding="utf-8")))
            except Exception:
                pass

    skills_count = catalog_stats["skills_count"]
    return RebuildResponse(
        status="success",
        skills_count=skills_count,
        roles_count=roles_count,
        csv_rows_processed=0,
        message=(
            f"Built {skills_count:,} skills from O*NET 30.3 data. "
            f"{roles_count} role templates available."
        ),
    )


@router.post(
    "/rebuild-catalog-csv",
    response_model=RebuildResponse,
    summary="Rebuild catalog from flat CSV (legacy)",
)
def rebuild_csv():
    """
    Legacy endpoint — builds catalog from a flat job-skills CSV.
    Looks for: job_skill_data.csv, job_skills.csv, skills.csv in data/.
    """
    csv_candidates = [
        settings.DATA_DIR / "job_skill_data.csv",
        settings.DATA_DIR / "job_skills.csv",
        settings.DATA_DIR / "skills.csv",
    ]
    csv_path = next((p for p in csv_candidates if p.exists()), None)
    if csv_path is None:
        raise HTTPException(
            404,
            detail=f"No CSV found in {settings.DATA_DIR}. "
                   "Upload one of: job_skill_data.csv, job_skills.csv, skills.csv",
        )

    try:
        stats = rebuild_catalog(data_dir=settings.DATA_DIR, csv_path=csv_path)
    except Exception as exc:
        log.error("CSV catalog rebuild failed: %s", exc, exc_info=True)
        raise HTTPException(500, detail=f"Rebuild failed: {exc}")

    return RebuildResponse(
        status="success",
        skills_count=stats["skills_count"],
        roles_count=stats["roles_count"],
        csv_rows_processed=stats["csv_rows_processed"],
        message=(
            f"Built {stats['skills_count']} skills, "
            f"{stats['roles_count']} roles from {stats['csv_rows_processed']} CSV rows."
        ),
    )


@router.get("/catalog-stats", response_model=CatalogStatsResponse, summary="Catalog statistics")
def catalog_stats():
    catalog_path = settings.DATA_DIR / "skills_catalog.json"
    roles_path   = settings.DATA_DIR / "role_templates.json"

    skills_count = 0
    roles_count  = 0
    source       = "unknown"

    if catalog_path.exists():
        try:
            catalog = json.loads(catalog_path.read_text(encoding="utf-8"))
            skills_count = sum(1 for k in catalog if not k.startswith("_"))
            meta = catalog.get("_metadata", {})
            source = meta.get("source", "csv")
        except Exception:
            pass

    if roles_path.exists():
        try:
            roles_count = len(json.loads(roles_path.read_text(encoding="utf-8")))
        except Exception:
            pass

    return CatalogStatsResponse(
        catalog_exists=catalog_path.exists(),
        roles_exists=roles_path.exists(),
        skills_count=skills_count,
        roles_count=roles_count,
        source=source,
    )
