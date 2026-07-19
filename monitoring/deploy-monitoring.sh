#!/bin/bash

# X-Agent Monitoring System Deployment Script
# This script deploys and configures the complete monitoring stack

set -e

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Configuration
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(dirname "$SCRIPT_DIR")"
LOG_DIR="/var/log/xagent"
BACKUP_DIR="/backups"
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

# Check prerequisites
check_prerequisites() {
    print_header "Checking Prerequisites"

    # Check Docker
    if ! command -v docker &> /dev/null; then
        print_error "Docker is not installed"
        exit 1
    fi
    print_success "Docker is installed ($(docker --version))"

    # Check Docker Compose
    if ! command -v docker-compose &> /dev/null; then
        print_error "Docker Compose is not installed"
        exit 1
    fi
    print_success "Docker Compose is installed ($(docker-compose --version))"

    # Check Docker daemon
    if ! docker ps > /dev/null 2>&1; then
        print_error "Docker daemon is not running"
        exit 1
    fi
    print_success "Docker daemon is running"

    # Check disk space
    available_space=$(df "$SCRIPT_DIR" | awk 'NR==2 {print $4}')
    if [ "$available_space" -lt 10485760 ]; then  # 10GB in KB
        print_warning "Less than 10GB available disk space ($(numfmt --to=iec $((available_space * 1024)) 2>/dev/null || echo "$available_space KB"))"
    else
        print_success "Sufficient disk space available ($(numfmt --to=iec $((available_space * 1024)) 2>/dev/null || echo "$available_space KB"))"
    fi

    # Check required ports
    print_info "Checking required ports..."
    local ports=(9090 3000 9093 9200 5601 16686 5000 5001 8080)
    for port in "${ports[@]}"; do
        if netstat -tuln 2>/dev/null | grep -q ":$port "; then
            print_warning "Port $port is already in use"
        else
            print_success "Port $port is available"
        fi
    done
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

    mkdir -p "$SCRIPT_DIR/grafana/provisioning/dashboards"
    mkdir -p "$SCRIPT_DIR/grafana/provisioning/datasources"
    mkdir -p "$SCRIPT_DIR/prometheus"
    mkdir -p "$SCRIPT_DIR/alertmanager"
    mkdir -p "$SCRIPT_DIR/elk"
    print_success "Created monitoring directories"
}

# Validate configurations
validate_configurations() {
    print_header "Validating Configurations"

    local config_files=(
        "prometheus.yml"
        "alert_rules.yml"
        "alertmanager.yml"
        "grafana/provisioning/datasources.yml"
        "elk/logstash.conf"
    )

    for config_file in "${config_files[@]}"; do
        if [ -f "$SCRIPT_DIR/$config_file" ]; then
            print_success "Found: $config_file"
        else
            print_warning "Missing: $config_file"
        fi
    done

    # Validate docker-compose file
    if docker-compose -f "$DOCKER_COMPOSE_FILE" config > /dev/null 2>&1; then
        print_success "Docker Compose configuration is valid"
    else
        print_error "Docker Compose configuration is invalid"
        exit 1
    fi
}

# Setup environment
setup_environment() {
    print_header "Setting Up Environment"

    # Create .env file if it doesn't exist
    if [ ! -f "$SCRIPT_DIR/.env" ]; then
        cat > "$SCRIPT_DIR/.env" << 'EOF'
# Monitoring Environment Configuration

# Jaeger Configuration
JAEGER_AGENT_HOST=jaeger
JAEGER_AGENT_PORT=6831
JAEGER_SAMPLER_TYPE=const
JAEGER_SAMPLER_PARAM=1

# Elasticsearch Configuration
ELASTICSEARCH_HOST=elasticsearch
ELASTICSEARCH_PORT=9200
ELASTICSEARCH_USER=elastic
ELASTICSEARCH_PASSWORD=changeme

# Logstash Configuration
LOGSTASH_JAVA_OPTS=-Xmx256m -Xms256m
ENVIRONMENT=production
APP_VERSION=0.1.0

# Slack Webhook (optional)
SLACK_WEBHOOK_URL=https://hooks.slack.com/services/YOUR/WEBHOOK/URL

# PagerDuty (optional)
PAGERDUTY_SERVICE_KEY=your-service-key

# Grafana Configuration
GF_SECURITY_ADMIN_PASSWORD=admin
GF_SECURITY_ADMIN_USER=admin
GF_INSTALL_PLUGINS=grafana-piechart-panel
GF_USERS_ALLOW_SIGN_UP=false
GF_SERVER_ROOT_URL=http://localhost:3000

# Prometheus Configuration
PROMETHEUS_RETENTION=30d
PROMETHEUS_SCRAPE_INTERVAL=15s
PROMETHEUS_EVALUATION_INTERVAL=15s

# Database Configuration
POSTGRES_USER=xagent
POSTGRES_PASSWORD=xagent
POSTGRES_DB=xagent

# Redis Configuration
REDIS_PASSWORD=

# Qdrant Configuration
QDRANT_API_KEY=qdrant_key
EOF
        print_success "Created .env file"
        print_warning "Please review and update .env file with your settings"
    else
        print_success ".env file already exists"
    fi
}

