# JobSearchSaathi v2

**AI Career Readiness & Resume Gap Analyzer** — built to help newcomers, new graduates, and career changers understand why they are not getting interviews, whether they should apply now, and what they should improve first.

JobSearchSaathi analyzes a resume against either a target role or a real job description. It identifies skill gaps, certification gaps, experience gaps, ATS keyword gaps, and resume-quality issues, then returns an apply-ready verdict with practical next steps.

---

## Problem

Many job seekers apply to roles without knowing why they are not receiving interviews. The issue may be:

* Missing required skills
* Weak experience proof
* Missing certifications
* Poor ATS keyword alignment
* Resume bullets that describe tasks but do not prove impact
* Applying to roles beyond the candidate’s current level

JobSearchSaathi helps candidates stop applying blindly by showing what is missing and what to fix first.

---

## What It Does

Upload a resume and either select a target role or paste a job description. JobSearchSaathi runs a multi-pass NLP pipeline and returns a structured readiness report.

| Output                   | Description                                                                 |
| ------------------------ | --------------------------------------------------------------------------- |
| **Apply-Ready Verdict**  | “Apply Now”, “Apply With Prep”, or “Build First”                            |
| **Skill Gap Analysis**   | Required and preferred skills missing from the resume                       |
| **Certification Gaps**   | Certifications mentioned in the job description but not found in the resume |
| **Experience Gap**       | Years required by the job vs. experience implied from the resume            |
| **ATS Keyword Gaps**     | Important job-description phrases missing from the resume                   |
| **Resume Quality Score** | Bullet-level scoring for impact, action verbs, tool mentions, and vagueness |
| **Learning Resources**   | Free resources mapped to missing skills                                     |
| **Next Steps**           | Prioritized action plan ranked by impact                                    |
| **Alternative Roles**    | Related roles the candidate may be more ready for                           |

---

## Key Features

* Resume upload support for PDF, DOCX, and TXT
* Resume + target role analysis
* Resume + job description analysis
* FastAPI backend with typed Pydantic schemas
* React + Vite frontend
* Multi-pass skill extraction pipeline
* FAISS-based semantic retrieval for job-description skill discovery
* HuggingFace LLM integration with optional OpenAI fallback
* PII redaction before NLP processing
* Skill evidence, confidence scores, and low-confidence flags
* Resume-quality scoring for experience/project bullets
* Apply-ready verdict engine
* Docker and docker-compose support

---

## Architecture

```text
User
  |
  v
React + Vite Frontend
  - HomePage.jsx
  - ResultsPage.jsx
  - Resume upload
  - JD paste / role selection
  |
  | HTTP multipart/form-data
  v
FastAPI Backend
  - POST /analyze
  - POST /analyze/text
  - POST /analyze/jd
  - GET /roles
  - GET /services
  - POST /feedback
  - POST /admin/rebuild-catalog
  |
  v
Analysis Pipeline
  1. Resume parser
  2. PII redaction
  3. Section detection
  4. Alias matching
  5. Fuzzy matching
  6. BERT NER
  7. Semantic matching
  8. FAISS retrieval for JD skills
  9. JD gap analysis
  10. Resume quality scoring
  11. Apply-ready verdict
  |
  v
JSON Response
  - Readiness score
  - Skill gaps
  - Certification gaps
  - Experience gap
  - Keyword gaps
  - Resume quality
  - Next steps
```

---

## NLP Pipeline

JobSearchSaathi uses multiple extraction methods because no single technique catches all skill mentions in a resume.

### Pass 1 — Alias Matching

**File:** `skill_extractor.py`

Exact string and alias matching against the skills catalog.

Examples:

* `ML` → `machine learning`
* `k8s` → `kubernetes`
* `sklearn` → `scikit-learn`
* `tf` → `tensorflow`

Why it matters:

* Fast
* High precision
* Good for clearly listed skills
* Easy to explain and debug

---

### Pass 2 — Fuzzy Matching

**File:** `fuzzy_extractor.py`

Uses RapidFuzz-style matching to catch spelling differences, spacing issues, and minor typos.

Examples:

* `scikit learn` → `scikit-learn`
* `react js` → `react`
* `pyhton` → `python`

Why it matters:

* Resumes often contain inconsistent formatting
* Candidates may use alternate spellings
* Helps reduce false negatives

---

### Pass 3 — BERT NER

