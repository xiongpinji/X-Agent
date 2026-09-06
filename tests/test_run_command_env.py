"""run_command 子进程环境契约（2026-09-06 长任务实测发现的两类缺陷）。

实测背景：agent 用裸 "python -m pytest" 时解析到系统解释器——无 venv 依赖、
Windows GBK 下 site 模块崩溃（Fatal Python error: init_import_site），
间接诱发模型虚报测试结果。本文件固化修复契约：
1. PATH 前置当前解释器目录 → 裸 python/pytest 命中本进程环境
2. PYTHONUTF8/PYTHONIOENCODING → 中文路径/输出不崩
"""

from __future__ import annotations

import sys

import pytest

from backend.app.core.contracts import RunContext
from backend.app.core.policy import ToolPolicyEngine
from backend.app.core.tools import build_default_tool_registry


@pytest.fixture
def registry():
    return build_default_tool_registry(ToolPolicyEngine())


async def _run(registry, command: str) -> dict:
    rec = await registry.execute(RunContext(), "run_command", {"command": command})
    out = rec.output if isinstance(rec.output, dict) else {}
    return out


async def test_bare_python_resolves_to_current_interpreter(registry):
    """裸 `python` 必须命中当前解释器（venv），而不是系统 Python。"""
    out = await _run(registry, "python -c \"import sys; print(sys.executable)\"")
    assert out.get("success") is True, out.get("stderr", "")[:200]
    resolved = str(out.get("stdout", "")).strip()
    # 同一 venv 目录（解析后比较，容忍路径形式差异）
    from pathlib import Path

    assert Path(resolved).resolve() == Path(sys.executable).resolve(), (
        f"bare python resolved to {resolved}, expected {sys.executable}"
    )


async def test_utf8_output_survives(registry):
    """中文输出在子进程正常返回（UTF-8 强制，不因 GBK 崩溃）。"""
    out = await _run(registry, "python -c \"print('中文编码探针 OK')\"")
    assert out.get("exit_code") == 0, out.get("stderr", "")[:200]
    assert "中文编码探针 OK" in str(out.get("stdout", ""))


async def test_pytest_available_in_subprocess(registry):
    """裸 `pytest --version` 可执行（venv Scripts 目录已前置 PATH）。"""
    out = await _run(registry, "pytest --version")
    assert out.get("exit_code") == 0, out.get("stderr", "")[:200]
    assert "pytest" in str(out.get("stdout", "")).lower()
