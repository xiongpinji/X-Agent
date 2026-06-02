#!/bin/bash

# X-Agent Monitoring System Deployment Verification Script
# Verifies that all monitoring components are properly deployed and configured

set -e

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Configuration
DOCKER_COMPOSE_FILE="${DOCKER_COMPOSE_FILE:-docker-compose.yml}"
LOG_FILE="/tmp/monitoring-verification.log"

# Counters
PASSED=0
FAILED=0
WARNINGS=0

# Logging function
log() {
    echo "[$(date +'%Y-%m-%d %H:%M:%S')] $1" | tee -a "$LOG_FILE"
}

# Test result functions
pass() {
    echo -e "${GREEN}✓ PASS${NC}: $1" | tee -a "$LOG_FILE"
    ((PASSED++))
}

fail() {
    echo -e "${RED}✗ FAIL${NC}: $1" | tee -a "$LOG_FILE"
    ((FAILED++))
}

warn() {
    echo -e "${YELLOW}⚠ WARN${NC}: $1" | tee -a "$LOG_FILE"
    ((WARNINGS++))
}

info() {
    echo -e "${BLUE}ℹ INFO${NC}: $1" | tee -a "$LOG_FILE"
}

# Header
print_header() {
    echo -e "\n${BLUE}========================================${NC}"
    echo -e "${BLUE}$1${NC}"
    echo -e "${BLUE}========================================${NC}\n"
}

# ============ Verification Functions ============

verify_docker() {
    print_header "Docker and Docker Compose Verification"

    if command -v docker &> /dev/null; then
        pass "Docker is installed"
        local docker_version=$(docker --version)
        info "Docker version: $docker_version"
    else
        fail "Docker is not installed"
        return 1
    fi

    if command -v docker-compose &> /dev/null; then
        pass "Docker Compose is installed"
        local compose_version=$(docker-compose --version)
        info "Docker Compose version: $compose_version"
    else
        fail "Docker Compose is not installed"
        return 1
    fi
}

verify_services() {
    print_header "Service Status Verification"

    local services=("prometheus" "grafana" "alertmanager" "node-exporter" "postgres-exporter" "redis-exporter" "elasticsearch" "logstash" "kibana" "jaeger")

    for service in "${services[@]}"; do
        if docker-compose -f "$DOCKER_COMPOSE_FILE" ps "$service" 2>/dev/null | grep -q "Up"; then
            pass "$service is running"
        else
            fail "$service is not running"
        fi
    done
}

verify_ports() {
    print_header "Port Availability Verification"

    local ports=(
        "3000:Grafana"
        "9090:Prometheus"
        "9093:AlertManager"
        "9100:Node Exporter"
        "9187:PostgreSQL Exporter"
        "9121:Redis Exporter"
        "9200:Elasticsearch"
        "5601:Kibana"
        "16686:Jaeger"
    )

    for port_info in "${ports[@]}"; do
        local port=$(echo "$port_info" | cut -d: -f1)
        local name=$(echo "$port_info" | cut -d: -f2)

        if nc -z localhost "$port" 2>/dev/null; then
            pass "$name (port $port) is accessible"
        else
            fail "$name (port $port) is not accessible"
        fi
    done
}

