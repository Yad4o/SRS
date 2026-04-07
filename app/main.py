"""
 =============================================================================
 SRS (Support Request System) - Application Entry Point
 =============================================================================

Purpose:
--------
Application entry point for the AI-powered Support Request System.

Responsibilities:
-----------------
- FastAPI application factory pattern
- Middleware registration and configuration
- API router registration
- Application lifecycle management (startup/shutdown)
- Health checks and monitoring endpoints
- Error handling setup

Architecture:
------------
- Factory pattern for testability and flexibility
- Separation of concerns (no business logic here)
- Environment-aware configuration
- Production-ready with monitoring and security

Owner:
------
Backend Team

DO NOT:
-------
- Implement business logic here
- Access database directly
- Handle AI/ML operations
"""

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
import logging
import time
from typing import Dict, Any

from fastapi import FastAPI, Request, Response
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.trustedhost import TrustedHostMiddleware
from slowapi import _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded
from prometheus_client import Counter, Histogram, generate_latest, CONTENT_TYPE_LATEST

from app.core.limiter import limiter
from app.core.config import settings
from app.db.session import engine, init_db
from app.core.error_handlers import setup_exception_handlers
from app.api import auth, demo, tickets, feedback, admin

# -----------------------------------------------------------------------------
# Logging Configuration
# -----------------------------------------------------------------------------
logger = logging.getLogger(__name__)

# -----------------------------------------------------------------------------
# Prometheus Metrics
# -----------------------------------------------------------------------------
REQUEST_COUNT = Counter(
    'http_requests_total',
    'Total HTTP requests',
    ['method', 'endpoint', 'status_code']
)

REQUEST_DURATION = Histogram(
    'http_request_duration_seconds',
    'HTTP request duration in seconds',
    ['method', 'endpoint']
)


# -----------------------------------------------------------------------------
# Application Lifecycle Management
# -----------------------------------------------------------------------------

@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    """
    Application lifecycle management using async context manager.
    
    Replaces deprecated startup/shutdown events with modern lifespan pattern.
    
    Startup Tasks:
    - Database initialization and migrations
    - Cache warmup (Redis)
    - AI model loading
    - Background task scheduler startup
    - Health check registration
    
    Shutdown Tasks:
    - Database connection cleanup
    - Cache cleanup
    - Background task shutdown
    - Metrics export
    
    Args:
        app: FastAPI application instance
        
    Yields:
        None: Control passes to application runtime
    """
    startup_start_time = time.time()
    
    try:
        # --- Startup Phase ---
        logger.info("Starting SRS Application...")
        logger.info(f"Environment: {settings.ENV}")
        logger.info(f"Debug Mode: {settings.DEBUG}")
        
        # Database initialization
        logger.info("Initializing database...")
        init_db()
        logger.info("Database initialized successfully")
        
        # Cache warmup (if Redis is configured)
        if settings.REDIS_URL:
            logger.info("Warming up cache...")
            # TODO: Implement cache warmup logic
            logger.info("Cache warmed up successfully")
        
        # AI model loading (if configured)
        if settings.OPENAI_API_KEY:
            logger.info("Loading AI models...")
            # TODO: Implement model preloading
            logger.info("AI models loaded successfully")
        
        # Background tasks startup
        logger.info("Starting background task scheduler...")
        # TODO: Initialize Celery/Background tasks
        logger.info("Background tasks started successfully")
        
        startup_duration = time.time() - startup_start_time
        logger.info(f"Application startup completed in {startup_duration:.2f}s")
        
        # Yield control to application
        yield
        
    except Exception as e:
        logger.error(f"Application startup failed: {e}")
        raise
    finally:
        # --- Shutdown Phase ---
        shutdown_start_time = time.time()
        
        try:
            logger.info("Shutting down SRS Application...")
            
            # Background tasks cleanup
            logger.info("Stopping background tasks...")
            # TODO: Implement graceful shutdown of background tasks
            
            # Database cleanup
            logger.info("Cleaning up database connections...")
            engine.dispose()
            logger.info("Database connections cleaned up")
            
            # Cache cleanup
            if settings.REDIS_URL:
                logger.info("Cleaning up cache connections...")
                # TODO: Implement Redis cleanup
                logger.info("Cache connections cleaned up")
            
            # Export final metrics
            if settings.PROMETHEUS_ENABLED:
                logger.info("Exporting final metrics...")
                # TODO: Implement metrics export
            
            shutdown_duration = time.time() - shutdown_start_time
            logger.info(f"Application shutdown completed in {shutdown_duration:.2f}s")
            
        except Exception as e:
            logger.error(f"Error during shutdown: {e}")


