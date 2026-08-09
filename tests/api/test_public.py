"""
Tests for the public, unauthenticated /resolve endpoint (app/api/public.py).
"""
from tests.conftest import client
from app.db.session import SessionLocal
from app.models.ticket import Ticket


def test_resolve_requires_no_auth():
    """No Authorization header at all — should still work."""
    response = client.post("/resolve", json={"message": "How do I reset my password?"})
    assert response.status_code == 200


def test_resolve_returns_expected_shape():
    response = client.post("/resolve", json={"message": "I want a refund for my order"})
    data = response.json()
    for field in (
        "intent",
        "sub_intent",
        "confidence",
        "sentiment",
        "sentiment_confidence",
        "decision",
        "response",
        "response_source",
    ):
        assert field in data
    assert data["decision"] in ("AUTO_RESOLVE", "ESCALATE")


def test_resolve_does_not_persist_a_ticket():
    """The whole point of this endpoint: nothing gets written to the DB."""
    db = SessionLocal()
    try:
        before = db.query(Ticket).count()
    finally:
        db.close()

    client.post("/resolve", json={"message": "My internet is down again"})

    db = SessionLocal()
    try:
        after = db.query(Ticket).count()
    finally:
        db.close()

    assert after == before


def test_resolve_rejects_empty_message():
    response = client.post("/resolve", json={"message": ""})
    assert response.status_code == 400


def test_resolve_rejects_missing_message():
    response = client.post("/resolve", json={})
    assert response.status_code == 400


def test_resolve_ignores_bearer_token(user_token):
    """Passing a token shouldn't change anything — the route ignores auth entirely."""
    response = client.post(
        "/resolve",
        json={"message": "How do I reset my password?"},
        headers={"Authorization": user_token},
    )
    assert response.status_code == 200
