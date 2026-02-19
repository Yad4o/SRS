"""
app/main.py

Application entry point for the Automated Customer Support Resolution System.

This file is responsible ONLY for:
- Creating the FastAPI application
- Registering middleware
- Attaching API routers
- Managing startup and shutdown events

⚠️ IMPORTANT:
- Do NOT put business logic here
- Do NOT access the database directly here
- Do NOT implement AI logic here
"""

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

# TODO (later): import routers when they are implemented
# from app.api import auth, tickets, feedback, admin

from app.db.session import init_db


def create_app() -> FastAPI:
    """
    Application factory.

    Why factory pattern?
    - Easier testing
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
    )

    # --------------------------------------------------
    # Middleware Configuration
    # --------------------------------------------------

    """
    CORS Middleware

    TODO (production):
    - Restrict allowed origins
    - Allow only required headers
    """

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

    """
    API Routers

    Each router handles a separate domain:
    - auth      → authentication & authorization
    - tickets   → ticket lifecycle
    - feedback  → user feedback
    - admin     → admin metrics & controls
    """

    # TODO: Uncomment these once routers are implemented
    # app.include_router(auth.router, prefix="/auth", tags=["Auth"])
    # app.include_router(tickets.router, prefix="/tickets", tags=["Tickets"])
    # app.include_router(feedback.router, prefix="/feedback", tags=["Feedback"])
    # app.include_router(admin.router, prefix="/admin", tags=["Admin"])

    # --------------------------------------------------
    # Application Lifecycle Events
    # --------------------------------------------------

    @app.on_event("startup")
    async def on_startup() -> None:
        """
        Runs once when the application starts.

        Typical startup tasks:
        - Initialize database connections
        - Connect to Redis / cache
        - Warm up AI models (optional)
        """

        init_db()

    @app.on_event("shutdown")
    async def on_shutdown() -> None:
        """
        Runs once when the application shuts down.

        Typical shutdown tasks:
        - Close database connections
        - Gracefully stop background workers
        """

        from app.db.session import engine

        engine.dispose()

    return app


# --------------------------------------------------
# Application Instance
# --------------------------------------------------

app = create_app()


# --------------------------------------------------
# Health Check Endpoint
# --------------------------------------------------

@app.get("/health", tags=["Health"])
async def health_check() -> dict:
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
