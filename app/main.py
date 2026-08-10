"""
app/main.py

Application entry point for the Automated Customer Support Resolution System.

This file is responsible ONLY for:
- Creating the FastAPI application
- Registering middleware
- Attaching API routers
- Managing startup and shutdown events via lifespan

⚠️ IMPORTANT:
- Do NOT put business logic here
- Do NOT access the database directly here
- Do NOT implement AI logic here
"""

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from slowapi import _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded
from app.core.limiter import limiter

from app.api import auth, demo, tickets, feedback, admin, public
from app.core.config import settings
from app.core.error_handlers import setup_exception_handlers
from app.db.session import engine, init_db


# --------------------------------------------------
# Application Lifespan (startup / shutdown)
# --------------------------------------------------

@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    """
    Manages the application lifecycle using an async context manager.

    Replaces the deprecated @app.on_event("startup") / @app.on_event("shutdown")
    pattern. FastAPI runs the code before `yield` on startup and after `yield`
    on shutdown.

    Startup tasks:
    - Initialize database connections / create tables

    Shutdown tasks:
    - Dispose of SQLAlchemy engine connection pool
    """
    # --- Startup ---
    init_db()

    yield

    # --- Shutdown ---
    engine.dispose()


# --------------------------------------------------
# Application Factory
# --------------------------------------------------

def create_app() -> FastAPI:
    """
    Application factory.

    Why factory pattern?
    - Easier testing (each test can get a fresh app instance)
    - Cleaner dependency injection
    - Production-ready architecture

    Returns:
        FastAPI: Configured FastAPI application
    """

    app = FastAPI(
        title="Automated Customer Support Resolution System",
        description=(
            "AI-powered support message classifier and auto-responder.\n\n"
            "**No login needed.** Send a message to `POST /resolve` and get an "
            "instant classification plus (when confident) a generated answer — "
            "free to call, nothing to sign up for. Everything else in this API "
            "(ticket history, agent queues, admin metrics) is optional and lives "
            "behind auth for teams that want it."
        ),
        version="0.1.0",
        lifespan=lifespan,
        openapi_tags=[
            {
                "name": "Tickets",
                "description": "Create and view support tickets. No login needed to create one.",
            },
            {
                "name": "Feedback",
                "description": "Rate how well a resolved ticket's answer worked.",
            },
            {
                "name": "Admin",
                "description": "Admin-only metrics and controls. Requires an admin token.",
            },
            {
                "name": "Authentication",
                "description": "Register, log in, and manage sessions — only needed for the agent/admin dashboard, not for basic ticket use.",
            },
            {
                "name": "Demo",
                "description": "Sample data browsing for local development. Disabled in production.",
            },
            {
                "name": "Health",
                "description": "Service status checks.",
            },
        ],
    )

    # --------------------------------------------------
    # Middleware Configuration
    # --------------------------------------------------

    # CORS Middleware
    #
    # Wide open on purpose: this API is designed to be called directly from
    # other people's frontends (the whole point of POST /resolve is "embed
    # this in your repo"), and auth here is a Bearer token in the
    # Authorization header, never a cookie — so allow_credentials=False +
    # allow_origins=["*"] is safe. If cookie-based auth is ever introduced,
    # this needs to go back to an explicit origin allowlist.
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.CORS_ORIGINS if settings.CORS_ORIGINS else ["*"],
        allow_credentials=False,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # Rate Limit Setup (decorator-only mode)
    app.state.limiter = limiter
    app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)
    # SlowAPIMiddleware is NOT added - decorator-only mode avoids response wrapping issues

    # --------------------------------------------------
    # Exception Handler Registration
    # --------------------------------------------------
    setup_exception_handlers(app)

    # --------------------------------------------------
    # Router Registration
    # --------------------------------------------------
    # Each router handles a separate domain:
    #   public   → the free, no-login single-endpoint API (start here)
    #   auth     → authentication & authorization
    #   tickets  → ticket lifecycle
    #   feedback → user feedback
    #   admin    → admin metrics & controls
    #
    # `public` is registered first so it's the first thing listed in
    # /docs — it's the one endpoint most integrators actually need.
    app.include_router(public.router, tags=["Public API"])

    app.include_router(tickets.router, tags=["Tickets"])
    app.include_router(feedback.router, tags=["Feedback"])
    app.include_router(admin.router, tags=["Admin"])
    app.include_router(auth.router)
    
    # Demo endpoints — only mount in non-production environments.
    # Set ENV=production in your environment to disable these routes.
    if settings.ENV != "production":
        app.include_router(demo.router, tags=["Demo"])

    # --------------------------------------------------
    # Health Check Endpoint
    # --------------------------------------------------

    @app.get("/", tags=["Health"])
    def root() -> dict:
        """
        Landing route — points people at the one endpoint that matters.

        Returns:
            dict: Quick pointers to docs and the public resolve endpoint.
        """
        return {
            "service": "automated-customer-support",
            "try_it": "POST /resolve  (no login required)",
            "docs": "/docs",
        }

    @app.get("/health", tags=["Health"])
    def health_check() -> dict:
        """
        Health check endpoint.

        Used by:
        - Load balancers
        - Monitoring systems
        - CI/CD pipelines

        Returns:
            dict: Basic service health information
        """
        return {
            "status": "ok",
            "service": "automated-customer-support",
        }

    return app


# --------------------------------------------------
# Application Instance
# --------------------------------------------------

app = create_app()
