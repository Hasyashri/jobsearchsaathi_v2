# JobSearchSaathi v2

**AI-powered resume gap analyser** — built to help newcomers, new graduates, and career changers understand *why* they are not getting interviews, and *exactly* what to fix.

---

## What it does

Upload your resume and a job description. JobSearchSaathi runs a 5-pass NLP pipeline, then gives you:

| Output | Description |
|--------|-------------|
| **Apply-Ready Verdict** | "Apply Now" / "Apply With Prep" / "Build First" — the one decision you actually need |
| **Skill Gap Analysis** | Every required and preferred skill you are missing, with free learning resources |
| **Certification Gaps** | Certs mentioned in the JD that are absent from your resume |
| **Experience Gap** | Years required vs years implied in your resume |
| **Resume Keyword Gaps** | ATS phrases in the JD not present in your resume |
| **Resume Quality Score** | Bullet-by-bullet analysis: impact signal, action verbs, vagueness |
| **Next Steps** | Prioritised action plan ranked by impact |

---

## Architecture

```
                        ┌─────────────────────────────────┐
                        │         React + Vite SPA         │
                        │  HomePage  ──►  ResultsPage      │
                        │  (dual file-blocks + mode toggle) │
                        └────────────┬────────────────────┘
                                     │ HTTP (form multipart)
                        ┌────────────▼────────────────────┐
                        │     FastAPI (ASGI, uvicorn)      │
                        │  POST /analyze/jd               │
                        │  POST /analyze  (template mode) │
                        │  GET  /roles  GET /services     │
                        └──────────────────────────────────┘
                                  │
          ┌───────────────────────┼────────────────────────────┐
          │                       │                            │
   ┌──────▼──────┐    ┌───────────▼────────────┐  ┌──────────▼────────┐
   │  resume_    │    │    5-pass NLP pipeline  │  │   jd_parser.py    │
   │  parser.py  │    │                        │  │  (skills / certs / │
   │  (PDF/DOCX/ │    │  Pass 1: alias match   │  │   exp / keywords)  │
   │   TXT)      │    │  Pass 2: fuzzy (RapidF) │  └──────────┬────────┘
   └─────────────┘    │  Pass 3: BERT NER      │             │
                      │  Pass 4: semantic SBERT │  ┌──────────▼────────┐
                      │  Pass 5: RAG / FAISS   │  │  jd_gap_analyzer  │
                      └───────────┬────────────┘  │  + apply verdict  │
                                  │               └──────────┬────────┘
                      ┌───────────▼────────────┐             │
                      │   resume_quality.py     │  ┌──────────▼────────┐
                      │   (bullet scoring)      │  │   llm_service.py  │
                      └────────────────────────┘  │   HuggingFace +   │
                                                   │   OpenAI fallback │
                                                   └───────────────────┘
```

---

## NLP Pipeline — why each pass exists

### Pass 1 — Alias matching (`skill_extractor.py`)
**Algorithm:** exact string match against a manually curated alias table.
**Why:** fastest and highest precision. "ML" → "machine learning", "k8s" → "kubernetes".
**Dataset used:** custom `skills_catalog.json` built from O*NET-SOC skill taxonomy.

