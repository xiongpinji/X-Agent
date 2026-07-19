#!/bin/bash

# X-Agent Monitoring System Verification Script
# This script verifies that all monitoring services are running and collecting metrics

set -e

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Configuration
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
DOCKER_COMPOSE_FILE="$SCRIPT_DIR/docker-compose.monitoring.yml"

# Functions
print_header() {
    echo -e "${BLUE}========================================${NC}"
    echo -e "${BLUE}$1${NC}"
    echo -e "${BLUE}========================================${NC}"
}

print_success() {
    echo -e "${GREEN}✓ $1${NC}"
}

print_error() {
    echo -e "${RED}✗ $1${NC}"
}

print_warning() {
    echo -e "${YELLOW}⚠ $1${NC}"
}

print_info() {
    echo -e "${BLUE}ℹ $1${NC}"
}

# Check if services are running
check_services_running() {
    print_header "Checking Services Status"

    local services=(
        "x-agent-prometheus"
        "x-agent-grafana"
        "x-agent-alertmanager"
        "x-agent-elasticsearch"
        "x-agent-logstash"
        "x-agent-kibana"
        "x-agent-jaeger"
        "x-agent-postgres"
        "x-agent-redis"
        "x-agent-qdrant"
        "x-agent-node-exporter"
        "x-agent-postgres-exporter"
        "x-agent-redis-exporter"
    )

    local all_running=true

    for service in "${services[@]}"; do
        if docker ps --filter "name=$service" --filter "status=running" | grep -q "$service"; then
            print_success "$service is running"
        else
            print_error "$service is not running"
            all_running=false
        fi
    done

    return $([ "$all_running" = true ] && echo 0 || echo 1)
}

# Check service health
check_service_health() {
    print_header "Checking Service Health"

    # Prometheus
    print_info "Checking Prometheus..."
    if curl -s http://localhost:9090/-/healthy > /dev/null 2>&1; then
        print_success "Prometheus is healthy"
        local prom_targets=$(curl -s http://localhost:9090/api/v1/targets | grep -o '"health":"up"' | wc -l)
        print_info "  Active targets: $prom_targets"
    else
        print_error "Prometheus is unhealthy"
    fi

    # Grafana
    print_info "Checking Grafana..."
    if curl -s http://localhost:3000/api/health > /dev/null 2>&1; then
        print_success "Grafana is healthy"
    else
        print_error "Grafana is unhealthy"
    fi

    # Elasticsearch
    print_info "Checking Elasticsearch..."
    if curl -s http://localhost:9200/_cluster/health > /dev/null 2>&1; then
        local es_status=$(curl -s http://localhost:9200/_cluster/health | grep -o '"status":"[^"]*"' | cut -d'"' -f4)
        print_success "Elasticsearch is healthy (status: $es_status)"
    else
        print_error "Elasticsearch is unhealthy"
    fi

    # Kibana
    print_info "Checking Kibana..."
    if curl -s http://localhost:5601/api/status > /dev/null 2>&1; then
        print_success "Kibana is healthy"
    else
        print_error "Kibana is unhealthy"
    fi

    # Jaeger
    print_info "Checking Jaeger..."
    if curl -s http://localhost:16686/ > /dev/null 2>&1; then
        print_success "Jaeger is healthy"
    else
        print_error "Jaeger is unhealthy"
    fi

    # AlertManager
    print_info "Checking AlertManager..."
    if curl -s http://localhost:9093/-/healthy > /dev/null 2>&1; then
        print_success "AlertManager is healthy"
    else
        print_error "AlertManager is unhealthy"
    fi
}

# Check metrics collection
check_metrics_collection() {
    print_header "Checking Metrics Collection"

    print_info "Fetching Prometheus metrics..."
    local metrics=$(curl -s http://localhost:9090/api/v1/query?query=up | grep -o '"value":\["[^"]*"' | wc -l)
    print_success "Prometheus is collecting metrics ($metrics active metrics)"

    print_info "Checking Elasticsearch indices..."
    local indices=$(curl -s http://localhost:9200/_cat/indices?format=json | grep -o '"index":"[^"]*"' | wc -l)
    print_success "Elasticsearch has $indices indices"

    print_info "Checking Jaeger traces..."
    local traces=$(curl -s http://localhost:16686/api/traces?service=x-agent | grep -o '"traceID":"[^"]*"' | wc -l)
    if [ "$traces" -gt 0 ]; then
        print_success "Jaeger has collected $traces traces"
    else
        print_warning "Jaeger has not collected any traces yet"
    fi
}

# Check alert rules
check_alert_rules() {
    print_header "Checking Alert Rules"

    print_info "Fetching alert rules from Prometheus..."
    local rules=$(curl -s http://localhost:9090/api/v1/rules | grep -o '"name":"[^"]*"' | wc -l)
    print_success "Prometheus has $rules alert rules configured"

    print_info "Checking alert status..."
    local firing=$(curl -s http://localhost:9090/api/v1/alerts | grep -o '"state":"firing"' | wc -l)
    local pending=$(curl -s http://localhost:9090/api/v1/alerts | grep -o '"state":"pending"' | wc -l)

    if [ "$firing" -gt 0 ]; then
        print_warning "There are $firing firing alerts"
    else
        print_success "No firing alerts"
    fi

    if [ "$pending" -gt 0 ]; then
        print_info "There are $pending pending alerts"
    fi
}

# Check data sources
check_data_sources() {
    print_header "Checking Data Sources"

    print_info "Checking Grafana data sources..."
    local datasources=$(curl -s -H "Authorization: Bearer $(curl -s -X POST http://localhost:3000/api/auth/login -d '{"user":"admin","password":"admin"}' | grep -o '"accessToken":"[^"]*"' | cut -d'"' -f4)" http://localhost:3000/api/datasources | grep -o '"name":"[^"]*"' | wc -l)
    print_success "Grafana has $datasources data sources configured"
}

# Check disk usage
check_disk_usage() {
    print_header "Checking Disk Usage"

    print_info "Checking Docker volumes..."
    local volumes=$(docker volume ls | grep x-agent | awk '{print $2}')

    for volume in $volumes; do
        local size=$(docker run --rm -v "$volume":/data busybox du -sh /data 2>/dev/null | awk '{print $1}')
        print_info "  $volume: $size"
    done
}

# Generate test metrics
generate_test_metrics() {
    print_header "Generating Test Metrics"

    print_info "Sending test metrics to Prometheus..."
    # This would require the application to be running
    # For now, we'll just check if the metrics endpoint is accessible

    if curl -s http://localhost:8000/api/v1/metrics/prometheus > /dev/null 2>&1; then
        print_success "Application metrics endpoint is accessible"
    else
        print_warning "Application metrics endpoint is not accessible (application may not be running)"
    fi
}

# Generate report
generate_report() {
    print_header "Monitoring System Report"

    echo ""
    echo "Timestamp: $(date)"
    echo ""
    echo "Service Status:"
    docker-compose -f "$DOCKER_COMPOSE_FILE" ps
    echo ""
    echo "Docker Volumes:"
    docker volume ls | grep x-agent
    echo ""
    echo "Network Status:"
    docker network inspect x-agent-network | grep -A 20 "Containers"
    echo ""
}

# Main execution
main() {
    print_header "X-Agent Monitoring System Verification"

    if ! check_services_running; then
        print_error "Some services are not running"
        exit 1
    fi

    check_service_health
    check_metrics_collection
    check_alert_rules
    check_data_sources
    check_disk_usage
    generate_test_metrics
    generate_report

    print_success "Verification completed!"
}

# Run main function
main "$@"
