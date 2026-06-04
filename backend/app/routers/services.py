"""
routers/services.py — GET /services (learning resources catalog)
"""

import json
import logging
from typing import Optional

from fastapi import APIRouter, HTTPException, Query
from app.config import settings
from app.schemas import ServiceEntry, ServicesResponse

log = logging.getLogger(__name__)
router = APIRouter(prefix="/services", tags=["Services"])

_DEFAULT_SERVICES = [
    {"service_id": "kaggle_learn", "title": "Kaggle Learn", "provider": "Kaggle",
     "url": "https://www.kaggle.com/learn",
     "skills_covered": ["python", "pandas", "scikit-learn", "sql", "machine learning",
                        "deep learning", "natural language processing", "data visualization"],
     "categories": ["ml_ai", "data", "programming_language"], "free": True, "level": "beginner",
     "description": "Free micro-courses covering Python, ML, SQL, and data viz."},
    {"service_id": "fast_ai", "title": "fast.ai Practical Deep Learning", "provider": "fast.ai",
     "url": "https://course.fast.ai",
     "skills_covered": ["deep learning", "pytorch", "computer vision", "natural language processing"],
     "categories": ["ml_ai"], "free": True, "level": "intermediate",
     "description": "Top-down practical deep learning using PyTorch."},
    {"service_id": "cs50", "title": "CS50", "provider": "Harvard / edX",
     "url": "https://cs50.harvard.edu/x",
     "skills_covered": ["python", "c", "javascript", "sql", "algorithms", "data structures"],
     "categories": ["programming_language"], "free": True, "level": "beginner",
     "description": "Harvard's legendary intro CS course, free to audit."},
    {"service_id": "google_ml", "title": "Machine Learning Crash Course", "provider": "Google",
     "url": "https://developers.google.com/machine-learning/crash-course",
     "skills_covered": ["machine learning", "tensorflow", "python", "numpy", "pandas"],
     "categories": ["ml_ai", "data"], "free": True, "level": "beginner",
     "description": "Google's ML guide using TensorFlow."},
    {"service_id": "docker_official", "title": "Docker Getting Started", "provider": "Docker",
     "url": "https://docs.docker.com/get-started",
     "skills_covered": ["docker", "containerisation"], "categories": ["devops"],
     "free": True, "level": "beginner", "description": "Official hands-on Docker tutorial."},
    {"service_id": "k8s_official", "title": "Kubernetes Basics", "provider": "Kubernetes",
     "url": "https://kubernetes.io/docs/tutorials/kubernetes-basics",
     "skills_covered": ["kubernetes", "docker", "devops"], "categories": ["devops"],
     "free": True, "level": "intermediate", "description": "Official interactive Kubernetes tutorial."},
    {"service_id": "aws_skill_builder", "title": "AWS Skill Builder", "provider": "Amazon Web Services",
     "url": "https://skillbuilder.aws",
     "skills_covered": ["aws", "cloud computing", "ec2", "s3", "lambda", "cloudformation"],
     "categories": ["cloud", "devops"], "free": True, "level": "beginner",
     "description": "Free AWS learning hub with hundreds of digital courses."},
    {"service_id": "mode_sql", "title": "SQL Tutorial for Data Analysis", "provider": "Mode Analytics",
     "url": "https://mode.com/sql-tutorial",
     "skills_covered": ["sql", "postgresql", "data analysis"],
     "categories": ["database", "data"], "free": True, "level": "beginner",
     "description": "Interactive SQL tutorial with real datasets."},
    {"service_id": "mlops_zoomcamp", "title": "MLOps Zoomcamp", "provider": "DataTalks.Club",
     "url": "https://github.com/DataTalksClub/mlops-zoomcamp",
     "skills_covered": ["mlops", "docker", "kubernetes", "airflow", "mlflow", "machine learning"],
     "categories": ["ml_ai", "devops"], "free": True, "level": "intermediate",
     "description": "Free MLOps course covering the full ML lifecycle in production."},
    {"service_id": "hf_nlp", "title": "HuggingFace NLP Course", "provider": "Hugging Face",
     "url": "https://huggingface.co/learn/nlp-course",
     "skills_covered": ["natural language processing", "transformers", "pytorch", "bert"],
     "categories": ["ml_ai"], "free": True, "level": "intermediate",
     "description": "End-to-end NLP with Transformers."},
    {"service_id": "fullstack_open", "title": "Full Stack Open", "provider": "University of Helsinki",
     "url": "https://fullstackopen.com",
     "skills_covered": ["javascript", "react", "node.js", "rest api", "graphql", "typescript", "docker"],
     "categories": ["programming_language", "framework"], "free": True, "level": "intermediate",
     "description": "University-quality full-stack JavaScript course, free."},
    {"service_id": "dbt_learn", "title": "dbt Learn", "provider": "dbt Labs",
     "url": "https://courses.getdbt.com",
     "skills_covered": ["dbt", "sql", "data warehouse", "analytics engineering"],
     "categories": ["data", "database"], "free": True, "level": "beginner",
     "description": "Free dbt fundamentals and advanced courses."},
]


def _load_services() -> list[dict]:
    path = settings.DATA_DIR / "services_catalog.json"
    if not path.exists():
        path.write_text(json.dumps(_DEFAULT_SERVICES, indent=2, ensure_ascii=False), encoding="utf-8")
    return json.loads(path.read_text(encoding="utf-8"))


@router.get("", response_model=ServicesResponse, summary="List learning services")
def list_services(
    skill:    Optional[str]  = Query(None, description="Filter by skill, e.g. 'python'"),
    category: Optional[str]  = Query(None, description="Filter by category: ml_ai, data, cloud, devops …"),
    free:     Optional[bool] = Query(None, description="true = free resources only"),
    level:    Optional[str]  = Query(None, description="beginner | intermediate | advanced"),
):
    raw = _load_services()
    entries: list[ServiceEntry] = []
    for item in raw:
        try:
            e = ServiceEntry(**item)
        except Exception:
            continue
        if skill    and skill.lower()    not in [s.lower() for s in e.skills_covered]:
            continue
        if category and category.lower() not in [c.lower() for c in e.categories]:
            continue
        if free is not None and e.free != free:
            continue
        if level and e.level.lower() != level.lower():
            continue
        entries.append(e)

    return ServicesResponse(
        services=entries,
        total=len(entries),
        filtered_by_skill=skill,
        filtered_by_category=category,
    )


@router.get("/{service_id}", response_model=ServiceEntry, summary="Get a single service")
def get_service(service_id: str):
    for item in _load_services():
        if item.get("service_id") == service_id:
            return ServiceEntry(**item)
    raise HTTPException(404, detail=f"Service '{service_id}' not found.")
