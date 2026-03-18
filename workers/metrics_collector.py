"""
workers/metrics_collector.py

Owner:
------
Om (Backend / System)

Purpose:
--------
Aggregate system-wide metrics for admin and monitoring purposes.

This worker precomputes metrics such as:
- Total number of tickets
- Auto-resolved vs escalated ratio
- Feedback success rate

Why this is a worker:
---------------------
- Metrics aggregation can be DB-heavy
- Precomputation improves admin API performance
- Not required in real-time

Responsibilities:
-----------------
- Query ticket and feedback tables
- Compute aggregate statistics
- Store results for admin dashboards

DO NOT:
-------
- Handle HTTP requests
- Contain AI logic
- Modify business decisions

Usage:
------
    python workers/metrics_collector.py [--output metrics_<YYYYMMDD_HHMMSS>.json]
"""

import argparse
import json
import logging
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict

# Add project root to path so worker can be run directly
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from sqlalchemy import func

from app.db.session import SessionLocal, init_db
from app.models.feedback import Feedback
from app.models.ticket import Ticket

logger = logging.getLogger(__name__)

DEFAULT_OUTPUT = project_root / "metrics.json"


# ---------------------------------------------------------------------------
# Metric computation
# ---------------------------------------------------------------------------

def collect_metrics(db) -> Dict:
    """
    Query the database and return a snapshot of system-wide metrics.

    Returned keys
    -------------
    - ``collected_at`` — ISO-8601 timestamp of collection
    - ``tickets`` — breakdown by status and intent
    - ``feedback`` — aggregate rating and resolution statistics
    - ``auto_resolve_rate`` — fraction of non-open tickets that were auto-resolved
    - ``escalation_rate`` — fraction of non-open tickets that were escalated

    Args:
        db: Active SQLAlchemy session.

    Returns:
        Dict with all computed metrics.
    """
    # ------------------------------------------------------------------
    # Ticket metrics
    # ------------------------------------------------------------------
    total_tickets: int = db.query(func.count(Ticket.id)).scalar() or 0

    # Count per status using a single query
    status_rows = (
        db.query(Ticket.status, func.count(Ticket.id))
        .group_by(Ticket.status)
        .all()
    )
    tickets_by_status = {status: count for status, count in status_rows}

    # Count per intent
    intent_rows = (
        db.query(Ticket.intent, func.count(Ticket.id))
        .filter(Ticket.intent.isnot(None))
        .group_by(Ticket.intent)
        .all()
    )
    tickets_by_intent = {intent: count for intent, count in intent_rows}

    # Resolved / escalated ticket counts.
    # "Decided" = all tickets that have left the open state.
    # Using total - open ensures archived tickets (is_archived=True) are
    # counted correctly since archiving preserves the original status.
    open_count = tickets_by_status.get("open", 0)
    decided = total_tickets - open_count  # tickets that left open state

    auto_resolved = tickets_by_status.get("auto_resolved", 0)
    escalated = tickets_by_status.get("escalated", 0)

    auto_resolve_rate = round(auto_resolved / decided, 3) if decided else 0.0
    escalation_rate = round(escalated / decided, 3) if decided else 0.0

    # ------------------------------------------------------------------
    # Feedback metrics
    # ------------------------------------------------------------------
    total_feedback: int = db.query(func.count(Feedback.id)).scalar() or 0

    avg_rating_row = db.query(func.avg(Feedback.rating)).scalar()
    average_rating = round(float(avg_rating_row), 3) if avg_rating_row is not None else 0.0

    resolved_count: int = (
        db.query(func.count(Feedback.id)).filter(Feedback.resolved.is_(True)).scalar() or 0
    )
    resolution_rate = round(resolved_count / total_feedback, 3) if total_feedback else 0.0

    # ------------------------------------------------------------------
    # Assemble result
    # ------------------------------------------------------------------
    return {
        "collected_at": datetime.now(timezone.utc).isoformat(),
        "tickets": {
            "total": total_tickets,
            "by_status": tickets_by_status,
            "by_intent": tickets_by_intent,
        },
        "feedback": {
            "total": total_feedback,
            "average_rating": average_rating,
            "resolution_rate": resolution_rate,
        },
        "auto_resolve_rate": auto_resolve_rate,
        "escalation_rate": escalation_rate,
    }


# ---------------------------------------------------------------------------
# Runner
# ---------------------------------------------------------------------------

def run_metrics_collector(output_path: Path = DEFAULT_OUTPUT) -> Dict:
    """
    Collect system metrics and persist them to *output_path*.

    Args:
        output_path: Destination file for the JSON metrics snapshot.

    Returns:
        The metrics dict produced by :func:`collect_metrics`.
    """
    init_db()
    db = SessionLocal()
    try:
        logger.info("Collecting system metrics…")
        metrics = collect_metrics(db)
    finally:
        db.close()

    output_path.parent.mkdir(parents=True, exist_ok=True)
    with output_path.open("w", encoding="utf-8") as fh:
        json.dump(metrics, fh, indent=2)

    logger.info(
        "Metrics written to %s (total_tickets=%d, auto_resolve_rate=%.3f, escalation_rate=%.3f).",
        output_path,
        metrics["tickets"]["total"],
        metrics["auto_resolve_rate"],
        metrics["escalation_rate"],
    )
    return metrics


# ---------------------------------------------------------------------------
# CLI entry point
# ---------------------------------------------------------------------------

def _parse_args(argv=None):
    # Generate a timestamped default filename for CLI use so each standalone
    # run produces a distinct snapshot rather than overwriting the previous one.
    _ts = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
    _default_cli_output = project_root / f"metrics_{_ts}.json"

    parser = argparse.ArgumentParser(
        description="Metrics collector — aggregate system-wide stats and persist results.",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=_default_cli_output,
        help="Path to write the JSON metrics snapshot (default: metrics_<timestamp>.json).",
    )
    return parser.parse_args(argv)


if __name__ == "__main__":
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    )
    args = _parse_args()
    run_metrics_collector(output_path=args.output)
