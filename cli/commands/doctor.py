"""`xagent doctor` — local environment self-check.

Runs a series of environment checks and prints ✓/⚠/✗ per item with a
fix suggestion. Exit code is 0 when no check fails (warnings allowed),
1 otherwise.

Checks:
    1. Python version (>= 3.11)
    2. backend package importable
    3. DATABASE_URL driver (sqlite must use aiosqlite)
    4. LLM API key configured (deepseek / openai / anthropic, or mock backend)
    5. playwright availability
    6. sandbox (subprocess) availability
    7. data/ directory writable
"""

from __future__ import annotations

import os
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path

import typer

from cli.state import get_current_config

# Project root = repo root (cli/commands/doctor.py -> parents[2]).
PROJECT_ROOT = Path(__file__).resolve().parents[2]


@dataclass
class DoctorCheck:
    """Single doctor check result."""

    name: str
    status: str  # "pass" | "warn" | "fail"
    message: str
    suggestion: str = ""

    @property
    def icon(self) -> str:
        return {"pass": "✓", "warn": "⚠", "fail": "✗"}.get(self.status, "?")


def _check_python_version() -> DoctorCheck:
    v = sys.version_info
    version_str = f"{v.major}.{v.minor}.{v.micro}"
    if v >= (3, 11):
        return DoctorCheck("python_version", "pass", f"Python {version_str} (>= 3.11)")
    return DoctorCheck(
        "python_version",
        "fail",
        f"Python {version_str}，需要 >= 3.11",
        "安装 Python 3.11+ 并重建 venv: py -3.11 -m venv venv",
    )


def _check_backend_importable() -> DoctorCheck:
    try:
        import backend.app.core.agent
        import backend.app.settings  # noqa: F401
    except Exception as e:
        return DoctorCheck(
            "backend_import",
            "fail",
            f"backend 导入失败: {e}",
            "在仓库根目录运行，并安装依赖: venv/Scripts/pip install -r requirements.txt",
        )
    return DoctorCheck("backend_import", "pass", "backend 包可正常导入")


def _load_settings():
    """Load backend settings; returns (settings, error)."""
    try:
        from backend.app.settings import get_settings

        return get_settings(), None
    except Exception as e:  # pragma: no cover - defensive
        return None, e


def _check_database_url() -> DoctorCheck:
    settings, err = _load_settings()
    if settings is None:
        return DoctorCheck(
            "database_url",
            "warn",
            f"无法读取 backend settings: {err}",
            "先修复 backend_import 检查项",
        )
    url = str(getattr(settings, "database_url", "") or "")
    lowered = url.lower()
    if lowered.startswith("sqlite"):
        if "aiosqlite" in lowered:
            return DoctorCheck("database_url", "pass", f"DATABASE_URL 使用 sqlite+aiosqlite 驱动: {url}")
        return DoctorCheck(
            "database_url",
            "fail",
            f"sqlite 数据库必须使用 aiosqlite 异步驱动: {url}",
            "将 XAGENT_DATABASE_URL 改为 sqlite+aiosqlite:///./data/xagent.db",
        )
    if lowered.startswith("postgresql"):
        if "asyncpg" in lowered:
            return DoctorCheck("database_url", "pass", f"DATABASE_URL 使用 postgresql+asyncpg 驱动: {url}")
        return DoctorCheck(
            "database_url",
            "warn",
            f"postgresql 建议使用 asyncpg 异步驱动: {url}",
            "将 XAGENT_DATABASE_URL 改为 postgresql+asyncpg://user:pass@host:5432/db",
        )
    return DoctorCheck("database_url", "pass", f"DATABASE_URL: {url or '(未设置)'}")


def _check_llm_keys() -> DoctorCheck:
    settings, _err = _load_settings()
    if settings is None:
        # Fall back to raw environment variables.
        keys = {
            "deepseek": os.getenv("XAGENT_DEEPSEEK_API_KEY"),
            "openai": os.getenv("XAGENT_OPENAI_API_KEY"),
            "anthropic": os.getenv("XAGENT_ANTHROPIC_API_KEY"),
        }
        backend = os.getenv("XAGENT_LLM_BACKEND", "auto")
    else:
        keys = {
            "deepseek": getattr(settings, "deepseek_api_key", None),
            "openai": getattr(settings, "openai_api_key", None),
            "anthropic": getattr(settings, "anthropic_api_key", None),
        }
        backend = str(getattr(settings, "llm_backend", "auto"))

    configured = [name for name, key in keys.items() if key]
    if backend == "mock":
        return DoctorCheck(
            "llm_keys",
            "warn",
            "XAGENT_LLM_BACKEND=mock（使用确定性 mock 后端，不调用真实 LLM）"
            + (f"；已配置 key: {', '.join(configured)}" if configured else ""),
            "生产/真实调用请配置 XAGENT_DEEPSEEK_API_KEY（或 OPENAI/ANTHROPIC）并设置 XAGENT_LLM_BACKEND=deepseek",
        )
    if configured:
        return DoctorCheck(
            "llm_keys",
            "pass",
            f"LLM key 已配置: {', '.join(configured)} (backend={backend})",
        )
    return DoctorCheck(
        "llm_keys",
        "fail",
        f"未配置任何 LLM API key (backend={backend})",
        "在 .env.development 配置 XAGENT_DEEPSEEK_API_KEY / XAGENT_OPENAI_API_KEY / XAGENT_ANTHROPIC_API_KEY，"
        "或设置 XAGENT_LLM_BACKEND=mock 进行离线验证",
    )


