#!/bin/bash
set -e

# X-Agent Pre-deployment Checklist
# This script verifies all prerequisites before deployment

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m'

# Counters
PASSED=0
FAILED=0
WARNINGS=0

# Functions
check_pass() {
    echo -e "${GREEN}✓${NC} $1"
    ((PASSED++))
}

check_fail() {
    echo -e "${RED}✗${NC} $1"
    ((FAILED++))
}

check_warn() {
    echo -e "${YELLOW}⚠${NC} $1"
    ((WARNINGS++))
}

# System checks
echo "=== System Checks ==="

if command -v docker &> /dev/null; then
    check_pass "Docker is installed"
else
    check_fail "Docker is not installed"
fi

if command -v docker-compose &> /dev/null; then
    check_pass "Docker Compose is installed"
else
    check_fail "Docker Compose is not installed"
fi

if command -v kubectl &> /dev/null; then
    check_pass "kubectl is installed"
else
    check_warn "kubectl is not installed (required for K8s deployment)"
fi

if command -v helm &> /dev/null; then
    check_pass "Helm is installed"
else
    check_warn "Helm is not installed (required for Helm deployment)"
fi

# Resource checks
echo ""
echo "=== Resource Checks ==="

AVAILABLE_MEMORY=$(free -m | awk 'NR==2{print $7}')
if [ "$AVAILABLE_MEMORY" -gt 4096 ]; then
    check_pass "Sufficient memory available: ${AVAILABLE_MEMORY}MB"
else
    check_warn "Low memory available: ${AVAILABLE_MEMORY}MB (recommended: 8GB+)"
fi

AVAILABLE_DISK=$(df -m / | awk 'NR==2{print $4}')
if [ "$AVAILABLE_DISK" -gt 50000 ]; then
    check_pass "Sufficient disk space available: ${AVAILABLE_DISK}MB"
else
    check_fail "Insufficient disk space: ${AVAILABLE_DISK}MB (required: 50GB+)"
fi

# Configuration checks
echo ""
echo "=== Configuration Checks ==="

if [ -f ".env" ]; then
    check_pass ".env file exists"
else
    check_fail ".env file not found"
fi

if [ -f "docker-compose.yml" ]; then
    check_pass "docker-compose.yml exists"
else
    check_fail "docker-compose.yml not found"
fi

if [ -f "Dockerfile" ]; then
    check_pass "Dockerfile exists"
else
    check_fail "Dockerfile not found"
fi

# P1-15: deployment/k8s/ 裸清单已归档(archive/legacy_k8s_manifests_2026-08/),
# Helm chart 为唯一部署权威, 下方 helm 检查即覆盖。
if [ -d "deployment/k8s" ]; then
    check_warn "deployment/k8s reappeared; raw manifests were archived in favor of deployment/helm"
else
    check_pass "Raw k8s manifests archived (helm is the single authority)"
fi

if [ -d "deployment/helm" ]; then
    check_pass "Helm chart directory exists"
else
    check_warn "Helm chart directory not found"
fi

# Database checks
echo ""
echo "=== Database Checks ==="

if command -v psql &> /dev/null; then
    check_pass "PostgreSQL client is installed"
else
    check_warn "PostgreSQL client is not installed"
fi

if command -v redis-cli &> /dev/null; then
    check_pass "Redis CLI is installed"
else
    check_warn "Redis CLI is not installed"
fi

# Security checks
echo ""
echo "=== Security Checks ==="

if grep -q "change-me-in-production" .env 2>/dev/null; then
    check_fail "Default secrets found in .env (must be changed for production)"
else
    check_pass "No default secrets found in .env"
fi

# P0-03: 应用密钥为 XAGENT_JWT_SECRET(backend/app/settings.py, env_prefix="XAGENT_"), 不再使用 SECRET_KEY
if [ -f ".env" ] && grep -q "XAGENT_JWT_SECRET" .env; then
    XAGENT_JWT_SECRET=$(grep "XAGENT_JWT_SECRET" .env | cut -d'=' -f2)
    if [ ${#XAGENT_JWT_SECRET} -lt 32 ]; then
        check_fail "XAGENT_JWT_SECRET is too short (minimum 32 characters)"
    else
        check_pass "XAGENT_JWT_SECRET has sufficient length"
    fi
fi

# Summary
echo ""
echo "=== Summary ==="
echo -e "${GREEN}Passed: $PASSED${NC}"
echo -e "${RED}Failed: $FAILED${NC}"
echo -e "${YELLOW}Warnings: $WARNINGS${NC}"

if [ $FAILED -gt 0 ]; then
    echo ""
    echo -e "${RED}Deployment checklist FAILED${NC}"
    exit 1
else
    echo ""
    echo -e "${GREEN}Deployment checklist PASSED${NC}"
    exit 0
fi