# Pull Docker images
pull_images() {
    print_header "Pulling Docker Images"

    print_info "This may take a few minutes..."
    docker-compose -f "$DOCKER_COMPOSE_FILE" pull

    print_success "Docker images pulled successfully"
}

# Start monitoring stack
start_monitoring() {
    print_header "Starting Monitoring Stack"

    cd "$SCRIPT_DIR"

    print_info "Starting services..."
    docker-compose -f "$DOCKER_COMPOSE_FILE" up -d

    print_success "Monitoring stack started"
}

# Wait for services
wait_for_services() {
    print_header "Waiting for Services to Start"

    local services=(
        "prometheus:9090"
        "grafana:3000"
        "elasticsearch:9200"
        "kibana:5601"
        "jaeger:16686"
        "alertmanager:9093"
    )

    for service in "${services[@]}"; do
        local host="${service%:*}"
        local port="${service#*:}"
        local container_name="x-agent-$host"

        print_info "Waiting for $host:$port..."
        local max_attempts=60
        local attempt=0

        while [ $attempt -lt $max_attempts ]; do
            if docker exec "$container_name" curl -s "http://localhost:$port" > /dev/null 2>&1; then
                print_success "$host is ready"
                break
            fi
            if [ $attempt -eq $((max_attempts - 1)) ]; then
                print_warning "$host is not responding (may still be starting)"
            fi
            sleep 2
            ((attempt++))
        done
    done
}

# Verify services
verify_services() {
    print_header "Verifying Services"

    # Prometheus
    if curl -s http://localhost:9090/-/healthy > /dev/null 2>&1; then
        print_success "Prometheus is healthy"
    else
        print_warning "Prometheus health check failed"
    fi

    # Grafana
    if curl -s http://localhost:3000/api/health > /dev/null 2>&1; then
        print_success "Grafana is healthy"
    else
        print_warning "Grafana health check failed"
    fi

    # Elasticsearch
    if curl -s http://localhost:9200/_cluster/health > /dev/null 2>&1; then
        print_success "Elasticsearch is healthy"
    else
        print_warning "Elasticsearch health check failed"
    fi

    # Jaeger
    if curl -s http://localhost:16686/ > /dev/null 2>&1; then
        print_success "Jaeger is healthy"
    else
        print_warning "Jaeger health check failed"
    fi

    # AlertManager
    if curl -s http://localhost:9093/-/healthy > /dev/null 2>&1; then
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
    echo "    docker-compose -f $DOCKER_COMPOSE_FILE logs -f"
    echo ""
    echo "  View specific service logs:"
    echo "    docker-compose -f $DOCKER_COMPOSE_FILE logs -f prometheus"
    echo ""
    echo "  Stop services:"
    echo "    docker-compose -f $DOCKER_COMPOSE_FILE down"
    echo ""
    echo "  Check service status:"
    echo "    docker-compose -f $DOCKER_COMPOSE_FILE ps"
    echo ""
    echo "  Restart a service:"
    echo "    docker-compose -f $DOCKER_COMPOSE_FILE restart <service-name>"
    echo ""
    echo "Documentation:"
    echo "  - Setup Guide: $SCRIPT_DIR/MONITORING_SETUP_GUIDE.md"
    echo "  - Deployment Checklist: $SCRIPT_DIR/DEPLOYMENT_CHECKLIST.md"
    echo ""
}

# Main execution
main() {
    print_header "X-Agent Monitoring System Deployment"

    check_prerequisites
    create_directories
    setup_environment
    validate_configurations
    pull_images
    start_monitoring
    wait_for_services
    verify_services
    print_access_info

    print_success "Deployment completed successfully!"
}

# Run main function
main "$@"
