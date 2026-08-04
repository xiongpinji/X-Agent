#!/bin/bash

# X-Agent Test Environment Deployment Script
# This script deploys the complete test environment with all services

set -e

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Configuration
PROJECT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
COMPOSE_FILE="${PROJECT_DIR}/docker-compose.test.yml"
ENV_FILE="${PROJECT_DIR}/.env.test"
LOG_DIR="${PROJECT_DIR}/logs"
TIMESTAMP=$(date +%Y%m%d_%H%M%S)

# Functions
log_info() {
    echo -e "${BLUE}[INFO]${NC} $1"
}

log_success() {
    echo -e "${GREEN}[SUCCESS]${NC} $1"
}

log_warning() {
    echo -e "${YELLOW}[WARNING]${NC} $1"
}

log_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

# Check prerequisites
check_prerequisites() {
    log_info "Checking prerequisites..."

    if ! command -v docker &> /dev/null; then
        log_error "Docker is not installed"
        exit 1
    fi

    if ! command -v docker-compose &> /dev/null; then
        log_error "Docker Compose is not installed"
        exit 1
    fi

    if [ ! -f "$ENV_FILE" ]; then
        log_error "Environment file not found: $ENV_FILE"
        exit 1
    fi

    if [ ! -f "$COMPOSE_FILE" ]; then
        log_error "Docker Compose file not found: $COMPOSE_FILE"
        exit 1
    fi

    log_success "All prerequisites met"
}

# Create necessary directories
create_directories() {
    log_info "Creating necessary directories..."

    mkdir -p "$LOG_DIR"
    mkdir -p "${PROJECT_DIR}/test-results"
    mkdir -p "${PROJECT_DIR}/coverage"
    mkdir -p "${PROJECT_DIR}/performance-results"
    # P0-01/P0-04 收敛：deployment/migrations（init.sql 旧路径）与
    # deployment/prometheus（监控栈已归 monitoring/）均不再创建
    mkdir -p "${PROJECT_DIR}/deployment/grafana/provisioning/dashboards"
    mkdir -p "${PROJECT_DIR}/deployment/grafana/provisioning/datasources"
    mkdir -p "${PROJECT_DIR}/deployment/alertmanager"
    mkdir -p "${PROJECT_DIR}/deployment/elk"

    log_success "Directories created"
}

# Build Docker images
build_images() {
    log_info "Building Docker images..."

    docker-compose -f "$COMPOSE_FILE" --env-file "$ENV_FILE" build --no-cache

    log_success "Docker images built successfully"
}

# Start services
start_services() {
    log_info "Starting services..."

    # Start infrastructure services first
    log_info "Starting infrastructure services..."
    docker-compose -f "$COMPOSE_FILE" --env-file "$ENV_FILE" up -d postgres redis qdrant neo4j

    # Wait for infrastructure to be healthy
    log_info "Waiting for infrastructure services to be healthy..."
    sleep 30

    # Start monitoring services
    log_info "Starting monitoring services..."
    docker-compose -f "$COMPOSE_FILE" --env-file "$ENV_FILE" up -d prometheus grafana alertmanager node-exporter jaeger

    # Start logging services
    log_info "Starting logging services..."
    docker-compose -f "$COMPOSE_FILE" --env-file "$ENV_FILE" up -d elasticsearch logstash kibana

    # Wait for services to be ready
    log_info "Waiting for services to be ready..."
    sleep 30

    # Start backend services
    log_info "Starting backend services..."
    docker-compose -f "$COMPOSE_FILE" --env-file "$ENV_FILE" up -d xagent-api xagent-worker xagent-beat

    # Start frontend
    log_info "Starting frontend..."
    docker-compose -f "$COMPOSE_FILE" --env-file "$ENV_FILE" up -d xagent-web

    log_success "All services started"
}

# Health checks
health_checks() {
    log_info "Performing health checks..."

    local services=(
        "xagent-api:8000"
        "xagent-web:3000"
        "prometheus:9090"
        "grafana:3001"
        "kibana:5601"
        "jaeger:16686"
    )

    for service in "${services[@]}"; do
        IFS=':' read -r name port <<< "$service"
        log_info "Checking $name on port $port..."

        for i in {1..30}; do
            if curl -s "http://localhost:$port" > /dev/null 2>&1; then
                log_success "$name is healthy"
                break
            fi

            if [ $i -eq 30 ]; then
                log_warning "$name health check failed"
            fi

            sleep 2
        done
    done
}

# Display service URLs
display_urls() {
    log_info "Test environment is ready!"
    echo ""
    echo -e "${GREEN}Service URLs:${NC}"
    echo "  API:              http://localhost:8000"
    echo "  API Docs:         http://localhost:8000/docs"
    echo "  Web Frontend:     http://localhost:3000"
    echo "  Prometheus:       http://localhost:9090"
    echo "  Grafana:          http://localhost:3001 (admin/admin)"
    echo "  Kibana:           http://localhost:5601"
    echo "  Jaeger:           http://localhost:16686"
    echo "  AlertManager:     http://localhost:9093"
    echo ""
    echo -e "${GREEN}Database Connections:${NC}"
    echo "  PostgreSQL:       localhost:5432 (xagent_test/test_password_123)"
    echo "  Redis:            localhost:6379"
    echo "  Qdrant:           localhost:6333"
    echo "  Neo4j:            localhost:7687 (neo4j/test_neo4j_123)"
    echo ""
}

# Run tests
run_tests() {
    log_info "Running tests..."

    docker-compose -f "$COMPOSE_FILE" --env-file "$ENV_FILE" run --rm test-runner

    log_success "Tests completed"
}

# Generate reports
generate_reports() {
    log_info "Generating reports..."

    if [ -d "${PROJECT_DIR}/coverage" ]; then
        log_success "Coverage report available at: ${PROJECT_DIR}/coverage/index.html"
    fi

    if [ -d "${PROJECT_DIR}/test-results" ]; then
        log_success "Test results available at: ${PROJECT_DIR}/test-results"
    fi
}

# Cleanup
cleanup() {
    log_info "Cleaning up..."

    docker-compose -f "$COMPOSE_FILE" --env-file "$ENV_FILE" down -v

    log_success "Cleanup completed"
}

# Main execution
main() {
    log_info "Starting X-Agent Test Environment Deployment"
    log_info "Timestamp: $TIMESTAMP"
    echo ""

    case "${1:-deploy}" in
        deploy)
            check_prerequisites
            create_directories
            build_images
            start_services
            health_checks
            display_urls
            ;;
        test)
            check_prerequisites
            run_tests
            generate_reports
            ;;
        logs)
            docker-compose -f "$COMPOSE_FILE" --env-file "$ENV_FILE" logs -f
            ;;
        stop)
            log_info "Stopping services..."
            docker-compose -f "$COMPOSE_FILE" --env-file "$ENV_FILE" down
            log_success "Services stopped"
            ;;
        clean)
            cleanup
            ;;
        restart)
            cleanup
            check_prerequisites
            create_directories
            build_images
            start_services
            health_checks
            display_urls
            ;;
        *)
            echo "Usage: $0 {deploy|test|logs|stop|clean|restart}"
            echo ""
            echo "Commands:"
            echo "  deploy   - Deploy the complete test environment (default)"
            echo "  test     - Run the test suite"
            echo "  logs     - Show service logs"
            echo "  stop     - Stop all services"
            echo "  clean    - Stop and remove all containers and volumes"
            echo "  restart  - Restart the entire environment"
            exit 1
            ;;
    esac
}

# Run main function
main "$@"
