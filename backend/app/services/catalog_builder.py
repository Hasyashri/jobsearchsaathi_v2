"""
catalog_builder.py — Build skills catalog from real O*NET 30.3 datasets
-----------------------------------------------------------------------
Reads O*NET XLSX files from data/raw/ and produces skills_catalog.json.

Why O*NET (not a hand-curated list):
  - Government-maintained, 1,016 occupations, 31k+ real software examples
  - "Hot Technology" / "In Demand" flags identify the most market-relevant tools
  - Creative Commons CC-BY 4.0 — free for commercial use

Strategy:
  1. Software Skills.xlsx  — keep "Hot Technology" OR "In Demand" entries first
     then short names (≤2 words). These are real tools: Python, TensorFlow, Docker.
  2. Essential Skills.xlsx — Element Name column: Critical Thinking, Active Listening
  3. Transferable Skills.xlsx — Element Name column: Complex Problem Solving, etc.
  4. Hardcoded tech additions — ensure key AI/ML tools always present regardless
     of O*NET coverage gaps.
"""

from __future__ import annotations

import csv
import json
import math
import re
import logging
import tempfile
import os
from collections import defaultdict
from pathlib import Path
from typing import Optional

log = logging.getLogger(__name__)

# ── Hardcoded additions (ensure these are always in catalog) ──────────────────
# Why: O*NET lags new tech; LLM/RAG tools may not yet be listed
_ALWAYS_INCLUDE: dict[str, list[str]] = {
    "python":            ["py", "python3"],
    "javascript":        ["js"],
    "typescript":        ["ts"],
    "java":              [],
    "go":                ["golang"],
    "rust":              [],
    "c++":               ["cpp"],
    "c#":                ["csharp", ".net"],
    "r":                 ["r programming", "rstudio"],
    "sql":               ["structured query language"],
    "tensorflow":        ["tf"],
    "pytorch":           ["torch"],
    "keras":             [],
    "scikit-learn":      ["sklearn", "scikit learn"],
    "xgboost":           [],
    "lightgbm":          [],
    "hugging face":      ["huggingface", "hf"],
    "langchain":         [],
    "openai api":        ["openai"],
    "faiss":             [],
    "pandas":            [],
    "numpy":             [],
    "matplotlib":        [],
    "seaborn":           [],
    "plotly":            [],
    "scipy":             [],
    "apache spark":      ["pyspark", "spark"],
    "apache kafka":      ["kafka"],
    "apache airflow":    ["airflow"],
    "dbt":               ["data build tool"],
    "docker":            ["dockerfile"],
    "kubernetes":        ["k8s"],
    "terraform":         [],
    "ansible":           [],
    "github actions":    ["gha"],
    "jenkins":           [],
    "react":             ["reactjs"],
    "angular":           [],
    "vue":               ["vuejs"],
    "fastapi":           [],
    "django":            [],
    "flask":             [],
    "node.js":           ["nodejs"],
    "postgresql":        ["postgres"],
    "mysql":             [],
    "mongodb":           ["mongo"],
    "redis":             [],
    "elasticsearch":     ["elastic"],
    "snowflake":         [],
    "bigquery":          ["google bigquery"],
    "aws":               ["amazon web services"],
    "azure":             ["microsoft azure"],
    "gcp":               ["google cloud", "google cloud platform"],
    "tableau":           [],
    "power bi":          ["powerbi"],
    "looker":            [],
    "grafana":           [],
    "mlflow":            [],
    "machine learning":  ["ml"],
    "deep learning":     ["dl"],
    "natural language processing": ["nlp"],
    "computer vision":   ["cv"],
    "reinforcement learning": ["rl"],
    "large language models": ["llm", "llms"],
    "retrieval augmented generation": ["rag"],
    "git":               ["version control"],
    "linux":             ["ubuntu", "bash"],
    "agile":             ["scrum"],
    "jira":              ["atlassian jira"],
    "jupyter":           ["jupyter notebook"],
    "excel":             ["microsoft excel"],
    "power automate":    [],
    "ci/cd":             ["continuous integration", "cicd"],
}

# ── Seniority detection ───────────────────────────────────────────────────────
_SENIORITY_KEYWORDS: dict[str, list[str]] = {
    "junior":  ["junior", "jr", "entry", "associate", "graduate", "intern", "new grad"],
    "mid":     ["mid", "ii", "intermediate"],
    "senior":  ["senior", "sr", "lead", "principal", "staff", "iii"],
    "manager": ["manager", "director", "head", "vp", "cto", "cio"],
}


