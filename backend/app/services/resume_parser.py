"""
resume_parser.py — Section detection, name extraction, and text cleaning.
Section-aware parsing is the foundation that makes every detection pass stronger.
"""
import re
import logging
from pathlib import Path

log = logging.getLogger(__name__)

# ── Section header patterns ───────────────────────────────────────────────────
_SECTION_PATTERNS: dict[str, list[str]] = {
    "experience": [
        r"work\s+experience", r"experience", r"employment", r"professional\s+experience",
        r"career\s+history", r"work\s+history",
    ],
    "education": [
        r"education", r"academic", r"qualifications", r"degrees?",
    ],
    "skills": [
        r"skills?", r"technical\s+skills?", r"core\s+competencies", r"technologies",
        r"tech\s+stack", r"tools",
    ],
    "projects": [
        r"projects?", r"personal\s+projects?", r"side\s+projects?",
        r"open\s+source", r"portfolio",
    ],
    "summary": [
        r"summary", r"objective", r"profile", r"about\s+me", r"overview",
    ],
    "awards": [
        r"awards?", r"honours?", r"honors?", r"achievements?", r"certifications?",
        r"certificates?",
    ],
    "publications": [
        r"publications?", r"papers?", r"research",
    ],
}

# Compiled: (section_name, compiled_regex)
_COMPILED: list[tuple[str, re.Pattern]] = []
for _section, _patterns in _SECTION_PATTERNS.items():
    combined = "|".join(f"(?:{p})" for p in _patterns)
    _COMPILED.append((_section, re.compile(
        rf"^\s*(?:{combined})\s*[:\-–]?\s*$", re.IGNORECASE | re.MULTILINE
    )))


def clean_text(raw: str) -> str:
    """
    Normalise resume text:
    - Strip bullet symbols (•, *, ►, ‣)
    - Collapse 3+ blank lines to 2
    - Normalise tabs to spaces
    """
    if not raw:
        return ""
    text = raw.replace("\r\n", "\n").replace("\r", "\n")
    text = re.sub(r"^[\s•\*►‣▪▸]+", "", text, flags=re.MULTILINE)
    text = re.sub(r"\t", " ", text)
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()


def detect_sections(text: str) -> dict[str, str]:
    """
    Split resume text into named sections.
    Returns dict: section_name → section_text.
    Always includes a "header" key for text before the first section heading.
    """
    if not text.strip():
        return {}

    lines = text.split("\n")
    sections: dict[str, list[str]] = {"header": []}
    current = "header"

    for line in lines:
        matched = False
        for section_name, pattern in _COMPILED:
            if pattern.match(line):
                current = section_name
                sections.setdefault(current, [])
                matched = True
                break
        if not matched:
            sections.setdefault(current, [])
            sections[current].append(line)

    return {k: "\n".join(v).strip() for k, v in sections.items() if "\n".join(v).strip()}


def extract_candidate_name(sections: dict[str, str]) -> str:
    """
    Extract the candidate's name from the header section.
    Heuristic: first non-empty line with 2-4 capitalised words,
    no digits, not an email/URL.
    """
    header = sections.get("header", "")
    if not header:
        return "Unknown"

    for line in header.split("\n"):
        line = line.strip()
        if not line or len(line) > 60:
            continue
        if re.search(r"[@\d/\\]", line):
            continue
        words = line.split()
        if 2 <= len(words) <= 4 and all(w[0].isupper() for w in words if w):
            return line
    return "Unknown"


def extract_text_from_file(file_path: Path) -> str:
    """Extract plain text from .pdf, .docx, or .txt files."""
    suffix = file_path.suffix.lower()

    if suffix == ".txt":
        return file_path.read_text(encoding="utf-8", errors="ignore")

    if suffix == ".pdf":
        try:
            import pdfplumber
            chunks = []
            with pdfplumber.open(str(file_path)) as pdf:
                for page in pdf.pages:
                    chunks.append(page.extract_text() or "")
            return "\n".join(chunks)
        except ImportError:
            log.warning("pdfplumber not installed — install with: pip install pdfplumber")
            return ""

    if suffix == ".docx":
        try:
            import docx
            doc = docx.Document(str(file_path))
            return "\n".join(p.text for p in doc.paragraphs)
        except ImportError:
            log.warning("python-docx not installed — install with: pip install python-docx")
            return ""

    return file_path.read_text(encoding="utf-8", errors="ignore")




def extract_text_from_bytes(content, suffix):
    """Extract text from raw bytes (used by the HTTP upload endpoint)."""
    import io
    if suffix == '.txt':
        return content.decode('utf-8', errors='ignore')
    if suffix == '.pdf':
        try:
            import pdfplumber
            chunks = []
            with pdfplumber.open(io.BytesIO(content)) as pdf:
                for page in pdf.pages:
                    chunks.append(page.extract_text() or '')
            return chr(10).join(chunks)
        except ImportError:
            return ''
    if suffix == '.docx':
        try:
            import docx
            doc = docx.Document(io.BytesIO(content))
            return chr(10).join(p.text for p in doc.paragraphs)
        except ImportError:
            return ''
    return content.decode('utf-8', errors='ignore')
