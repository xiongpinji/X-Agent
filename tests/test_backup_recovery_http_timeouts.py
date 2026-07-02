from __future__ import annotations

import ast
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def test_backup_recovery_requests_calls_define_timeouts() -> None:
    tree = ast.parse((ROOT / "scripts" / "backup_recovery.py").read_text(encoding="utf-8"))

    calls_without_timeout = []
    for node in ast.walk(tree):
        if not isinstance(node, ast.Call):
            continue
        func = node.func
        if not isinstance(func, ast.Attribute):
            continue
        if not isinstance(func.value, ast.Name) or func.value.id != "requests":
            continue
        if func.attr not in {"get", "post", "put", "delete", "patch", "head", "options"}:
            continue
        if not any(keyword.arg == "timeout" for keyword in node.keywords):
            calls_without_timeout.append(node.lineno)

    assert calls_without_timeout == []
