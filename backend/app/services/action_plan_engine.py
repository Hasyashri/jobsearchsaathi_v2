"""
action_plan_engine.py
---------------------
Given skill gaps and an experience gap, produces a structured action plan:

  1. For each SKILL GAP  → top certifications + free courses with direct links
  2. For EXPERIENCE GAP  → entry-level job search links + volunteer platforms
  3. Always             → resume improvement tips personalised to the gap report
"""
from __future__ import annotations
from dataclasses import dataclass, field
import urllib.parse

# ─────────────────────────────────────────────────────────────────────────────
# 1. CERTIFICATION CATALOGUE
#    skill_name (lowercase) -> list of certifications
# ─────────────────────────────────────────────────────────────────────────────
_CERTS: dict[str, list[dict]] = {
    # Cloud
    "aws": [
        {"name": "AWS Certified Cloud Practitioner", "provider": "Amazon", "level": "Beginner",
         "url": "https://aws.amazon.com/certification/certified-cloud-practitioner/", "free_prep": "https://skillbuilder.aws/learn/course/134/play/31418/aws-cloud-practitioner-essentials"},
        {"name": "AWS Certified Solutions Architect – Associate", "provider": "Amazon", "level": "Intermediate",
         "url": "https://aws.amazon.com/certification/certified-solutions-architect-associate/", "free_prep": "https://skillbuilder.aws"},
    ],
    "azure": [
        {"name": "Microsoft Azure Fundamentals (AZ-900)", "provider": "Microsoft", "level": "Beginner",
         "url": "https://learn.microsoft.com/en-us/certifications/azure-fundamentals/", "free_prep": "https://learn.microsoft.com/en-us/training/paths/az-900-describe-cloud-concepts/"},
        {"name": "Azure AI Fundamentals (AI-900)", "provider": "Microsoft", "level": "Beginner",
         "url": "https://learn.microsoft.com/en-us/certifications/azure-ai-fundamentals/", "free_prep": "https://learn.microsoft.com/en-us/training/paths/get-started-with-artificial-intelligence-on-azure/"},
    ],
    "google cloud": [
        {"name": "Google Cloud Associate Cloud Engineer", "provider": "Google", "level": "Intermediate",
         "url": "https://cloud.google.com/certification/cloud-engineer", "free_prep": "https://cloud.google.com/training/free-tier"},
        {"name": "Google Professional ML Engineer", "provider": "Google", "level": "Advanced",
         "url": "https://cloud.google.com/certification/machine-learning-engineer", "free_prep": "https://cloud.google.com/training/machinelearning-ai"},
    ],
    "gcp": [
        {"name": "Google Cloud Associate Cloud Engineer", "provider": "Google", "level": "Intermediate",
         "url": "https://cloud.google.com/certification/cloud-engineer", "free_prep": "https://cloud.google.com/training/free-tier"},
    ],
    # ML / AI
    "machine learning": [
        {"name": "Machine Learning Specialization (Coursera)", "provider": "DeepLearning.AI / Stanford", "level": "Beginner",
         "url": "https://www.coursera.org/specializations/machine-learning-introduction", "free_prep": "https://www.coursera.org/specializations/machine-learning-introduction"},
        {"name": "Google ML Crash Course", "provider": "Google", "level": "Beginner",
         "url": "https://developers.google.com/machine-learning/crash-course", "free_prep": "https://developers.google.com/machine-learning/crash-course"},
    ],
    "deep learning": [
        {"name": "Deep Learning Specialization (Coursera)", "provider": "DeepLearning.AI", "level": "Intermediate",
         "url": "https://www.coursera.org/specializations/deep-learning", "free_prep": "https://www.coursera.org/specializations/deep-learning"},
        {"name": "fast.ai Practical Deep Learning", "provider": "fast.ai", "level": "Intermediate",
         "url": "https://course.fast.ai", "free_prep": "https://course.fast.ai"},
    ],
    "tensorflow": [
        {"name": "TensorFlow Developer Certificate", "provider": "Google", "level": "Intermediate",
         "url": "https://www.tensorflow.org/certificate", "free_prep": "https://www.tensorflow.org/tutorials"},
        {"name": "DeepLearning.AI TensorFlow Developer (Coursera)", "provider": "DeepLearning.AI", "level": "Intermediate",
         "url": "https://www.coursera.org/professional-certificates/tensorflow-in-practice", "free_prep": "https://www.coursera.org/professional-certificates/tensorflow-in-practice"},
    ],
    "pytorch": [
        {"name": "PyTorch for Deep Learning Bootcamp (Udemy)", "provider": "Udemy", "level": "Intermediate",
         "url": "https://www.udemy.com/course/pytorch-for-deep-learning/", "free_prep": "https://pytorch.org/tutorials/"},
        {"name": "fast.ai Practical Deep Learning", "provider": "fast.ai", "level": "Intermediate",
         "url": "https://course.fast.ai", "free_prep": "https://course.fast.ai"},
    ],
    "natural language processing": [
        {"name": "NLP Specialization (Coursera)", "provider": "DeepLearning.AI", "level": "Intermediate",
         "url": "https://www.coursera.org/specializations/natural-language-processing", "free_prep": "https://www.coursera.org/specializations/natural-language-processing"},
        {"name": "HuggingFace NLP Course", "provider": "HuggingFace", "level": "Intermediate",
         "url": "https://huggingface.co/learn/nlp-course/chapter1/1", "free_prep": "https://huggingface.co/learn/nlp-course/chapter1/1"},
    ],
    "large language models": [
        {"name": "LLMOps: Building Real-World Applications (Coursera)", "provider": "DeepLearning.AI", "level": "Intermediate",
         "url": "https://www.coursera.org/learn/llmops", "free_prep": "https://www.deeplearning.ai/short-courses/"},
        {"name": "Building LLM Apps (DeepLearning.AI short course)", "provider": "DeepLearning.AI", "level": "Beginner",
         "url": "https://www.deeplearning.ai/short-courses/building-systems-with-chatgpt/", "free_prep": "https://www.deeplearning.ai/short-courses/"},
    ],
    # Data
    "python": [
        {"name": "Python for Everybody Specialization (Coursera)", "provider": "University of Michigan", "level": "Beginner",
         "url": "https://www.coursera.org/specializations/python", "free_prep": "https://www.coursera.org/specializations/python"},
        {"name": "PCEP – Certified Entry-Level Python Programmer", "provider": "Python Institute", "level": "Beginner",
         "url": "https://pythoninstitute.org/pcep", "free_prep": "https://edube.org/study/pe1"},
    ],
    "sql": [
        {"name": "Google Data Analytics Certificate (Coursera)", "provider": "Google", "level": "Beginner",
         "url": "https://www.coursera.org/professional-certificates/google-data-analytics", "free_prep": "https://www.coursera.org/professional-certificates/google-data-analytics"},
        {"name": "Mode SQL Tutorial", "provider": "Mode", "level": "Beginner",
         "url": "https://mode.com/sql-tutorial/", "free_prep": "https://mode.com/sql-tutorial/"},
    ],
    "data science": [
        {"name": "IBM Data Science Professional Certificate (Coursera)", "provider": "IBM", "level": "Beginner",
         "url": "https://www.coursera.org/professional-certificates/ibm-data-science", "free_prep": "https://www.coursera.org/professional-certificates/ibm-data-science"},
        {"name": "Google Advanced Data Analytics Certificate", "provider": "Google", "level": "Intermediate",
         "url": "https://www.coursera.org/professional-certificates/google-advanced-data-analytics", "free_prep": "https://www.coursera.org/professional-certificates/google-advanced-data-analytics"},
    ],
    "tableau": [
        {"name": "Tableau Desktop Specialist", "provider": "Tableau / Salesforce", "level": "Beginner",
         "url": "https://www.tableau.com/learn/certification/desktop-specialist", "free_prep": "https://www.tableau.com/learn/training/elearning"},
    ],
    "power bi": [
        {"name": "PL-300: Microsoft Power BI Data Analyst", "provider": "Microsoft", "level": "Intermediate",
         "url": "https://learn.microsoft.com/en-us/certifications/power-bi-data-analyst-associate/", "free_prep": "https://learn.microsoft.com/en-us/training/courses/pl-300t00"},
    ],
    # DevOps / Infra
    "docker": [
        {"name": "Docker Foundations Professional Certificate (LinkedIn)", "provider": "LinkedIn Learning", "level": "Beginner",
         "url": "https://www.linkedin.com/learning/paths/docker-foundations-professional-certificate", "free_prep": "https://docs.docker.com/get-started/"},
    ],
    "kubernetes": [
        {"name": "Certified Kubernetes Administrator (CKA)", "provider": "CNCF / Linux Foundation", "level": "Advanced",
         "url": "https://training.linuxfoundation.org/certification/certified-kubernetes-administrator-cka/", "free_prep": "https://kubernetes.io/docs/tutorials/kubernetes-basics/"},
        {"name": "Certified Kubernetes Application Developer (CKAD)", "provider": "CNCF / Linux Foundation", "level": "Intermediate",
         "url": "https://training.linuxfoundation.org/certification/certified-kubernetes-application-developer-ckad-2/", "free_prep": "https://kubernetes.io/docs/tutorials/"},
    ],
    "terraform": [
        {"name": "HashiCorp Certified: Terraform Associate", "provider": "HashiCorp", "level": "Intermediate",
         "url": "https://developer.hashicorp.com/certifications/infrastructure-automation", "free_prep": "https://developer.hashicorp.com/terraform/tutorials"},
    ],
    # Project management
    "project management": [
        {"name": "Google Project Management Certificate (Coursera)", "provider": "Google", "level": "Beginner",
         "url": "https://www.coursera.org/professional-certificates/google-project-management", "free_prep": "https://www.coursera.org/professional-certificates/google-project-management"},
        {"name": "PMP – Project Management Professional", "provider": "PMI", "level": "Advanced",
         "url": "https://www.pmi.org/certifications/project-management-pmp", "free_prep": "https://www.pmi.org/certifications/project-management-pmp"},
    ],
    "agile": [
        {"name": "Professional Scrum Master I (PSM I)", "provider": "Scrum.org", "level": "Beginner",
         "url": "https://www.scrum.org/assessments/professional-scrum-master-i-certification", "free_prep": "https://www.scrum.org/open-assessments/scrum-open"},
        {"name": "Certified ScrumMaster (CSM)", "provider": "Scrum Alliance", "level": "Beginner",
         "url": "https://www.scrumalliance.org/get-certified/scrum-master-track/certified-scrummaster", "free_prep": "https://www.scrumalliance.org/get-certified"},
    ],
    # Security
    "cybersecurity": [
        {"name": "CompTIA Security+", "provider": "CompTIA", "level": "Beginner",
         "url": "https://www.comptia.org/certifications/security", "free_prep": "https://www.professormesser.com/security-plus/sy0-701/sy0-701-video/sy0-701-free-course/"},
        {"name": "Google Cybersecurity Certificate (Coursera)", "provider": "Google", "level": "Beginner",
         "url": "https://www.coursera.org/professional-certificates/google-cybersecurity", "free_prep": "https://www.coursera.org/professional-certificates/google-cybersecurity"},
    ],
    # LangChain / AI Engineering
    "langchain": [
        {"name": "LangChain for LLM Application Development (DeepLearning.AI)", "provider": "DeepLearning.AI", "level": "Beginner",
         "url": "https://www.deeplearning.ai/short-courses/langchain-for-llm-application-development/", "free_prep": "https://www.deeplearning.ai/short-courses/langchain-for-llm-application-development/"},
        {"name": "Functions, Tools and Agents with LangChain", "provider": "DeepLearning.AI", "level": "Intermediate",
         "url": "https://www.deeplearning.ai/short-courses/functions-tools-agents-langchain/", "free_prep": "https://www.deeplearning.ai/short-courses/functions-tools-agents-langchain/"},
    ],
    "hugging face": [
        {"name": "HuggingFace NLP Course (free)", "provider": "HuggingFace", "level": "Beginner",
         "url": "https://huggingface.co/learn/nlp-course", "free_prep": "https://huggingface.co/learn/nlp-course"},
        {"name": "Open-Source AI Cookbook", "provider": "HuggingFace", "level": "Intermediate",
         "url": "https://huggingface.co/learn/cookbook", "free_prep": "https://huggingface.co/learn/cookbook"},
    ],
    "react": [
        {"name": "Meta Front-End Developer Certificate (Coursera)", "provider": "Meta", "level": "Beginner",
         "url": "https://www.coursera.org/professional-certificates/meta-front-end-developer", "free_prep": "https://react.dev/learn"},
    ],
    "fastapi": [
        {"name": "FastAPI Full Course (freeCodeCamp, YouTube)", "provider": "freeCodeCamp", "level": "Beginner",
         "url": "https://www.youtube.com/watch?v=0sOvCWFmrtA", "free_prep": "https://fastapi.tiangolo.com/tutorial/"},
    ],
}

