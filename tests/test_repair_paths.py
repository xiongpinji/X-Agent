from __future__ import annotations

from backend.app.core.contracts import RiskLevel, ToolCallRecord, ToolPolicyVerdict
from backend.app.core.repair_loop import RepairLoop


def _record(error: str) -> ToolCallRecord:
    return ToolCallRecord(
        tool_name="write_file",
        success=False,
        error=error,
        policy=ToolPolicyVerdict(allowed=False, requires_approval=False, sandbox_profile="test", reason=error),
        risk_level=RiskLevel.HIGH,
        latency_ms=1.0,
        arguments_preview={"path": "x.py"},
        trace_id="t",
        request_id="r",
    )


def test_repair_path_authorization_failure() -> None:
    _, suggestion = RepairLoop().analyze(_record("permission denied"))
    assert suggestion.should_retry is False


def test_repair_path_timeout() -> None:
    _, suggestion = RepairLoop().analyze(_record("timeout"))
    assert suggestion.error_type == "timeout"


def test_repair_path_runtime_failure() -> None:
    _, suggestion = RepairLoop().analyze(_record("boom"))
    assert suggestion.should_retry is True
