"""
tests/test_main.py

Tests for app/main.py — Task 1.7: Main Application Entry Point

Covers:
- create_app() returns a FastAPI instance with correct metadata
- CORS middleware is registered
- GET /health returns the exact required response
- Startup lifecycle calls init_db()
- Shutdown lifecycle calls engine.dispose()
- Demo router is registered and reachable
- Health route is accessible at the top level (not nested)
"""
import inspect
from unittest.mock import patch

from fastapi import FastAPI
from fastapi.testclient import TestClient


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def make_client() -> tuple[FastAPI, TestClient]:
    """Create a fresh app instance and TestClient for each test."""
    from app.main import create_app
    application = create_app()
    return application, TestClient(application, raise_server_exceptions=True)


# ---------------------------------------------------------------------------
# TestCreateApp — app factory smoke tests
# ---------------------------------------------------------------------------

class TestCreateApp:
    """Tests for the create_app() factory function."""

    def test_returns_fastapi_instance(self):
        """create_app() must return a FastAPI application."""
        from app.main import create_app
        application = create_app()
        assert isinstance(application, FastAPI)

    def test_app_title(self):
        """App title must match the spec."""
        from app.main import create_app
        application = create_app()
        assert application.title == "Automated Customer Support Resolution System"

    def test_app_version(self):
        """App version must be set."""
        from app.main import create_app
        application = create_app()
        assert application.version == "0.1.0"

    def test_app_description_contains_key_phrases(self):
        """App description must mention core purpose."""
        from app.main import create_app
        application = create_app()
        desc = application.description.lower()
        assert "classif" in desc or "support" in desc  # classifies / support

    def test_module_level_app_is_fastapi(self):
        """The module-level `app` instance must be a FastAPI app."""
        from app.main import app
        assert isinstance(app, FastAPI)

    def test_multiple_create_app_calls_return_independent_instances(self):
        """Each call to create_app() should produce a separate app object."""
        from app.main import create_app
        app1 = create_app()
        app2 = create_app()
        assert app1 is not app2


# ---------------------------------------------------------------------------
# TestHealthEndpoint — /health route
# ---------------------------------------------------------------------------

class TestHealthEndpoint:
    """Tests for GET /health (Technical Spec § 4 / Task 1.7 deliverables)."""

    def test_health_returns_200(self):
        """GET /health must respond with HTTP 200."""
        _, client = make_client()
        response = client.get("/health")
        assert response.status_code == 200

    def test_health_returns_exact_payload(self):
        """GET /health must return exactly the spec-mandated payload."""
        _, client = make_client()
        response = client.get("/health")
        assert response.json() == {
            "status": "ok",
            "service": "automated-customer-support",
        }

    def test_health_status_field(self):
        """health.status must be 'ok'."""
        _, client = make_client()
        data = client.get("/health").json()
        assert data["status"] == "ok"

    def test_health_service_field(self):
        """health.service must be 'automated-customer-support'."""
        _, client = make_client()
        data = client.get("/health").json()
        assert data["service"] == "automated-customer-support"

    def test_health_content_type_is_json(self):
        """GET /health response should be JSON."""
        _, client = make_client()
        response = client.get("/health")
        assert "application/json" in response.headers.get("content-type", "")

    def test_health_route_is_registered_on_app(self):
        """The /health route should appear in the app's route list."""
        from app.main import create_app
        application = create_app()
        routes = [getattr(r, "path", None) for r in application.routes]
        assert "/health" in routes


# ---------------------------------------------------------------------------
# TestCORSMiddleware — CORS configuration
# ---------------------------------------------------------------------------

class TestCORSMiddleware:
    """Tests for CORS middleware registration."""

    def test_cors_middleware_is_registered(self):
        """CORSMiddleware should be in the app's middleware stack."""
        from app.main import create_app
        from fastapi.middleware.cors import CORSMiddleware
        from starlette.middleware import Middleware

        application = create_app()
        # Check user-defined middleware list (FastAPI stores them here before build)
        middleware_types = [
            m.cls if isinstance(m, Middleware) else type(m)
            for m in application.user_middleware
        ]
        assert CORSMiddleware in middleware_types

    def test_cors_allows_origin_header(self):
        """CORS pre-flight OPTIONS should return 200 and allow the origin."""
        _, client = make_client()
        response = client.options(
            "/health",
            headers={
                "Origin": "http://localhost:3000",
                "Access-Control-Request-Method": "GET",
            },
        )
        # Starlette CORS returns 200 for pre-flight when origin is allowed
        assert response.status_code == 200

    def test_cors_response_includes_allow_origin(self):
        """A regular GET to /health with Origin header should reflect the origin."""
        _, client = make_client()
        response = client.get(
            "/health",
            headers={"Origin": "http://localhost:3000"},
        )
        # With allow_origins=["*"], the header value is "*"
        assert "access-control-allow-origin" in response.headers


# ---------------------------------------------------------------------------
# TestLifespan — startup/shutdown lifecycle
# ---------------------------------------------------------------------------

class TestLifespan:
    """Tests for the lifespan context manager (startup and shutdown events)."""

    def test_startup_calls_init_db(self):
        """init_db() must be called once during application startup."""
        with patch("app.main.init_db") as mock_init_db, \
             patch("app.main.engine") as mock_engine:
            from app.main import create_app
            application = create_app()
            with TestClient(application):
                # TestClient triggers startup when entering the context
                mock_init_db.assert_called_once()

    def test_shutdown_calls_engine_dispose(self):
        """engine.dispose() must be called once during application shutdown."""
        with patch("app.main.init_db"), \
             patch("app.main.engine") as mock_engine:
            from app.main import create_app
            application = create_app()
            with TestClient(application):
                pass  # entering & exiting the context triggers startup + shutdown
            mock_engine.dispose.assert_called_once()

    def test_lifespan_function_exists(self):
        """The lifespan async context manager should be importable from main."""
        from app.main import lifespan
        assert inspect.isfunction(lifespan) or callable(lifespan)

    def test_app_has_lifespan_set(self):
        """The FastAPI app must have a lifespan configured (not None)."""
        from app.main import create_app
        application = create_app()
        # FastAPI stores the lifespan on the router
        assert application.router.lifespan_context is not None


# ---------------------------------------------------------------------------
# TestRouterRegistration — routers included in the app
# ---------------------------------------------------------------------------

class TestRouterRegistration:
    """Tests for API router registration."""

    def test_demo_router_users_endpoint_exists(self):
        """GET /demo/users must be reachable (demo router is mounted)."""
        _, client = make_client()
        response = client.get("/demo/users")
        # 200 or 500 (if DB not init'd) — but NOT 404
        assert response.status_code != 404

    def test_demo_router_tables_endpoint_exists(self):
        """GET /demo/tables must be reachable (demo router is mounted)."""
        _, client = make_client()
        response = client.get("/demo/tables")
        assert response.status_code != 404

    def test_unknown_route_returns_404(self):
        """A non-existent route must return 404."""
        _, client = make_client()
        response = client.get("/nonexistent-route-xyz")
        assert response.status_code == 404

    def test_health_not_under_prefix(self):
        """/health must be a top-level route, not nested under /demo or similar."""
        _, client = make_client()
        # Should succeed at /health
        assert client.get("/health").status_code == 200
        # Should NOT exist at /demo/health
        assert client.get("/demo/health").status_code == 404