# ─────────────────────────────────────────────────────────────────────────────
# 2. FREE COURSE CATALOGUE  (broader — for skills without a specific cert)
# ─────────────────────────────────────────────────────────────────────────────
_COURSES: dict[str, list[dict]] = {
    "python":            [{"name": "Python for Everybody (Coursera — free audit)", "url": "https://www.coursera.org/specializations/python", "provider": "University of Michigan", "free": True}],
    "sql":               [{"name": "SQLZoo Interactive Tutorials", "url": "https://sqlzoo.net", "provider": "SQLZoo", "free": True},
                          {"name": "W3Schools SQL Tutorial", "url": "https://www.w3schools.com/sql/", "provider": "W3Schools", "free": True}],
    "machine learning":  [{"name": "Google ML Crash Course", "url": "https://developers.google.com/machine-learning/crash-course", "provider": "Google", "free": True},
                          {"name": "fast.ai Practical Deep Learning", "url": "https://course.fast.ai", "provider": "fast.ai", "free": True}],
    "deep learning":     [{"name": "fast.ai Practical Deep Learning", "url": "https://course.fast.ai", "provider": "fast.ai", "free": True}],
    "tensorflow":        [{"name": "TensorFlow Tutorials", "url": "https://www.tensorflow.org/tutorials", "provider": "Google", "free": True}],
    "pytorch":           [{"name": "PyTorch Official Tutorials", "url": "https://pytorch.org/tutorials/", "provider": "Meta", "free": True}],
    "docker":            [{"name": "Docker Getting Started", "url": "https://docs.docker.com/get-started/", "provider": "Docker", "free": True}],
    "kubernetes":        [{"name": "Kubernetes Basics (k8s.io)", "url": "https://kubernetes.io/docs/tutorials/kubernetes-basics/", "provider": "CNCF", "free": True}],
    "aws":               [{"name": "AWS Skill Builder Free Tier", "url": "https://skillbuilder.aws", "provider": "Amazon", "free": True}],
    "react":             [{"name": "React Official Docs (react.dev)", "url": "https://react.dev/learn", "provider": "Meta", "free": True}],
    "langchain":         [{"name": "LangChain Python Docs", "url": "https://python.langchain.com/docs/get_started/introduction", "provider": "LangChain", "free": True}],
    "hugging face":      [{"name": "HuggingFace NLP Course", "url": "https://huggingface.co/learn/nlp-course/chapter1/1", "provider": "HuggingFace", "free": True}],
    "large language models": [{"name": "DeepLearning.AI Short Courses (free)", "url": "https://www.deeplearning.ai/short-courses/", "provider": "DeepLearning.AI", "free": True}],
    "git":               [{"name": "Pro Git Book (free)", "url": "https://git-scm.com/book/en/v2", "provider": "Git SCM", "free": True}],
    "data science":      [{"name": "Kaggle Learn (free)", "url": "https://www.kaggle.com/learn", "provider": "Kaggle", "free": True}],
}