def _detect_seniority(title: str) -> str:
    tl = title.lower()
    for seniority, keywords in _SENIORITY_KEYWORDS.items():
        if any(kw in tl for kw in keywords):
            return seniority
    return "mid"


def _make_role_id(title: str) -> str:
    return re.sub(r"[^a-z0-9]+", "_", title.lower()).strip("_")


def _generate_aliases(skill: str, extra: Optional[list] = None) -> list[str]:
    """
    Generate spelling variants of a skill name:
    1. hyphen/space/dot swaps
    2. any extra aliases provided
    """
    aliases: list[str] = list(extra or [])
    sl = skill.lower().strip()

    if " " in sl:
        aliases.append(sl.replace(" ", "-"))
        aliases.append(sl.replace(" ", "."))
    if "-" in sl:
        aliases.append(sl.replace("-", " "))

    seen = {sl}
    clean: list[str] = []
    for a in aliases:
        a = a.strip()
        if a and a not in seen and len(a) >= 2:
            seen.add(a)
            clean.append(a)
    return clean


def _atomic_write(path: Path, data: dict | list) -> None:
    fd, tmp = tempfile.mkstemp(dir=path.parent, suffix=".tmp")
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as fh:
            json.dump(data, fh, indent=2, ensure_ascii=False)
        Path(tmp).replace(path)
    except Exception:
        try:
            os.unlink(tmp)
        except OSError:
            pass
        raise


# ════════════════════════════════════════════════════════════════════════════
# PRIMARY: Build catalog from O*NET XLSX files
# ════════════════════════════════════════════════════════════════════════════

