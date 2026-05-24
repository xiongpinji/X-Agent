from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from backend.app.core.contracts import ToolCallRecord
from backend.app.core.verification import VerificationEngine, VerificationResult


@dataclass
class RepairSuggestion:
    should_retry: bool
    tool_name: str | None = None
    arguments: dict[str, Any] = field(default_factory=dict)
    reason: str = ""
    error_type: str | None = None
    confidence: float = 0.5
    follow_up: list[str] = field(default_factory=list)


class RepairLoop:
    """Generate a simple retry suggestion from verification results."""

    def __init__(self, verifier: VerificationEngine | None = None) -> None:
        self.verifier = verifier or VerificationEngine()

    @staticmethod
    def _dump_model(value: Any) -> Any:
        if hasattr(value, "model_dump"):
            return value.model_dump(mode="json")
        if hasattr(value, "dict"):
            return value.dict()
        if isinstance(value, dict):
            return value
        return getattr(value, "__dict__", value)

    def analyze(self, tool_call: ToolCallRecord) -> tuple[VerificationResult, RepairSuggestion]:
        result = self.verifier.verify_tool_call(tool_call)
        suggestion = self._suggest(tool_call, result)
        return result, suggestion

    def summarize(self, tool_calls: list[ToolCallRecord]) -> dict[str, Any]:
        summary = self.verifier.summarize_run(tool_calls)
        summary["repairs"] = []
        summary["retry_count"] = 0
        summary["retryable_failures"] = 0
        for call in tool_calls:
            if call.success:
                continue
            result, suggestion = self.analyze(call)
            if suggestion.should_retry:
                summary["retryable_failures"] += 1
            summary["repairs"].append(
                {
                    "tool_name": call.tool_name,
                    "verification": self._dump_model(result),
                    "suggestion": {
                        "should_retry": suggestion.should_retry,
                        "tool_name": suggestion.tool_name,
                        "arguments": suggestion.arguments,
                        "reason": suggestion.reason,
                        "error_type": suggestion.error_type,
                        "confidence": suggestion.confidence,
                        "follow_up": suggestion.follow_up,
                    },
                }
            )
        summary["retry_count"] = summary["retryable_failures"]
        return summary

    @staticmethod
    def _suggest(tool_call: ToolCallRecord, result: VerificationResult) -> RepairSuggestion:
        error_type = result.error_type or "unknown"
        tool_name = tool_call.tool_name
        arguments = dict(tool_call.arguments_preview)
        if error_type == "validation_error":
            return RepairSuggestion(True, tool_name, arguments, "retry with corrected arguments", error_type, 0.92, ["rebuild arguments", "re-run validation"])
        if error_type == "missing_resource":
            retry_tool = "read_file" if tool_name != "read_file" else None
            retry_arguments = {"path": arguments.get("path", ""), "limit": 8000}
            if tool_name in {"apply_text_patch", "write_file"} and arguments.get("content"):
                retry_arguments["content"] = arguments.get("content", "")
            return RepairSuggestion(True, retry_tool, retry_arguments, "re-read context before retrying", error_type, 0.88, ["refresh file context", "retry with discovered path"])
        if error_type == "patch_mismatch":
            retry_tool = "read_file" if tool_name != "read_file" else None
            retry_arguments = {"path": arguments.get("path", ""), "limit": 8000}
            return RepairSuggestion(True, retry_tool, retry_arguments, "refresh file context and rebuild the patch", error_type, 0.86, ["re-read file", "reconstruct patch"])
        if error_type in {"approval_required", "permission_denied"}:
            return RepairSuggestion(False, reason="await approval or authorization before retrying" if error_type == "approval_required" else "permission denied; manual intervention required", error_type=error_type, confidence=0.1, follow_up=["request approval", "pause execution"])
        if error_type == "timeout":
            return RepairSuggestion(True, tool_name, arguments, "retry after timeout with backoff", error_type, 0.7, ["backoff and retry", "reduce scope if needed"])
        if error_type == "rate_limit":
            return RepairSuggestion(True, tool_name, arguments, "retry after rate limit backoff", error_type, 0.68, ["backoff", "retry later"])
        return RepairSuggestion(True, tool_name, arguments, "retry after unexpected runtime failure", error_type, 0.58, ["re-read context", "retry carefully"])
