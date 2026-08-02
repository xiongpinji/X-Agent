#!/usr/bin/env bash
# X-Agent one-command installer (Linux / macOS / Windows Git Bash).
#
#   bash install.sh          # install (idempotent; re-run only fills gaps)
#   bash install.sh --dev    # also install dev dependencies
#
# Steps: check Python >= 3.11 -> create/reuse venv -> pip install -e .
# -> generate .env from .env.development -> run `xagent doctor` self-check.
#
# Idempotency: if a working venv already exists (backend package importable
# and the xagent entry point present), the heavy pip install is skipped.
set -euo pipefail

# Allow unit tests to source this file without executing the installer.
if [[ "${XAGENT_INSTALL_LIB_ONLY:-0}" != "1" && "${BASH_SOURCE[0]}" != "${0}" ]]; then
    return 0
fi

INSTALL_DEV=0
VENV_DIR="venv"
ENV_FILE=".env"
ENV_TEMPLATE=".env.development"
MIN_PY_MAJOR=3
MIN_PY_MINOR=11

log()  { printf '==> %s\n' "$*"; }
ok()   { printf '  ✓ %s\n' "$*"; }
warn() { printf '  ⚠ %s\n' "$*"; }
die()  { printf '  ✗ %s\n' "$*" >&2; exit 1; }

usage() {
    cat <<'EOF'
X-Agent one-command installer

Usage:
  bash install.sh [--dev]

Options:
  --dev, -d    Install with dev dependencies (pip install -e ".[dev]")
  --help, -h   Show this help
EOF
}

# ─── Python discovery ────────────────────────────────────────────────────────

# Echo a working python command (possibly multi-word like "py -3.11") that is
# >= 3.11; return 1 if none found.
find_system_python() {
    local candidates=("python" "python3" "py -3.13" "py -3.12" "py -3.11" "py")
    local cmd
    for cmd in "${candidates[@]}"; do
        # shellcheck disable=SC2086
        if command -v ${cmd%% *} >/dev/null 2>&1; then
            # shellcheck disable=SC2086
            if $cmd -c "import sys; raise SystemExit(0 if sys.version_info >= (${MIN_PY_MAJOR}, ${MIN_PY_MINOR}) else 1)" 2>/dev/null; then
                printf '%s' "$cmd"
                return 0
            fi
        fi
    done
    return 1
}

# Path of the venv's python (Git Bash on Windows uses Scripts/, POSIX bin/).
venv_python() {
    if [[ -x "${VENV_DIR}/Scripts/python.exe" ]]; then
        printf '%s' "${VENV_DIR}/Scripts/python.exe"
    elif [[ -x "${VENV_DIR}/bin/python" ]]; then
        printf '%s' "${VENV_DIR}/bin/python"
    else
        return 1
    fi
}

# Path of the venv's xagent entry point (empty string if missing).
venv_xagent() {
    if [[ -x "${VENV_DIR}/Scripts/xagent.exe" ]]; then
        printf '%s' "${VENV_DIR}/Scripts/xagent.exe"
    elif [[ -x "${VENV_DIR}/bin/xagent" ]]; then
        printf '%s' "${VENV_DIR}/bin/xagent"
    else
        printf '%s' ""
    fi
}

# Return 0 if the venv python can import the backend package.
backend_importable() {
    local vpy="$1"
    "$vpy" -c "import backend.app.settings, backend.app.core.agent" >/dev/null 2>&1
}

# Decide whether the heavy pip install can be skipped: venv python exists,
# backend imports, and the xagent entry point is present.
should_skip_install() {
    local vpy
    vpy="$(venv_python)" || return 1
    [[ -n "$(venv_xagent)" ]] || return 1
    backend_importable "$vpy"
}

# Copy the env template only when the target does not exist (never overwrite).
ensure_env_file() {
    if [[ -f "${ENV_FILE}" ]]; then
        ok "${ENV_FILE} 已存在，保留现状"
        return 0
    fi
    if [[ -f "${ENV_TEMPLATE}" ]]; then
        cp "${ENV_TEMPLATE}" "${ENV_FILE}"
        ok "已从 ${ENV_TEMPLATE} 生成 ${ENV_FILE}"
    else
        warn "${ENV_TEMPLATE} 不存在，跳过 .env 生成"
    fi
}

