.PHONY: help install install-dev install-all dev test test-unit test-serial test-integration test-contract test-e2e test-coverage test-performance lint format format-check type-check security security-check-deps pre-commit-install pre-commit-run pre-commit-update ci ci-full quality build docker-build docker-push docker-run deploy deploy-staging deploy-production clean clean-docker clean-all monitor-start monitor-stop monitor-logs monitor-status run run-worker version status requirements-update demo demo-seed demo-reset demo-quickstart smoke smoke-full

# Variables
PYTHON := python3 -X utf8
PIP := pip3
DOCKER := docker

# Force UTF-8 mode for Windows Chinese path compatibility
export PYTHONUTF8 := 1
DOCKER_COMPOSE := docker-compose
PROJECT_NAME := x-agent-core
PYTHON_VERSION := 3.11
VERSION := $(shell git describe --tags --always 2>/dev/null || echo "0.1.0")
REGISTRY := ghcr.io
IMAGE_NAME := $(REGISTRY)/$(PROJECT_NAME)
DOCKER_TAG := $(IMAGE_NAME):$(VERSION)

# Colors for output
BLUE := \033[0;34m
GREEN := \033[0;32m
RED := \033[0;31m
NC := \033[0m # No Color

help:
	@echo "$(BLUE)X-Agent Core - Development Commands$(NC)"
	@echo ""
	@echo "$(GREEN)Setup:$(NC)"
	@echo "  make install          Install production dependencies"
	@echo "  make install-dev      Install development dependencies"
	@echo "  make install-all      Install all dependencies"
	@echo "  make dev              Setup development environment"
	@echo ""
	@echo "$(GREEN)Testing:$(NC)"
	@echo "  make test             Run all tests (unit + integration + contract + e2e)"
	@echo "  make test-unit        Run unit tests (parallel with -n auto)"
	@echo "  make test-serial      Run unit tests serially (for debugging)"
	@echo "  make test-integration Run integration tests"
	@echo "  make test-contract    Run contract tests"
	@echo "  make test-e2e         Run end-to-end tests"
	@echo "  make test-coverage    Generate coverage report"
	@echo "  make test-performance Run performance tests"
	@echo "  make smoke            Run full-stack smoke test"
	@echo "  make smoke-full       Start docker services + run smoke test"
	@echo ""
	@echo "$(GREEN)Code Quality:$(NC)"
	@echo "  make lint             Run linting checks (ruff + tsc)"
	@echo "  make format           Format code (ruff, isort)"
	@echo "  make format-check     Check code formatting"
	@echo "  make type-check       Run type checking (mypy)"
	@echo "  make security         Run security scans (bandit)"
	@echo "  make security-check-deps Check for vulnerable dependencies"
	@echo "  make quality          Run all quality gates (lint + type-check + security + test)"
	@echo ""
	@echo "$(GREEN)Pre-commit:$(NC)"
	@echo "  make pre-commit-install Install pre-commit hooks"
	@echo "  make pre-commit-run   Run pre-commit hooks on all files"
	@echo "  make pre-commit-update Update pre-commit hooks"
	@echo ""
	@echo "$(GREEN)Build & Deploy:$(NC)"
	@echo "  make build            Build (format, lint, type-check, test)"
	@echo "  make docker-build     Build Docker image"
	@echo "  make docker-push      Push Docker image to registry"
	@echo "  make docker-run       Run Docker image locally"
	@echo "  make deploy           Deploy to staging"
	@echo "  make deploy-staging   Deploy to staging environment"
	@echo "  make deploy-production Deploy to production environment"
	@echo ""
	@echo "$(GREEN)CI/CD:$(NC)"
	@echo "  make ci               Run CI checks (lint, type-check, test)"
	@echo "  make ci-full          Run full CI pipeline"
	@echo ""
	@echo "$(GREEN)Demo:$(NC)"
	@echo "  make demo             Seed demo data + start server"
	@echo "  make demo-seed        Seed demo data only"
	@echo "  make demo-reset       Reset and re-seed demo data"
	@echo "  make demo-quickstart  Full quickstart (seed + server + browser)"
	@echo ""
	@echo "$(GREEN)Development:$(NC)"
	@echo "  make run              Run application locally"
	@echo "  make run-worker       Run workflow worker"
	@echo ""
	@echo "$(GREEN)Database Migrations:$(NC)"
	@echo "  make migrate          Run all pending migrations"
	@echo "  make migrate-down     Rollback last migration"
	@echo "  make migrate-create   Create new migration"
	@echo "  make migrate-status   Show current migration status"
	@echo ""
	@echo "$(GREEN)Monitoring:$(NC)"
	@echo "  make monitor-start    Start monitoring stack"
	@echo "  make monitor-stop     Stop monitoring stack"
	@echo "  make monitor-logs     View monitoring stack logs"
	@echo "  make monitor-status   Check monitoring stack status"
	@echo ""
	@echo "$(GREEN)Utilities:$(NC)"
	@echo "  make version          Show project version"
	@echo "  make status           Show project status"
	@echo "  make requirements-update Update requirements.txt"
	@echo ""
	@echo "$(GREEN)Cleanup:$(NC)"
	@echo "  make clean            Clean up temporary files and caches"
	@echo "  make clean-docker     Clean up Docker containers and volumes"
	@echo "  make clean-all        Full cleanup"

# ============================================================================
# Setup Commands
# ============================================================================

install:
	@echo "$(BLUE)Installing production dependencies...$(NC)"
	$(PIP) install --upgrade pip setuptools wheel
	$(PIP) install -r requirements.txt

install-dev:
	@echo "$(BLUE)Installing development dependencies...$(NC)"
	$(PIP) install --upgrade pip setuptools wheel
	$(PIP) install -e ".[dev,test]"
	pre-commit install

install-all: install install-dev
	@echo "$(GREEN)All dependencies installed!$(NC)"

dev: install-dev pre-commit-install
	@echo "$(GREEN)Development environment setup completed!$(NC)"

# ============================================================================
# Development Commands
# ============================================================================

# Testing targets
test: test-unit test-integration test-contract test-e2e
	@echo "$(GREEN)All tests completed!$(NC)"

test-unit:
	@echo "$(BLUE)Running unit tests (parallel)...$(NC)"
	pytest tests/unit/ --no-cov -q --tb=short -n auto

test-serial:
	@echo "$(BLUE)Running unit tests (serial, for debugging)...$(NC)"
	pytest tests/unit/ --no-cov -q --tb=short -p no:xdist

test-integration:
	@echo "$(BLUE)Running integration tests...$(NC)"
	pytest tests/integration/ --no-cov -q --tb=short -n auto

test-contract:
	@echo "$(BLUE)Running contract tests...$(NC)"
	pytest tests/ -m "contracts" --no-cov -q --tb=short

test-e2e:
	@echo "$(BLUE)Running E2E tests...$(NC)"
	pytest tests/e2e/ --no-cov -q --tb=short

test-coverage:
	@echo "$(BLUE)Generating coverage report...$(NC)"
	pytest tests/ \
		--cov=backend \
		--cov-report=html \
		--cov-report=term-missing \
		--cov-report=xml \
		-v
	@echo "$(GREEN)Coverage report generated in htmlcov/index.html$(NC)"

test-performance:
	@echo "$(BLUE)Running performance tests...$(NC)"
	pytest tests/ -m "performance" -v --tb=short

# Database migration targets (Alembic)
db-migrate:
	@echo "$(BLUE)Running database migrations (alembic upgrade head)...$(NC)"
	alembic upgrade head
	@echo "$(GREEN)Migrations completed!$(NC)"

db-revision:
	@echo "$(BLUE)Auto-generating new revision...$(NC)"
	@read -p "Revision message: " msg; \
	alembic revision --autogenerate -m "$$msg"

migrate:
	@echo "$(BLUE)Running database migrations...$(NC)"
	alembic -c backend/migrations/alembic.ini upgrade head
	@echo "$(GREEN)Migrations completed!$(NC)"

migrate-down:
	@echo "$(BLUE)Rolling back last migration...$(NC)"
	alembic -c backend/migrations/alembic.ini downgrade -1

migrate-create:
	@echo "$(BLUE)Creating new migration...$(NC)"
	@read -p "Migration message: " msg; \
	alembic -c backend/migrations/alembic.ini revision -m "$$msg"

migrate-autogenerate:
	@echo "$(BLUE)Auto-generating migration from models...$(NC)"
	@read -p "Migration message: " msg; \
	alembic -c backend/migrations/alembic.ini revision --autogenerate -m "$$msg"

migrate-status:
	@echo "$(BLUE)Current migration status:$(NC)"
	alembic -c backend/migrations/alembic.ini current

migrate-history:
	@echo "$(BLUE)Migration history:$(NC)"
	alembic -c backend/migrations/alembic.ini history --verbose

# Code quality targets
lint:
	@echo "$(BLUE)Running linting checks...$(NC)"
	@echo "$(GREEN)Running ruff check (blocking: F,E9)...$(NC)"
	ruff check backend/ --select F,E9
	@echo "$(GREEN)Running ruff check (full, informational)...$(NC)"
	ruff check backend/ tests/ --output-format=github || true
	@echo "$(GREEN)Running TypeScript check...$(NC)"
	cd frontend && npx tsc --noEmit
	@echo "$(GREEN)Linting complete!$(NC)"

format:
	@echo "$(BLUE)Formatting code...$(NC)"
	@echo "$(GREEN)Running ruff format...$(NC)"
	ruff format backend/ tests/
	@echo "$(GREEN)Running isort...$(NC)"
	isort backend/ tests/
	@echo "$(GREEN)Code formatting complete!$(NC)"

format-check:
	@echo "$(BLUE)Checking code formatting...$(NC)"
	ruff format --check backend/ tests/
	isort --check-only backend/ tests/

type-check:
	@echo "$(BLUE)Running type checks...$(NC)"
	mypy backend/ --ignore-missing-imports --no-strict-optional

security:
	@echo "$(BLUE)Running security checks...$(NC)"
	bandit -r backend/app/ -ll --skip B101 || true
	@echo "$(GREEN)Security check completed!$(NC)"

security-check-deps:
	@echo "$(BLUE)Checking for vulnerable dependencies...$(NC)"
	pip-audit --desc
	safety check

# Pre-commit targets
pre-commit-install:
	@echo "$(BLUE)Installing pre-commit hooks...$(NC)"
	pre-commit install

pre-commit-run:
	@echo "$(BLUE)Running pre-commit hooks...$(NC)"
	pre-commit run --all-files

pre-commit-update:
	@echo "$(BLUE)Updating pre-commit hooks...$(NC)"
	pre-commit autoupdate

# ============================================================================
# CI/CD Commands
# ============================================================================

ci: lint type-check test
	@echo "$(GREEN)CI checks passed!$(NC)"

ci-full: clean lint type-check security-check-deps test docker-build
	@echo "$(GREEN)Full CI pipeline completed!$(NC)"

quality: lint type-check security test
	@echo "$(GREEN)All quality gates passed!$(NC)"

build: format lint type-check test
	@echo "$(GREEN)Build completed successfully!$(NC)"

docker-build:
	@echo "$(BLUE)Building Docker image: $(DOCKER_TAG)$(NC)"
	$(DOCKER) build \
		--tag $(DOCKER_TAG) \
		--build-arg VERSION=$(VERSION) \
		--build-arg BUILD_DATE=$$(date -u +'%Y-%m-%dT%H:%M:%SZ') \
		--build-arg VCS_REF=$$(git rev-parse --short HEAD) \
		.
	@echo "$(GREEN)Docker image built: $(DOCKER_TAG)$(NC)"

docker-push: docker-build
	@echo "$(BLUE)Pushing Docker image to registry...$(NC)"
	$(DOCKER) push $(DOCKER_TAG)
	@echo "$(GREEN)Docker image pushed: $(DOCKER_TAG)$(NC)"

docker-run: docker-build
	@echo "$(BLUE)Running Docker image...$(NC)"
	$(DOCKER) run -it --rm \
		-p 8000:8000 \
		-e DATABASE_URL=postgresql://xagent:xagent@host.docker.internal:5432/xagent \
		-e REDIS_URL=redis://host.docker.internal:6379 \
		$(DOCKER_TAG)

# Deployment targets
deploy: deploy-staging

deploy-staging:
	@echo "$(BLUE)Deploying to staging...$(NC)"
	./deploy.sh staging $(VERSION)

deploy-production:
	@echo "$(YELLOW)Deploying to production...$(NC)"
	@read -p "Are you sure you want to deploy to production? [y/N] " -n 1 -r; \
	echo; \
	if [[ $$REPLY =~ ^[Yy]$$ ]]; then \
		./deploy.sh production $(VERSION); \
	else \
		echo "$(RED)Deployment cancelled$(NC)"; \
		exit 1; \
	fi

# Demo targets
demo: demo-seed run
	@echo "$(GREEN)Demo environment ready!$(NC)"

demo-seed:
	@echo "$(BLUE)Seeding demo data...$(NC)"
	$(PYTHON) scripts/seed_demo.py
	@echo "$(GREEN)Demo data seeded!$(NC)"

demo-reset:
	@echo "$(BLUE)Resetting and re-seeding demo data...$(NC)"
	$(PYTHON) scripts/seed_demo.py --reset
	@echo "$(GREEN)Demo data reset complete!$(NC)"

demo-quickstart:
	@echo "$(BLUE)Starting X-Agent demo environment...$(NC)"
	$(PYTHON) scripts/quickstart.py

# Development targets
run:
	@echo "$(BLUE)Running X-Agent locally...$(NC)"
	uvicorn backend.app.web:app --reload --host 0.0.0.0 --port 8000

run-worker:
	@echo "$(BLUE)Running workflow worker...$(NC)"
	python -m backend.app.workflow_worker

# Utility targets
version:
	@echo "$(BLUE)X-Agent Core Version: $(VERSION)$(NC)"

status:
	@echo "$(BLUE)X-Agent Core Status$(NC)"
	@echo "Version: $(VERSION)"
	@echo "Python: $$($(PYTHON) --version)"
	@echo "Git Branch: $$(git rev-parse --abbrev-ref HEAD)"
	@echo "Git Commit: $$(git rev-parse --short HEAD)"

requirements-update:
	@echo "$(BLUE)Updating requirements...$(NC)"
	pip-compile pyproject.toml -o requirements.txt
	@echo "$(GREEN)Requirements updated$(NC)"

# ============================================================================
# Monitoring Commands
# ============================================================================

monitor-start:
	@echo "$(BLUE)Starting monitoring stack...$(NC)"
	@echo "$(GREEN)Starting Docker Compose services...$(NC)"
	$(DOCKER_COMPOSE) -f monitoring/docker-compose.monitoring.yml up -d
	@echo "$(GREEN)Waiting for services to be healthy...$(NC)"
	@sleep 10
	@echo ""
	@echo "$(GREEN)Monitoring stack started successfully!$(NC)"
	@echo ""
	@echo "$(BLUE)Access the following services:$(NC)"
	@echo "  Prometheus:    http://localhost:9090"
	@echo "  Grafana:       http://localhost:3000 (admin/admin)"
	@echo "  AlertManager:  http://localhost:9093"
	@echo "  Elasticsearch: http://localhost:9200"
	@echo "  Kibana:        http://localhost:5601"
	@echo "  Jaeger:        http://localhost:16686"
	@echo "  Node Exporter: http://localhost:9100"
	@echo ""

monitor-stop:
	@echo "$(BLUE)Stopping monitoring stack...$(NC)"
	$(DOCKER_COMPOSE) -f monitoring/docker-compose.monitoring.yml down
	@echo "$(GREEN)Monitoring stack stopped!$(NC)"

monitor-logs:
	@echo "$(BLUE)Showing monitoring stack logs...$(NC)"
	$(DOCKER_COMPOSE) -f monitoring/docker-compose.monitoring.yml logs -f

monitor-status:
	@echo "$(BLUE)Monitoring stack status:$(NC)"
	$(DOCKER_COMPOSE) -f monitoring/docker-compose.monitoring.yml ps
	@echo ""
	@echo "$(BLUE)Service health checks:$(NC)"
	@echo "  Prometheus:    $$(curl -s http://localhost:9090/-/healthy || echo 'DOWN')"
	@echo "  Grafana:       $$(curl -s http://localhost:3000/api/health | grep -q 'ok' && echo 'UP' || echo 'DOWN')"
	@echo "  AlertManager:  $$(curl -s http://localhost:9093/-/healthy || echo 'DOWN')"
	@echo "  Elasticsearch: $$(curl -s http://localhost:9200/_cluster/health | grep -q 'green' && echo 'UP' || echo 'DOWN')"
	@echo "  Kibana:        $$(curl -s http://localhost:5601/api/status | grep -q 'green' && echo 'UP' || echo 'DOWN')"
	@echo "  Jaeger:        $$(curl -s http://localhost:16686/ > /dev/null && echo 'UP' || echo 'DOWN')"

# ============================================================================
# Smoke Test Commands
# ============================================================================

smoke:
	@echo "$(BLUE)Running full-stack smoke test...$(NC)"
	$(PYTHON) scripts/smoke_test.py

smoke-full:
	@echo "$(BLUE)Starting Docker services (postgres + redis)...$(NC)"
	$(DOCKER_COMPOSE) up -d postgres redis
	@echo "$(BLUE)Waiting for services to be healthy...$(NC)"
	@sleep 5
	$(PYTHON) scripts/smoke_test.py

# ============================================================================
# Cleanup Commands
# ============================================================================

clean:
	@echo "$(BLUE)Cleaning up temporary files...$(NC)"
	find . -type d -name __pycache__ -exec rm -rf {} + 2>/dev/null || true
	find . -type d -name .pytest_cache -exec rm -rf {} + 2>/dev/null || true
	find . -type d -name .mypy_cache -exec rm -rf {} + 2>/dev/null || true
	find . -type d -name .ruff_cache -exec rm -rf {} + 2>/dev/null || true
	find . -type d -name htmlcov -exec rm -rf {} + 2>/dev/null || true
	find . -type f -name .coverage -delete 2>/dev/null || true
	find . -type f -name "*.pyc" -delete 2>/dev/null || true
	find . -type f -name "*-report.json" -delete 2>/dev/null || true
	find . -type f -name "*-report.xml" -delete 2>/dev/null || true
	@echo "$(GREEN)Cleanup complete!$(NC)"

clean-docker:
	@echo "$(BLUE)Cleaning up Docker resources...$(NC)"
	$(DOCKER_COMPOSE) -f monitoring/docker-compose.monitoring.yml down -v 2>/dev/null || true
	$(DOCKER) system prune -f
	@echo "$(GREEN)Docker cleanup complete!$(NC)"

clean-all: clean clean-docker
	@echo "$(GREEN)Full cleanup complete!$(NC)"

.DEFAULT_GOAL := help