verify_prometheus() {
    print_header "Prometheus Configuration Verification"

    # Check Prometheus targets
    local targets=$(curl -s http://localhost:9090/api/v1/targets | jq '.data.activeTargets | length')
    if [ "$targets" -gt 0 ]; then
        pass "Prometheus has $targets active targets"
    else
        fail "Prometheus has no active targets"
    fi

    # Check alert rules
    local rules=$(curl -s http://localhost:9090/api/v1/rules | jq '.data.groups | length')
    if [ "$rules" -gt 0 ]; then
        pass "Prometheus has $rules alert rule groups"
    else
        warn "Prometheus has no alert rules configured"
    fi

    # Check data retention
    local retention=$(curl -s http://localhost:9090/api/v1/query?query=up | jq '.data.result | length')
    if [ "$retention" -gt 0 ]; then
        pass "Prometheus is collecting metrics"
    else
        warn "Prometheus has no metrics data yet"
    fi
}

verify_grafana() {
    print_header "Grafana Configuration Verification"

    # Check Grafana health
    if curl -sf http://localhost:3000/api/health > /dev/null 2>&1; then
        pass "Grafana is healthy"
    else
        fail "Grafana health check failed"
        return 1
    fi

    # Check data sources
    local datasources=$(curl -s -H "Authorization: Bearer admin" http://localhost:3000/api/datasources | jq '. | length')
    if [ "$datasources" -gt 0 ]; then
        pass "Grafana has $datasources data sources configured"
    else
        warn "Grafana has no data sources configured"
    fi

    # Check dashboards
    local dashboards=$(curl -s -H "Authorization: Bearer admin" http://localhost:3000/api/search | jq '. | length')
    if [ "$dashboards" -gt 0 ]; then
        pass "Grafana has $dashboards dashboards"
    else
        warn "Grafana has no dashboards configured"
    fi
}

verify_alertmanager() {
    print_header "AlertManager Configuration Verification"

    # Check AlertManager status
    if curl -sf http://localhost:9093/api/v1/status > /dev/null 2>&1; then
        pass "AlertManager is healthy"
    else
        fail "AlertManager health check failed"
        return 1
    fi

    # Check alerts
    local alerts=$(curl -s http://localhost:9093/api/v1/alerts | jq '.data | length')
    info "AlertManager has $alerts active alerts"
}

verify_elasticsearch() {
    print_header "Elasticsearch Configuration Verification"

    # Check Elasticsearch health
    if curl -sf http://localhost:9200/_cluster/health > /dev/null 2>&1; then
        pass "Elasticsearch is healthy"
    else
        fail "Elasticsearch health check failed"
        return 1
    fi

    # Check indices
    local indices=$(curl -s http://localhost:9200/_cat/indices?format=json | jq '. | length')
    if [ "$indices" -gt 0 ]; then
        pass "Elasticsearch has $indices indices"
    else
        warn "Elasticsearch has no indices"
    fi
}

verify_kibana() {
    print_header "Kibana Configuration Verification"

    # Check Kibana status
    if curl -sf http://localhost:5601/api/status > /dev/null 2>&1; then
        pass "Kibana is healthy"
    else
        fail "Kibana health check failed"
        return 1
    fi
}

verify_jaeger() {
    print_header "Jaeger Configuration Verification"

    # Check Jaeger UI
    if curl -sf http://localhost:16686 > /dev/null 2>&1; then
        pass "Jaeger UI is accessible"
    else
        fail "Jaeger UI is not accessible"
        return 1
    fi

    # Check Jaeger services
    local services=$(curl -s http://localhost:16686/api/services | jq '.data | length')
    if [ "$services" -gt 0 ]; then
        pass "Jaeger has $services services"
    else
        warn "Jaeger has no services yet"
    fi
}

verify_metrics_collection() {
    print_header "Metrics Collection Verification"

    # Check API metrics
    if curl -sf http://localhost:8000/metrics > /dev/null 2>&1; then
        pass "API metrics endpoint is accessible"
    else
        warn "API metrics endpoint is not accessible"
    fi

    # Check Prometheus scrape success
    local scrape_success=$(curl -s http://localhost:9090/api/v1/query?query='up' | jq '.data.result | length')
    if [ "$scrape_success" -gt 0 ]; then
        pass "Prometheus is scraping metrics from $scrape_success targets"
    else
        fail "Prometheus is not scraping any metrics"
    fi
}

verify_log_collection() {
    print_header "Log Collection Verification"

    # Check if log files exist
    if [ -f "/var/log/xagent/app.log" ]; then
        pass "Application log file exists"
    else
        warn "Application log file not found"
    fi

    # Check Logstash
    if docker-compose -f "$DOCKER_COMPOSE_FILE" ps logstash 2>/dev/null | grep -q "Up"; then
        pass "Logstash is running"
    else
        fail "Logstash is not running"
    fi

    # Check Elasticsearch indices for logs
    local log_indices=$(curl -s http://localhost:9200/_cat/indices?format=json | jq '.[] | select(.index | startswith("xagent")) | .index' | wc -l)
    if [ "$log_indices" -gt 0 ]; then
        pass "Elasticsearch has $log_indices X-Agent log indices"
    else
        warn "No X-Agent log indices found in Elasticsearch"
    fi
}

verify_disk_space() {
    print_header "Disk Space Verification"

    local available=$(df /var/lib/docker | awk 'NR==2 {print $4}')
    local available_gb=$((available / 1024 / 1024))

    if [ "$available_gb" -gt 50 ]; then
        pass "Sufficient disk space available: ${available_gb}GB"
    elif [ "$available_gb" -gt 20 ]; then
        warn "Limited disk space available: ${available_gb}GB (recommended: >50GB)"
    else
        fail "Insufficient disk space: ${available_gb}GB (required: >20GB)"
    fi
}

verify_memory() {
    print_header "Memory Verification"

    local available=$(free -m | awk 'NR==2 {print $7}')

    if [ "$available" -gt 4096 ]; then
        pass "Sufficient memory available: ${available}MB"
    elif [ "$available" -gt 2048 ]; then
        warn "Limited memory available: ${available}MB (recommended: >4GB)"
    else
        fail "Insufficient memory: ${available}MB (required: >2GB)"
    fi
}

verify_configuration_files() {
    print_header "Configuration Files Verification"

    local config_files=(
        "prometheus.yml"
        "alert_rules.yml"
        "recording_rules.yml"
        "alertmanager.yml"
        "grafana-datasource.yml"
        "elk/logstash.conf"
        "jaeger-config.yml"
    )

    for file in "${config_files[@]}"; do
        if [ -f "$file" ]; then
            pass "Configuration file exists: $file"
        else
            fail "Configuration file missing: $file"
        fi
    done
}

verify_scripts() {
    print_header "Automation Scripts Verification"

    local scripts=(
        "scripts/autoscaling.sh"
        "scripts/autorestart.sh"
        "scripts/backup.sh"
    )

    for script in "${scripts[@]}"; do
        if [ -f "$script" ]; then
            if [ -x "$script" ]; then
                pass "Script is executable: $script"
            else
                warn "Script is not executable: $script"
            fi
        else
            fail "Script missing: $script"
        fi
    done
}

# ============ Main Verification ============

main() {
    log "Starting X-Agent Monitoring System Verification"
    log "Timestamp: $(date)"

    verify_docker
    verify_services
    verify_ports
    verify_prometheus
    verify_grafana
    verify_alertmanager
    verify_elasticsearch
    verify_kibana
    verify_jaeger
    verify_metrics_collection
    verify_log_collection
    verify_disk_space
    verify_memory
    verify_configuration_files
    verify_scripts

    # Print summary
    print_header "Verification Summary"
    echo -e "${GREEN}Passed: $PASSED${NC}"
    echo -e "${RED}Failed: $FAILED${NC}"
    echo -e "${YELLOW}Warnings: $WARNINGS${NC}"

    if [ "$FAILED" -eq 0 ]; then
        echo -e "\n${GREEN}✓ All critical checks passed!${NC}"
        return 0
    else
        echo -e "\n${RED}✗ Some checks failed. Please review the log file: $LOG_FILE${NC}"
        return 1
    fi
}

# Run main function
main
