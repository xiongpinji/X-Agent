#!/usr/bin/env bash
set -euo pipefail

# Backward-compatible entrypoint for application-only Helm rollback.
# Database downgrades are intentionally unsupported: migration 0002 is
# forward-only and recovery requires an operator-approved verified backup.
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

if [[ $# -ne 0 ]]; then
  echo "Legacy rollback options are disabled; database rollback is not supported." >&2
  exit 2
fi

exec "$SCRIPT_DIR/scripts/rollback.sh"
