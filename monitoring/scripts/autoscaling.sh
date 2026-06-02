#!/bin/bash

# X-Agent Auto-Scaling Script
# Automatically scales services based on CPU and memory usage

set -e

# Configuration
PROMETHEUS_URL="${PROMETHEUS_URL:-http://localhost:9090}"
DOCKER_COMPOSE_FILE="${DOCKER_COMPOSE_FILE:-docker-compose.yml}"
MIN_REPLICAS="${MIN_REPLICAS:-1}"
MAX_REPLICAS="${MAX_REPLICAS:-5}"
CPU_THRESHOLD="${CPU_THRESHOLD:-80}"
MEMORY_THRESHOLD="${MEMORY_THRESHOLD:-85}"
SCALE_UP_COOLDOWN="${SCALE_UP_COOLDOWN:-300}"  # 5 minutes
SCALE_DOWN_COOLDOWN="${SCALE_DOWN_COOLDOWN:-600}"  # 10 minutes
LOG_FILE="/var/log/xagent/autoscaling.log"

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Logging function
log() {
    echo "[$(date +'%Y-%m-%d %H:%M:%S')] $1" | tee -a "$LOG_FILE"
}

# Get current metric from Prometheus
get_metric() {
    local query=$1
    local result=$(curl -s "${PROMETHEUS_URL}/api/v1/query?query=${query}" | jq -r '.data.result[0].value[1]' 2>/dev/null || echo "0")
    echo "$result"
}

# Get current CPU usage
get_cpu_usage() {
    local query="xagent:system:cpu_usage_percent"
    get_metric "$query"
}

# Get current memory usage
get_memory_usage() {
    local query="xagent:system:memory_usage_percent"
    get_metric "$query"
}

# Get current replica count
get_replica_count() {
    local service=$1
    docker-compose -f "$DOCKER_COMPOSE_FILE" ps "$service" 2>/dev/null | grep -c "$service" || echo "0"
}

# Scale service up
scale_up() {
    local service=$1
    local current_replicas=$(get_replica_count "$service")
    local new_replicas=$((current_replicas + 1))

    if [ "$new_replicas" -le "$MAX_REPLICAS" ]; then
        log "${GREEN}Scaling up $service from $current_replicas to $new_replicas replicas${NC}"
        docker-compose -f "$DOCKER_COMPOSE_FILE" up -d --scale "$service=$new_replicas" 2>&1 | tee -a "$LOG_FILE"
        return 0
    else
        log "${YELLOW}Cannot scale up $service: already at max replicas ($MAX_REPLICAS)${NC}"
        return 1
    fi
}

# Scale service down
scale_down() {
    local service=$1
    local current_replicas=$(get_replica_count "$service")
    local new_replicas=$((current_replicas - 1))

    if [ "$new_replicas" -ge "$MIN_REPLICAS" ]; then
        log "${GREEN}Scaling down $service from $current_replicas to $new_replicas replicas${NC}"
        docker-compose -f "$DOCKER_COMPOSE_FILE" up -d --scale "$service=$new_replicas" 2>&1 | tee -a "$LOG_FILE"
        return 0
    else
        log "${YELLOW}Cannot scale down $service: already at min replicas ($MIN_REPLICAS)${NC}"
        return 1
    fi
}

# Check and auto-scale
check_and_scale() {
    local cpu_usage=$(get_cpu_usage)
    local memory_usage=$(get_memory_usage)

    log "Current metrics - CPU: ${cpu_usage}%, Memory: ${memory_usage}%"

    # Scale up if thresholds exceeded
    if (( $(echo "$cpu_usage > $CPU_THRESHOLD" | bc -l) )) || (( $(echo "$memory_usage > $MEMORY_THRESHOLD" | bc -l) )); then
        log "${RED}High resource usage detected. Scaling up...${NC}"
        scale_up "x-agent-api"
        scale_up "x-agent-worker"
        sleep "$SCALE_UP_COOLDOWN"
    fi

    # Scale down if resources are low
    if (( $(echo "$cpu_usage < 30" | bc -l) )) && (( $(echo "$memory_usage < 40" | bc -l) )); then
        log "${GREEN}Low resource usage detected. Scaling down...${NC}"
        scale_down "x-agent-api"
        scale_down "x-agent-worker"
        sleep "$SCALE_DOWN_COOLDOWN"
    fi
}

# Main loop
main() {
    log "Starting X-Agent Auto-Scaling Service"
    log "Configuration: CPU_THRESHOLD=$CPU_THRESHOLD%, MEMORY_THRESHOLD=$MEMORY_THRESHOLD%"
    log "Min Replicas: $MIN_REPLICAS, Max Replicas: $MAX_REPLICAS"

    while true; do
        check_and_scale
        sleep 60  # Check every minute
    done
}

# Run main function
main
