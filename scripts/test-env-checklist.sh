#!/bin/bash

# X-Agent Test Environment Deployment Checklist
# This script verifies all components of the test environment

set -e

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
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

print_header() {
    echo ""
    echo -e "${BLUE}=== $1 ===${NC}"
}

# Main checks
main() {
    echo -e "${BLUE}X-Agent Test Environment Deployment Checklist${NC}"
    echo "Timestamp: $(date)"
    echo ""

    # ========================================================================
    # SYSTEM REQUIREMENTS
    # ========================================================================
    print_header "System Requirements"

    # Docker
    if command -v docker &> /dev/null; then
        DOCKER_VERSION=$(docker --version)
        check_pass "Docker installed: $DOCKER_VERSION"
    else
        check_fail "Docker not installed"
    fi

    # Docker Compose
    if command -v docker-compose &> /dev/null; then
        COMPOSE_VERSION=$(docker-compose --version)
        check_pass "Docker Compose installed: $COMPOSE_VERSION"
    else
        check_fail "Docker Compose not installed"
    fi

    # Disk space
    DISK_AVAILABLE=$(df -BG . | awk 'NR==2 {print $4}' | sed 's/G//')
    if [ "$DISK_AVAILABLE" -gt 50 ]; then
        check_pass "Disk space available: ${DISK_AVAILABLE}GB"
    else
        check_warn "Low disk space: ${DISK_AVAILABLE}GB (recommended: 50GB+)"
    fi

    # Memory
    MEMORY_AVAILABLE=$(free -BG | awk 'NR==2 {print $7}' | sed 's/G//')
    if [ "$MEMORY_AVAILABLE" -gt 8 ]; then
        check_pass "Memory available: ${MEMORY_AVAILABLE}GB"
    else
        check_warn "Low memory: ${MEMORY_AVAILABLE}GB (recommended: 8GB+)"
    fi

    # ========================================================================
    # PROJECT FILES
    # ========================================================================
    print_header "Project Files"

    # Docker Compose file
    if [ -f "docker-compose.test.yml" ]; then
        check_pass "docker-compose.test.yml exists"
    else
        check_fail "docker-compose.test.yml not found"
    fi

    # Environment file
    if [ -f ".env.test" ]; then
        check_pass ".env.test exists"
    else
        check_fail ".env.test not found"
    fi

    # Deployment scripts
    if [ -f "scripts/deploy-test-env.sh" ]; then
        check_pass "scripts/deploy-test-env.sh exists"
    else
        check_fail "scripts/deploy-test-env.sh not found"
    fi

    # Prometheus config
    if [ -f "deployment/prometheus/prometheus.yml" ]; then
        check_pass "deployment/prometheus/prometheus.yml exists"
    else
        check_fail "deployment/prometheus/prometheus.yml not found"
    fi

    # Alert rules
    if [ -f "deployment/prometheus/alerts.yml" ]; then
        check_pass "deployment/prometheus/alerts.yml exists"
    else
        check_fail "deployment/prometheus/alerts.yml not found"
    fi

    # ========================================================================
    # DOCKER SERVICES
    # ========================================================================
    print_header "Docker Services"

    # Check if services are running
    RUNNING_SERVICES=$(docker-compose -f docker-compose.test.yml ps --services --filter "status=running" 2>/dev/null | wc -l)
    TOTAL_SERVICES=$(docker-compose -f docker-compose.test.yml config --services 2>/dev/null | wc -l)

    if [ "$RUNNING_SERVICES" -gt 0 ]; then
        check_pass "Services running: $RUNNING_SERVICES/$TOTAL_SERVICES"
    else
        check_warn "No services running (environment may not be deployed yet)"
    fi

    # Check individual services
    SERVICES=("postgres" "redis" "qdrant" "neo4j" "xagent-api" "xagent-worker" "xagent-beat" "xagent-web" "prometheus" "grafana" "elasticsearch" "kibana" "jaeger")

    for service in "${SERVICES[@]}"; do
        if docker-compose -f docker-compose.test.yml ps "$service" 2>/dev/null | grep -q "Up"; then
            check_pass "$service is running"
        else
            check_warn "$service is not running"
        fi
    done

    # ========================================================================
    # PORT AVAILABILITY
    # ========================================================================
    print_header "Port Availability"

    PORTS=(
        "5432:PostgreSQL"
        "6379:Redis"
        "6333:Qdrant"
        "7687:Neo4j"
        "8000:API"
        "3000:Web"
        "9090:Prometheus"
        "3001:Grafana"
        "9093:AlertManager"
        "9200:Elasticsearch"
        "5601:Kibana"
        "16686:Jaeger"
    )

    for port_info in "${PORTS[@]}"; do
        IFS=':' read -r port name <<< "$port_info"
        if nc -z localhost "$port" 2>/dev/null; then
            check_pass "Port $port ($name) is accessible"
        else
            check_warn "Port $port ($name) is not accessible"
        fi
    done

    # ========================================================================
    # DATABASE CONNECTIVITY
    # ========================================================================
    print_header "Database Connectivity"

    # PostgreSQL
    if docker-compose -f docker-compose.test.yml exec -T postgres pg_isready -U xagent_test &>/dev/null; then
        check_pass "PostgreSQL is accessible"
    else
        check_warn "PostgreSQL is not accessible"
    fi

    # Redis
    if docker-compose -f docker-compose.test.yml exec -T redis redis-cli -a test_redis_123 ping &>/dev/null; then
        check_pass "Redis is accessible"
    else
        check_warn "Redis is not accessible"
    fi

    # Qdrant
    if curl -s http://localhost:6333/health &>/dev/null; then
        check_pass "Qdrant is accessible"
    else
        check_warn "Qdrant is not accessible"
    fi

    # Neo4j
    if curl -s http://localhost:7474 &>/dev/null; then
        check_pass "Neo4j is accessible"
    else
        check_warn "Neo4j is not accessible"
    fi

    # ========================================================================
    # API HEALTH
    # ========================================================================
    print_header "API Health"

    if curl -s http://localhost:8000/health &>/dev/null; then
        check_pass "API health endpoint is responding"
    else
        check_warn "API health endpoint is not responding"
    fi

    if curl -s http://localhost:8000/docs &>/dev/null; then
        check_pass "API documentation is available"
    else
        check_warn "API documentation is not available"
    fi

    # ========================================================================
    # MONITORING HEALTH
    # ========================================================================
    print_header "Monitoring Health"

    # Prometheus
    if curl -s http://localhost:9090/-/healthy &>/dev/null; then
        check_pass "Prometheus is healthy"
    else
        check_warn "Prometheus is not healthy"
    fi

    # Grafana
    if curl -s http://localhost:3001/api/health &>/dev/null; then
        check_pass "Grafana is healthy"
    else
        check_warn "Grafana is not healthy"
    fi

    # AlertManager
    if curl -s http://localhost:9093/-/healthy &>/dev/null; then
        check_pass "AlertManager is healthy"
    else
        check_warn "AlertManager is not healthy"
    fi

    # Jaeger
    if curl -s http://localhost:16686 &>/dev/null; then
        check_pass "Jaeger is accessible"
    else
        check_warn "Jaeger is not accessible"
    fi

    # ========================================================================
    # LOGGING HEALTH
    # ========================================================================
    print_header "Logging Health"

    # Elasticsearch
    if curl -s http://localhost:9200/_cluster/health &>/dev/null; then
        check_pass "Elasticsearch is accessible"
    else
        check_warn "Elasticsearch is not accessible"
    fi

    # Kibana
    if curl -s http://localhost:5601/api/status &>/dev/null; then
        check_pass "Kibana is accessible"
    else
        check_warn "Kibana is not accessible"
    fi

    # ========================================================================
    # DOCKER IMAGES
    # ========================================================================
    print_header "Docker Images"

    IMAGES=$(docker images --format "{{.Repository}}:{{.Tag}}" | grep -E "xagent|postgres|redis|qdrant|neo4j|prometheus|grafana|elasticsearch|kibana|jaeger" | wc -l)
    if [ "$IMAGES" -gt 0 ]; then
        check_pass "Docker images available: $IMAGES"
    else
        check_warn "No Docker images found"
    fi

    # ========================================================================
    # DISK USAGE
    # ========================================================================
    print_header "Disk Usage"

    DOCKER_DISK=$(docker system df --format "{{.Size}}" | head -1)
    check_pass "Docker disk usage: $DOCKER_DISK"

    # ========================================================================
    # SUMMARY
    # ========================================================================
    print_header "Summary"

    echo ""
    echo -e "${GREEN}Passed: $PASSED${NC}"
    echo -e "${YELLOW}Warnings: $WARNINGS${NC}"
    echo -e "${RED}Failed: $FAILED${NC}"
    echo ""

    if [ "$FAILED" -eq 0 ]; then
        echo -e "${GREEN}All critical checks passed!${NC}"
        return 0
    else
        echo -e "${RED}Some critical checks failed. Please review the errors above.${NC}"
        return 1
    fi
}

# Run main function
main "$@"