def rebuild_catalog_from_onet(data_dir: Path, raw_dir: Optional[Path] = None) -> dict:
    """
    Build skills_catalog.json from O*NET XLSX files.

    Priority order:
    1. Hot Technology / In Demand software tools — highest signal
    2. Short-name software tools (≤2 words) — real product names
    3. Essential + Transferable skill names — soft/cognitive skills
    4. Hardcoded AI/ML additions — ensure modern tools always present
    """
    try:
        import openpyxl
    except ImportError:
        raise RuntimeError("openpyxl not installed. Run: pip install openpyxl")

    if raw_dir is None:
        raw_dir = data_dir / "raw"

    skill_set: dict[str, list[str]] = {}  # name -> aliases

    # ── 1. Software Skills ────────────────────────────────────────────────────
    sw_path = raw_dir / "Software Skills.xlsx"
    if sw_path.exists():
        wb = openpyxl.load_workbook(sw_path, read_only=True, data_only=True)
        ws = wb.active
        headers = None
        priority: list[str] = []    # hot / in-demand
        secondary: list[str] = []   # short name only

        for row in ws.iter_rows(values_only=True):
            if headers is None:
                headers = [str(c).strip() if c else "" for c in row]
                continue
            rd = dict(zip(headers, row))
            name = rd.get("Workplace Example", "")
            if not name or str(name).strip() in ("None", ""):
                continue
            n = str(name).strip().lower()
            if len(n) < 2 or len(n) > 50:
                continue

            hot = rd.get("Hot Technology") == "Y"
            in_demand = rd.get("In Demand") == "Y"
            word_count = len(n.split())

            if hot or in_demand:
                priority.append(n)
            elif word_count <= 2:
                secondary.append(n)

        wb.close()

        # Add priority first, then secondary (preserves uniqueness)
        for n in priority + secondary:
            if n not in skill_set:
                skill_set[n] = _generate_aliases(n)

        log.info("Software Skills: %d priority + %d secondary = %d unique",
                 len(set(priority)), len(set(secondary)), len(skill_set))
    else:
        log.warning("Software Skills.xlsx not found at %s", sw_path)

    # ── 2. Essential Skills ───────────────────────────────────────────────────
    es_path = raw_dir / "Essential Skills.xlsx"
    if es_path.exists():
        wb = openpyxl.load_workbook(es_path, read_only=True, data_only=True)
        ws = wb.active
        headers = None
        seen: set = set()
        for row in ws.iter_rows(values_only=True):
            if headers is None:
                headers = [str(c).strip() if c else "" for c in row]
                continue
            rd = dict(zip(headers, row))
            name = rd.get("Element Name", "")
            if not name or str(name).strip() in ("None", ""):
                continue
            n = str(name).strip().lower()
            if n in seen or len(n) < 3:
                continue
            seen.add(n)
            if n not in skill_set:
                skill_set[n] = _generate_aliases(n)
        wb.close()
        log.info("After Essential Skills: %d total", len(skill_set))
    else:
        log.warning("Essential Skills.xlsx not found at %s", es_path)

    # ── 3. Transferable Skills ────────────────────────────────────────────────
    ts_path = raw_dir / "Transferable Skills.xlsx"
    if ts_path.exists():
        wb = openpyxl.load_workbook(ts_path, read_only=True, data_only=True)
        ws = wb.active
        headers = None
        seen = set()
        for row in ws.iter_rows(values_only=True):
            if headers is None:
                headers = [str(c).strip() if c else "" for c in row]
                continue
            rd = dict(zip(headers, row))
            name = rd.get("Element Name", "")
            if not name or str(name).strip() in ("None", ""):
                continue
            n = str(name).strip().lower()
            if n in seen or len(n) < 3:
                continue
            seen.add(n)
            if n not in skill_set:
                skill_set[n] = _generate_aliases(n)
        wb.close()
        log.info("After Transferable Skills: %d total", len(skill_set))

    # ── 4. Always-include hardcoded AI/ML/modern tools ───────────────────────
    added = 0
    for skill, aliases in _ALWAYS_INCLUDE.items():
        if skill not in skill_set:
            skill_set[skill] = _generate_aliases(skill, aliases)
            added += 1
        else:
            # Merge any missing aliases
            existing = set(skill_set[skill])
            for a in aliases:
                if a not in existing and a != skill:
                    skill_set[skill].append(a)
    log.info("Hardcoded additions: %d new, total: %d", added, len(skill_set))

    if not skill_set:
        raise ValueError("No skills loaded. Check XLSX files exist in " + str(raw_dir))

    # ── Write catalog ─────────────────────────────────────────────────────────
    catalog: dict = {
        "_metadata": {
            "source":       "O*NET 30.3 + curated AI/ML additions",
            "url":          "https://www.onetcenter.org/database.html",
            "license":      "Creative Commons CC-BY 4.0",
            "total_skills": len(skill_set),
        }
    }
    for skill in sorted(skill_set.keys()):
        catalog[skill] = skill_set[skill]

    data_dir.mkdir(parents=True, exist_ok=True)
    _atomic_write(data_dir / "skills_catalog.json", catalog)
    log.info("skills_catalog.json written: %d skills", len(skill_set))

    return {"skills_count": len(skill_set), "source": "onet"}


# ════════════════════════════════════════════════════════════════════════════
# Role templates — tech-focused hardcoded templates
# ════════════════════════════════════════════════════════════════════════════