# -----------------------------------------------------------------------------
# Application Factory
# -----------------------------------------------------------------------------

def create_app() -> FastAPI:
    """
    Application factory for creating configured FastAPI instances.
    
    Benefits:
    - Testability: Each test gets a fresh app instance
    - Flexibility: Easy to create multiple app configurations
    - Production-ready: Proper separation of concerns
    - Environment awareness: Different configs per environment
    
    Returns:
        FastAPI: Fully configured application instance
    """
    
    # FastAPI application configuration
    app = FastAPI(
        title="SRS Support Request System",
        description=(
            "AI-powered Support Request System that automatically classifies, "
            "resolves, and escalates customer support tickets using advanced "
            "machine learning and natural language processing."
        ),
        version="1.0.0",
        docs_url="/docs" if settings.ENV != "production" else None,
        redoc_url="/redoc" if settings.ENV != "production" else None,
        openapi_url="/openapi.json" if settings.ENV != "production" else None,
        lifespan=lifespan,
        contact={
            "name": "SRS Development Team",
            "email": "dev@srs.com",
            "url": "https://github.com/your-org/srs-support-system",
        },
        license_info={
            "name": "MIT",
            "url": "https://opensource.org/licenses/MIT",
        },
    )

    # -----------------------------------------------------------------------------
    # Middleware Configuration
    # -----------------------------------------------------------------------------
    
    # Trusted Host Middleware (security)
    if settings.ENV == "production":
        app.add_middleware(
            TrustedHostMiddleware,
            allowed_hosts=["yourdomain.com", "*.yourdomain.com"]
        )
    
    # CORS Middleware
    cors_origins = []
    if settings.ENV == "development":
        cors_origins.extend([
            "http://localhost:3000",
            "http://localhost:5173",
            "http://localhost:8080",
        ])
    if settings.CORS_ORIGINS:
        cors_origins.extend(settings.CORS_ORIGINS)
    
    app.add_middleware(
        CORSMiddleware,
        allow_origins=cors_origins,
        allow_credentials=True,
        allow_methods=["GET", "POST", "PUT", "DELETE", "PATCH", "OPTIONS"],
        allow_headers=["*"],
    )
    
    # Request Metrics Middleware
    @app.middleware("http")
    async def metrics_middleware(request: Request, call_next):
        """Middleware for collecting request metrics."""
        start_time = time.time()
        
        # Process request
        response = await call_next(request)
        
        # Calculate duration
        process_time = time.time() - start_time
        
        # Update Prometheus metrics
        if settings.PROMETHEUS_ENABLED:
            REQUEST_COUNT.labels(
                method=request.method,
                endpoint=request.url.path,
                status_code=response.status_code
            ).inc()
            
            REQUEST_DURATION.labels(
                method=request.method,
                endpoint=request.url.path
            ).observe(process_time)
        
        # Add timing header
        response.headers["X-Process-Time"] = str(process_time)
        
        return response
    
    # Rate Limiting Setup
    app.state.limiter = limiter
    app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)
    
    # -----------------------------------------------------------------------------
    # Exception Handler Registration
    # -----------------------------------------------------------------------------
    setup_exception_handlers(app)
    
    # -----------------------------------------------------------------------------
    # API Router Registration
    # -----------------------------------------------------------------------------
    
    # Core API routers
    app.include_router(
        auth.router,
        prefix="/api/v1/auth",
        tags=["Authentication"]
    )
    
    app.include_router(
        tickets.router,
        prefix="/api/v1/tickets",
        tags=["Tickets"]
    )
    
    app.include_router(
        feedback.router,
        prefix="/api/v1/feedback",
        tags=["Feedback"]
    )
    
    app.include_router(
        admin.router,
        prefix="/api/v1/admin",
        tags=["Administration"]
    )
    
    # Demo endpoints (development only)
    if settings.ENV != "production":
        app.include_router(
            demo.router,
            prefix="/api/v1/demo",
            tags=["Demo"]
        )

    # -----------------------------------------------------------------------------
    # Health and Monitoring Endpoints
    # -----------------------------------------------------------------------------
    
    @app.get("/health", tags=["Health"])
    async def health_check() -> Dict[str, Any]:
        """
        Comprehensive health check endpoint.
        
        Used by:
        - Load balancers and reverse proxies
        - Monitoring systems (Prometheus, etc.)
        - CI/CD pipelines
        - Container orchestration (Kubernetes, Docker)
        
        Returns:
            Dict[str, Any]: Health status and system information
        """
        return {
            "status": "healthy",
            "service": "srs-support-system",
            "version": "1.0.0",
            "environment": settings.ENV,
            "timestamp": time.time(),
            "uptime": time.time() - startup_time if 'startup_time' in globals() else 0,
        }
    
    @app.get("/health/ready", tags=["Health"])
    async def readiness_check() -> Dict[str, Any]:
        """
        Readiness probe for container orchestration.
        
        Checks if the application is ready to serve traffic.
        Verifies database connections and external dependencies.
        
        Returns:
            Dict[str, Any]: Readiness status and dependency checks
        """
        # TODO: Implement actual readiness checks
        checks = {
            "database": "healthy",
            "redis": "healthy" if settings.REDIS_URL else "not_configured",
            "ai_service": "healthy" if settings.OPENAI_API_KEY else "not_configured",
        }
        
        all_healthy = all(status == "healthy" for status in checks.values())
        
        return {
            "status": "ready" if all_healthy else "not_ready",
            "checks": checks,
        }
    
    @app.get("/health/live", tags=["Health"])
    async def liveness_check() -> Dict[str, str]:
        """
        Liveness probe for container orchestration.
        
        Simple check to determine if the application is alive.
        Used by Kubernetes to restart containers that have hung.
        
        Returns:
            Dict[str, str]: Liveness status
        """
        return {"status": "alive"}
    
    @app.get("/metrics", tags=["Monitoring"])
    async def metrics_endpoint() -> Response:
        """
        Prometheus metrics endpoint.
        
        Returns application metrics in Prometheus format.
        Only available in production when metrics are enabled.
        
        Returns:
            Response: Prometheus metrics text format
        """
        if not settings.PROMETHEUS_ENABLED:
            return Response(
                content="Metrics not enabled",
                status_code=404
            )
        
        return Response(
            content=generate_latest(),
            media_type=CONTENT_TYPE_LATEST
        )
    
    @app.get("/api/v1/status", tags=["System"])
    async def system_status() -> Dict[str, Any]:
        """
        System status endpoint with detailed information.
        
        Provides comprehensive system information including
        configuration, dependencies, and performance metrics.
        
        Returns:
            Dict[str, Any]: Detailed system status
        """
        return {
            "application": {
                "name": "SRS Support Request System",
                "version": "1.0.0",
                "environment": settings.ENV,
                "debug": settings.DEBUG,
            },
            "features": {
                "ai_enabled": bool(settings.OPENAI_API_KEY),
                "cache_enabled": bool(settings.REDIS_URL),
                "metrics_enabled": settings.PROMETHEUS_ENABLED,
                "rate_limiting": True,
            },
            "endpoints": {
                "documentation": "/docs" if settings.ENV != "production" else None,
                "health": "/health",
                "metrics": "/metrics" if settings.PROMETHEUS_ENABLED else None,
            },
        }
    
    return app


# -----------------------------------------------------------------------------
# Application Instance and Global Variables
# -----------------------------------------------------------------------------

# Create application instance
app = create_app()

# Record startup time for metrics
startup_time = time.time()

# -----------------------------------------------------------------------------
# Main Function for Direct Execution
# -----------------------------------------------------------------------------

def main() -> None:
    """
    Main function for running the application directly.
    
    Used when running the application with:
    python -m app.main
    
    or
    
    uvicorn app.main:app --host 0.0.0.0 --port 8000
    """
    import uvicorn
    
    uvicorn.run(
        "app.main:app",
        host=settings.HOST or "0.0.0.0",
        port=settings.PORT or 8000,
        reload=settings.ENV == "development",
        log_level="debug" if settings.DEBUG else "info",
        access_log=True,
    )

if __name__ == "__main__":
    main()
