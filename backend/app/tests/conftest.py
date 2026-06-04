"""
conftest.py - Shared pytest fixtures for the v2 test suite.
"""
import json
import pytest
from pathlib import Path
from fastapi.testclient import TestClient

from app.config import settings
assert (settings.DATA_DIR / "skills_catalog.json").exists(), (
    f"skills_catalog.json not found at {settings.DATA_DIR}. "
    "Run tests from the backend/ directory."
)

from app.main import app


@pytest.fixture(scope="session")
def client():
    return TestClient(app)


@pytest.fixture(scope="session")
def catalog():
    path = settings.DATA_DIR / "skills_catalog.json"
    raw = json.loads(path.read_text(encoding="utf-8"))
    return {k: v for k, v in raw.items() if not k.startswith("_") and isinstance(v, list)}


@pytest.fixture(scope="session")
def roles():
    path = settings.DATA_DIR / "role_templates.json"
    return json.loads(path.read_text(encoding="utf-8"))


DATA_SCIENCE_RESUME = """
John Doe
john@example.com | github.com/johndoe

Work Experience
Senior Data Scientist at TechCorp (2021-2024)
  - Built ML pipelines using Python, pandas, scikit-learn, and XGBoost
  - Deployed models to AWS SageMaker with Docker and Kubernetes
  - Implemented A/B testing frameworks; reduced churn by 18%
  - Used Apache Airflow for data pipeline orchestration
  - Worked with PostgreSQL, Redis, and Apache Spark for large-scale data

Education
MSc Computer Science, IIT Bombay (2019)

Skills
Python, SQL, TensorFlow, PyTorch, machine learning, deep learning, NLP
"""

ML_ENGINEER_RESUME = """
Priya Sharma
priya@example.com

Work Experience
Machine Learning Engineer, StartupXYZ (2022-2024)
  - Designed and deployed NLP models using PyTorch and HuggingFace transformers
  - Built MLOps pipelines with MLflow, Docker, Kubernetes
  - Used FastAPI for model serving; REST API design and gRPC

Education
BTech, BITS Pilani (2022)

Skills
Python, PyTorch, TensorFlow, Docker, Kubernetes, CI/CD, Linux, git
"""

JUNIOR_RESUME = """
Alex Kumar

Work Experience
Data Analyst Intern, DataCo (2023)
  - Created dashboards in Tableau and Power BI
  - Wrote SQL queries against PostgreSQL

Education
BSc Statistics (2023)

Skills
Python, SQL, pandas, Excel
"""


@pytest.fixture
def ds_resume():
    return DATA_SCIENCE_RESUME

@pytest.fixture
def ml_resume():
    return ML_ENGINEER_RESUME

@pytest.fixture
def junior_resume():
    return JUNIOR_RESUME