> **Real dataset:** [O*NET Content Model — Knowledge, Skills, Abilities](https://www.onetcenter.org/database.html#individual-files)
> Download `Skills.txt` from the O*NET 28.0 database. Run `catalog_builder.py` to convert it.

---

### Pass 2 — Fuzzy matching (`fuzzy_extractor.py`)
**Algorithm:** RapidFuzz `token_sort_ratio` with a configurable threshold (default 82).
**Why:** catches typos, abbreviations, and partial matches that exact match misses.
`"pytorch"` vs `"pyTorch"`, `"react js"` vs `"reactjs"`.
**Why RapidFuzz over fuzzywuzzy:** 10–100× faster due to Levenshtein C extension; same API.

---

### Pass 3 — BERT NER (`ner_extractor.py`)
**Model:** `dslim/bert-base-NER` — fine-tuned on CoNLL-2003 for named entity recognition.
**Why this model:** CoNLL-2003 includes technology entity labels. It surfaces skill names
that appear in context ("worked with TensorFlow and Keras") without needing alias rules.
**Why lazy-load:** model is 440 MB; loaded on first request, cached in memory.

> **Model card:** https://huggingface.co/dslim/bert-base-NER

---

### Pass 4 — Semantic matching (`semantic_matcher.py`)
**Model:** `all-MiniLM-L6-v2` (sentence-transformers, 384-dim embeddings, 80 MB).
**Why this model:** best quality-to-speed ratio for semantic search at this scale.
Trained on 1B+ sentence pairs. Inference: ~5 ms per sentence on CPU.
Finds `"built data pipelines"` → detects `"apache airflow"` context.

> **Model card:** https://huggingface.co/sentence-transformers/all-MiniLM-L6-v2

---

### Pass 5 — RAG with FAISS (`rag_service.py`)
**Algorithm:** FAISS `IndexFlatIP` (inner product = cosine on L2-normalised vectors).
**Why FAISS over a vector DB:** in-process, zero network overhead, sub-millisecond search
at our scale (~200 skills). `IndexFlatIP` gives exact results — no approximation needed here.
**Why inner product instead of L2:** cosine similarity is scale-invariant; normalising once
and using dot product is faster than computing L2 distances at query time.
**How it works:** all skill names + aliases are embedded at startup and stored in FAISS.
At query time, each sentence from the JD is encoded and the top-k nearest skills are retrieved.

> **FAISS paper:** Johnson et al. (2017). *Billion-scale similarity search with GPUs*.
> https://arxiv.org/abs/1702.08734

---

## LLM Integration (`llm_service.py`)

**Primary:** HuggingFace Inference API — `google/flan-t5-large` (780M params)
**Fallback:** OpenAI GPT-3.5-turbo via `OPENAI_API_KEY`
**Fallback-of-fallback:** deterministic template strings (app always works, even offline)

**Why flan-t5-large:**
- Instruction-tuned on 1,800+ tasks (Flan dataset from Google Brain)
- Free HF Inference API tier — no credit card needed
- 3–5 s latency acceptable for a gap analysis tool
- Outperforms GPT-2 on structured output tasks by large margin

**Prompt design:**
- Role assignment: `"You are a career coach specialising in tech hiring."`
- Output constraint: `"Answer in exactly 2 sentences."`
- Chain-of-thought not used (flan-t5 responds better to direct instruction at this size)

> **Flan paper:** Chung et al. (2022). *Scaling Instruction-Finetuned Language Models*.
> https://arxiv.org/abs/2210.11416

---

## Resume Quality Analyser (`resume_quality.py`)

Scores each resume bullet on three signals:

| Signal | Weight | What it measures |
|--------|--------|-----------------|
| Impact | +0.40 | Numbers, %, $, scale words (10×, 50k users) |
| Action verb | +0.25 | Built, deployed, reduced, led, designed… |
| Tool mention | +0.20 | Technology names in the bullet |
| Vagueness | −0.30 | "worked on", "helped with", "responsible for" |

**Research basis:**
- Ladders eye-tracking study: recruiters spend 6 seconds per resume
- LinkedIn data: 47% of resumes rejected for lack of demonstrated impact
- Harvard OCS guidelines: every bullet should have Action + Task + Result

---

## Datasets

| Dataset | Use | Link |
|---------|-----|------|
| O*NET 28.0 Skills | Skills catalog (2,300+ canonical skills + aliases) | https://www.onetcenter.org/database.html |
| Kaggle Resume Dataset | Testing NER & fuzzy matching accuracy | https://www.kaggle.com/datasets/snehaanbhawal/resume-dataset |
| LinkedIn Job Postings (Kaggle) | JD parser validation | https://www.kaggle.com/datasets/arshkon/linkedin-job-postings |
| CoNLL-2003 | BERT NER training set (used by dslim model) | https://huggingface.co/datasets/conll2003 |
| SNLI + MultiNLI | MiniLM semantic model training (via SBERT) | https://nlp.stanford.edu/projects/snli/ |

---

## Tech Stack

| Layer | Technology | Why |
|-------|-----------|-----|
| Backend API | FastAPI + Pydantic v2 | Async, auto-docs, typed validation |
| NLP Pass 1-2 | RapidFuzz | 100× faster than fuzzywuzzy, C extension |
| NLP Pass 3 | HuggingFace Transformers (BERT) | Pre-trained NER, no labelling needed |
| NLP Pass 4 | sentence-transformers (SBERT) | Best CPU semantic similarity at 80 MB |
| NLP Pass 5 | FAISS | In-process vector search, sub-ms at 200 skills |
| LLM | HuggingFace Inference API + OpenAI | Free tier primary, paid fallback |
| Frontend | React 18 + Vite | Fast HMR, tree-shaking, modern JSX |
| Packaging | Docker + docker-compose | One-command deploy |
| File parsing | PyMuPDF (PDF) + python-docx | Best extraction quality for each format |

---

## How to run

### Option A — Docker (recommended)

```bash
git clone <repo>
cd jobsearchsaathi-v2

# Copy and fill in your API keys
cp .env.example .env
# Set: HF_TOKEN, OPENAI_API_KEY (optional)

docker-compose up --build
```

Open http://localhost:5173

---

### Option B — Local development

**Backend:**
```bash
cd backend
python -m venv venv
source venv/bin/activate          # Windows: venv\Scripts\activate
pip install -r requirements.txt

# On first run, generate the skills catalog:
curl -X POST http://localhost:8000/admin/rebuild-catalog

uvicorn app.main:app --reload --port 8000
```

**Frontend:**
```bash
cd frontend
npm install
npm run dev
```

Open http://localhost:5173

**Environment variables (backend `.env`):**

```env
HF_TOKEN=hf_xxxx              # HuggingFace token — get free at huggingface.co
OPENAI_API_KEY=sk-xxxx        # Optional — used as LLM fallback
HF_MODEL=google/flan-t5-large # Change to a different model if needed
USE_LLM=true                   # Set false to disable LLM (faster, no API calls)
MAX_FILE_SIZE_MB=5
```

---

## Apply-Ready verdict logic

| Required skill coverage | Verdict | Colour |
|------------------------|---------|--------|
| ≥ 70 % | Apply Now | Green |
| 40 – 69 % | Apply With Prep | Amber |
| < 40 % | Build First | Red |

The summary text is generated by the LLM using the score, missing required skills, job title, and candidate name.

---

## API reference

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/analyze/jd` | POST | Resume + JD → full gap analysis (primary endpoint) |
| `/analyze` | POST | Resume + role_id → template-based analysis |
| `/analyze/text` | POST | Plain text resume + role_id → analysis |
| `/roles` | GET | List all role templates |
| `/services` | GET | Learning resource catalog |
| `/admin/rebuild-catalog` | POST | Rebuild skills_catalog.json from CSV |
| `/health` | GET | Health check |
| `/docs` | GET | Interactive Swagger UI |

---

## Project structure

```
jobsearchsaathi-v2/
├── backend/
│   ├── app/
│   │   ├── main.py              # FastAPI app, ASGI lifespan
│   │   ├── config.py            # Settings via pydantic-settings
│   │   ├── schemas.py           # All Pydantic models
│   │   ├── routers/
│   │   │   ├── analyze.py       # /analyze  /analyze/jd  /analyze/text
│   │   │   ├── roles.py         # /roles
│   │   │   ├── services.py      # /services
│   │   │   ├── feedback.py      # /feedback
│   │   │   └── admin.py         # /admin/rebuild-catalog
│   │   └── services/
│   │       ├── resume_parser.py     # PDF/DOCX/TXT extraction, section detection
│   │       ├── skill_extractor.py   # Pass 1: alias matching
│   │       ├── fuzzy_extractor.py   # Pass 2: RapidFuzz
│   │       ├── ner_extractor.py     # Pass 3: BERT NER
│   │       ├── semantic_matcher.py  # Pass 4: SBERT
│   │       ├── rag_service.py       # Pass 5: FAISS RAG
│   │       ├── jd_parser.py         # JD skill/cert/exp/keyword extraction
│   │       ├── jd_gap_analyzer.py   # Gap analysis + apply verdict
│   │       ├── llm_service.py       # HuggingFace + OpenAI LLM
│   │       ├── resume_quality.py    # Bullet quality scoring
│   │       ├── readiness_engine.py  # Readiness score (template mode)
│   │       ├── recommendation.py    # Multi-role matching + career path
│   │       ├── pipeline.py          # Orchestrates all passes
│   │       └── catalog_builder.py   # Builds skills_catalog from CSV
│   ├── data/
│   │   ├── skills_catalog.json  # Auto-generated from O*NET CSV
│   │   ├── role_templates.json  # 20+ pre-built role templates
│   │   └── services_catalog.json
│   ├── tests/
│   └── requirements.txt
├── frontend/
│   ├── src/
│   │   ├── main.jsx             # React entry + navbar
│   │   ├── styles.css           # Light theme (navy/blue)
│   │   ├── pages/
│   │   │   ├── HomePage.jsx     # Dual-block input (resume + JD)
│   │   │   └── ResultsPage.jsx  # Verdict + 6 tabs of gap analysis
│   │   └── api/client.js        # fetch wrappers for all endpoints
│   └── vite.config.js
├── docker-compose.yml
├── .env.example
└── README.md
```

---

## Why JobSearchSaathi beats a simple keyword matcher

| Feature | Simple keyword match | JobSearchSaathi |
|---------|---------------------|-----------------|
| Detects "ML" = "machine learning" | ✗ | ✓ (alias) |
| Handles typos | ✗ | ✓ (fuzzy, threshold 82) |
| Extracts skills from sentences | ✗ | ✓ (BERT NER) |
| Understands context | ✗ | ✓ (SBERT semantic) |
| JD-aware retrieval | ✗ | ✓ (FAISS RAG) |
| LLM explanations | ✗ | ✓ (flan-t5 / GPT-3.5) |
| Resume bullet quality | ✗ | ✓ |
| Apply/Don't-apply verdict | ✗ | ✓ |
| Experience gap detection | ✗ | ✓ |
| ATS keyword gaps | ✗ | ✓ |
| Career path intelligence | ✗ | ✓ |

---

*Built as an AI/ML portfolio project targeting AI Engineer and ML Engineer roles in Canada.
All model choices are explained with citations; all datasets are publicly available.*
#   j o b s e a r c h s a a t h i _ v 2  
 