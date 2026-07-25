# ==============================================================================
# Multi-stage Dockerfile for X-Agent Production Deployment
# Stages: frontend (Node build) → builder (Python deps) → runtime (minimal)
# ==============================================================================

# ------------------------------------------------------------------------------
# Stage 1: Frontend — build React/Vite static assets
# ------------------------------------------------------------------------------
FROM node:20-alpine AS frontend

WORKDIR /build/frontend

# Leverage layer cache: install deps only when lockfile changes
COPY frontend/package.json frontend/package-lock.json ./
RUN npm ci --ignore-scripts

# Copy source and build
COPY frontend/ ./
RUN npm run build

# ------------------------------------------------------------------------------
# Stage 2: Builder — install Python dependencies into isolated prefix
# ------------------------------------------------------------------------------
FROM python:3.11-slim AS builder

WORKDIR /build

# Build-time system deps (compiled C extensions, libpq headers)
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    libpq-dev \
    && rm -rf /var/lib/apt/lists/*

# Install Python packages into /install (isolated prefix)
COPY requirements-lock.txt pyproject.toml ./
COPY backend/ ./backend/
COPY cli/ ./cli/
RUN pip install --no-cache-dir --upgrade pip setuptools wheel \
    && pip install --no-cache-dir --prefix=/install -r requirements-lock.txt \
    && pip install --no-cache-dir --prefix=/install --no-deps .

# ------------------------------------------------------------------------------
# Stage 3: Runtime — minimal production image
# ------------------------------------------------------------------------------
FROM python:3.11-slim AS runtime

# Runtime system deps only (curl for healthcheck, ca-certificates for TLS)
RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    ca-certificates \
    && rm -rf /var/lib/apt/lists/*

# Security: create non-root user
RUN useradd -m -r -u 1000 xagent \
    && mkdir -p /app/logs /app/data \
    && chown -R xagent:xagent /app

WORKDIR /app

# Copy installed Python packages from builder
COPY --from=builder /install /usr/local

# Copy application code
COPY --chown=xagent:xagent backend/ ./backend/
COPY --chown=xagent:xagent config/ ./config/
COPY --chown=xagent:xagent gunicorn.conf.py ./
COPY --chown=xagent:xagent pyproject.toml ./

# Copy frontend static HTML (served directly by FastAPI)
COPY --chown=xagent:xagent frontend/*.html frontend/*.css ./frontend/
# Copy Vite build output (React SPA)
COPY --from=frontend --chown=xagent:xagent /build/frontend/dist ./frontend/dist/

# Environment
ENV PYTHONUTF8=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PORT=8000 \
    API_WORKERS=4

USER xagent

EXPOSE 8000

HEALTHCHECK --interval=30s --timeout=10s --start-period=40s --retries=3 \
    CMD curl -f http://localhost:${PORT}/health || exit 1

# Production: gunicorn + uvicorn workers
CMD ["gunicorn", "-c", "gunicorn.conf.py", "backend.app.main:app"]
