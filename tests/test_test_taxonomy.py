from __future__ import annotations

from pathlib import Path


def test_test_file_naming_matches_taxonomy() -> None:
    root = Path(__file__).resolve().parent
    files = [path.relative_to(root) for path in root.rglob("test_*.py")]

    for path in files:
        parts = path.parts
        name = path.name
        if parts[0] == "e2e":
            assert name.endswith("_e2e.py") or name in {"test_open_source_e2e.py", "test_workflow_e2e.py", "test_desktop_e2e.py"}
        elif parts[0] == "runtime":
            assert name.endswith("_runtime.py") or name.endswith("_helpers.py") or name.endswith("_compose.py") or name in {"test_desktop_runtime_complex.py"}
        elif parts[0] == "contracts":
            assert name.endswith("_contract.py") or name.endswith("_contracts.py") or name.endswith("_guard.py") or name.endswith("_imports.py")
