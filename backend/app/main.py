"""
main.py — FastAPI application entry point
------------------------------------------
Starts the JobSearchSaathi Pro API.

Endpoints:
    POST   /analyze          — Upload resume + role_id → AnalysisReport
    POST   /analyze/text     — Plain-text resume variant
    GET    /roles            — List all available roles
    GET    /roles/{role_id}  — Get a single role
    POST   /feedback         — Submit skill feedback
    GET    /services         — Learning resources catalog (filterable)
    GET    /services/{id}    — Single learning resource
    POST   /admin/rebuild-catalog   — Rebuild catalog from CSV
    GET    /admin/catalog-stats     — Catalog statistics
    GET    /health           — Health check
"""

import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.config import settings
from app.logging_config import configure_logging
from app.services.catalog_builder import ensure_catalog
from app.routers import analyze, roles, feedback, services, admin

configure_logging()
log = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Startup / shutdown lifecycle."""
    log.info("=== JobSearchSaathi Pro v%s starting ===", settings.API_VERSION)
    ensure_catalog(settings.DATA_DIR)
    yield
    log.info("=== JobSearchSaathi Pro shutdown ===")


app = FastAPI(
    title=settings.API_TITLE,
    version=settings.API_VERSION,
    description=(
        "AI-powered resume analysis API. "
        "Upload a resume, choose a target role, and receive a detailed "
        "readiness score, skill gap analysis, and career path intelligence."
    ),
    lifespan=lifespan,
    docs_url="/docs",
    redoc_url="/redoc",
)

# ── CORS ──────────────────────────────────────────────────────────────────────
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],   # Restrict in production
    allow_methods=["*"],
    allow_headers=["*"],
)

# ── Routers ───────────────────────────────────────────────────────────────────
app.include_router(analyze.router)
app.include_router(roles.router)
app.include_router(feedback.router)
app.include_router(services.router)
app.include_router(admin.router)


# ── Health check ─────────────────────────────────────────────────────────────
@app.get("/health", tags=["Health"])
def health():
    return {"status": "ok", "version": settings.API_VERSION}
