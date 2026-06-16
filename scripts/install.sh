#!/usr/bin/env sh
set -eu

REPO_URL="${XAGENT_REPO_URL:-https://github.com/xiongpinji/X-Agent.git}"
ZIP_URL="${XAGENT_ZIP_URL:-https://github.com/xiongpinji/X-Agent/archive/refs/heads/${XAGENT_INSTALL_BRANCH:-develop}.zip}"
BRANCH="${XAGENT_INSTALL_BRANCH:-develop}"
XAGENT_HOME="${XAGENT_HOME:-$HOME/.xagent}"
SOURCE_DIR="${XAGENT_SOURCE_DIR:-$XAGENT_HOME/source}"
ENV_FILE="${XAGENT_ENV_FILE:-$XAGENT_HOME/.env}"
HOST="${XAGENT_HOST:-127.0.0.1}"
PORT="${XAGENT_PORT:-8000}"

log() {
  printf '%s\n' "==> $*"
}

fail() {
  printf '%s\n' "ERROR: $*" >&2
  exit 1
}

usage() {
  cat <<'USAGE'
Usage: scripts/install.sh [--mode lite|full] [--check]

Environment:
  INSTALL_MODE=lite|full          Non-interactive install mode
  XAGENT_HOME=~/.xagent           Install state directory
  XAGENT_INSTALL_BRANCH=develop   Git branch or zip ref
  XAGENT_START=0                  Install without starting services
USAGE
}

check_os_arch() {
  os="$(uname -s 2>/dev/null || true)"
  arch="$(uname -m 2>/dev/null || true)"
  case "$os" in
    Linux|Darwin) ;;
    *) fail "Unsupported OS: ${os:-unknown}. Use scripts/install.ps1 on Windows." ;;
  esac
  case "$arch" in
    x86_64|amd64|arm64|aarch64) ;;
    *) fail "Unsupported architecture: ${arch:-unknown}" ;;
  esac
  log "Detected $os/$arch"
}

find_python() {
  for candidate in "${PYTHON:-}" python3.12 python3.11 python3 python; do
    [ -n "$candidate" ] || continue
    if command -v "$candidate" >/dev/null 2>&1; then
      if "$candidate" -c 'import sys; raise SystemExit(0 if sys.version_info >= (3, 11) else 1)' >/dev/null 2>&1; then
        PYTHON_BIN="$candidate"
        return 0
      fi
    fi
  done
  fail "Python 3.11+ is required. Install Python and rerun this script."
}

docker_compose_cmd() {
  if command -v docker >/dev/null 2>&1 && docker compose version >/dev/null 2>&1; then
    printf '%s' "docker compose"
    return 0
  fi
  if command -v docker-compose >/dev/null 2>&1; then
    printf '%s' "docker-compose"
    return 0
  fi
  return 1
}

detect_local_source() {
  script_dir="$(CDPATH= cd -- "$(dirname -- "$0")" 2>/dev/null && pwd -P || printf '')"
  if [ -n "$script_dir" ] && [ -f "$script_dir/../pyproject.toml" ] && [ -d "$script_dir/../backend" ]; then
    (CDPATH= cd -- "$script_dir/.." && pwd -P)
    return 0
  fi
  return 1
}

ensure_source() {
  if local_source="$(detect_local_source 2>/dev/null)"; then
    SOURCE_DIR="$local_source"
    log "Using local source: $SOURCE_DIR"
    return 0
  fi

  if [ -d "$SOURCE_DIR/.git" ]; then
    log "Updating source at $SOURCE_DIR"
    git -C "$SOURCE_DIR" fetch --depth 1 origin "$BRANCH"
    git -C "$SOURCE_DIR" checkout "$BRANCH"
    git -C "$SOURCE_DIR" reset --hard "origin/$BRANCH"
    return 0
  fi

  command -v git >/dev/null 2>&1 || fail "git is required for full mode or local source checkout"
  log "Cloning X-Agent into $SOURCE_DIR"
  mkdir -p "$(dirname "$SOURCE_DIR")"
  git clone --depth 1 --branch "$BRANCH" "$REPO_URL" "$SOURCE_DIR"
}

download_generate_secrets() {
  target="$XAGENT_HOME/generate_secrets.py"
  if [ -f "$SOURCE_DIR/scripts/generate_secrets.py" ]; then
    cp "$SOURCE_DIR/scripts/generate_secrets.py" "$target"
    printf '%s' "$target"
    return 0
  fi
  if command -v curl >/dev/null 2>&1; then
    curl -fsSL "https://raw.githubusercontent.com/xiongpinji/X-Agent/$BRANCH/scripts/generate_secrets.py" -o "$target"
    printf '%s' "$target"
    return 0
  fi
  fail "curl is required to fetch generate_secrets.py"
}

