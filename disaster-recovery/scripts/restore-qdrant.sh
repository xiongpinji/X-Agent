#!/bin/bash
# X-Agent Qdrant Restore Script (P1-17)
# Restores a collection from a snapshot file produced by deployment/backup/backup.sh,
# using the official snapshot upload API:
#   POST /collections/{name}/snapshots/upload  (multipart field "snapshot")
# Usage: bash disaster-recovery/scripts/restore-qdrant.sh <snapshot_file> <collection_name>

set -euo pipefail

if [ $# -lt 2 ]; then
  echo "Usage: bash disaster-recovery/scripts/restore-qdrant.sh <snapshot_file> <collection_name>"
  exit 1
fi

SNAPSHOT_FILE="$1"
COLLECTION="$2"
QDRANT_HOST=${QDRANT_HOST:-localhost}
QDRANT_PORT=${QDRANT_PORT:-6333}
QDRANT_API_KEY=${QDRANT_API_KEY:-}
BASE="http://$QDRANT_HOST:$QDRANT_PORT"

GREEN='\033[0;32m'; RED='\033[0;31m'; NC='\033[0m'
log_info() { echo -e "${GREEN}[INFO]${NC} $1"; }
log_error() { echo -e "${RED}[ERROR]${NC} $1"; }

[ -f "$SNAPSHOT_FILE" ] || { log_error "Snapshot not found: $SNAPSHOT_FILE"; exit 1; }

AUTH=()
[ -n "$QDRANT_API_KEY" ] && AUTH=(-H "api-key: $QDRANT_API_KEY")

log_info "Uploading snapshot $SNAPSHOT_FILE -> collection '$COLLECTION' ($BASE)"
if curl -sf -X POST "${AUTH[@]}" \
    -F "snapshot=@$SNAPSHOT_FILE" \
    "$BASE/collections/$COLLECTION/snapshots/upload" > /dev/null; then
  log_info "Snapshot uploaded, verifying collection info..."
  info=$(curl -sf "${AUTH[@]}" "$BASE/collections/$COLLECTION") || {
    log_error "Collection info unavailable after restore"; exit 1; }
  echo "$info"
  log_info "Restore completed for collection: $COLLECTION"
else
  log_error "Snapshot upload failed for collection: $COLLECTION"
  exit 1
fi
