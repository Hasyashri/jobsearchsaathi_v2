"""
text_utils.py — PII redaction and character-level span utilities.
"""
import re
from typing import List

_EMAIL_RE = re.compile(r"[A-Za-z0-9._%+\-]+@[A-Za-z0-9.\-]+\.[A-Za-z]{2,}", re.I)
_PHONE_RE = re.compile(r"(\+?\d[\d\s\-().]{7,}\d)")
_URL_RE   = re.compile(r"https?://[^\s]+|www\.[^\s]+", re.I)


def redact_pii(text: str) -> str:
    """Replace emails, phone numbers, and URLs with safe tokens."""
    if not text:
        return text
    text = _EMAIL_RE.sub("[EMAIL]", text)
    text = _PHONE_RE.sub("[PHONE]", text)
    text = _URL_RE.sub("[URL]", text)
    return text


def find_spans(text: str, term: str) -> List[List[int]]:
    """Return all [start, end] positions of term in text (word-boundary, case-insensitive)."""
    if not text or not term:
        return []
    pattern = re.compile(r"\b" + re.escape(term) + r"\b", re.IGNORECASE)
    return [[m.start(), m.end()] for m in pattern.finditer(text)]


def merge_spans(spans: List[List[int]]) -> List[List[int]]:
    """Merge overlapping/adjacent spans into clean non-overlapping ranges."""
    if not spans:
        return []
    srt = sorted(spans)
    merged = [srt[0]]
    for s, e in srt[1:]:
        if s <= merged[-1][1]:
            merged[-1][1] = max(merged[-1][1], e)
        else:
            merged.append([s, e])
    return merged
