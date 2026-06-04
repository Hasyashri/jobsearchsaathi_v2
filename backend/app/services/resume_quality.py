"""
resume_quality.py — Resume bullet point quality analysis.

WHY BULLET QUALITY ANALYSIS?
------------------------------
Skill extraction tells us WHAT technologies a candidate lists.
Bullet quality analysis tells us HOW WELL they demonstrate those skills.
Recruiters reject candidates not just for missing skills, but for failing
to prove the skills they claim. This is the "experience proof gap" — the
most common invisible rejection reason for newcomers and new graduates.

RESEARCH BASIS:
  - Ladders (2018) eye-tracking: recruiters spend 6 seconds on average
  - LinkedIn Talent Insights (2023): 47% of rejections are due to "lack of
    demonstrated impact" not missing skills
  - Resume studies: bullets with numbers increase callback rate by ~40%
    (TheLadders resume guide, Jobscan research)

ALGORITHM DESIGN:
  Three signals per bullet point:

  1. IMPACT SIGNAL — does it show measurable result?
     Patterns: percentages, dollar amounts, user counts, time saved
     Why: hiring managers are trained to look for these as evidence of value

  2. ACTION SIGNAL — does it start with a strong verb?
     Patterns: built, designed, deployed, led, reduced, improved, etc.
     Why: passive language ("was responsible for") signals junior thinking

  3. VAGUENESS SIGNAL — does it use filler phrases that add no information?
     Patterns: "worked on", "helped with", "assisted in", "involved in"
     Why: these phrases appear on almost every weak resume
"""
from __future__ import annotations
import re
from dataclasses import dataclass, field

# ── Patterns ───────────────────────────────────────────────────────────────

# Impact: numbers, percentages, monetary values, scale indicators
_IMPACT_RE = re.compile(
    r"\b\d+[\%x]|\$[\d,]+|"                          # 40%, 3x, $50,000
    r"\b\d+[KkMmBb]\b|"                               # 50K users, 2M records
    r"\b(reduced|improved|increased|decreased|saved|grew|scaled|cut)\b.*\d|"
    r"\b\d+\s*(users?|customers?|requests?|endpoints?|models?|pipelines?|"
    r"seconds?|minutes?|hours?|days?|weeks?|months?|records?|rows?|features?|"
    r"accuracy|f1|auc|rmse|precision|recall)\b",
    re.IGNORECASE,
)

# Strong action verbs (past tense — standard resume convention)
_ACTION_VERBS = {
    "built","designed","developed","created","implemented","deployed","architected",
    "led","managed","delivered","launched","shipped","automated","optimised","optimized",
    "reduced","improved","increased","scaled","refactored","migrated","integrated",
    "trained","fine-tuned","finetuned","evaluated","analysed","analyzed","modelled","modeled",
    "extracted","transformed","orchestrated","monitored","debugged","tested","validated",
    "researched","published","presented","collaborated","mentored","coordinated",
    "engineered","configured","established","streamlined","accelerated",
}

# Vagueness phrases — penalise these
_VAGUE_RE = re.compile(
    r"\b(worked\s+on|helped\s+(with|to)|assisted\s+(in|with)|"
    r"was\s+responsible\s+for|was\s+involved\s+in|"
    r"participated\s+in|contributed\s+to|"
    r"familiar\s+with|exposure\s+to|knowledge\s+of|"
    r"understanding\s+of|experience\s+with)\b",
    re.IGNORECASE,
)

# Technology/tool nouns (present = more credible)
_TOOL_RE = re.compile(
    r"\b(python|sql|java|react|docker|kubernetes|aws|gcp|azure|"
    r"tensorflow|pytorch|scikit|pandas|spark|kafka|airflow|"
    r"fastapi|flask|django|postgres|mongodb|redis|git|"
    r"langchain|huggingface|bert|gpt|llm|transformer|"
    r"faiss|vector|embedding|rag|agent|pipeline|api|rest|"
    r"etl|dbt|tableau|power\s*bi|excel)\b",
    re.IGNORECASE,
)


@dataclass
class BulletAnalysis:
    text: str
    has_impact: bool = False
    has_action_verb: bool = False
    has_tool_mention: bool = False
    is_vague: bool = False
    quality_score: float = 0.0     # 0.0 (weak) to 1.0 (strong)
    quality_label: str = "Weak"    # Weak | Fair | Strong
    improvement_hint: str = ""


@dataclass
class ResumeQualityReport:
    total_bullets: int = 0
    strong_bullets: int = 0
    fair_bullets: int = 0
    weak_bullets: int = 0
    overall_quality: str = "Needs Work"   # Needs Work | Fair | Good | Strong
    overall_score: float = 0.0
    bullet_analyses: list[BulletAnalysis] = field(default_factory=list)
    top_weak_bullets: list[str] = field(default_factory=list)
    summary: str = ""


