"""
workers/embedding_builder.py

Owner:
------
Prajwal (AI / NLP)

Purpose:
--------
Precompute vector embeddings for resolved tickets.

These embeddings are used to:
- Speed up similarity search
- Improve semantic matching accuracy
- Reduce computation during API requests

Why this is a worker:
---------------------
- Embedding generation is computationally expensive
- Should not run during ticket creation
- Best suited for batch processing

Responsibilities:
-----------------
- Fetch resolved tickets
- Generate embeddings (TF-IDF / sentence embeddings)
- Store embeddings for fast retrieval

DO NOT:
-------
- Perform similarity search here
- Access FastAPI routes
- Make resolution decisions

Usage:
------
    python workers/embedding_builder.py [--output embeddings.json]
"""

import argparse
import json
import logging
import math
import re
import sys
from collections import Counter
from pathlib import Path
from typing import Dict, List

# Add project root to path so worker can be run directly
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from app.db.session import SessionLocal, init_db
from app.models.ticket import Ticket

logger = logging.getLogger(__name__)

# Statuses considered "resolved" and therefore useful for embedding pre-computation
RESOLVED_STATUSES = {"auto_resolved", "closed"}

# Default output path (relative to project root)
DEFAULT_OUTPUT = project_root / "embeddings.json"


# ---------------------------------------------------------------------------
# TF-IDF helpers
# These implement a standard smoothed TF-IDF: IDF is computed over the
# resolved-ticket corpus (the full batch being embedded).  This differs from
# the runtime similarity scorer in app/services/similarity_search.py, which
# incorporates the incoming query into the IDF corpus at search time.
# Precomputed vectors therefore use corpus-only weighting and serve as a
# fast approximation for batch indexing.
# ---------------------------------------------------------------------------

def _tokenize(text: str) -> List[str]:
    """Return lowercase word tokens from *text*."""
    if not text or not isinstance(text, str):
        return []
    return re.findall(r"\b\w+\b", text.lower())


def _compute_idf(corpus: List[str]) -> Dict[str, float]:
    """Compute IDF scores for every token present in *corpus*."""
    total = len(corpus)
    doc_counts: Counter = Counter()
    for doc in corpus:
        for token in set(_tokenize(doc)):
            doc_counts[token] += 1
    return {
        word: math.log((total + 1) / (count + 1)) + 1
        for word, count in doc_counts.items()
    }


def _tf_idf_vector(text: str, idf: Dict[str, float]) -> Dict[str, float]:
    """Return the TF-IDF vector for *text* given precomputed *idf* scores."""
    tokens = _tokenize(text)
    if not tokens:
        return {}
    tf = Counter(tokens)
    total = len(tokens)
    return {word: (count / total) * idf.get(word, 1.0) for word, count in tf.items()}


# ---------------------------------------------------------------------------
# Core logic
# ---------------------------------------------------------------------------

def fetch_resolved_tickets(db) -> List[Dict]:
    """
    Load all resolved tickets from the database.

    Returns:
        List of dicts with keys ``id``, ``message``, ``intent``, ``response``.
    """
    tickets = (
        db.query(Ticket)
        .filter(Ticket.status.in_(RESOLVED_STATUSES))
        .order_by(Ticket.id)
        .all()
    )
    return [
        {
            "id": t.id,
            "message": t.message,
            "intent": t.intent,
            "response": t.response,
            "status": t.status,
        }
        for t in tickets
    ]


def build_embeddings(tickets: List[Dict]) -> Dict:
    """
    Build TF-IDF embeddings for a list of ticket dicts.

    Args:
        tickets: Each dict must contain both an ``id`` key (used as the vector
            identifier) and a ``message`` key (the text to embed).  Entries
            missing a ``message`` value are silently skipped.

    Returns:
        A dict with:
        - ``idf``: shared IDF vocabulary mapping word → score
        - ``vectors``: list of ``{ticket_id, vector}`` dicts
        - ``ticket_count``: total number of tickets embedded
    """
    messages = [t["message"] for t in tickets if t.get("message")]
    if not messages:
        return {"idf": {}, "vectors": [], "ticket_count": 0}

    idf = _compute_idf(messages)

    vectors = []
    for ticket in tickets:
        msg = ticket.get("message", "")
        if not msg:
            continue
        vec = _tf_idf_vector(msg, idf)
        vectors.append({"ticket_id": ticket["id"], "vector": vec})

    return {
        "idf": idf,
        "vectors": vectors,
        "ticket_count": len(vectors),
    }


def save_embeddings(data: Dict, output_path: Path) -> None:
    """Persist *data* to *output_path* as JSON."""
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with output_path.open("w", encoding="utf-8") as fh:
        json.dump(data, fh, indent=2)
    logger.info("Embeddings written to %s (%d vectors).", output_path, data.get("ticket_count", 0))


def run_embedding_builder(output_path: Path = DEFAULT_OUTPUT) -> Dict:
    """
    Fetch resolved tickets, compute TF-IDF embeddings, and save them.

    Args:
        output_path: File path where the JSON embedding cache is stored.

    Returns:
        The embedding data dict (same structure as :func:`build_embeddings`).
    """
    init_db()
    db = SessionLocal()
    try:
        logger.info("Fetching resolved tickets from the database…")
        tickets = fetch_resolved_tickets(db)
        logger.info("Found %d resolved ticket(s).", len(tickets))
    finally:
        db.close()

    if not tickets:
        logger.warning("No resolved tickets found. Embedding cache will be empty.")

    data = build_embeddings(tickets)
    save_embeddings(data, output_path)
    return data


# ---------------------------------------------------------------------------
# CLI entry point
# ---------------------------------------------------------------------------

def _parse_args(argv=None):
    parser = argparse.ArgumentParser(
        description="Embedding builder — precompute TF-IDF vectors for resolved tickets.",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=DEFAULT_OUTPUT,
        help="Path to write the JSON embedding cache (default: embeddings.json).",
    )
    return parser.parse_args(argv)


if __name__ == "__main__":
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    )
    args = _parse_args()
    run_embedding_builder(output_path=args.output)