# ─────────────────────────────────────────────────────────────────────────────
# 3. JOB SEARCH PLATFORMS  (entry-level + volunteer)
# ─────────────────────────────────────────────────────────────────────────────
_JOB_PLATFORMS = [
    {"name": "LinkedIn Jobs (entry-level filter)",
     "description": "Filter by Experience Level → Entry Level. Best for tech and professional roles in Canada.",
     "search_url_template": "https://www.linkedin.com/jobs/search/?keywords={query}&location=Canada&f_E=2",
     "icon": "linkedin"},
    {"name": "Indeed Canada",
     "description": "Largest job board. Use '0-1 years experience' in the search filters.",
     "search_url_template": "https://ca.indeed.com/jobs?q={query}+entry+level&l=Canada",
     "icon": "indeed"},
    {"name": "Wellfound (AngelList) — Startups",
     "description": "Best for AI/ML startup jobs. Many explicitly hire new grads and career changers.",
     "search_url_template": "https://wellfound.com/jobs?q={query}&role=engineer",
     "icon": "wellfound"},
    {"name": "Jobright.ai",
     "description": "AI-powered job matching — the company you are applying to. Uses AI to match your profile.",
     "search_url_template": "https://jobright.ai/jobs/{query}-jobs-in-united-states",
     "icon": "jobright"},
    {"name": "Glassdoor (Canada)",
     "description": "See salary ranges alongside job postings. Filter by 'Entry Level'.",
     "search_url_template": "https://www.glassdoor.ca/Job/canada-{query}-jobs-SRCH_IL.0,6_IN3_KO7,{qlen}.htm",
     "icon": "glassdoor"},
]