def analyse_bullet(text: str) -> BulletAnalysis:
    """Score a single resume bullet point."""
    b = BulletAnalysis(text=text.strip())

    if not b.text or len(b.text) < 15:
        return b

    # Signal 1: Impact (quantified results)
    b.has_impact = bool(_IMPACT_RE.search(b.text))

    # Signal 2: Action verb (first word)
    first_word = b.text.split()[0].lower().rstrip(".,;:")
    b.has_action_verb = first_word in _ACTION_VERBS

    # Signal 3: Tool/tech mention
    b.has_tool_mention = bool(_TOOL_RE.search(b.text))

    # Signal 4: Vagueness
    b.is_vague = bool(_VAGUE_RE.search(b.text))

    # Scoring
    score = 0.0
    score += 0.40 if b.has_impact else 0.0
    score += 0.25 if b.has_action_verb else 0.0
    score += 0.20 if b.has_tool_mention else 0.0
    score -= 0.30 if b.is_vague else 0.0
    score = max(0.0, min(1.0, score))
    b.quality_score = round(score, 2)

    if score >= 0.65:
        b.quality_label = "Strong"
    elif score >= 0.35:
        b.quality_label = "Fair"
    else:
        b.quality_label = "Weak"

    # Generate improvement hint
    hints = []
    if not b.has_impact:
        hints.append("Add a number (%, users, time saved, accuracy)")
    if not b.has_action_verb:
        hints.append("Start with an action verb (Built, Reduced, Deployed...)")
    if b.is_vague:
        hints.append("Replace vague phrase with specific ownership language")
    if not b.has_tool_mention:
        hints.append("Name the specific tool or technology used")
    b.improvement_hint = " · ".join(hints) if hints else "Well written — no changes needed"

    return b


def _extract_bullets(resume_text: str) -> list[str]:
    """
    Extract likely bullet point lines from resume text.
    We look for:
      - Lines starting with bullet characters (•, *, -)
      - Indented lines with past-tense verbs
      - Lines in the experience or projects sections
    """
    bullets = []
    for line in resume_text.split("\n"):
        line = line.strip()
        # Skip short lines, headers, education lines
        if len(line) < 20 or len(line) > 300:
            continue
        # Skip lines that look like headers (all caps or very short)
        if line.isupper() or len(line.split()) <= 2:
            continue
        # Skip date lines
        if re.match(r"^\d{4}", line) or re.search(r"\d{4}\s*[-–]\s*(\d{4}|present)", line, re.I):
            continue

        # Include lines that start with bullet symbols or look like experience bullets
        first = line.lstrip("•*-–▪▸►‣ ").strip()
        first_word = first.split()[0].lower().rstrip(".,") if first.split() else ""

        if (
            line[0] in "•*-–▪▸►‣" or
            first_word in _ACTION_VERBS or
            first_word in {"the", "a", "an", "used", "using"} and len(first) > 40
        ):
            bullets.append(first)

    return bullets


def analyse_resume_quality(resume_text: str) -> ResumeQualityReport:
    """
    Full resume quality analysis.
    Returns ResumeQualityReport with per-bullet breakdown and overall quality.
    """
    report = ResumeQualityReport()
    bullets = _extract_bullets(resume_text)

    if not bullets:
        report.summary = "No bullet points detected. Add work experience with specific bullet points to demonstrate your skills."
        return report

    report.total_bullets = len(bullets)
    analyses = [analyse_bullet(b) for b in bullets]
    report.bullet_analyses = analyses

    report.strong_bullets = sum(1 for b in analyses if b.quality_label == "Strong")
    report.fair_bullets   = sum(1 for b in analyses if b.quality_label == "Fair")
    report.weak_bullets   = sum(1 for b in analyses if b.quality_label == "Weak")

    avg_score = sum(b.quality_score for b in analyses) / len(analyses)
    report.overall_score = round(avg_score, 2)

    if avg_score >= 0.65:
        report.overall_quality = "Strong"
    elif avg_score >= 0.40:
        report.overall_quality = "Good"
    elif avg_score >= 0.20:
        report.overall_quality = "Fair"
    else:
        report.overall_quality = "Needs Work"

    # Top weak bullets to show as examples
    weak = sorted([b for b in analyses if b.quality_label == "Weak"], key=lambda x: x.quality_score)
    report.top_weak_bullets = [b.text for b in weak[:3]]

    # Summary
    pct_strong = round(report.strong_bullets / report.total_bullets * 100)
    report.summary = (
        f"{pct_strong}% of your resume bullets show measurable impact. "
        f"You have {report.weak_bullets} weak bullet(s) that could be rewritten to "
        f"significantly increase your interview callback rate."
    )

    return report