def _check_playwright() -> DoctorCheck:
    try:
        import playwright  # noqa: F401
    except ImportError:
        return DoctorCheck(
            "playwright",
            "warn",
            "playwright 未安装（浏览器自动化能力不可用）",
            "venv/Scripts/pip install playwright && venv/Scripts/python -m playwright install chromium",
        )
    try:
        from playwright.sync_api import sync_playwright

        with sync_playwright() as p:
            browser_type = p.chromium
            executable = browser_type.executable_path
            if executable and Path(executable).exists():
                return DoctorCheck("playwright", "pass", f"playwright 可用 (chromium: {executable})")
            return DoctorCheck(
                "playwright",
                "warn",
                "playwright 已安装但 chromium 浏览器未下载",
                "venv/Scripts/python -m playwright install chromium",
            )
    except Exception as e:
        return DoctorCheck(
            "playwright",
            "warn",
            f"playwright 已安装但浏览器探测失败: {e}",
            "venv/Scripts/python -m playwright install chromium",
        )


def _check_sandbox_subprocess() -> DoctorCheck:
    try:
        result = subprocess.run(
            [sys.executable, "-c", "print('sandbox-ok')"],
            capture_output=True,
            text=True,
            timeout=15,
            check=False,
        )
    except Exception as e:
        return DoctorCheck(
            "sandbox_subprocess",
            "fail",
            f"子进程沙箱不可用: {e}",
            "检查 Python 安装与系统进程创建权限（杀毒/组策略可能拦截）",
        )
    if result.returncode == 0 and "sandbox-ok" in result.stdout:
        return DoctorCheck("sandbox_subprocess", "pass", "子进程沙箱可用（可创建隔离子进程执行代码）")
    return DoctorCheck(
        "sandbox_subprocess",
        "fail",
        f"子进程执行异常: rc={result.returncode} stderr={result.stderr.strip()[:100]}",
        "检查 Python 安装与系统进程创建权限",
    )


def _check_data_dir_writable() -> DoctorCheck:
    data_dir = PROJECT_ROOT / "data"
    try:
        data_dir.mkdir(parents=True, exist_ok=True)
        probe = data_dir / ".doctor_probe"
        probe.write_text("ok", encoding="utf-8")
        probe.unlink()
    except Exception as e:
        return DoctorCheck(
            "data_dir_writable",
            "fail",
            f"data/ 目录不可写: {e}",
            "检查目录权限: mkdir data && icacls data /grant %USERNAME%:F",
        )
    return DoctorCheck("data_dir_writable", "pass", f"data/ 目录可写: {data_dir}")


def run_doctor_checks() -> list[DoctorCheck]:
    """Run all doctor checks and return results in order."""
    return [
        _check_python_version(),
        _check_backend_importable(),
        _check_database_url(),
        _check_llm_keys(),
        _check_playwright(),
        _check_sandbox_subprocess(),
        _check_data_dir_writable(),
    ]


def doctor() -> None:
    """Run local environment self-checks (Python/backend/DB/LLM/playwright/sandbox/data).

    Prints ✓/⚠/✗ per check with fix suggestions. Exit code is 0 when no
    check fails (warnings are allowed), 1 otherwise.

    Example:
        xagent doctor
    """
    config = None
    try:
        config = get_current_config()
    except Exception:
        pass

    checks = run_doctor_checks()

    if config is not None and config.output_format == "json":
        import json

        print(
            json.dumps(
                {
                    "status": "fail" if any(c.status == "fail" for c in checks) else "pass",
                    "checks": [
                        {
                            "name": c.name,
                            "status": c.status,
                            "message": c.message,
                            "suggestion": c.suggestion,
                        }
                        for c in checks
                    ],
                },
                ensure_ascii=False,
                indent=2,
            )
        )
    else:
        from rich.console import Console

        console = Console()
        console.print("[bold]X-Agent doctor 自检[/bold]")
        for check in checks:
            style = {"pass": "green", "warn": "yellow", "fail": "red"}.get(check.status, "white")
            console.print(f"[{style}]{check.icon} {check.name}: {check.message}[/{style}]")
            if check.suggestion and check.status != "pass":
                console.print(f"    [dim]→ 修复建议: {check.suggestion}[/dim]")

    failed = [c for c in checks if c.status == "fail"]
    if failed:
        raise typer.Exit(code=1)
    raise typer.Exit(code=0)
