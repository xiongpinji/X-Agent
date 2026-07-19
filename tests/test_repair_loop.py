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


def test_repair_loop_validation_failure() -> None:
    result, suggestion = RepairLoop().analyze(_record("missing required argument: path"))
    assert result.error_type == "validation_error"
    assert suggestion.should_retry is True


def test_repair_loop_missing_resource() -> None:
    result, suggestion = RepairLoop().analyze(_record("file_not_found"))
    assert result.error_type == "missing_resource"
    assert suggestion.should_retry is True


def test_repair_loop_patch_mismatch() -> None:
    result, suggestion = RepairLoop().analyze(_record("pattern_not_found"))
    assert result.error_type == "patch_mismatch"
    assert suggestion.should_retry is True