_VOLUNTEER_PLATFORMS = [
    {"name": "Catchafire",
     "description": "Pro bono skills volunteering for nonprofits. Match your tech skills to real projects. Builds portfolio and Canadian references fast.",
     "url": "https://www.catchafire.org",
     "best_for": "Data science, web dev, ML, content strategy"},
    {"name": "VolunteerMatch",
     "description": "Large volunteer database. Search by skill. Many tech-focused nonprofits need data and dev help.",
     "url": "https://www.volunteermatch.org",
     "best_for": "General tech skills, project management"},
    {"name": "Idealist",
     "description": "Tech volunteer and internship postings at nonprofits and social impact orgs.",
     "url": "https://www.idealist.org",
     "best_for": "Tech roles at mission-driven organizations"},
    {"name": "Statistics Canada Open Data Challenges",
     "description": "Government data challenges — real datasets, build portfolio projects with public sector data.",
     "url": "https://www.statcan.gc.ca/en/data-science/network/open-data",
     "best_for": "Data science, ML, analytics"},
    {"name": "GitHub — Good First Issues",
     "description": "Contribute to open source. 'Good first issue' label is designed for new contributors. Great for portfolio.",
     "url": "https://goodfirstissue.dev",
     "best_for": "Software engineering, ML, Python, any tech skill"},
]