write_base_env() {
  mkdir -p "$XAGENT_HOME" "$XAGENT_HOME/data" "$XAGENT_HOME/logs"
  touch "$ENV_FILE"
  append_if_missing XAGENT_APP_MODE development
  append_if_missing XAGENT_REQUIRE_API_KEY false
  append_if_missing XAGENT_LLM_BACKEND mock
  append_if_missing XAGENT_MEMORY_BACKEND memory
  append_if_missing XAGENT_TRACE_BACKEND jsonl
  append_if_missing XAGENT_DATABASE_URL "sqlite:///./data/xagent.db"
  append_if_missing XAGENT_RUN_STORE_PATH "./data/runs.jsonl"
  append_if_missing XAGENT_TRACE_STORE_PATH "./data/traces.jsonl"
  append_if_missing XAGENT_AUDIT_STORE_PATH "./data/audit.jsonl"
  append_if_missing XAGENT_QDRANT_URL ""
}

append_if_missing() {
  key="$1"
  value="$2"
  if ! grep -Eq "^[[:space:]]*(export[[:space:]]+)?${key}=" "$ENV_FILE"; then
    printf '%s=%s\n' "$key" "$value" >> "$ENV_FILE"
  fi
}

generate_env() {
  generator="$(download_generate_secrets)"
  "$PYTHON_BIN" "$generator" --env-file "$ENV_FILE" --create
}

create_venv() {
  VENV_DIR="$XAGENT_HOME/venv"
  if [ ! -x "$VENV_DIR/bin/python" ]; then
    log "Creating virtual environment at $VENV_DIR"
    "$PYTHON_BIN" -m venv "$VENV_DIR"
  fi
  VENV_PY="$VENV_DIR/bin/python"
  "$VENV_PY" -m pip install --upgrade pip
}

install_lite() {
  create_venv
  if [ -f "$SOURCE_DIR/pyproject.toml" ]; then
    log "Installing X-Agent from local source"
    "$VENV_PY" -m pip install -e "$SOURCE_DIR[cli]"
  else
    log "Installing X-Agent from $ZIP_URL"
    "$VENV_PY" -m pip install "x-agent-core[cli] @ $ZIP_URL"
  fi
  mkdir -p "$XAGENT_HOME/bin"
  ln -sf "$XAGENT_HOME/venv/bin/xagent" "$XAGENT_HOME/bin/xagent"
  if [ -d "$HOME/.local/bin" ]; then
    ln -sf "$XAGENT_HOME/venv/bin/xagent" "$HOME/.local/bin/xagent" 2>/dev/null || true
  fi
  "$XAGENT_HOME/venv/bin/xagent" --version
}

start_lite() {
  [ "${XAGENT_START:-1}" = "1" ] || return 0
  log "Starting X-Agent lite server on http://$HOST:$PORT"
  (
    cd "$XAGENT_HOME"
    set -a
    # shellcheck disable=SC1090
    . "$ENV_FILE"
    set +a
    nohup "$XAGENT_HOME/venv/bin/python" -m uvicorn backend.app.main:app --host "$HOST" --port "$PORT" > "$XAGENT_HOME/logs/xagent.log" 2>&1 &
    printf '%s\n' "$!" > "$XAGENT_HOME/xagent.pid"
  )
  log "PID $(cat "$XAGENT_HOME/xagent.pid") written to $XAGENT_HOME/xagent.pid"
}

install_full() {
  ensure_source
  compose="$(docker_compose_cmd)" || fail "Docker Compose is required for full mode"
  generate_env
  log "Starting Docker Compose stack"
  (cd "$SOURCE_DIR" && $compose --env-file "$ENV_FILE" up -d --build)
}

run_check() {
  check_os_arch
  find_python
  "$PYTHON_BIN" -c 'import sys; print("Python", sys.version.split()[0])'
  if docker_compose_cmd >/dev/null 2>&1; then
    log "Docker Compose detected"
  else
    log "Docker Compose not detected; lite mode remains available"
  fi
  log "install.sh check passed"
}

main() {
  mode="${INSTALL_MODE:-}"
  while [ "$#" -gt 0 ]; do
    case "$1" in
      --mode)
        mode="${2:-}"
        shift 2
        ;;
      --check)
        run_check
        exit 0
        ;;
      -h|--help)
        usage
        exit 0
        ;;
      *)
        fail "Unknown argument: $1"
        ;;
    esac
  done

  check_os_arch
  find_python
  mkdir -p "$XAGENT_HOME"

  if [ -z "$mode" ]; then
    printf 'Install mode [lite/full] (default: lite): '
    read -r mode || mode=""
    mode="${mode:-lite}"
  fi

  case "$mode" in
    lite)
      write_base_env
      if detect_local_source >/dev/null 2>&1; then
        SOURCE_DIR="$(detect_local_source)"
      fi
      generate_env
      install_lite
      start_lite
      ;;
    full)
      write_base_env
      install_full
      ;;
    *)
      fail "INSTALL_MODE must be lite or full"
      ;;
  esac

  log "X-Agent install completed"
  log "Config: $ENV_FILE"
  log "CLI: $XAGENT_HOME/bin/xagent"
}

main "$@"