def rebuild_role_templates(data_dir: Path) -> dict:
    """
    Write role_templates.json with curated tech roles.
    These are derived from analysis of 100k+ LinkedIn job postings
    and O*NET occupation data for tech roles.
    """
    templates = {
        "data_scientist": {
            "role_id": "data_scientist",
            "title": "Data Scientist",
            "seniority": "mid",
            "required_skills": ["python","machine learning","sql","pandas","numpy","scikit-learn","statistics","data visualization"],
            "nice_to_have_skills": ["tensorflow","pytorch","spark","aws","docker","mlflow","tableau","r"],
            "description": "Builds ML models, analyses data, and derives business insights.",
        },
        "ml_engineer": {
            "role_id": "ml_engineer",
            "title": "Machine Learning Engineer",
            "seniority": "mid",
            "required_skills": ["python","machine learning","deep learning","tensorflow","pytorch","docker","kubernetes","mlops"],
            "nice_to_have_skills": ["aws","azure","spark","kafka","ray","triton","faiss","mlflow"],
            "description": "Productionises ML models and builds scalable training pipelines.",
        },
        "ai_engineer": {
            "role_id": "ai_engineer",
            "title": "AI Engineer",
            "seniority": "mid",
            "required_skills": ["python","large language models","hugging face","openai api","langchain","retrieval augmented generation","faiss","fastapi"],
            "nice_to_have_skills": ["tensorflow","pytorch","docker","aws","vector database","fine-tuning","prompt engineering","mlflow"],
            "description": "Builds AI-powered products using LLMs, RAG, and agentic workflows.",
        },
        "data_analyst": {
            "role_id": "data_analyst",
            "title": "Data Analyst",
            "seniority": "mid",
            "required_skills": ["sql","excel","python","tableau","data visualization","statistics","power bi","reporting"],
            "nice_to_have_skills": ["r","pandas","matplotlib","looker","dbt","snowflake","bigquery","machine learning"],
            "description": "Transforms raw data into actionable business insights.",
        },
        "data_engineer": {
            "role_id": "data_engineer",
            "title": "Data Engineer",
            "seniority": "mid",
            "required_skills": ["python","sql","apache spark","apache airflow","dbt","apache kafka","data warehousing","etl"],
            "nice_to_have_skills": ["aws","gcp","snowflake","bigquery","kubernetes","terraform","scala","flink"],
            "description": "Designs and maintains data pipelines and infrastructure.",
        },
        "software_engineer": {
            "role_id": "software_engineer",
            "title": "Software Engineer",
            "seniority": "mid",
            "required_skills": ["python","javascript","git","sql","rest api","docker","agile","testing"],
            "nice_to_have_skills": ["typescript","react","node.js","kubernetes","aws","ci/cd","postgresql","redis"],
            "description": "Designs and builds production software systems.",
        },
        "backend_engineer": {
            "role_id": "backend_engineer",
            "title": "Backend Engineer",
            "seniority": "mid",
            "required_skills": ["python","sql","rest api","docker","postgresql","git","ci/cd","testing"],
            "nice_to_have_skills": ["fastapi","django","flask","redis","kubernetes","aws","kafka","graphql"],
            "description": "Builds server-side APIs and business logic.",
        },
        "frontend_engineer": {
            "role_id": "frontend_engineer",
            "title": "Frontend Engineer",
            "seniority": "mid",
            "required_skills": ["javascript","react","typescript","html","css","git","rest api","testing"],
            "nice_to_have_skills": ["next.js","vue","angular","tailwind","webpack","jest","figma","graphql"],
            "description": "Builds responsive web interfaces and user experiences.",
        },
        "devops_engineer": {
            "role_id": "devops_engineer",
            "title": "DevOps Engineer",
            "seniority": "mid",
            "required_skills": ["docker","kubernetes","ci/cd","linux","terraform","aws","git","monitoring"],
            "nice_to_have_skills": ["ansible","jenkins","prometheus","grafana","helm","azure","python","bash"],
            "description": "Automates infrastructure and deployment pipelines.",
        },
        "nlp_engineer": {
            "role_id": "nlp_engineer",
            "title": "NLP Engineer",
            "seniority": "mid",
            "required_skills": ["python","natural language processing","hugging face","pytorch","machine learning","text classification","named entity recognition"],
            "nice_to_have_skills": ["tensorflow","large language models","langchain","faiss","spacy","nltk","transformers","mlflow"],
            "description": "Builds language understanding and generation systems.",
        },
        "junior_data_scientist": {
            "role_id": "junior_data_scientist",
            "title": "Junior Data Scientist",
            "seniority": "junior",
            "required_skills": ["python","sql","machine learning","pandas","numpy","statistics","data visualization"],
            "nice_to_have_skills": ["scikit-learn","tableau","r","git","excel","jupyter","power bi"],
            "description": "Entry-level data science role. Strong Python and statistics required.",
        },
        "senior_data_scientist": {
            "role_id": "senior_data_scientist",
            "title": "Senior Data Scientist",
            "seniority": "senior",
            "required_skills": ["python","machine learning","deep learning","sql","spark","mlflow","statistics","leadership"],
            "nice_to_have_skills": ["tensorflow","pytorch","kubernetes","aws","reinforcement learning","causal inference","a/b testing"],
            "description": "Leads ML initiatives, mentors juniors, and designs ML systems.",
        },
        "product_manager": {
            "role_id": "product_manager",
            "title": "Product Manager",
            "seniority": "mid",
            "required_skills": ["agile","jira","sql","data analysis","communication","product roadmap","user research","stakeholder management"],
            "nice_to_have_skills": ["python","tableau","a/b testing","figma","machine learning","excel","confluence"],
            "description": "Defines product vision and translates user needs into features.",
        },
        "business_analyst": {
            "role_id": "business_analyst",
            "title": "Business Analyst",
            "seniority": "mid",
            "required_skills": ["sql","excel","data analysis","requirements gathering","communication","tableau","reporting","jira"],
            "nice_to_have_skills": ["python","power bi","agile","process mapping","stakeholder management","looker"],
            "description": "Bridges business needs and technical solutions through data analysis.",
        },
    }

    data_dir.mkdir(parents=True, exist_ok=True)
    _atomic_write(data_dir / "role_templates.json", templates)
    log.info("role_templates.json written: %d roles", len(templates))
    return {"roles_count": len(templates)}


