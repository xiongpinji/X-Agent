from __future__ import annotations

from backend.app.core.code_index import code_index
from backend.app.core.execution_planner import execution_planner
from backend.app.core.test_mapper import test_mapper
from backend.app.core.verification import VerificationEngine


def test_planning_pipeline_produces_execution_and_verification_data(tmp_path) -> None:
    root = tmp_path / "repo"
    root.mkdir()
    (root / "app.py").write_text("print('hello')", encoding="utf-8")
    (root / "test_app.py").write_text("def test_app():\n    assert True", encoding="utf-8")

    code_index.index(str(root), limit=20)
    mapping = test_mapper.map("update app", limit=5)
    plan = execution_planner.build("update app", test_mapping=mapping)
    verification = VerificationEngine().summarize_run([], test_mapping=mapping)

    assert plan.steps
    assert plan.suggested_test_commands
    assert plan.rollback_steps
    assert plan.risk_notes
    assert plan.next_actions
    assert mapping.test_files
    assert mapping.dependency_hints
    assert mapping.recommended_commands
    assert verification["test_mapping"]["test_files"] == mapping.test_files
    assert verification["test_mapping"]["dependency_hints"] == mapping.dependency_hints
    assert verification["suggested_test_commands"]
    assert verification["recovery_plan"]["validation_commands"]
    assert verification["next_actions"]