# ─────────────────────────────────────────────────────────────────────────────
# 4. RESUME IMPROVEMENT TIPS  (personalised)
# ─────────────────────────────────────────────────────────────────────────────
def _resume_tips(
    missing_required: list[str],
    keyword_gaps: list[str],
    weak_bullet_count: int,
    experience_gap_years: int,
    job_title: str,
) -> list[dict]:
    tips = []

    if weak_bullet_count > 0:
        tips.append({
            "priority": 1,
            "category": "bullet_quality",
            "title": f"Rewrite {weak_bullet_count} weak bullet point(s)",
            "detail": (
                "Weak bullets use passive language ('worked on', 'helped with') with no numbers. "
                "Replace each with: [Action verb] + [what you did] + [measurable result]. "
                "Example: 'Reduced model inference time by 40% by switching from numpy loops to vectorised operations.'"
            ),
            "example_before": "Worked on machine learning models for the team.",
            "example_after": "Trained and deployed 3 scikit-learn classification models, improving prediction accuracy from 72% to 89%.",
        })

    if keyword_gaps:
        tips.append({
            "priority": 2,
            "category": "ats_keywords",
            "title": f"Add {len(keyword_gaps)} missing ATS keyword(s)",
            "detail": (
                f"These phrases appear in the job description but not in your resume: "
                f"{', '.join(keyword_gaps[:5])}. "
                "ATS systems scan for exact or near-exact matches. "
                "Add them naturally in your experience bullets or a skills section."
            ),
            "keywords": keyword_gaps[:8],
        })

    if missing_required:
        tips.append({
            "priority": 3,
            "category": "skills_section",
            "title": "Add a dedicated Technical Skills section",
            "detail": (
                "If you have learned but not listed: "
                f"{', '.join(missing_required[:4])}, add them under Technical Skills "
                "with proficiency level (e.g. 'Python (advanced), TensorFlow (intermediate)'). "
                "This helps Pass 1 (exact match) catch your skills."
            ),
        })

    if experience_gap_years > 0:
        tips.append({
            "priority": 4,
            "category": "experience_gap",
            "title": f"Bridge the {experience_gap_years}-year experience gap with projects",
            "detail": (
                "Add a Projects section if you do not have one. "
                "Each project entry should include: project name, tech stack, what problem it solved, "
                "and a quantified outcome (users, accuracy, time saved). "
                f"For a {job_title} role, a relevant personal or open-source project "
                "is weighted almost as heavily as 1 year of work experience by many hiring managers."
            ),
        })

    tips.append({
        "priority": 5,
        "category": "formatting",
        "title": "Tailor the summary section to this specific role",
        "detail": (
            f"Your resume summary should mention the job title ({job_title}) "
            "and your 2-3 most relevant skills in the first sentence. "
            "Recruiters spend 6 seconds on a resume — the summary must confirm "
            "role fit immediately. Avoid generic phrases like 'results-driven professional'."
        ),
    })

    tips.append({
        "priority": 6,
        "category": "formatting",
        "title": "Use a single-column ATS-safe format",
        "detail": (
            "Multi-column layouts, text boxes, tables, and graphics confuse ATS parsers. "
            "Use a plain single-column format with standard section headers: "
            "Summary, Experience, Projects, Education, Skills, Certifications. "
            "Recommended tools: Overleaf (LaTeX), Google Docs with a clean template, or Canva ATS-friendly templates."
        ),
    })

    return tips


