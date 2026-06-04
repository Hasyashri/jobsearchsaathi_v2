"""
jd_parser.py — Extract structured requirements from a job description.

Parses: required skills, preferred skills, certifications, experience years,
key phrases (for resume keyword matching), and job title.
"""
from __future__ import annotations
import re
import logging
from dataclasses import dataclass, field

log = logging.getLogger(__name__)

# ── Common certification patterns ──────────────────────────────────────────
_CERT_PATTERNS = [
    r"AWS\s+Certified[^\n,;]*",
    r"Google\s+Cloud\s+(?:Certified|Professional)[^\n,;]*",
    r"Azure\s+(?:Certified|Administrator|Developer|Solutions\s+Architect)[^\n,;]*",
    r"Certified\s+(?:Kubernetes|K8s)[^\n,;]*",
    r"CKA|CKAD|CKS",
    r"PMP(?:\s+Certified)?",
    r"Scrum\s+Master|CSM|PSM",
    r"CISSP|CEH|CompTIA\s+\w+",
    r"Tableau\s+(?:Desktop\s+)?(?:Certified|Specialist)[^\n,;]*",
    r"Databricks\s+Certified[^\n,;]*",
    r"TensorFlow\s+Developer\s+Certificate",
    r"Oracle\s+Certified[^\n,;]*",
    r"Salesforce\s+Certified[^\n,;]*",
    r"PMI-?\w+",
    r"ITIL\s+\w*",
]
_CERT_RE = re.compile("|".join(f"(?:{p})" for p in _CERT_PATTERNS), re.IGNORECASE)

# ── Experience year patterns ────────────────────────────────────────────────
_EXP_RE = re.compile(
    r"(\d+)\s*(?:\+|or\s+more|plus)?\s*(?:to|-)\s*(\d+)?\s*years?\s+(?:of\s+)?(?:experience|exp\.?)|"
    r"(\d+)\s*\+?\s*years?\s+(?:of\s+)?(?:relevant\s+)?(?:experience|exp\.?)",
    re.IGNORECASE,
)

# ── Section signal words ────────────────────────────────────────────────────
_REQUIRED_SIGNALS = re.compile(
    r"required|must\s+have|mandatory|essential|minimum\s+qualifications?|"
    r"what\s+you.ll\s+need|you\s+(?:must|will)\s+have|we\s+require",
    re.IGNORECASE,
)
_PREFERRED_SIGNALS = re.compile(
    r"preferred|nice\s+to\s+have|bonus|plus|desired|advantageous|"
    r"would\s+be\s+(?:great|a\s+plus|beneficial)|optional",
    re.IGNORECASE,
)

# ── Stop words for key-phrase filtering ─────────────────────────────────────
_STOP = frozenset({
    "the", "and", "or", "in", "of", "to", "a", "an", "with", "for", "on",
    "at", "is", "are", "will", "be", "we", "you", "your", "our", "this",
    "that", "have", "has", "by", "as", "from", "must", "can", "able",
    "strong", "good", "excellent", "knowledge", "experience", "skills",
    "ability", "understanding", "familiar", "proficient", "work", "using",
    "use", "build", "building", "develop", "developing", "design",
})


@dataclass
class JDParseResult:
    job_title: str = ""
    required_skills: list[str] = field(default_factory=list)
    preferred_skills: list[str] = field(default_factory=list)
    required_certifications: list[str] = field(default_factory=list)
    required_experience_years: int = 0          # minimum years asked for
    key_phrases: list[str] = field(default_factory=list)  # important JD terms for resume keyword check
    raw_text: str = ""


def parse_jd(jd_text: str, catalog: dict[str, list[str]]) -> JDParseResult:
    """
    Parse a job description and return structured requirements.
    Uses the skills catalog for alias-aware extraction.
    """
    if not jd_text.strip():
        return JDParseResult()

    result = JDParseResult(raw_text=jd_text)
    result.job_title = _extract_job_title(jd_text)
    result.required_experience_years = _extract_experience_years(jd_text)
    result.required_certifications = _extract_certifications(jd_text)

    req_skills, pref_skills = _extract_skills_from_jd(jd_text, catalog)
    result.required_skills = req_skills
    result.preferred_skills = pref_skills
    result.key_phrases = _extract_key_phrases(jd_text)

    log.info(
        "JD parsed: title=%r req=%d pref=%d certs=%d exp_years=%d phrases=%d",
        result.job_title, len(req_skills), len(pref_skills),
        len(result.required_certifications), result.required_experience_years,
        len(result.key_phrases),
    )
    return result


# ── Internal helpers ────────────────────────────────────────────────────────

