"""
routers/feedback.py — POST /feedback
--------------------------------------
Stores user feedback (correct/wrong/missing skills) as JSONL for
future model improvement.  Minimal implementation — no auth required.
"""

import json
import logging
from datetime import datetime, timezone
from pathlib import Path

from fastapi import APIRouter
from app.config import settings
from app.schemas import FeedbackRequest, FeedbackResponse

log = logging.getLogger(__name__)
router = APIRouter(prefix="/feedback", tags=["Feedback"])

_FEEDBACK_FILE = settings.STORAGE_DIR / "feedback.jsonl"


@router.post("", response_model=FeedbackResponse, summary="Submit skill feedback")
def submit_feedback(body: FeedbackRequest):
    """
    Record user corrections.

    **Fields:**
    - `report_id`:      ID of the analysis run this feedback is for.
    - `correct_skills`: Skills that were correctly identified.
    - `wrong_skills`:   Skills the model got wrong (false positives).
    - `missing_skills`: Skills the model missed (false negatives).
    - `comment`:        Optional free-text comment.
    """
    settings.STORAGE_DIR.mkdir(parents=True, exist_ok=True)

    record = {
        "timestamp":      datetime.now(timezone.utc).isoformat(),
        "report_id":      body.report_id,
        "correct_skills": body.correct_skills,
        "wrong_skills":   body.wrong_skills,
        "missing_skills": body.missing_skills,
        "comment":        body.comment,
    }

    try:
        with open(_FEEDBACK_FILE, "a", encoding="utf-8") as fh:
            fh.write(json.dumps(record, ensure_ascii=False) + "\n")
        log.info("Feedback saved for report %s", body.report_id)
    except Exception as exc:
        log.error("Could not save feedback: %s", exc)
        return FeedbackResponse(success=False, message=f"Storage error: {exc}")

    return FeedbackResponse(success=True, message="Feedback recorded. Thank you!")
