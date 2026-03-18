"""
workers/feedback_analyzer.py

Owner:
------
Prajwal (AI / NLP)

Purpose:
--------
Analyze user feedback collected after ticket resolution.

This worker processes feedback data asynchronously to:
- Measure auto-resolution success rate
- Identify weak intents or responses
- Prepare data for future AI improvements

Why this is a worker:
---------------------
- Feedback analysis is not time-sensitive
- Can run periodically (hourly / daily)
- Should not block API requests

Responsibilities:
-----------------
- Fetch feedback records from database
- Aggregate ratings and resolution flags
- Compute performance metrics

DO NOT:
-------
- Modify ticket status
- Retrain models automatically
- Serve API requests directly

Usage:
------
    python workers/feedback_analyzer.py [--output feedback_analysis.json]
"""

import argparse
import json
import logging
import sys
from collections import Counter, defaultdict
from pathlib import Path
from typing import Dict, List

# Add project root to path so worker can be run directly
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from app.db.session import SessionLocal, init_db
from app.models.feedback import Feedback
from app.models.ticket import Ticket

logger = logging.getLogger(__name__)

DEFAULT_OUTPUT = project_root / "feedback_analysis.json"


# ---------------------------------------------------------------------------
# Data fetching
# ---------------------------------------------------------------------------

def fetch_feedback_with_tickets(db) -> List[Dict]:
    """
    Return all feedback records joined with their parent ticket's intent.

    Returns:
        List of dicts containing feedback fields and the ticket's ``intent``.
    """
    rows = (
        db.query(Feedback, Ticket)
        .join(Ticket, Feedback.ticket_id == Ticket.id)
        .order_by(Feedback.id)
        .all()
    )
    return [
        {
            "feedback_id": fb.id,
            "ticket_id": fb.ticket_id,
            "rating": fb.rating,
            "resolved": fb.resolved,
            "created_at": fb.created_at.isoformat() if fb.created_at else None,
            "intent": ticket.intent,
            "ticket_status": ticket.status,
        }
        for fb, ticket in rows
    ]


# ---------------------------------------------------------------------------
# Analysis helpers
# ---------------------------------------------------------------------------

def _safe_avg(values: List[float]) -> float:
    """Return the average of *values*, or 0.0 if the list is empty."""
    return round(sum(values) / len(values), 3) if values else 0.0


def analyze_feedback(records: List[Dict]) -> Dict:
    """
    Aggregate feedback records into actionable metrics.

    Computed metrics
    ----------------
    - ``total_feedback`` — total number of feedback records
    - ``average_rating`` — mean rating across all records
    - ``resolution_rate`` — fraction of records where ``resolved`` is True
    - ``by_intent`` — per-intent breakdown with avg rating and resolution rate
    - ``by_ticket_status`` — per-status breakdown
    - ``rating_distribution`` — count of each rating value

    Args:
        records: List of feedback+ticket dicts from :func:`fetch_feedback_with_tickets`.

    Returns:
        Dict containing all computed metrics.
    """
    if not records:
        return {
            "total_feedback": 0,
            "average_rating": 0.0,
            "resolution_rate": 0.0,
            "by_intent": {},
            "by_ticket_status": {},
            "rating_distribution": {},
        }

    total = len(records)
    all_ratings = [r["rating"] for r in records if r["rating"] is not None]
    all_resolved = [r["resolved"] for r in records if r["resolved"] is not None]

    # Per-intent aggregation
    by_intent: Dict[str, Dict] = defaultdict(lambda: {"ratings": [], "resolved": []})
    for rec in records:
        intent_key = rec.get("intent") or "unknown"
        if rec["rating"] is not None:
            by_intent[intent_key]["ratings"].append(rec["rating"])
        if rec["resolved"] is not None:
            by_intent[intent_key]["resolved"].append(rec["resolved"])

    intent_summary = {
        intent: {
            "count": len(vals["ratings"]),
            "average_rating": _safe_avg(vals["ratings"]),
            "resolution_rate": round(sum(vals["resolved"]) / len(vals["resolved"]), 3)
            if vals["resolved"]
            else 0.0,
        }
        for intent, vals in by_intent.items()
    }

    # Per-ticket-status aggregation
    by_status: Dict[str, Dict] = defaultdict(lambda: {"ratings": [], "resolved": []})
    for rec in records:
        status_key = rec.get("ticket_status") or "unknown"
        if rec["rating"] is not None:
            by_status[status_key]["ratings"].append(rec["rating"])
        if rec["resolved"] is not None:
            by_status[status_key]["resolved"].append(rec["resolved"])

    status_summary = {
        status: {
            "count": len(vals["ratings"]),
            "average_rating": _safe_avg(vals["ratings"]),
            "resolution_rate": round(sum(vals["resolved"]) / len(vals["resolved"]), 3)
            if vals["resolved"]
            else 0.0,
        }
        for status, vals in by_status.items()
    }

    # Rating distribution.
    # Keys are explicitly converted to strings so the JSON representation
    # is consistent (JSON always coerces object keys to strings anyway).
    rating_distribution = {
        str(k): v
        for k, v in Counter(r["rating"] for r in records if r["rating"] is not None).items()
    }

    return {
        "total_feedback": total,
        "average_rating": _safe_avg(all_ratings),
        "resolution_rate": round(sum(all_resolved) / len(all_resolved), 3) if all_resolved else 0.0,
        "by_intent": intent_summary,
        "by_ticket_status": status_summary,
        "rating_distribution": rating_distribution,
    }


# ---------------------------------------------------------------------------
# Runner
# ---------------------------------------------------------------------------

def run_feedback_analyzer(output_path: Path = DEFAULT_OUTPUT) -> Dict:
    """
    Fetch feedback records, compute metrics, and save the analysis.

    Args:
        output_path: Destination file for the JSON analysis report.

    Returns:
        The analysis dict produced by :func:`analyze_feedback`.
    """
    init_db()
    db = SessionLocal()
    try:
        logger.info("Fetching feedback records…")
        records = fetch_feedback_with_tickets(db)
        logger.info("Found %d feedback record(s).", len(records))
    finally:
        db.close()

    analysis = analyze_feedback(records)

    output_path.parent.mkdir(parents=True, exist_ok=True)
    with output_path.open("w", encoding="utf-8") as fh:
        json.dump(analysis, fh, indent=2)

    logger.info(
        "Feedback analysis written to %s (total=%d, avg_rating=%.3f, resolution_rate=%.3f).",
        output_path,
        analysis["total_feedback"],
        analysis["average_rating"],
        analysis["resolution_rate"],
    )
    return analysis


# ---------------------------------------------------------------------------
# CLI entry point
# ---------------------------------------------------------------------------

def _parse_args(argv=None):
    parser = argparse.ArgumentParser(
        description="Feedback analyzer — aggregate feedback metrics and persist results.",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=DEFAULT_OUTPUT,
        help="Path to write the JSON analysis report (default: feedback_analysis.json).",
    )
    return parser.parse_args(argv)


if __name__ == "__main__":
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    )
    args = _parse_args()
    run_feedback_analyzer(output_path=args.output)
