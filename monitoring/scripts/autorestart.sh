#!/bin/bash

# X-Agent Auto-Restart Script
# Automatically restarts unhealthy services

set -e

# Configuration
HEALTH_CHECK_URL="${HEALTH_CHECK_URL:-http://localhost:8000/health}"
DOCKER_COMPOSE_FILE="${DOCKER_COMPOSE_FILE:-docker-compose.yml}"
CHECK_INTERVAL="${CHECK_INTERVAL:-30}"  # seconds
MAX_RETRIES="${MAX_RETRIES:-3}"
RETRY_DELAY="${RETRY_DELAY:-10}"  # seconds
LOG_FILE="/var/log/xagent/autorestart.log"

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Logging function
log() {
    echo "[$(date +'%Y-%m-%d %H:%M:%S')] $1" | tee -a "$LOG_FILE"
}

# Check service health
check_health() {
    local service=$1
    local url=$2
    local retries=0

    while [ $retries -lt "$MAX_RETRIES" ]; do
        if curl -sf "$url" > /dev/null 2>&1; then
            log "${GREEN}$service is healthy${NC}"
            return 0
        fi
        retries=$((retries + 1))
        if [ $retries -lt "$MAX_RETRIES" ]; then
            log "${YELLOW}$service health check failed (attempt $retries/$MAX_RETRIES). Retrying in ${RETRY_DELAY}s...${NC}"
            sleep "$RETRY_DELAY"
        fi
    done

    log "${RED}$service is unhealthy after $MAX_RETRIES attempts${NC}"
    return 1
}

# Restart service
restart_service() {
    local service=$1
    log "${YELLOW}Restarting $service...${NC}"

    docker-compose -f "$DOCKER_COMPOSE_FILE" restart "$service" 2>&1 | tee -a "$LOG_FILE"

    if [ $? -eq 0 ]; then
        log "${GREEN}$service restarted successfully${NC}"
        sleep 10  # Wait for service to start
        return 0
    else
        log "${RED}Failed to restart $service${NC}"
        return 1
    fi
}

# Get service status
get_service_status() {
    local service=$1
    docker-compose -f "$DOCKER_COMPOSE_FILE" ps "$service" 2>/dev/null | grep -q "Up" && echo "running" || echo "stopped"
}

# Monitor and restart services
monitor_services() {
    local services=("x-agent-api" "x-agent-worker" "postgres" "redis" "elasticsearch")

    for service in "${services[@]}"; do
        local status=$(get_service_status "$service")

        if [ "$status" != "running" ]; then
            log "${RED}$service is not running. Attempting restart...${NC}"
            restart_service "$service"
            continue
        fi

        # Check service-specific health endpoints
        case $service in
            "x-agent-api")
                if ! check_health "$service" "http://localhost:8000/health"; then
                    restart_service "$service"
                fi
                ;;
            "x-agent-worker")
                if ! check_health "$service" "http://localhost:8001/health"; then
                    restart_service "$service"
                fi
                ;;
            "postgres")
                if ! docker-compose -f "$DOCKER_COMPOSE_FILE" exec -T postgres pg_isready -U xagent > /dev/null 2>&1; then
                    log "${RED}PostgreSQL is not responding${NC}"
                    restart_service "$service"
                fi
                ;;
            "redis")
                if ! docker-compose -f "$DOCKER_COMPOSE_FILE" exec -T redis redis-cli ping > /dev/null 2>&1; then
                    log "${RED}Redis is not responding${NC}"
                    restart_service "$service"
                fi
                ;;
            "elasticsearch")
                if ! curl -sf "http://localhost:9200/_cluster/health" > /dev/null 2>&1; then
                    log "${RED}Elasticsearch is not responding${NC}"
                    restart_service "$service"
                fi
                ;;
        esac
    done
}

# Main loop
main() {
    log "Starting X-Agent Auto-Restart Service"
    log "Health check interval: ${CHECK_INTERVAL}s"
    log "Max retries: $MAX_RETRIES"

    while true; do
        monitor_services
        sleep "$CHECK_INTERVAL"
    done
}

# Trap signals for graceful shutdown
trap 'log "Shutting down..."; exit 0' SIGTERM SIGINT

# Run main function
main
