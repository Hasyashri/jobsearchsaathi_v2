"""
routers/analyze.py — POST /analyze  and  POST /analyze/jd
-----------------------------------------------------------
/analyze      — resume + role_id  (template-based)
/analyze/jd   — resume + job_description text/file (JD-based, richer gap analysis)
"""

import json
import logging
import uuid
from pathlib import Path
from typing import Optional

from fastapi import APIRouter, File, Form, HTTPException, UploadFile
from fastapi.responses import JSONResponse

from app.config import settings
from app.schemas import (AnalysisReport, JDAnalysisReport, ApplyVerdict, ResumeQualitySummary,
                         BulletQuality, BulletRewriteRequest, BulletRewriteResponse)
from app.services import resume_parser
from app.services.pipeline import run_pipeline
from app.services.jd_parser import parse_jd
from app.services.jd_gap_analyzer import analyze_jd_gaps, get_apply_verdict
from app.services.resume_quality import analyse_resume_quality
from app.services import rag_service
from app.services.action_plan_engine import build_action_plan
from app.services.llm_service import rewrite_bullet

log = logging.getLogger(__name__)

router = APIRouter(prefix="/analyze", tags=["Analysis"])


def _load_data() -> tuple[dict, dict]:
    catalog_path = settings.DATA_DIR / "skills_catalog.json"
    roles_path   = settings.DATA_DIR / "role_templates.json"

    if not catalog_path.exists():
        raise HTTPException(500, detail="skills_catalog.json not found. POST /admin/rebuild-catalog to generate it.")
    if not roles_path.exists():
        raise HTTPException(500, detail="role_templates.json not found. POST /admin/rebuild-catalog to generate it.")

    catalog = json.loads(catalog_path.read_text(encoding="utf-8"))
    roles   = json.loads(roles_path.read_text(encoding="utf-8"))
    return catalog, roles


@router.post("", response_model=AnalysisReport, summary="Analyse a resume against a job role")
async def analyze_resume(
    file: UploadFile = File(..., description="Resume file (.pdf, .docx, or .txt)"),
    role_id: str     = Form(..., description="Target role ID — use GET /roles to list available IDs"),
):
    """
    Upload a resume and receive a complete readiness analysis.

    **Pipeline:** File → text extraction → 4-pass skill detection →
    readiness scoring → gap analysis → multi-role scoring → JSON report
    """
    # Validate extension
    suffix = Path(file.filename or "").suffix.lower()
    if suffix not in settings.ALLOWED_EXTENSIONS:
        raise HTTPException(
            400,
            detail=f"File type '{suffix}' not supported. Allowed: {sorted(settings.ALLOWED_EXTENSIONS)}",
        )

    # Read and size-check
    content = await file.read()
    size_mb = len(content) / (1024 * 1024)
    if size_mb > settings.MAX_FILE_SIZE_MB:
        raise HTTPException(
            413,
            detail=f"File too large ({size_mb:.1f} MB). Max: {settings.MAX_FILE_SIZE_MB} MB",
        )

    # Extract text
    try:
        raw_text = resume_parser.extract_text_from_bytes(content, suffix)
    except Exception as exc:
        log.error("Text extraction failed: %s", exc)
        raise HTTPException(422, detail=f"Could not extract text from file: {exc}")

    if not raw_text.strip():
        raise HTTPException(422, detail="No text could be extracted from the uploaded file.")

    # Load catalog + roles
    catalog, roles = _load_data()

    # Run pipeline
    try:
        report = run_pipeline(raw_text, role_id, catalog, roles)
    except ValueError as exc:
        raise HTTPException(404, detail=str(exc))
    except Exception as exc:
        log.exception("Pipeline error")
        raise HTTPException(500, detail=f"Analysis failed: {exc}")

    return report


@router.post("/text", response_model=AnalysisReport, summary="Analyse resume from plain text")
async def analyze_text(role_id: str = Form(...), resume_text: str = Form(...)):
    """
    Alternative endpoint for clients that send plain text (e.g. tests, browser demos).
    """
    if not resume_text.strip():
        raise HTTPException(422, detail="resume_text is empty.")

    catalog, roles = _load_data()

    try:
        report = run_pipeline(resume_text, role_id, catalog, roles)
    except ValueError as exc:
        raise HTTPException(404, detail=str(exc))
    except Exception as exc:
        log.exception("Pipeline error")
        raise HTTPException(500, detail=f"Analysis failed: {exc}")

    return report


# ── JD-based analysis ─────────────────────────────────────────────────────────

def _load_services_catalog() -> list[dict]:
    path = settings.DATA_DIR / "services_catalog.json"
    if not path.exists():
        return []
    raw = json.loads(path.read_text(encoding="utf-8"))
    if isinstance(raw, list):
        return raw
    return raw.get("services", [])


