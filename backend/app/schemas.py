"""
schemas.py — Every data shape in the system.
Clean Pydantic models with full documentation on every field.
"""
from __future__ import annotations
from typing import Optional
from pydantic import BaseModel, Field


# ── Evidence ─────────────────────────────────────────────────────────────────

class EvidenceItem(BaseModel):
    snippet: str          = Field(description="Sentence where the skill was found.")
    section: str          = Field(description="Resume section: experience, skills, etc.")
    section_weight: float = Field(description="How much this section counts (1.5 for experience).")


# ── Extracted skill ───────────────────────────────────────────────────────────

class ExtractedSkill(BaseModel):
    name: str             = Field(description="Canonical skill name e.g. 'python'.")
    confidence: float     = Field(ge=0.0, le=1.0, description="Confidence 0–1.")
    how_found: str        = Field(description="alias | fuzzy | bert_ner | semantic | both")
    aliases_matched: list[str]        = Field(default_factory=list)
    evidence: list[EvidenceItem]      = Field(default_factory=list)
    evidence_offsets: list[list[int]] = Field(
        default_factory=list,
        description="Char-level [start, end] spans for frontend text highlighting.",
    )
    low_confidence_flag: bool = Field(default=False,
        description="True if match looks uncertain (section-only, no context words).")


# ── Skill gaps ───────────────────────────────────────────────────────────────

class LearningResource(BaseModel):
    title: str
    url: str
    provider: str
    free: bool = True


class SkillGap(BaseModel):
    skill: str          = Field(description="Missing canonical skill name.")
    importance: str     = Field(description="required | nice_to_have")
    why_it_matters: str = Field(description="Plain-English reason this skill matters.")
    resources: list[LearningResource] = Field(default_factory=list)


# ── Readiness ────────────────────────────────────────────────────────────────

class ReadinessScore(BaseModel):
    score: float               = Field(ge=0.0, le=100.0, description="Overall score 0–100.")
    label: str                 = Field(description="Excellent | Good | Fair | Needs Work")
    required_coverage: float   = Field(ge=0.0, le=1.0)
    nice_to_have_coverage: float = Field(ge=0.0, le=1.0)
    confidence_low: float      = Field(description="Lower bound of 90% CI.")
    confidence_high: float     = Field(description="Upper bound of 90% CI.")
    explanation: str           = Field(description="One-sentence plain-English summary.")


# ── Multi-role ────────────────────────────────────────────────────────────────

class OtherRoleMatch(BaseModel):
    role_id: str
    role_title: str
    score: float             = Field(ge=0.0, le=100.0)
    label: str
    required_coverage: float = Field(ge=0.0, le=1.0)
    skills_matched: int      = Field(default=0, description="Required skills already held.")
    skills_gap_count: int    = Field(default=0, description="Required skills still missing.")
    next_steps: list[str]    = Field(default_factory=list,
        description="Top 3 skills to add to improve fit for this role.")
    seniority: str           = Field(default="", description="junior | mid | senior | manager")


class CareerPathAdvice(BaseModel):
    target_role_id: str
    target_role_title: str
    current_label: str
    easier_roles: list[str]               = Field(default_factory=list)
    stretch_roles: list[str]              = Field(default_factory=list)
    key_skills_to_unlock_next: list[str]  = Field(default_factory=list)


# ── Report (full API response) ────────────────────────────────────────────────

class AnalysisReport(BaseModel):
    report_id: str
    role_id: str
    role_title: str
    candidate_name: str                       = "Unknown"
    readiness: ReadinessScore
    extracted_skills: list[ExtractedSkill]
    skill_gaps: list[SkillGap]
    other_role_matches: list[OtherRoleMatch]  = Field(default_factory=list)
    career_path_advice: Optional[CareerPathAdvice] = None
    resume_sections_found: list[str]
    total_skills_extracted: int = 0
    total_skills_required: int  = 0
    processing_notes: list[str] = Field(default_factory=list)


# ── Request / response helpers ────────────────────────────────────────────────

class FeedbackRequest(BaseModel):
    report_id: str
    correct_skills: list[str]  = Field(default_factory=list)
    wrong_skills: list[str]    = Field(default_factory=list)
    missing_skills: list[str]  = Field(default_factory=list)
    comment: Optional[str]     = None

class FeedbackResponse(BaseModel):
    success: bool
    message: str

class RoleItem(BaseModel):
    role_id: str
    title: str
    seniority: str = ""
    required_skills: list[str]    = Field(default_factory=list)
    nice_to_have_skills: list[str] = Field(default_factory=list)

class RolesResponse(BaseModel):
    roles: list[RoleItem]
    total: int

