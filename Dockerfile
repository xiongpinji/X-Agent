# syntax=docker/dockerfile:1.7@sha256:a57df69d0ea827fb7266491f2813635de6f17269be881f696fbfdf2d83dda33e
# ==============================================================================
# Multi-stage Dockerfile for X-Agent Production Deployment
# Stages: frontend (Node build) → builder (Python deps) → runtime (minimal)
# ==============================================================================

# ------------------------------------------------------------------------------
# Stage 1: Frontend — build React/Vite static assets
# ------------------------------------------------------------------------------
FROM node:20-alpine@sha256:fb4cd12c85ee03686f6af5362a0b0d56d50c58a04632e6c0fb8363f609372293 AS frontend

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
FROM cgr.dev/chainguard/python:latest-dev@sha256:e80d78c70f4d71290b8ea7adbe2b510a14b0fa87f422be76d0d7c76b2e0fd9f7 AS builder

USER root
WORKDIR /build

# Install Python packages into /install (isolated prefix)
COPY requirements-lock.txt pyproject.toml ./
RUN --mount=type=cache,target=/root/.cache/pip \
    pip install --prefix=/install -r requirements-lock.txt

# Application source changes must not invalidate the production dependency layer.
COPY backend/ ./backend/
COPY cli/ ./cli/
RUN --mount=type=cache,target=/root/.cache/pip \
    PYTHONPATH=/install/lib/python3.14/site-packages \
    pip install --prefix=/install --no-deps --no-build-isolation .

RUN mkdir -p /runtime-root/logs /runtime-root/data \
    && chown -R 65532:65532 /runtime-root

# ------------------------------------------------------------------------------
# Stage 3: Runtime — minimal production image
# ------------------------------------------------------------------------------
FROM cgr.dev/chainguard/python:latest@sha256:e15765ff7066a0eaf91e1b6fd5000c1bba47d62b9f9731f2da560711d910c4f3 AS runtime

WORKDIR /app

# Copy installed Python packages from builder
COPY --from=builder /install /install
COPY --from=builder --chown=65532:65532 /runtime-root/ /app/

# Copy application code
COPY --chown=65532:65532 backend/ ./backend/
COPY --chown=65532:65532 config/ ./config/
COPY --chown=65532:65532 gunicorn.conf.py ./
COPY --chown=65532:65532 pyproject.toml ./

# Copy frontend static HTML (served directly by FastAPI)
COPY --chown=65532:65532 frontend/*.html frontend/*.css ./frontend/
# Copy Vite build output (React SPA)
COPY --from=frontend --chown=65532:65532 /build/frontend/dist ./frontend/dist/

# Environment
ENV PYTHONUTF8=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PYTHONPATH=/install/lib/python3.14/site-packages \
    PATH=/install/bin:/usr/bin \
    PORT=8000 \
    API_WORKERS=4

USER 65532:65532

EXPOSE 8000

HEALTHCHECK --interval=30s --timeout=10s --start-period=40s --retries=3 \
    CMD ["/usr/bin/python", "-c", "import os,urllib.request; urllib.request.urlopen(f'http://127.0.0.1:{os.environ.get(\"PORT\",\"8000\")}/health',timeout=5).read()"]

# Production: gunicorn + uvicorn workers
ENTRYPOINT ["/usr/bin/python"]
CMD ["-m", "gunicorn", "-c", "gunicorn.conf.py", "backend.app.main:app"]
