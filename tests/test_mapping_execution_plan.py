from __future__ import annotations

from backend.app.core.code_index import code_index
from backend.app.core.execution_planner import execution_planner
from backend.app.core.test_mapper import test_mapper


def test_test_mapping_influences_execution_plan(tmp_path) -> None:
    root = tmp_path / "repo"
    root.mkdir()
    (root / "app.py").write_text("print('hello')", encoding="utf-8")
    (root / "test_app.py").write_text("def test_app():\n    assert True", encoding="utf-8")

    code_index.index(str(root), limit=20)
    mapping = test_mapper.map("update app", limit=10)
    plan = execution_planner.build("update app", test_mapping=mapping)

    assert mapping.test_files
    assert plan.suggested_test_commands