def _extract_job_title(text: str) -> str:
    """Heuristic: first non-empty line that looks like a job title."""
    for line in text.split("\n")[:10]:
        line = line.strip()
        if not line or len(line) > 80 or len(line) < 4:
            continue
        if re.search(r"[@\d{]", line):
            continue
        words = line.split()
        if 1 <= len(words) <= 8:
            return line
    return ""


def _extract_experience_years(text: str) -> int:
    """Return the minimum years of experience required."""
    years = []
    for m in _EXP_RE.finditer(text):
        try:
            val = int(m.group(1) or m.group(3) or 0)
            if val > 0:
                years.append(val)
        except (TypeError, ValueError):
            pass
    return min(years) if years else 0


def _extract_certifications(text: str) -> list[str]:
    found = []
    seen = set()
    for m in _CERT_RE.finditer(text):
        cert = m.group(0).strip()
        key = cert.lower()
        if key not in seen:
            seen.add(key)
            found.append(cert)
    return found


def _split_into_sections(text: str) -> dict[str, str]:
    """
    Split JD into rough sections: required, preferred, other.
    Returns dict with keys 'required', 'preferred', 'other'.
    """
    lines = text.split("\n")
    sections: dict[str, list[str]] = {"required": [], "preferred": [], "other": []}
    current = "other"

    for line in lines:
        if _REQUIRED_SIGNALS.search(line):
            current = "required"
        elif _PREFERRED_SIGNALS.search(line):
            current = "preferred"
        sections[current].append(line)

    # If we never detected a required section, treat whole JD as required
    if not sections["required"]:
        sections["required"] = sections["other"]
        sections["other"] = []

    return {k: "\n".join(v) for k, v in sections.items()}


def _skills_from_text(text: str, catalog: dict[str, list[str]]) -> list[str]:
    """Extract canonical skill names from text using alias lookup + simple token match."""
    found = set()
    text_lower = text.lower()

    for skill_name, aliases in catalog.items():
        # Check canonical name
        if re.search(rf"\b{re.escape(skill_name)}\b", text_lower):
            found.add(skill_name)
            continue
        # Check aliases
        for alias in aliases:
            if alias and re.search(rf"\b{re.escape(alias.lower())}\b", text_lower):
                found.add(skill_name)
                break

    return sorted(found)


def _extract_skills_from_jd(
    text: str, catalog: dict[str, list[str]]
) -> tuple[list[str], list[str]]:
    sections = _split_into_sections(text)
    required = _skills_from_text(sections["required"], catalog)
    preferred = _skills_from_text(sections["preferred"], catalog)
    # skills that appear in both → keep in required only
    preferred = [s for s in preferred if s not in set(required)]
    return required, preferred


def _extract_key_phrases(text: str) -> list[str]:
    """
    Extract important 1-3 word phrases from the JD for resume keyword gap analysis.
    Focus on nouns and noun phrases not in the skills catalog.
    """
    # Extract quoted phrases and hyphenated terms
    phrases = set()

    # Quoted phrases
    for m in re.finditer(r'"([^"]{3,40})"', text):
        phrases.add(m.group(1).strip().lower())

    # Hyphenated technical terms  e.g. "end-to-end", "real-time"
    for m in re.finditer(r"\b\w+(?:-\w+){1,3}\b", text):
        term = m.group(0).lower()
        if len(term) >= 5 and term not in _STOP:
            phrases.add(term)

    # Capitalised multi-word phrases (likely proper nouns / tech terms)
    for m in re.finditer(r"(?:[A-Z][a-z]+\s){1,3}[A-Z][a-z]+", text):
        phrase = m.group(0).strip().lower()
        words = phrase.split()
        if all(w not in _STOP for w in words) and len(phrase) >= 5:
            phrases.add(phrase)

    # Common tech domain terms from the text
    domain_re = re.compile(
        r"\b(microservices?|ci/cd|devops|agile|scrum|rest\s*api|graphql|"
        r"event.driven|test.driven|tdd|bdd|oop|solid\s+principles?|"
        r"distributed\s+systems?|data\s+pipeline|etl|elt|"
        r"a/b\s+testing?|unit\s+test|integration\s+test|"
        r"cross.functional|stakeholder|product\s+owner|"
        r"high\s+availability|fault\s+toleran|scalab|"
        r"real.time|low.latency|high.throughput)\b",
        re.IGNORECASE,
    )
    for m in domain_re.finditer(text):
        phrases.add(m.group(1).lower().strip())

    # Deduplicate and limit
    result = sorted(p for p in phrases if len(p) >= 4 and p not in _STOP)
    return result[:30]