**File:** `ner_extractor.py`

Uses a HuggingFace NER model to detect named entities and maps them to catalog skills using SBERT similarity.

Current model:

```text
dslim/bert-base-NER
```

Important note:

This is a general-purpose NER model, not a skill-specific model. JobSearchSaathi uses it as a supplemental extraction pass only. The final skill must still map to the controlled skills catalog using similarity thresholds.

Why it matters:

* Helps detect multi-word technical phrases
* Useful when skills appear inside sentences
* Adds recall beyond keyword matching

---

### Pass 4 — Semantic Matching

**File:** `semantic_matcher.py`

Uses sentence embeddings to find skills described conceptually rather than directly named.

Model:

```text
sentence-transformers/all-MiniLM-L6-v2
```

Examples:

* “built data pipelines” may suggest data engineering skills
* “optimized database queries” may suggest SQL or database performance
* “created classification models” may suggest machine learning

Why it matters:

* Resumes do not always use exact skill names
* Semantic similarity improves coverage
* Confidence is capped lower because semantic matches are less certain than exact evidence

---

### Pass 5 — FAISS Retrieval for Job Descriptions

**File:** `rag_service.py`

The resume pipeline extracts skills from the candidate’s resume. The FAISS retrieval layer works in the other direction: it reads the job description and retrieves skills the JD implies.

How it works:

1. Job description text is split into sentences
2. Each sentence is embedded using SBERT
3. FAISS retrieves the nearest catalog skills
4. Missing retrieved skills become JD-aware gap candidates

Why FAISS:

* Runs locally in-process
* No external vector database required
* Fast for a small-to-medium skills catalog
* Good fit for a portfolio/demo application

---

## JD Gap Analysis

**File:** `jd_gap_analyzer.py`

When the user provides a real job description, the system analyzes four gap categories.

| Gap Category          | What It Checks                                                  |
| --------------------- | --------------------------------------------------------------- |
| **Skill Gap**         | Required and preferred skills in the JD not found in the resume |
| **Certification Gap** | Certifications mentioned in the JD but absent from the resume   |
| **Experience Gap**    | Required years of experience vs. resume-implied experience      |
| **Keyword Gap**       | ATS-style phrases from the JD missing in the resume             |

---

## Apply-Ready Verdict Logic

JobSearchSaathi gives a simple verdict instead of only showing a score.

| Required Skill Coverage | Verdict             | Meaning                                                |
| ----------------------- | ------------------- | ------------------------------------------------------ |
| `>= 70%`                | **Apply Now**       | Candidate is reasonably aligned and should apply       |
| `40% – 69%`             | **Apply With Prep** | Candidate can apply but should fix key gaps first      |
| `< 40%`                 | **Build First**     | Candidate should build skills/projects before applying |

The verdict is designed to help users decide whether to apply now, improve their resume, build proof, or target a more realistic role.

---

## LLM Integration

**File:** `llm_service.py`

JobSearchSaathi can use an LLM to generate short, human-friendly explanations.

Primary provider:

```text
HuggingFace Inference API
```

Optional fallback:

```text
OpenAI API
```

Offline fallback:

```text
Deterministic template strings
```

LLM tasks:

* Explain why a missing skill matters
* Generate a short apply-ready verdict message
* Rewrite weak resume bullets
* Convert technical gaps into plain-English next steps

The app is designed to degrade gracefully. If external APIs are unavailable, it still returns useful template-based output.

---

## Resume Quality Analyzer

**File:** `resume_quality.py`

The resume-quality module checks whether resume bullets demonstrate evidence, not just responsibilities.

| Signal       |  Weight | What It Looks For                                      |
| ------------ | ------: | ------------------------------------------------------ |
| Impact       | `+0.40` | Numbers, metrics, percentages, scale, results          |
| Action Verb  | `+0.25` | Built, deployed, reduced, trained, designed, automated |
| Tool Mention | `+0.20` | Python, SQL, FastAPI, Docker, TensorFlow, FAISS, etc.  |
| Vagueness    | `-0.30` | “worked on”, “helped with”, “responsible for”          |

Output labels:

* **Strong**
* **Fair**
* **Weak**

Each weak bullet receives a specific improvement suggestion.

---

## Data Sources

