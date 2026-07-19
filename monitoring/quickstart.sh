#!/bin/bash

# X-Agent Monitoring System Quick Start Script
# This script sets up and starts the complete monitoring stack

set -e

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Configuration
MONITORING_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
LOG_DIR="/var/log/xagent"
BACKUP_DIR="/backups"

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

# Check prerequisites
check_prerequisites() {
    print_header "Checking Prerequisites"

    # Check Docker
    if ! command -v docker &> /dev/null; then
        print_error "Docker is not installed"
        exit 1
    fi
    print_success "Docker is installed"

    # Check Docker Compose
    if ! command -v docker-compose &> /dev/null; then
        print_error "Docker Compose is not installed"
        exit 1
    fi
    print_success "Docker Compose is installed"

    # Check disk space
    available_space=$(df "$MONITORING_DIR" | awk 'NR==2 {print $4}')
    if [ "$available_space" -lt 10485760 ]; then  # 10GB in KB
        print_warning "Less than 10GB available disk space"
    else
        print_success "Sufficient disk space available"
    fi
}

# Create directories
create_directories() {
    print_header "Creating Directories"

    mkdir -p "$LOG_DIR"
    chmod 755 "$LOG_DIR"
    print_success "Created log directory: $LOG_DIR"

    mkdir -p "$BACKUP_DIR"
    chmod 755 "$BACKUP_DIR"
    print_success "Created backup directory: $BACKUP_DIR"

    mkdir -p "$MONITORING_DIR/grafana/provisioning/dashboards"
    mkdir -p "$MONITORING_DIR/grafana/provisioning/datasources"
    print_success "Created Grafana directories"
}

# Setup environment
setup_environment() {
    print_header "Setting Up Environment"

    if [ ! -f "$MONITORING_DIR/.env" ]; then
        if [ -f "$MONITORING_DIR/.env.example" ]; then
            cp "$MONITORING_DIR/.env.example" "$MONITORING_DIR/.env"
            print_success "Created .env file from template"
            print_warning "Please review and update .env file with your settings"
        else
            print_warning ".env.example not found, skipping .env creation"
        fi
    else
        print_success ".env file already exists"
    fi
}

# Validate configurations
validate_configurations() {
    print_header "Validating Configurations"

    # Check Prometheus config
    if [ -f "$MONITORING_DIR/prometheus.yml" ]; then
        print_info "Prometheus configuration found"
    else
        print_error "Prometheus configuration not found"
        exit 1
    fi

    # Check AlertManager config
    if [ -f "$MONITORING_DIR/alertmanager.yml" ]; then
        print_info "AlertManager configuration found"
    else
        print_error "AlertManager configuration not found"
        exit 1
    fi

    # Check Logstash config
    if [ -f "$MONITORING_DIR/elk/logstash.conf" ]; then
        print_info "Logstash configuration found"
    else
        print_error "Logstash configuration not found"
        exit 1
    fi

    print_success "All configurations validated"
}

# Start monitoring stack
start_monitoring() {
    print_header "Starting Monitoring Stack"

    cd "$MONITORING_DIR"

    # Pull latest images
    print_info "Pulling latest Docker images..."
    docker-compose -f docker-compose.monitoring.yml pull

    # Start services
    print_info "Starting services..."
    docker-compose -f docker-compose.monitoring.yml up -d

    print_success "Monitoring stack started"
}

# Wait for services
wait_for_services() {
    print_header "Waiting for Services to Start"

    services=(
        "prometheus:9090"
        "grafana:3000"
        "elasticsearch:9200"
        "kibana:5601"
        "jaeger:16686"
        "alertmanager:9093"
    )

    for service in "${services[@]}"; do
        host="${service%:*}"
        port="${service#*:}"
        container_name="x-agent-$host"

        print_info "Waiting for $host:$port..."
        for i in {1..30}; do
            if docker exec "$container_name" curl -s "http://localhost:$port" > /dev/null 2>&1; then
                print_success "$host is ready"
                break
            fi
            if [ $i -eq 30 ]; then
                print_warning "$host is not responding (may still be starting)"
            fi
            sleep 2
        done
    done
}

# Verify services
verify_services() {
    print_header "Verifying Services"

    # Prometheus
    if curl -s http://localhost:9090/-/healthy > /dev/null; then
        print_success "Prometheus is healthy"
    else
        print_warning "Prometheus health check failed"
    fi

    # Grafana
    if curl -s http://localhost:3000/api/health > /dev/null; then
        print_success "Grafana is healthy"
    else
        print_warning "Grafana health check failed"
    fi

    # Elasticsearch
    if curl -s http://localhost:9200/_cluster/health > /dev/null; then
        print_success "Elasticsearch is healthy"
    else
        print_warning "Elasticsearch health check failed"
    fi

    # Jaeger
    if curl -s http://localhost:16686/ > /dev/null; then
        print_success "Jaeger is healthy"
    else
        print_warning "Jaeger health check failed"
    fi

    # AlertManager
    if curl -s http://localhost:9093/-/healthy > /dev/null; then
        print_success "AlertManager is healthy"
    else
        print_warning "AlertManager health check failed"
    fi
}

# Print access information
print_access_info() {
    print_header "Monitoring Stack is Ready!"

    echo ""
    echo "Access the monitoring interfaces:"
    echo ""
    echo -e "${GREEN}Prometheus${NC}:      http://localhost:9090"
    echo -e "${GREEN}Grafana${NC}:         http://localhost:3000 (admin/admin)"
    echo -e "${GREEN}Kibana${NC}:          http://localhost:5601"
    echo -e "${GREEN}Jaeger${NC}:          http://localhost:16686"
    echo -e "${GREEN}AlertManager${NC}:    http://localhost:9093"
    echo ""
    echo "Useful commands:"
    echo ""
    echo "  View logs:"
    echo "    docker-compose -f $MONITORING_DIR/docker-compose.monitoring.yml logs -f"
    echo ""
    echo "  Stop services:"
    echo "    docker-compose -f $MONITORING_DIR/docker-compose.monitoring.yml down"
    echo ""
    echo "  Check service status:"
    echo "    docker-compose -f $MONITORING_DIR/docker-compose.monitoring.yml ps"
    echo ""
    echo "Documentation:"
    echo "  - Setup Guide: $MONITORING_DIR/MONITORING_SETUP_GUIDE.md"
    echo "  - Deployment Checklist: $MONITORING_DIR/DEPLOYMENT_CHECKLIST.md"
    echo "  - Integration Examples: $MONITORING_DIR/INTEGRATION_EXAMPLES.md"
    echo ""
}

# Main execution
main() {
    print_header "X-Agent Monitoring System Setup"

    check_prerequisites
    create_directories
    setup_environment
    validate_configurations
    start_monitoring
    wait_for_services
    verify_services
    print_access_info

    print_success "Setup completed successfully!"
}

# Run main function
main "$@"
