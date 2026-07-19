#!/bin/bash
set -e

# X-Agent Rollback Script
# This script rolls back X-Agent deployment to previous version

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

# Configuration
NAMESPACE=${NAMESPACE:-xagent}
RELEASE_NAME=${RELEASE_NAME:-xagent}

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m'

log_info() {
    echo -e "${GREEN}[INFO]${NC} $1"
}

log_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

# Get current revision
get_current_revision() {
    helm history "$RELEASE_NAME" -n "$NAMESPACE" | tail -1 | awk '{print $1}'
}

# Get previous revision
get_previous_revision() {
    helm history "$RELEASE_NAME" -n "$NAMESPACE" | tail -2 | head -1 | awk '{print $1}'
}

# Rollback deployment
rollback() {
    local current_revision=$(get_current_revision)
    local previous_revision=$(get_previous_revision)

    if [ -z "$previous_revision" ]; then
        log_error "No previous revision found"
        exit 1
    fi

    log_info "Current revision: $current_revision"
    log_info "Rolling back to revision: $previous_revision"

    helm rollback "$RELEASE_NAME" "$previous_revision" -n "$NAMESPACE" --wait

    log_info "Rollback completed successfully"
}

# Main
main() {
    log_info "Starting X-Agent rollback"
    log_info "Namespace: $NAMESPACE"
    log_info "Release: $RELEASE_NAME"

    rollback
}

main "$@"
