"""
tests/api/test_agent_router.py

Confirms the agent-only queue actions (assign/accept/close/my-assignments)
live under /agent/* and are no longer reachable under /tickets/*, and that
they still require an authenticated agent/admin.
"""
from tests.conftest import client


def test_old_ticket_paths_are_gone_for_assign():
    response = client.post("/tickets/1/assign")
    assert response.status_code == 404


def test_old_ticket_paths_are_gone_for_close():
    response = client.post("/tickets/1/close")
    assert response.status_code == 404


def test_old_ticket_paths_are_gone_for_accept():
    response = client.post("/tickets/1/accept")
    assert response.status_code == 404


def test_old_ticket_paths_are_gone_for_my_assignments():
    # "/tickets/my-assignments" now matches the "/tickets/{ticket_id}" route,
    # and "my-assignments" fails int path-param validation -> 400, not 404.
    response = client.get("/tickets/my-assignments")
    assert response.status_code == 400


def test_agent_routes_require_auth():
    assert client.get("/agent/my-assignments").status_code in (401, 403)
    assert client.post("/agent/tickets/1/assign").status_code in (401, 403)
    assert client.post("/agent/tickets/1/accept").status_code in (401, 403)
    assert client.post("/agent/tickets/1/close").status_code in (401, 403)


def test_regular_user_cannot_hit_agent_routes(user_token):
    response = client.get("/agent/my-assignments", headers={"Authorization": user_token})
    assert response.status_code == 403
