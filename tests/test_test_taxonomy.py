from __future__ import annotations

from pathlib import Path


def test_test_file_naming_matches_taxonomy() -> None:
    root = Path(__file__).resolve().parent
    files = [path.relative_to(root) for path in root.rglob("test_*.py")]

    for path in files:
        parts = path.parts
        name = path.name
        if parts[0] == "e2e":
            # 命名债白名单：test_agent_fix_real_llm.py 不符合 _e2e 后缀约定，
            # 但 scripts/release_candidate_check.py:46 以该路径硬编码引用，
            # 重命名需同步修改 scripts/（超出测试目录范围），暂列入白名单。
            assert name.endswith("_e2e.py") or name in {'test_agent_fix_real_llm.py', 'test_desktop_e2e.py', 'test_desktop_macro_e2e.py', 'test_execution_reporting.py', 'test_functional_e2e.py', 'test_offline_e2e.py', 'test_open_source_catalog_e2e.py', 'test_open_source_e2e.py', 'test_performance_security_e2e.py', 'test_sync_e2e.py', 'test_workflow_e2e.py'}
        elif parts[0] == "runtime":
            assert name.endswith("_runtime.py") or name.endswith("_helpers.py") or name.endswith("_compose.py") or name in {'test_desktop_runtime_complex.py', 'test_open_source_package_only.py'}
        elif parts[0] == "contracts":
            assert name.endswith("_contract.py") or name.endswith("_contracts.py") or name.endswith("_guard.py") or name.endswith("_imports.py") or name in {'test_open_source_import_guard.py'}
