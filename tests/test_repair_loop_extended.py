"""Extended test coverage for repair_loop module."""
from __future__ import annotations

from backend.app.core.contracts import RiskLevel, ToolCallRecord, ToolPolicyVerdict
from backend.app.core.repair_loop import RepairLoop, RepairSuggestion
from backend.app.core.verification import VerificationEngine, VerificationResult


def _record(tool_name: str = "write_file", error: str = "", success: bool = False) -> ToolCallRecord:
    """Helper to create test ToolCallRecord."""
    return ToolCallRecord(
        tool_name=tool_name,
        success=success,
        error=error,
        policy=ToolPolicyVerdict(allowed=False, requires_approval=False, sandbox_profile="test", reason=error),
        risk_level=RiskLevel.HIGH,
        latency_ms=1.0,
        arguments_preview={"path": "x.py", "content": "test content"},
        trace_id="t",
        request_id="r",
    )


class TestRepairLoopAnalysis:
    """Test repair loop analysis for various error types."""

    def test_validation_error_retry(self) -> None:
        """Test validation error triggers retry."""
        result, suggestion = RepairLoop().analyze(_record(error="missing required argument: path"))
        assert result.error_type == "validation_error"
        assert suggestion.should_retry is True
        assert suggestion.confidence > 0.8

    def test_missing_resource_error(self) -> None:
        """Test missing resource error handling."""
        result, suggestion = RepairLoop().analyze(_record(error="file_not_found"))
        assert result.error_type == "missing_resource"
        assert suggestion.should_retry is True
        assert suggestion.tool_name == "read_file"

    def test_patch_mismatch_error(self) -> None:
        """Test patch mismatch error handling."""
        result, suggestion = RepairLoop().analyze(_record(error="pattern_not_found"))
        assert result.error_type == "patch_mismatch"
        assert suggestion.should_retry is True
        assert "refresh file context" in suggestion.reason.lower()

    def test_approval_required_error(self) -> None:
        """Test approval required error does not retry."""
        result, suggestion = RepairLoop().analyze(_record(error="approval_required"))
        assert result.error_type == "approval_required"
        assert suggestion.should_retry is False
        assert suggestion.confidence < 0.5

    def test_permission_denied_error(self) -> None:
        """Test permission denied error does not retry."""
        result, suggestion = RepairLoop().analyze(_record(error="permission_denied"))
        assert result.error_type == "permission_denied"
        assert suggestion.should_retry is False

    def test_timeout_error(self) -> None:
        """Test timeout error triggers retry with backoff."""
        result, suggestion = RepairLoop().analyze(_record(error="timeout"))
        assert result.error_type == "timeout"
        assert suggestion.should_retry is True
        assert "retry after timeout" in suggestion.reason.lower()

    def test_rate_limit_error(self) -> None:
        """Test rate limit error triggers retry."""
        result, suggestion = RepairLoop().analyze(_record(error="rate_limit"))
        assert result.error_type == "rate_limit"
        assert suggestion.should_retry is True
        assert suggestion.confidence < 0.7

    def test_unknown_error_retry(self) -> None:
        """Test unknown error triggers retry with low confidence."""
        result, suggestion = RepairLoop().analyze(_record(error="unexpected_failure"))
        assert result.error_type == "unexpected_runtime_error"
        assert suggestion.should_retry is True
        assert suggestion.confidence < 0.6


class TestRepairLoopSummarize:
    """Test repair loop summarization of multiple tool calls."""

    def test_summarize_successful_calls(self) -> None:
        """Test summarization of successful tool calls."""
        calls = [
            _record(success=True),
            _record(success=True),
        ]
        summary = RepairLoop().summarize(calls)
        assert summary["retryable_failures"] == 0
        assert summary["retry_count"] == 0
        assert len(summary["repairs"]) == 0

    def test_summarize_mixed_calls(self) -> None:
        """Test summarization of mixed success/failure calls."""
        calls = [
            _record(success=True),
            _record(error="validation_error", success=False),
            _record(error="timeout", success=False),
        ]
        summary = RepairLoop().summarize(calls)
        assert summary["retryable_failures"] == 2
        assert summary["retry_count"] == 2
        assert len(summary["repairs"]) == 2

    def test_summarize_non_retryable_failures(self) -> None:
        """Test summarization with non-retryable failures."""
        calls = [
            _record(error="approval_required", success=False),
            _record(error="permission_denied", success=False),
        ]
        summary = RepairLoop().summarize(calls)
        assert summary["retryable_failures"] == 0
        assert summary["retry_count"] == 0
        assert len(summary["repairs"]) == 2


class TestRepairSuggestion:
    """Test RepairSuggestion dataclass."""

    def test_repair_suggestion_defaults(self) -> None:
        """Test RepairSuggestion default values."""
        suggestion = RepairSuggestion(should_retry=True)
        assert suggestion.should_retry is True
        assert suggestion.tool_name is None
        assert suggestion.arguments == {}
        assert suggestion.reason == ""
        assert suggestion.error_type is None
        assert suggestion.confidence == 0.5
        assert suggestion.follow_up == []

    def test_repair_suggestion_with_values(self) -> None:
        """Test RepairSuggestion with custom values."""
        suggestion = RepairSuggestion(
            should_retry=True,
            tool_name="read_file",
            arguments={"path": "test.py"},
            reason="retry after timeout",
            error_type="timeout",
            confidence=0.75,
            follow_up=["backoff", "retry"],
        )
        assert suggestion.should_retry is True
        assert suggestion.tool_name == "read_file"
        assert suggestion.arguments == {"path": "test.py"}
        assert suggestion.reason == "retry after timeout"
        assert suggestion.error_type == "timeout"
        assert suggestion.confidence == 0.75
        assert suggestion.follow_up == ["backoff", "retry"]


class TestRepairLoopDumpModel:
    """Test model dumping functionality."""

    def test_dump_model_with_dict(self) -> None:
        """Test dumping dict values."""
        value = {"key": "value"}
        result = RepairLoop._dump_model(value)
        assert result == {"key": "value"}

    def test_dump_model_with_pydantic(self) -> None:
        """Test dumping Pydantic model."""
        from pydantic import BaseModel

        class TestModel(BaseModel):
            name: str
            value: int

        model = TestModel(name="test", value=42)
        result = RepairLoop._dump_model(model)
        assert result["name"] == "test"
        assert result["value"] == 42

    def test_dump_model_with_primitive(self) -> None:
        """Test dumping primitive values."""
        assert RepairLoop._dump_model("string") == "string"
        assert RepairLoop._dump_model(42) == 42
        assert RepairLoop._dump_model(3.14) == 3.14