# ─────────────────────────────────────────────────────────────────────────────
# 5. MAIN: build_action_plan
# ─────────────────────────────────────────────────────────────────────────────

@dataclass
class CertRecommendation:
    skill: str
    name: str
    provider: str
    level: str          # Beginner | Intermediate | Advanced
    url: str
    free_prep_url: str


@dataclass
class CourseRecommendation:
    skill: str
    name: str
    provider: str
    url: str
    free: bool = True


@dataclass
class JobOpportunity:
    platform: str
    description: str
    search_url: str
    icon: str = ""


@dataclass
class VolunteerOpportunity:
    name: str
    description: str
    url: str
    best_for: str


@dataclass
class ResumeTip:
    priority: int
    category: str
    title: str
    detail: str
    example_before: str = ""
    example_after: str = ""
    keywords: list[str] = field(default_factory=list)


@dataclass
class ActionPlan:
    certifications: list[CertRecommendation] = field(default_factory=list)
    courses: list[CourseRecommendation] = field(default_factory=list)
    job_opportunities: list[JobOpportunity] = field(default_factory=list)
    volunteer_opportunities: list[VolunteerOpportunity] = field(default_factory=list)
    resume_tips: list[ResumeTip] = field(default_factory=list)
    has_experience_gap: bool = False
    experience_gap_years: int = 0