class ServiceEntry(BaseModel):
    service_id: str
    title: str
    provider: str
    url: str
    skills_covered: list[str] = Field(default_factory=list)
    categories: list[str]     = Field(default_factory=list)
    free: bool   = True
    level: str   = "beginner"
    description: str = ""

class ServicesResponse(BaseModel):
    services: list[ServiceEntry]
    total: int

class RebuildResponse(BaseModel):
    status: str
    skills_count: int
    roles_count: int
    csv_rows_processed: int
    message: str


# ── JD-based analysis schemas ─────────────────────────────────────────────────

class JDSkillGapItem(BaseModel):
    name: str
    importance: str           # "required" | "preferred"
    reason: str
    resources: list[dict]     = Field(default_factory=list)

class JDCertGapItem(BaseModel):
    name: str
    why_relevant: str
    how_to_get: str

class JDExperienceGap(BaseModel):
    required_years: int
    resume_implied_years: int
    gap_years: int
    verdict: str              # "sufficient" | "close" | "significant"
    advice: str

class JDKeywordGap(BaseModel):
    phrase: str
    suggestion: str

class JDNextStep(BaseModel):
    priority: int
    category: str             # "skill" | "cert" | "experience" | "keyword" | "resume"
    action: str
    details: str

class JDAnalysisReport(BaseModel):
    report_id: str
    candidate_name: str                        = "Unknown"
    jd_job_title: str                          = ""
    jd_readiness_score: float                  = Field(ge=0.0, le=100.0)
    jd_readiness_label: str
    required_skill_coverage: float             = Field(ge=0.0, le=1.0)
    preferred_skill_coverage: float            = Field(ge=0.0, le=1.0)
    matched_required: list[str]                = Field(default_factory=list)
    matched_preferred: list[str]               = Field(default_factory=list)
    extracted_skills: list[ExtractedSkill]     = Field(default_factory=list)
    skill_gaps: list[JDSkillGapItem]           = Field(default_factory=list)
    certification_gaps: list[JDCertGapItem]    = Field(default_factory=list)
    experience_gap: Optional[JDExperienceGap]  = None
    keyword_gaps: list[JDKeywordGap]           = Field(default_factory=list)
    next_steps: list[JDNextStep]               = Field(default_factory=list)
    resume_sections_found: list[str]           = Field(default_factory=list)
    apply_verdict: Optional["ApplyVerdict"]        = None
    resume_quality: Optional["ResumeQualitySummary"] = None
    action_plan: Optional["ActionPlan"]            = None
    processing_notes: list[str]               = Field(default_factory=list)


class ApplyVerdict(BaseModel):
    tier: str                    # "Apply Now" | "Apply With Prep" | "Build First"
    colour: str                  # "green" | "amber" | "red"
    icon: str
    summary: str
    required_coverage_pct: int

class BulletQuality(BaseModel):
    text: str
    quality_label: str           # "Strong" | "Fair" | "Weak"
    quality_score: float
    improvement_hint: str

class ResumeQualitySummary(BaseModel):
    overall_quality: str
    overall_score: float
    total_bullets: int
    strong_bullets: int
    weak_bullets: int
    summary: str
    top_weak_bullets: list[str]  = Field(default_factory=list)
    bullet_details: list[BulletQuality] = Field(default_factory=list)


# ── Action Plan schemas ───────────────────────────────────────────────────────

class CertRecommendation(BaseModel):
    skill: str
    name: str
    provider: str
    level: str                  # Beginner | Intermediate | Advanced
    url: str
    free_prep_url: str

class CourseRecommendation(BaseModel):
    skill: str
    name: str
    provider: str
    url: str
    free: bool = True

class JobOpportunity(BaseModel):
    platform: str
    description: str
    search_url: str
    icon: str = ""

class VolunteerOpportunity(BaseModel):
    name: str
    description: str
    url: str
    best_for: str

class ResumeTip(BaseModel):
    priority: int
    category: str               # bullet_quality | ats_keywords | skills_section | experience_gap | formatting
    title: str
    detail: str
    example_before: str = ""
    example_after: str = ""
    keywords: list[str] = Field(default_factory=list)

class ActionPlan(BaseModel):
    certifications: list[CertRecommendation]      = Field(default_factory=list)
    courses: list[CourseRecommendation]            = Field(default_factory=list)
    job_opportunities: list[JobOpportunity]        = Field(default_factory=list)
    volunteer_opportunities: list[VolunteerOpportunity] = Field(default_factory=list)
    resume_tips: list[ResumeTip]                   = Field(default_factory=list)
    has_experience_gap: bool                       = False
    experience_gap_years: int                      = 0


# ── Bullet rewrite schemas ────────────────────────────────────────────────────

class BulletRewriteRequest(BaseModel):
    bullet: str
    skill: str
    job_title: str

class BulletRewriteResponse(BaseModel):
    original: str
    rewritten: str
    skill: str