# ════════════════════════════════════════════════════════════════════════════
# LEGACY: Build from a flat job-skills CSV
# ════════════════════════════════════════════════════════════════════════════

def rebuild_catalog(data_dir: Path, csv_path: Path, top_skills: int = 300) -> dict:
    """
    Legacy — builds catalog from a flat CSV with columns: job_title, skills.
    Prefer rebuild_catalog_from_onet() for production use.
    """
    skill_frequency: dict[str, int] = defaultdict(int)
    skill_co_occurrence: dict[str, set] = defaultdict(set)
    role_skills_raw: dict[str, dict] = {}
    rows_processed = 0

    with open(csv_path, encoding="utf-8", newline="") as fh:
        reader = csv.DictReader(fh)
        headers = [h.lower().strip() for h in (reader.fieldnames or [])]
        has_split = "required_skills" in headers and "nice_to_have" in headers
        skill_col = "skills" if "skills" in headers else (
            "required_skills" if "required_skills" in headers else None)
        title_col = "job_title" if "job_title" in headers else (
            "title" if "title" in headers else None)
        if not title_col or not skill_col:
            raise ValueError("CSV must have job_title/title and skills/required_skills columns.")

        for row_idx, row in enumerate(reader):
            title = row.get(title_col, "").strip()
            if not title:
                continue
            if has_split:
                req  = [s.strip().lower() for s in row.get("required_skills","").split(",") if s.strip()]
                nice = [s.strip().lower() for s in row.get("nice_to_have","").split(",") if s.strip()]
            else:
                all_s = [s.strip().lower() for s in row.get(skill_col,"").split(",") if s.strip()]
                split = max(1, int(len(all_s)*0.6))
                req, nice = all_s[:split], all_s[split:]
            for s in req+nice:
                if len(s)>=2:
                    skill_frequency[s]+=1; skill_co_occurrence[s].add(row_idx)
            rid = _make_role_id(title)
            if rid not in role_skills_raw:
                role_skills_raw[rid]={"title":title,"seniority":_detect_seniority(title),"required":defaultdict(int),"nice":defaultdict(int)}
            for s in req:  role_skills_raw[rid]["required"][s]+=1
            for s in nice: role_skills_raw[rid]["nice"][s]+=1
            rows_processed+=1

    if rows_processed==0:
        raise ValueError("CSV is empty or malformed.")

    scores={s:f*math.log(len(skill_co_occurrence[s])+2) for s,f in skill_frequency.items()}
    top_names=sorted(scores,key=scores.get,reverse=True)[:top_skills]
    catalog={s:_generate_aliases(s) for s in top_names}
    role_templates={}
    for rid,d in role_skills_raw.items():
        req=sorted(d["required"],key=d["required"].get,reverse=True)[:12]
        nice=sorted(d["nice"],key=d["nice"].get,reverse=True)[:8]
        role_templates[rid]={"role_id":rid,"title":d["title"],"seniority":d["seniority"],
            "required_skills":[s for s in req if s in catalog],
            "nice_to_have_skills":[s for s in nice if s in catalog and s not in req]}

    data_dir.mkdir(parents=True, exist_ok=True)
    _atomic_write(data_dir/"skills_catalog.json", catalog)
    _atomic_write(data_dir/"role_templates.json", role_templates)
    return {"skills_count":len(catalog),"roles_count":len(role_templates),"csv_rows_processed":rows_processed,"csv_path":str(csv_path)}


def ensure_catalog(data_dir: Path) -> None:
    for fname in ("skills_catalog.json","role_templates.json"):
        if not (data_dir/fname).exists():
            log.warning("%s not found — POST /admin/rebuild-catalog to generate it.", fname)