def build_action_plan(
    skill_gaps: list[str],          # canonical skill names that are missing
    experience_gap_years: int,       # 0 if no gap
    keyword_gaps: list[str],         # ATS keyword phrases missing from resume
    weak_bullet_count: int,          # number of weak bullets
    job_title: str,
    missing_required: list[str],
) -> ActionPlan:
    plan = ActionPlan(
        has_experience_gap=experience_gap_years > 0,
        experience_gap_years=experience_gap_years,
    )

    # ── Certifications ────────────────────────────────────────────────────
    seen_certs: set[str] = set()
    for skill in skill_gaps[:8]:   # top 8 gaps
        skill_lower = skill.lower()
        for certs in _CERTS.get(skill_lower, []):
            key = certs["name"]
            if key not in seen_certs:
                seen_certs.add(key)
                plan.certifications.append(CertRecommendation(
                    skill=skill,
                    name=certs["name"],
                    provider=certs["provider"],
                    level=certs["level"],
                    url=certs["url"],
                    free_prep_url=certs["free_prep"],
                ))

    # ── Courses ───────────────────────────────────────────────────────────
    seen_courses: set[str] = set()
    for skill in skill_gaps[:10]:
        skill_lower = skill.lower()
        for c in _COURSES.get(skill_lower, []):
            if c["name"] not in seen_courses:
                seen_courses.add(c["name"])
                plan.courses.append(CourseRecommendation(
                    skill=skill,
                    name=c["name"],
                    provider=c["provider"],
                    url=c["url"],
                    free=c.get("free", True),
                ))
        # If no specific course, add a Coursera search link
        if skill_lower not in _COURSES:
            q = urllib.parse.quote_plus(skill)
            plan.courses.append(CourseRecommendation(
                skill=skill,
                name=f"Search '{skill}' on Coursera (free audit available)",
                provider="Coursera",
                url=f"https://www.coursera.org/search?query={q}&price=free",
                free=True,
            ))

    # ── Entry-level jobs (when experience gap exists or fresh grad) ────────
    search_query = urllib.parse.quote_plus(
        (job_title or "software engineer").replace(" ", "+")
    )
    for plat in _JOB_PLATFORMS:
        url = plat["search_url_template"].format(
            query=search_query,
            qlen=len(urllib.parse.quote_plus(job_title or "software engineer")),
        )
        plan.job_opportunities.append(JobOpportunity(
            platform=plat["name"],
            description=plat["description"],
            search_url=url,
            icon=plat.get("icon", ""),
        ))

    # ── Volunteer opportunities ───────────────────────────────────────────
    for v in _VOLUNTEER_PLATFORMS:
        plan.volunteer_opportunities.append(VolunteerOpportunity(
            name=v["name"],
            description=v["description"],
            url=v["url"],
            best_for=v["best_for"],
        ))

    # ── Resume tips ───────────────────────────────────────────────────────
    raw_tips = _resume_tips(
        missing_required=missing_required,
        keyword_gaps=keyword_gaps,
        weak_bullet_count=weak_bullet_count,
        experience_gap_years=experience_gap_years,
        job_title=job_title,
    )
    for t in raw_tips:
        plan.resume_tips.append(ResumeTip(
            priority=t["priority"],
            category=t["category"],
            title=t["title"],
            detail=t["detail"],
            example_before=t.get("example_before", ""),
            example_after=t.get("example_after", ""),
            keywords=t.get("keywords", []),
        ))

    return plan