| Data Source                | Status             | Use                                   |
| -------------------------- | ------------------ | ------------------------------------- |
| `skills_catalog.json`      | Implemented        | Controlled skill names and aliases    |
| `role_templates.json`      | Implemented        | Template-based role matching          |
| `services_catalog.json`    | Implemented        | Learning resources for missing skills |
| `sample_cases.json`        | Implemented        | Testing and evaluation examples       |
| O*NET Skills Data          | Used / rebuildable | Source for expanding skills catalog   |
| HuggingFace model cards    | Indirect           | Pretrained model documentation        |
| Kaggle resume/job datasets | Optional / future  | Larger evaluation and validation      |

Important note:

Some datasets are used directly by the application, while others are used as references, pretrained-model sources, or future evaluation datasets.

---

## Tech Stack

| Layer           | Technology                                                       |
| --------------- | ---------------------------------------------------------------- |
| Backend         | Python 3.11, FastAPI, Pydantic                                   |
| Frontend        | React 18, Vite                                                   |
| NLP             | Regex, RapidFuzz, HuggingFace Transformers, SentenceTransformers |
| Semantic Search | FAISS                                                            |
| LLM             | HuggingFace Inference API, optional OpenAI fallback              |
| Data            | JSON catalogs, O*NET-based skills source                         |
| Deployment      | Docker, docker-compose, Nginx                                    |
| Testing         | Pytest                                                           |
| File Parsing    | PDF, DOCX, TXT parsing                                           |

---

## API Reference

| Endpoint                 | Method | Description                                |
| ------------------------ | ------ | ------------------------------------------ |
| `/analyze`               | POST   | Resume + role ID template analysis         |
| `/analyze/text`          | POST   | Plain-text resume + role ID analysis       |
| `/analyze/jd`            | POST   | Resume + job description full gap analysis |
| `/roles`                 | GET    | List available role templates              |
| `/roles/{role_id}`       | GET    | Get one role template                      |
| `/services`              | GET    | List learning resources                    |
| `/feedback`              | POST   | Submit skill correction feedback           |
| `/admin/rebuild-catalog` | POST   | Rebuild skills catalog                     |
| `/admin/catalog-stats`   | GET    | Return catalog statistics                  |
| `/health`                | GET    | Health check                               |
| `/docs`                  | GET    | Swagger API documentation                  |

---

## Project Structure

```text
jobsearchsaathi-v2/
├── backend/
│   ├── Dockerfile
│   ├── requirements.txt
│   └── app/
│       ├── main.py
│       ├── config.py
│       ├── logging_config.py
│       ├── schemas.py
│       ├── data/
│       │   ├── role_templates.json
│       │   ├── skills_catalog.json
│       │   ├── services_catalog.json
│       │   └── sample_cases.json
│       ├── routers/
│       │   ├── analyze.py
│       │   ├── roles.py
│       │   ├── services.py
│       │   ├── feedback.py
│       │   └── admin.py
│       ├── services/
│       │   ├── resume_parser.py
│       │   ├── skill_extractor.py
│       │   ├── fuzzy_extractor.py
│       │   ├── ner_extractor.py
│       │   ├── semantic_matcher.py
│       │   ├── rag_service.py
│       │   ├── jd_parser.py
│       │   ├── jd_gap_analyzer.py
│       │   ├── llm_service.py
│       │   ├── resume_quality.py
│       │   ├── readiness_engine.py
│       │   ├── recommendation_engine.py
│       │   ├── action_plan_engine.py
│       │   ├── pipeline.py
│       │   ├── catalog_builder.py
│       │   └── text_utils.py
│       └── tests/
│           ├── conftest.py
│           ├── test_api.py
│           └── test_services.py
├── frontend/
│   ├── Dockerfile
│   ├── index.html
│   ├── nginx.conf
│   ├── package.json
│   ├── vite.config.js
│   └── src/
│       ├── main.jsx
│       ├── styles.css
│       ├── api/
│       │   └── client.js
│       ├── pages/
│       │   ├── HomePage.jsx
│       │   └── ResultsPage.jsx
│       └── components/
│           ├── AltRoles.jsx
│           ├── CareerPath.jsx
│           ├── GapList.jsx
│           ├── ScoreGauge.jsx
│           └── SkillsGrid.jsx
├── docker-compose.yml
├── .gitignore
└── README.md
```

---

## How to Run

### Option 1 — Docker

```bash
git clone https://github.com/Hasyashri/jobsearchsaathi_v2.git
cd jobsearchsaathi_v2

docker-compose up --build
```

