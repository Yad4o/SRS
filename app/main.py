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

# TODO (later): import routers when they are implemented
# from app.api import auth, tickets, feedback, admin
from app.api import demo

from app.core.config import settings
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
            "Backend service that automatically classifies, "
            "resolves, and escalates customer support tickets "
            "using AI-driven decision logic."
        ),
        version="0.1.0",
        lifespan=lifespan,
    )

    # --------------------------------------------------
    # Middleware Configuration
    # --------------------------------------------------

    # CORS Middleware
    # TODO (production): restrict allowed origins to specific domains
    # TODO (production): allow only required headers
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],  # TODO: restrict in production
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # --------------------------------------------------
    # Router Registration
    # --------------------------------------------------
    # Each router handles a separate domain:
    #   auth     → authentication & authorization
    #   tickets  → ticket lifecycle
    #   feedback → user feedback
    #   admin    → admin metrics & controls

    # TODO: Uncomment these once routers are implemented
    # app.include_router(auth.router, prefix="/auth", tags=["Auth"])
    # app.include_router(tickets.router, prefix="/tickets", tags=["Tickets"])
    # app.include_router(feedback.router, prefix="/feedback", tags=["Feedback"])
    # app.include_router(admin.router, prefix="/admin", tags=["Admin"])
    
    # Demo endpoints for viewing database data
    app.include_router(demo.router, tags=["Demo"])

    # Demo endpoints — only mount in non-production environments.
    # Set ENV=production in your environment to disable these routes.
    if settings.ENV != "production":
        app.include_router(demo.router, tags=["Demo"])

    # --------------------------------------------------
    # Health Check Endpoint
    # --------------------------------------------------

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
