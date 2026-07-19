#!/usr/bin/env sh
set -eu

ROOT="$(CDPATH= cd -- "$(dirname -- "$0")/.." && pwd)"
EXECUTE=0

for arg in "$@"; do
  case "$arg" in
    --execute) EXECUTE=1 ;;
    --dry-run) EXECUTE=0 ;;
    *) echo "Unknown argument: $arg" >&2; exit 2 ;;
  esac
done

run_cmd() {
  echo "> $*"
  if [ "$EXECUTE" -eq 1 ]; then
    (cd "$ROOT" && sh -c "$*")
  fi
}

echo "X-Agent installer ($( [ "$EXECUTE" -eq 1 ] && echo execute || echo dry-run ))"
echo "Root: $ROOT"
run_cmd "python -m venv venv"
run_cmd "./venv/bin/python -m pip install --upgrade pip"
run_cmd "./venv/bin/python -m pip install -e '.[dev,cli]'"
run_cmd "cd frontend && npm ci && npm run type-check"
run_cmd "./venv/bin/python scripts/xagent_doctor.py --json"

if [ "$EXECUTE" -eq 0 ]; then
  echo "Dry-run only. Rerun with --execute to apply."
fi