@router.post("/jd", response_model=JDAnalysisReport, summary="Analyse resume against a real job description")
async def analyze_against_jd(
    resume_file: Optional[UploadFile] = File(None, description="Resume file (.pdf, .docx, .txt)"),
    resume_text_field: Optional[str]  = Form(None, alias="resume_text"),
    jd_file:     Optional[UploadFile] = File(None, description="Job description file"),
    jd_text_field: Optional[str]      = Form(None, alias="jd_text"),
):
    """
    JD-based gap analysis. Provide resume + job description (file or text).
    Returns skill gaps, certification gaps, experience gap, resume keyword gaps, next steps.
    """
    from app.services import resume_parser as rp
    from app.services.skill_extractor  import extract_skills_by_alias
    from app.services.fuzzy_extractor  import extract_skills_by_fuzzy
    from app.services.ner_extractor    import extract_skills_by_ner
    from app.services.semantic_matcher import find_semantic_skills
    from app.services.pipeline         import _merge_skill_lists
    from app.services.text_utils       import redact_pii
    from app.schemas import (JDSkillGapItem, JDCertGapItem, JDExperienceGap,
                              JDKeywordGap, JDNextStep)

    # ── Resolve resume text ──
    raw_resume = ""
    if resume_file and resume_file.filename:
        suffix = Path(resume_file.filename).suffix.lower()
        if suffix not in settings.ALLOWED_EXTENSIONS:
            raise HTTPException(400, detail=f"Resume file type '{suffix}' not supported.")
        content = await resume_file.read()
        try:
            raw_resume = rp.extract_text_from_bytes(content, suffix)
        except Exception as exc:
            raise HTTPException(422, detail=f"Could not read resume: {exc}")
    elif resume_text_field:
        raw_resume = resume_text_field

    if not raw_resume.strip():
        raise HTTPException(422, detail="Provide a resume file or resume_text.")

    # ── Resolve JD text ──
    raw_jd = ""
    if jd_file and jd_file.filename:
        suffix = Path(jd_file.filename).suffix.lower()
        if suffix not in settings.ALLOWED_EXTENSIONS:
            raise HTTPException(400, detail=f"JD file type '{suffix}' not supported.")
        content = await jd_file.read()
        try:
            raw_jd = rp.extract_text_from_bytes(content, suffix)
        except Exception as exc:
            raise HTTPException(422, detail=f"Could not read job description: {exc}")
    elif jd_text_field:
        raw_jd = jd_text_field

    if not raw_jd.strip():
        raise HTTPException(422, detail="Provide a jd_file or jd_text.")

    # ── Load catalog ──
    catalog_path = settings.DATA_DIR / "skills_catalog.json"
    if not catalog_path.exists():
        raise HTTPException(500, detail="skills_catalog.json missing.")
    catalog_raw = json.loads(catalog_path.read_text(encoding="utf-8"))
    catalog = {k: v for k, v in catalog_raw.items() if not k.startswith("_") and isinstance(v, list)}
    services = _load_services_catalog()

    # ── 4-pass pipeline on resume ──
    try:
        cleaned      = rp.clean_text(raw_resume)
        sections_raw = rp.detect_sections(cleaned)
        cand_name    = rp.extract_candidate_name(sections_raw)
        cleaned      = redact_pii(cleaned)
        sections     = rp.detect_sections(cleaned)
        sections_found = [s for s in sections if s != "header"]

        alias_skills = extract_skills_by_alias(sections, catalog)
        alias_found  = {s.name for s in alias_skills}
        fuzzy_skills = extract_skills_by_fuzzy(sections, catalog, alias_found)
        fuzzy_found  = alias_found | {s.name for s in fuzzy_skills}
        ner_skills   = extract_skills_by_ner(sections, catalog, fuzzy_found)
        ner_found    = fuzzy_found | {s.name for s in ner_skills}
        sem_skills   = find_semantic_skills(sections, catalog, ner_found)
        all_skills   = _merge_skill_lists(alias_skills, fuzzy_skills, ner_skills, sem_skills)
    except Exception as exc:
        log.exception("Resume pipeline error in JD mode")
        raise HTTPException(500, detail=f"Resume analysis failed: {exc}")

    # ── Parse JD + gap analysis ──
    jd_result  = parse_jd(raw_jd, catalog)
    gap_report = analyze_jd_gaps(jd_result, all_skills, cleaned, services)

    # ── Serialise ──
    def sk(g):
        return JDSkillGapItem(name=g.name, importance=g.importance, reason=g.reason, resources=g.resources)
    def ce(g):
        return JDCertGapItem(name=g.name, why_relevant=g.why_relevant, how_to_get=g.how_to_get)
    def ex(g):
        if g is None: return None
        return JDExperienceGap(required_years=g.required_years, resume_implied_years=g.resume_implied_years,
                               gap_years=g.gap_years, verdict=g.verdict, advice=g.advice)
    def kw(g):
        return JDKeywordGap(phrase=g.phrase, suggestion=g.suggestion)
    def ns(s):
        return JDNextStep(priority=s.priority, category=s.category, action=s.action, details=s.details)

    # ── Apply-Ready verdict (LLM-powered) ──
    verdict_dict = get_apply_verdict(gap_report, cand_name)
    verdict = ApplyVerdict(**verdict_dict)

    # ── Resume quality analysis ──
    rq = analyse_resume_quality(cleaned)
    from app.schemas import BulletQuality as BQ
    rq_schema = ResumeQualitySummary(
        overall_quality=rq.overall_quality,
        overall_score=rq.overall_score,
        total_bullets=rq.total_bullets,
        strong_bullets=rq.strong_bullets,
        weak_bullets=rq.weak_bullets,
        summary=rq.summary,
        top_weak_bullets=rq.top_weak_bullets,
        bullet_details=[
            BQ(text=b.text, quality_label=b.quality_label,
               quality_score=b.quality_score, improvement_hint=b.improvement_hint)
            for b in rq.bullet_analyses[:20]
        ],
    )

    # ── Action plan (certs, courses, job links, volunteer, resume tips) ──
    exp_gap_years   = gap_report.experience_gap.gap_years if gap_report.experience_gap else 0
    kw_gaps         = [k.phrase for k in gap_report.keyword_gaps]
    missing_req     = [g.name for g in gap_report.skill_gaps if g.importance == "required"]
    action_plan     = build_action_plan(
        skill_gaps=missing_req,
        experience_gap_years=exp_gap_years,
        keyword_gaps=kw_gaps,
        weak_bullet_count=rq.weak_bullets,
        job_title=gap_report.jd_job_title,
        missing_required=missing_req,
    )

    return JDAnalysisReport(
        report_id=str(uuid.uuid4())[:12],
        candidate_name=cand_name,
        jd_job_title=gap_report.jd_job_title,
        jd_readiness_score=gap_report.jd_readiness_score,
        jd_readiness_label=gap_report.jd_readiness_label,
        required_skill_coverage=gap_report.required_skill_coverage,
        preferred_skill_coverage=gap_report.preferred_skill_coverage,
        matched_required=gap_report.matched_required,
        matched_preferred=gap_report.matched_preferred,
        extracted_skills=all_skills,
        skill_gaps=[sk(g) for g in gap_report.skill_gaps],
        certification_gaps=[ce(g) for g in gap_report.certification_gaps],
        experience_gap=ex(gap_report.experience_gap),
        keyword_gaps=[kw(g) for g in gap_report.keyword_gaps],
        next_steps=[ns(s) for s in gap_report.next_steps],
        apply_verdict=verdict,
        resume_quality=rq_schema,
        action_plan=action_plan,
        resume_sections_found=sections_found,
        processing_notes=gap_report.processing_notes,
    )