main() {
    local arg
    for arg in "$@"; do
        case "$arg" in
            --dev|-d) INSTALL_DEV=1 ;;
            --help|-h) usage; exit 0 ;;
            *) die "未知参数: $arg（用 --help 查看用法）" ;;
        esac
    done

    [[ -f "pyproject.toml" && -d "backend" ]] || die "请在 X-Agent 仓库根目录运行本脚本"

    log "X-Agent 一条命令安装 (Track D2)"

    # ─── 1/5 Python >= 3.11 ─────────────────────────────────────────────────
    log "[1/5] 检查 Python >= ${MIN_PY_MAJOR}.${MIN_PY_MINOR}"
    local vpy=""
    if vpy="$(venv_python)"; then
        ok "复用已有 venv: $("$vpy" --version 2>&1)"
    else
        local syspy
        syspy="$(find_system_python)" || die "未找到 Python >= ${MIN_PY_MAJOR}.${MIN_PY_MINOR}，请先安装: https://www.python.org/downloads/"
        ok "系统 Python: $($syspy --version 2>&1)"
        log "[2/5] 创建虚拟环境 ${VENV_DIR}/"
        # shellcheck disable=SC2086
        $syspy -m venv "${VENV_DIR}"
        vpy="$(venv_python)" || die "venv 创建后未找到 python"
        ok "venv 已创建"
    fi
    [[ -z "${VIRTUAL_ENV:-}" ]] || warn "检测到已激活的 VIRTUAL_ENV=${VIRTUAL_ENV}，本脚本始终使用 ./${VENV_DIR}"

    # ─── 2-3/5 install (skip heavy work when venv is already usable) ────────
    if should_skip_install; then
        log "[2/5] 依赖安装: 跳过（venv 可用且 backend 可导入，幂等复用）"
        ok "xagent 入口: $(venv_xagent)"
    else
        log "[2/5] 安装依赖 pip install -e .$([[ $INSTALL_DEV -eq 1 ]] && echo '[dev]')"
        "$vpy" -m pip install --upgrade pip >/dev/null
        if [[ $INSTALL_DEV -eq 1 ]]; then
            "$vpy" -m pip install -e ".[dev]"
        else
            "$vpy" -m pip install -e .
        fi
        ok "依赖安装完成"
    fi
    if [[ $INSTALL_DEV -eq 1 ]]; then
        # Dev extras are cheap to top up even on the reuse path; only run when
        # something is clearly missing (pytest importable?).
        if ! "$vpy" -c "import pytest" >/dev/null 2>&1; then
            log "[3/5] 补齐 dev 依赖"
            "$vpy" -m pip install -e ".[dev]"
            ok "dev 依赖已补齐"
        else
            log "[3/5] dev 依赖已就绪，跳过"
        fi
    else
        log "[3/5] 未指定 --dev，跳过 dev 依赖"
    fi

    # ─── 4/5 .env ────────────────────────────────────────────────────────────
    log "[4/5] 配置 .env"
    ensure_env_file

    # ─── 5/5 doctor ─────────────────────────────────────────────────────────
    log "[5/5] 运行 xagent doctor 自检"
    local doctor_rc=0
    "$vpy" -m cli.main doctor || doctor_rc=$?
    if [[ $doctor_rc -ne 0 ]]; then
        warn "doctor 存在失败项（见上方 ✗），请先按修复建议处理"
    fi

    local xagent_bin
    xagent_bin="$(venv_xagent)"
    [[ -n "$xagent_bin" ]] || xagent_bin="$vpy -m cli.main"
    cat <<EOF

==> 安装完成。下一步:
  1. $xagent_bin doctor                                    # 环境自检
  2. $xagent_bin agent run "你好" --mode local             # 本地模式跑一个任务
  3. "$vpy" -m uvicorn backend.app.main:app --port 8000     # 启动 API 服务
EOF
    [[ $doctor_rc -eq 0 ]]
}

if [[ "${XAGENT_INSTALL_LIB_ONLY:-0}" != "1" ]]; then
    main "$@"
fi
