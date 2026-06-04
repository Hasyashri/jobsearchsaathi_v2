"""
readiness_engine.py - Compute candidate role readiness score
"""
from __future__ import annotations
import math
import logging

from app.config import settings
from app.schemas import ReadinessScore, ExtractedSkill

log = logging.getLogger(__name__)


def _label(score):
    if score >= 90: return "Excellent"
    if score >= 70: return "Good"
    if score >= 50: return "Fair"
    return "Needs Work"


def _confidence_interval(p, n):
    if n == 0:
        return 0.0, 0.0
    z = 1.645
    margin = z * math.sqrt(max(0.0, p * (1 - p)) / n)
    return round(max(0.0, (p - margin) * 100), 1), round(min(100.0, (p + margin) * 100), 1)


def compute_readiness(extracted_skills, role):
    required_skills      = role.get("required_skills", [])
    nice_to_have_skills  = role.get("nice_to_have_skills", [])

    present = {s.name for s in extracted_skills if s.confidence >= settings.PRESENCE_THRESHOLD}

    n_required = len(required_skills)
    n_nice     = len(nice_to_have_skills)

    matched_required = [s for s in required_skills if s in present]
    matched_nice     = [s for s in nice_to_have_skills if s in present]

    required_coverage     = len(matched_required) / n_required if n_required else 0.0
    nice_to_have_coverage = len(matched_nice) / n_nice if n_nice else 0.0

    # If no nice-to-have skills, renormalize so 100% required = score 100
    if n_nice == 0:
        raw = required_coverage
    else:
        raw = (
            required_coverage     * settings.READINESS_REQUIRED_WEIGHT +
            nice_to_have_coverage * settings.READINESS_NICE_TO_HAVE_WEIGHT
        )
    score = round(min(100.0, max(0.0, raw * 100)), 1)

    ci_low, ci_high = _confidence_interval(required_coverage, n_required)
    label = _label(score)

    missing_req = [s for s in required_skills if s not in present]
    if not missing_req:
        explanation = f"You have all {n_required} required skill(s) for this role."
    elif len(missing_req) <= 2:
        explanation = (
            f"You have {len(matched_required)}/{n_required} required skills. "
            f"Adding {' and '.join(missing_req[:2])} would make you fully ready."
        )
    else:
        explanation = (
            f"You have {len(matched_required)}/{n_required} required skills "
            f"({round(required_coverage * 100)}% coverage). "
            f"Focus on {', '.join(missing_req[:3])} to improve your score."
        )

    return ReadinessScore(
        score=score,
        label=label,
        required_coverage=round(required_coverage, 4),
        nice_to_have_coverage=round(nice_to_have_coverage, 4),
        confidence_low=ci_low,
        confidence_high=ci_high,
        explanation=explanation,
    )