@router.post("/rewrite-bullet", response_model=BulletRewriteResponse,
             summary="Rewrite a weak resume bullet using LLM")
async def rewrite_resume_bullet(body: BulletRewriteRequest):
    """
    Takes a weak resume bullet and rewrites it using an LLM (HuggingFace/OpenAI).
    Use the bullet text from resume_quality.bullet_details where quality_label == 'Weak'.
    """
    rewritten = rewrite_bullet(
        bullet=body.bullet,
        skill=body.skill,
        job_title=body.job_title,
    )
    return BulletRewriteResponse(
        original=body.bullet,
        rewritten=rewritten,
        skill=body.skill,
    )
el=gap_report.jd_readiness_label,
        required_skill_coverage=gap_report.required_skill_coverage,
        preferred_skill_coverage=gap_report.preferred_skill_coverage,
        matched_required=gap_report.matched_required,
        matched_preferred=gap_report.matched_preferred,
        extracted_skills=all_skills,
        skill_gaps=[sk(g) for g in gap_report.skill_gaps],
        certification_gaps=[ce(g) for g in gap_report.certification_gaps],
        experience_gap=ex(gap_report.experience_gap),
        keyword_gaps=[kw(g) for g in gap_report.keyword_gaps],
        next_steps=[ns(s) for s in gap_report.next_steps],
        apply_verdict=verdict,
        resume_quality=rq_schema,
        action_plan=action_plan,
        resume_sections_found=sections_found,
        processing_notes=gap_report.processing_notes,
    )


@router.post("/rewrite-bullet", response_model=BulletRewriteResponse,
             summary="Rewrite a weak resume bullet using LLM")
async def rewrite_resume_bullet(body: BulletRewriteRequest):
    """
    Takes a weak resume bullet and rewrites it using an LLM (HuggingFace/OpenAI).
    Use the bullet text from resume_quality.bullet_details where quality_label == 'Weak'.
    """
    rewritten = rewrite_bullet(
        bullet=body.bullet,
        skill=body.skill,
        job_title=body.job_title,
    )
    return BulletRewriteResponse(
        original=body.bullet,
        rewritten=rewritten,
        skill=body.skill,
    )
