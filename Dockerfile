# =============================================================================
# SRS (Support Request System) - Production Docker Image
# =============================================================================
# Multi-stage build for optimized production deployment

# -----------------------------------------------------------------------------
# Build Stage
# -----------------------------------------------------------------------------
FROM python:3.11-slim as builder

# Set build arguments
ARG BUILD_ENV=production
ARG APP_VERSION=1.0.0

# Set environment variables for building
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

# Install build dependencies
RUN apt-get update \
    && apt-get install -y --no-install-recommends \
        build-essential \
        curl \
        git \
        gcc \
        libpq-dev \
    && rm -rf /var/lib/apt/lists/*

# Create and activate virtual environment
RUN python -m venv /opt/venv
ENV PATH="/opt/venv/bin:$PATH"

# Upgrade pip and install wheel for faster builds
RUN pip install --upgrade pip setuptools wheel

# Copy requirements and install Python dependencies
COPY requirements.txt .
RUN pip install -r requirements.txt

# -----------------------------------------------------------------------------
# Production Stage
# -----------------------------------------------------------------------------
FROM python:3.11-slim as production

# Set labels for metadata
LABEL maintainer="SRS Development Team <dev@srs.com>" \
      version="${APP_VERSION}" \
      description="SRS Support Request System" \
      org.opencontainers.image.source="https://github.com/your-org/srs-support-system"

# Set environment variables
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PATH="/opt/venv/bin:$PATH" \
    APP_ENV=${BUILD_ENV} \
    APP_VERSION=${APP_VERSION}

# Install runtime dependencies only
RUN apt-get update \
    && apt-get install -y --no-install-recommends \
        curl \
        postgresql-client \
        netcat-traditional \
        ca-certificates \
    && rm -rf /var/lib/apt/lists/* \
    && apt-get clean

# Copy virtual environment from builder stage
COPY --from=builder /opt/venv /opt/venv

# Create application directory structure
WORKDIR /app
RUN mkdir -p /app/logs /app/temp /app/uploads

# Create non-root user with proper permissions
RUN groupadd -r appuser && useradd -r -g appuser --home-dir /app --shell /bin/bash appuser

# Copy application code with proper permissions
COPY --chown=appuser:appuser . .

# Set ownership of application directory
RUN chown -R appuser:appuser /app

# Switch to non-root user
USER appuser

# Verify installation and run health checks
RUN python -c "import fastapi, sqlalchemy, pydantic; print('Dependencies verified')"

# Create startup script
RUN echo '#!/bin/bash\n\
set -e\n\
echo "Starting SRS Application..."\n\
echo "Environment: $APP_ENV"\n\
echo "Version: $APP_VERSION"\n\
echo "Python: $(python --version)"\n\
echo "Working Directory: $(pwd)"\n\
echo "User: $(whoami)"\n\
\n\
# Wait for database if configured\n\
if [ -n "$DATABASE_URL" ]; then\n\
    echo "Waiting for database..."\n\
    timeout 60 bash -c "until nc -z ${DB_HOST:-localhost} ${DB_PORT:-5432}; do sleep 1; done"\n\
    echo "Database is ready!"\n\
fi\n\
\n\
# Wait for Redis if configured\n\
if [ -n "$REDIS_URL" ]; then\n\
    echo "Waiting for Redis..."\n\
    timeout 60 bash -c "until nc -z ${REDIS_HOST:-localhost} ${REDIS_PORT:-6379}; do sleep 1; done"\n\
    echo "Redis is ready!"\n\
fi\n\
\n\
# Run database migrations if in production\n\
if [ "$APP_ENV" = "production" ]; then\n\
    echo "Running database migrations..."\n\
    alembic upgrade head\n\
fi\n\
\n\
echo "Starting application server..."\n\
exec "$@"' > /app/start.sh && chmod +x /app/start.sh

# Expose port
EXPOSE 8000

# Health check with comprehensive validation
HEALTHCHECK --interval=30s --timeout=30s --start-period=60s --retries=3 \
    CMD curl -f http://localhost:8000/health || exit 1

# Set entrypoint and command
ENTRYPOINT ["/app/start.sh"]
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000", "--workers", "1"]

# -----------------------------------------------------------------------------
# Development Stage (optional)
# -----------------------------------------------------------------------------
FROM production as development

# Switch back to root for development tools
USER root

# Install development dependencies
RUN pip install --no-cache-dir \
    black==23.9.0 \
    isort==5.12.0 \
    flake8==6.1.0 \
    pytest==7.4.3

# Switch back to app user
USER appuser

# Override command for development
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000", "--reload", "--log-level", "debug"]
