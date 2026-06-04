"""
recommendation_engine.py — Generate skill gap recommendations
--------------------------------------------------------------
Takes the list of detected skills and the target role, and produces a
prioritised list of SkillGap objects — the skills the candidate still needs,
each enriched with a plain-English explanation and curated learning resources.

Ordering:
  Required gaps come first (sorted by position in the role's required_skills
  list, which reflects the role's own importance ordering).
  Nice-to-have gaps follow, sorted the same way.

Learning resources:
  Each gap skill is matched against the services catalog
  (app/data/services_catalog.json).  If no services file exists, the engine
  falls back to a small hard-coded resource list so the API never returns
  empty recommendations.
"""

from __future__ import annotations

import json
import logging
from pathlib import Path

from app.config import settings
from app.schemas import ExtractedSkill, SkillGap, LearningResource

log = logging.getLogger(__name__)

# ── Fallback resources (used if services_catalog.json is missing) ─────────────
_FALLBACK_RESOURCES: dict[str, list[dict]] = {
    "python": [
        {"title": "Python.org Tutorial", "url": "https://docs.python.org/3/tutorial/",
         "provider": "Python.org", "free": True},
    ],
    "sql": [
        {"title": "Mode Analytics SQL Tutorial", "url": "https://mode.com/sql-tutorial",
         "provider": "Mode Analytics", "free": True},
    ],
    "docker": [
        {"title": "Docker Official Getting Started", "url": "https://docs.docker.com/get-started",
         "provider": "Docker", "free": True},
    ],
    "machine learning": [
        {"title": "Google ML Crash Course",
         "url": "https://developers.google.com/machine-learning/crash-course",
         "provider": "Google", "free": True},
    ],
    "kubernetes": [
        {"title": "Kubernetes Basics", "url": "https://kubernetes.io/docs/tutorials/kubernetes-basics",
         "provider": "Kubernetes", "free": True},
    ],
    "aws": [
        {"title": "AWS Skill Builder", "url": "https://skillbuilder.aws",
         "provider": "Amazon Web Services", "free": True},
    ],
}

# ── Why-it-matters copy by category keyword ──────────────────────────────────
_WHY_IT_MATTERS: dict[str, str] = {
    "python":           "Python is the de-facto language for data science and ML workflows.",
    "sql":              "SQL is essential for querying and transforming structured data.",
    "docker":           "Docker is the standard for packaging and deploying applications consistently.",
    "kubernetes":       "Kubernetes is the industry standard for container orchestration at scale.",
    "machine learning": "Core ML knowledge underpins model development and evaluation.",
    "deep learning":    "Deep learning drives state-of-the-art results in vision and NLP tasks.",
    "aws":              "AWS is the leading cloud platform — most production systems run on it.",
    "azure":            "Azure is widely used in enterprise cloud infrastructure.",
    "google cloud":     "Google Cloud is strong in ML/AI tooling and big data processing.",
    "tensorflow":       "TensorFlow is widely used for production-grade ML model deployment.",
    "pytorch":          "PyTorch is the preferred framework for research and modern ML development.",
    "scikit-learn":     "scikit-learn is the standard library for classical ML algorithms.",
    "spark":            "Apache Spark is essential for processing large-scale datasets.",
    "kafka":            "Apache Kafka is the standard for real-time data streaming pipelines.",
    "airflow":          "Apache Airflow is widely used for orchestrating data pipelines.",
    "react":            "React is the dominant frontend framework for building web UIs.",
    "typescript":       "TypeScript adds type safety to JavaScript — standard in modern frontend.",
    "git":              "Git is a baseline expectation in every software engineering role.",
}

_DEFAULT_WHY = (
    "This skill appears in job postings for this role and is expected "
    "by most hiring managers."
)


def _load_services_catalog() -> list[dict]:
    """Load the services catalog, returning an empty list on failure."""
    catalog_path = settings.DATA_DIR / "services_catalog.json"
    if not catalog_path.exists():
        return []
    try:
        return json.loads(catalog_path.read_text(encoding="utf-8"))
    except Exception as exc:
        log.warning("Could not load services_catalog.json: %s", exc)
        return []


def _find_resources_for_skill(skill_name: str, services: list[dict]) -> list[LearningResource]:
    """Return up to 3 learning resources that cover this skill."""
    resources: list[LearningResource] = []

    for svc in services:
        covered = [s.lower() for s in svc.get("skills_covered", [])]
        if skill_name.lower() in covered or any(skill_name.lower() in c for c in covered):
            resources.append(LearningResource(
                title=svc.get("title", ""),
                url=svc.get("url", ""),
                provider=svc.get("provider", ""),
                free=svc.get("free", True),
            ))
        if len(resources) >= 3:
            break

    # Fall back to hard-coded if nothing found
    if not resources:
        for key, rlist in _FALLBACK_RESOURCES.items():
            if key in skill_name.lower() or skill_name.lower() in key:
                for r in rlist[:2]:
                    resources.append(LearningResource(**r))
                break

    return resources


def _why_it_matters(skill_name: str) -> str:
    skill_lower = skill_name.lower()
    for keyword, reason in _WHY_IT_MATTERS.items():
        if keyword in skill_lower or skill_lower in keyword:
            return reason
    return _DEFAULT_WHY


def generate_skill_gaps(
    extracted_skills: list[ExtractedSkill],
    role: dict,
) -> list[SkillGap]:
    """
    Generate prioritised skill gap recommendations.

    Args:
        extracted_skills: All skills detected by the 4-pass pipeline.
        role:             Role template dict.

    Returns:
        List of SkillGap, required gaps first, then nice-to-have.
    """
    services = _load_services_catalog()

    present = {
        s.name for s in extracted_skills
        if s.confidence >= settings.PRESENCE_THRESHOLD
    }

    required_skills:     list[str] = role.get("required_skills", [])
    nice_to_have_skills: list[str] = role.get("nice_to_have_skills", [])

    gaps: list[SkillGap] = []

    for skill_name in required_skills:
        if skill_name not in present:
            gaps.append(SkillGap(
                skill=skill_name,
                importance="required",
                why_it_matters=_why_it_matters(skill_name),
                resources=_find_resources_for_skill(skill_name, services),
            ))

    for skill_name in nice_to_have_skills:
        if skill_name not in present:
            gaps.append(SkillGap(
                skill=skill_name,
                importance="nice_to_have",
                why_it_matters=_why_it_matters(skill_name),
                resources=_find_resources_for_skill(skill_name, services),
            ))

    log.debug(
        "recommendation_engine: %d required gaps, %d nice-to-have gaps",
        sum(1 for g in gaps if g.importance == "required"),
        sum(1 for g in gaps if g.importance == "nice_to_have"),
    )
    return gaps
