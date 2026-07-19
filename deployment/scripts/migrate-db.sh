#!/bin/bash
set -e

# X-Agent Database Migration Script
# This script handles database migrations safely

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"

# Configuration
NAMESPACE=${NAMESPACE:-xagent}
ENVIRONMENT=${ENVIRONMENT:-production}

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m'

log_info() {
    echo -e "${GREEN}[INFO]${NC} $1"
}

log_warn() {
    echo -e "${YELLOW}[WARN]${NC} $1"
}

log_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

# Backup database before migration
backup_database() {
    log_info "Creating database backup..."

    local backup_dir="/backups/xagent"
    local backup_file="$backup_dir/pre_migration_$(date +%Y%m%d_%H%M%S).sql"

    mkdir -p "$backup_dir"

    if command -v docker-compose &> /dev/null; then
        docker-compose exec -T postgres pg_dump -U xagent xagent_db > "$backup_file"
    else
        kubectl exec -i deployment/postgres -n "$NAMESPACE" -- \
            pg_dump -U xagent xagent_db > "$backup_file"
    fi

    log_info "Backup created: $backup_file"
    echo "$backup_file"
}

# Run migrations
run_migrations() {
    log_info "Running database migrations..."

    if command -v docker-compose &> /dev/null; then
        docker-compose exec xagent-api alembic upgrade head
    else
        local api_pod=$(kubectl get pods -n "$NAMESPACE" -l app=xagent-api -o jsonpath='{.items[0].metadata.name}')
        kubectl exec -it "$api_pod" -n "$NAMESPACE" -- alembic upgrade head
    fi

    log_info "Migrations completed successfully"
}

# Verify migrations
verify_migrations() {
    log_info "Verifying migrations..."

    if command -v docker-compose &> /dev/null; then
        docker-compose exec xagent-api alembic current
    else
        local api_pod=$(kubectl get pods -n "$NAMESPACE" -l app=xagent-api -o jsonpath='{.items[0].metadata.name}')
        kubectl exec -it "$api_pod" -n "$NAMESPACE" -- alembic current
    fi

    log_info "Migration verification completed"
}

# Rollback migrations
rollback_migrations() {
    local backup_file=$1

    log_warn "Rolling back migrations..."

    if command -v docker-compose &> /dev/null; then
        docker-compose exec -T postgres psql -U xagent xagent_db < "$backup_file"
    else
        kubectl exec -i deployment/postgres -n "$NAMESPACE" -- \
            psql -U xagent xagent_db < "$backup_file"
    fi

    log_info "Rollback completed"
}

# Main
main() {
    log_info "Starting database migration"
    log_info "Environment: $ENVIRONMENT"

    # Create backup
    backup_file=$(backup_database)

    # Run migrations
    if ! run_migrations; then
        log_error "Migration failed, rolling back..."
        rollback_migrations "$backup_file"
        exit 1
    fi

    # Verify migrations
    verify_migrations

    log_info "Database migration completed successfully"
}

main "$@"