Then open:

```text
http://localhost
```

or, for local Vite development:

```text
http://localhost:5173
```

---

### Option 2 — Local Development

Backend:

```bash
cd backend
python -m venv venv

# Windows
venv\Scripts\activate

# macOS/Linux
source venv/bin/activate

pip install -r requirements.txt
uvicorn app.main:app --reload --port 8000
```

Frontend:

```bash
cd frontend
npm install
npm run dev
```

Open:

```text
http://localhost:5173
```

---

## Environment Variables

Create a `.env` file in the backend folder if using LLM features.

```env
HF_TOKEN=your_huggingface_token
OPENAI_API_KEY=your_openai_key_optional
HF_MODEL=google/flan-t5-large
USE_LLM=true
MAX_FILE_SIZE_MB=5
```

Do not commit `.env` to GitHub.

---

## Example Use Cases

### 1. New Graduate

A new graduate uploads a resume and a data analyst job description. JobSearchSaathi identifies missing SQL keywords, weak project bullets, and a lack of measurable results, then recommends resume improvements before applying.

### 2. Career Changer

A warehouse or customer-service worker wants to move into data analytics. JobSearchSaathi detects transferable skills but flags missing technical proof, suggesting Python/SQL projects and entry-level roles.

### 3. Newcomer

A newcomer to Canada uploads a resume for an AI or data role. The system identifies whether the resume lacks local proof, project evidence, or ATS-aligned keywords.

---

## Why It Is Different From a Keyword Matcher

| Feature                        | Simple Keyword Matcher | JobSearchSaathi |
| ------------------------------ | ---------------------: | --------------: |
| Alias matching                 |                     No |             Yes |
| Typo handling                  |                     No |             Yes |
| Resume section awareness       |                     No |             Yes |
| BERT NER extraction            |                     No |             Yes |
| Semantic matching              |                     No |             Yes |
| JD-aware retrieval             |                     No |             Yes |
| Evidence and confidence scores |                     No |             Yes |
| Apply-ready verdict            |                     No |             Yes |
| Certification gap detection    |                     No |             Yes |
| Experience gap detection       |                     No |             Yes |
| Resume quality scoring         |                     No |             Yes |
| Action plan generation         |                     No |             Yes |

---

## Current Status

Implemented:

* Resume upload and parsing
* Role-template analysis
* Job-description analysis
* Multi-pass skill extraction
* Readiness scoring
* Skill gap detection
* Certification, experience, and keyword gap logic
* Resume quality scoring
* Learning resource recommendations
* React frontend
* FastAPI backend
* Docker deployment
* Pytest test structure

In progress / future improvements:

* Larger evaluation dataset
* More role templates
* Stronger JD parsing
* User accounts and saved reports
* Database storage for feedback and analytics
* Model monitoring dashboard
* More advanced agentic workflows

---

## Evaluation Plan

The project includes sample cases for testing. Future evaluation will measure:

| Metric                     | Purpose                                                                  |
| -------------------------- | ------------------------------------------------------------------------ |
| Skill extraction precision | How many detected skills are correct                                     |
| Skill extraction recall    | How many true skills are found                                           |
| Gap precision              | Whether missing-skill recommendations are valid                          |
| Readiness verdict accuracy | Whether Apply Now / Apply With Prep / Build First matches human judgment |
| False positive skill rate  | Whether the system over-detects skills                                   |
| Resume quality agreement   | Whether bullet scores align with human review                            |

---

## Target Roles Demonstrated

This project demonstrates skills relevant to:

* AI Engineer
* Applied AI Engineer
* Machine Learning Engineer
* Data Analyst
* Full-Stack AI Developer
* NLP Engineer

It is especially aligned with AI job-search platforms because it works on resume understanding, job matching, skill gap analysis, LLM-generated explanations, and career-readiness recommendations.

---

## Author

**Hasyashri Bhatt**
Kitchener, Ontario, Canada
Email: [habhatt274@gmail.com](mailto:habhatt274@gmail.com)
GitHub: https://github.com/Hasyashri

---

## License

This project is for portfolio and educational use. Dataset licenses belong to their original providers. O*NET data is published by the U.S. Department of Labor under its own licensing terms.

---

## Repository

```text
https://github.com/Hasyashri/jobsearchsaathi_v2
```
