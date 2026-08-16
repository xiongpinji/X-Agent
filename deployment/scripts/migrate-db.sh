#!/usr/bin/env bash
set -euo pipefail

# Apply the forward-only production migration after an operator has verified a
# restorable backup. Database restoration is intentionally a separate,
# explicitly confirmed operation (restore-database.sh).

DRY_RUN=false
if [[ "${1:-}" == "--dry-run" ]]; then
  DRY_RUN=true
  shift
fi
if [[ $# -ne 0 ]]; then
  echo "Usage: migrate-db.sh [--dry-run]" >&2
  exit 2
fi

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"
NAMESPACE="${NAMESPACE:-xagent}"
BACKUP_ID="${XAGENT_PRE_MIGRATION_BACKUP_ID:-}"

if [[ ! -f "$PROJECT_ROOT/backend/migrations/alembic.ini" ]]; then
  echo "Required Alembic configuration is missing" >&2
  exit 2
fi
if [[ -z "$BACKUP_ID" ]]; then
  echo "XAGENT_PRE_MIGRATION_BACKUP_ID must reference a verified backup" >&2
  exit 2
fi

if $DRY_RUN; then
  echo "Migration dry-run validated namespace=$NAMESPACE backup_id=$BACKUP_ID"
  exit 0
fi

if command -v docker-compose >/dev/null 2>&1; then
  docker-compose exec -T \
    -e XAGENT_PRE_MIGRATION_BACKUP_ID="$BACKUP_ID" \
    xagent-api python -m backend.app.ops.migration_gate upgrade --timeout 300
else
  command -v kubectl >/dev/null 2>&1 || { echo "kubectl is required" >&2; exit 2; }
  api_pod="$(kubectl get pods -n "$NAMESPACE" -l app=xagent-api -o jsonpath='{.items[0].metadata.name}')"
  [[ -n "$api_pod" ]] || { echo "No xagent-api pod found" >&2; exit 2; }
  kubectl exec "$api_pod" -n "$NAMESPACE" -- env \
    XAGENT_PRE_MIGRATION_BACKUP_ID="$BACKUP_ID" \
    python -m backend.app.ops.migration_gate upgrade --timeout 300
fi

echo "Migration completed from verified backup reference: $BACKUP_ID"
