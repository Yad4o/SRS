"""
workers/cleanup.py

Owner:
------
Om (Backend / System)

Purpose:
--------
Perform routine maintenance and cleanup tasks.

This worker handles:
- Archiving old tickets
- Removing stale or temporary data
- Database housekeeping

Why this is a worker:
---------------------
- Maintenance tasks are not user-facing
- Can be scheduled during low-traffic periods
- Keeps the system healthy over time

Responsibilities:
-----------------
- Identify outdated records
- Clean or archive data safely
- Maintain database performance

DO NOT:
-------
- Delete active tickets
- Modify AI behavior
- Run inside API requests

Usage:
------
    python workers/cleanup.py [--days 90] [--dry-run]
"""

import argparse
import logging
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

# Add project root to path so worker can be run directly
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from sqlalchemy.orm import Session

from app.db.session import SessionLocal, init_db
from app.models.ticket import Ticket

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger(__name__)

# Ticket statuses that are safe to archive
ARCHIVABLE_STATUSES = {"closed", "auto_resolved", "escalated"}


def archive_old_tickets(db: Session, cutoff_date: datetime, dry_run: bool = False) -> int:
    """
    Mark old resolved/closed tickets as 'archived'.

    Only tickets whose ``status`` is one of :data:`ARCHIVABLE_STATUSES` **and**
    whose ``created_at`` is older than *cutoff_date* are affected.  Active
    (``open``) tickets are never touched.

    Args:
        db: Active SQLAlchemy session.
        cutoff_date: Tickets created before this timestamp are eligible.
        dry_run: When *True* log what would happen without writing to the DB.

    Returns:
        Number of tickets archived (or that would be archived in dry-run mode).
    """
    tickets = (
        db.query(Ticket)
        .filter(
            Ticket.status.in_(ARCHIVABLE_STATUSES),
            Ticket.created_at < cutoff_date,
        )
        .all()
    )

    count = len(tickets)
    if count == 0:
        logger.info("No old tickets found to archive.")
        return 0

    logger.info("Found %d ticket(s) eligible for archiving (before %s).", count, cutoff_date.date())

    if dry_run:
        for ticket in tickets:
            logger.info(
                "[DRY-RUN] Would archive ticket id=%d status=%s created_at=%s",
                ticket.id,
                ticket.status,
                ticket.created_at,
            )
        return count

    for ticket in tickets:
        ticket.status = "archived"

    db.commit()
    logger.info("Archived %d ticket(s).", count)
    return count


def remove_orphaned_feedback(db: Session, dry_run: bool = False) -> int:
    """
    Remove feedback records whose parent ticket no longer exists.

    Under normal operation this should never happen due to the FK constraint,
    but it is a useful safety net when rows are deleted outside the ORM.

    Args:
        db: Active SQLAlchemy session.
        dry_run: When *True* log what would happen without writing to the DB.

    Returns:
        Number of orphaned feedback records removed.
    """
    from app.models.feedback import Feedback

    orphaned = (
        db.query(Feedback)
        .filter(~Feedback.ticket_id.in_(db.query(Ticket.id)))
        .all()
    )

    count = len(orphaned)
    if count == 0:
        logger.info("No orphaned feedback records found.")
        return 0

    logger.info("Found %d orphaned feedback record(s).", count)

    if dry_run:
        for fb in orphaned:
            logger.info("[DRY-RUN] Would delete orphaned feedback id=%d ticket_id=%d", fb.id, fb.ticket_id)
        return count

    for fb in orphaned:
        db.delete(fb)

    db.commit()
    logger.info("Removed %d orphaned feedback record(s).", count)
    return count


def run_cleanup(days: int = 90, dry_run: bool = False) -> dict:
    """
    Execute all cleanup tasks.

    Args:
        days: Tickets older than this many days (and not open) are archived.
        dry_run: When *True* no database writes are performed.

    Returns:
        Summary dict with keys ``archived_tickets`` and ``removed_feedback``.
    """
    init_db()
    cutoff_date = datetime.now(timezone.utc) - timedelta(days=days)

    logger.info(
        "Starting cleanup (dry_run=%s, cutoff=%s, days=%d).",
        dry_run,
        cutoff_date.date(),
        days,
    )

    db: Session = SessionLocal()
    try:
        archived = archive_old_tickets(db, cutoff_date, dry_run=dry_run)
        removed_feedback = remove_orphaned_feedback(db, dry_run=dry_run)
    finally:
        db.close()

    summary = {
        "archived_tickets": archived,
        "removed_feedback": removed_feedback,
    }
    logger.info("Cleanup complete: %s", summary)
    return summary


# ---------------------------------------------------------------------------
# CLI entry point
# ---------------------------------------------------------------------------

def _parse_args(argv=None):
    parser = argparse.ArgumentParser(
        description="Cleanup worker — archive old tickets and remove orphaned records.",
    )
    parser.add_argument(
        "--days",
        type=int,
        default=90,
        help="Archive tickets older than DAYS days (default: 90).",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Show what would be done without making any changes.",
    )
    return parser.parse_args(argv)


if __name__ == "__main__":
    args = _parse_args()
    run_cleanup(days=args.days, dry_run=args.dry_run)
