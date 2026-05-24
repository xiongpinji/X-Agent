from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from backend.app.core.contracts import ToolCallRecord
from backend.app.core.test_mapper import TestMappingResult


@dataclass
class VerificationResult:
    passed: bool
    summary: str
    error_type: str | None = None
    details: dict[str, Any] = field(default_factory=dict)


class VerificationEngine:
    """Lightweight execution verification and failure classification."""

    def verify_tool_call(self, tool_call: ToolCallRecord) -> VerificationResult:
        if tool_call.success:
            return VerificationResult(
                passed=True,
                summary=f"{tool_call.tool_name} completed successfully",
                details={"tool_name": tool_call.tool_name, "latency_ms": tool_call.latency_ms},
            )

        error = (tool_call.error or "").lower()
        error_type = self._classify_error(error)
        return VerificationResult(
            passed=False,
            summary=f"{tool_call.tool_name} failed: {tool_call.error or 'unknown error'}",
            error_type=error_type,
            details={
                "tool_name": tool_call.tool_name,
                "latency_ms": tool_call.latency_ms,
                "arguments_preview": tool_call.arguments_preview,
            },
        )

    def summarize_run(self, tool_calls: list[ToolCallRecord], test_mapping: TestMappingResult | None = None) -> dict[str, Any]:
        verified = [self.verify_tool_call(call) for call in tool_calls]
        failures = [item for item in verified if not item.passed]
        mapped_tests = test_mapping.test_files if test_mapping is not None else []
        suggested_commands = self._suggest_test_commands(mapped_tests, test_mapping.recommended_commands if test_mapping is not None else [])
        retryable_failures = sum(1 for item in failures if item.error_type not in {"approval_required", "permission_denied"})
        return {
            "passed": not failures,
            "total": len(verified),
            "failed": len(failures),
            "retryable_failures": retryable_failures,
            "failure_types": [item.error_type for item in failures if item.error_type],
            "summaries": [item.summary for item in verified],
            "test_mapping": {
                "query": test_mapping.query if test_mapping is not None else None,
                "related_files": test_mapping.related_files if test_mapping is not None else [],
                "test_files": mapped_tests,
                "impact_hints": test_mapping.impact_hints if test_mapping is not None else [],
                "dependency_hints": test_mapping.dependency_hints if test_mapping is not None else [],
                "recommended_commands": test_mapping.recommended_commands if test_mapping is not None else [],
            },
            "suggested_test_commands": suggested_commands,
            "recovery_plan": self._build_recovery_plan(failures, test_mapping),
            "next_actions": self._build_next_actions(failures, test_mapping, suggested_commands),
        }

    @staticmethod
    def _suggest_test_commands(test_files: list[dict[str, Any]], recommended_commands: list[str] | None = None) -> list[str]:
        commands: list[str] = list(recommended_commands or [])
        for item in test_files[:5]:
            path = str(item.get("path", ""))
            if not path:
                continue
            if path.endswith(".py"):
                commands.append(f"pytest {path}")
            elif path.endswith((".js", ".jsx", ".ts", ".tsx")):
                commands.append(f"npm test -- {path}")
        if not commands:
            commands.append("pytest")
        return list(dict.fromkeys(commands))

    @staticmethod
    def _build_recovery_plan(failures: list[VerificationResult], test_mapping: TestMappingResult | None) -> dict[str, Any]:
        return {
            "failed_checks": [item.summary for item in failures],
            "retry_strategy": "re-run targeted tests after the next patch",
            "rollback_strategy": "restore the previous implementation if the next verification fails",
            "target_files": [item.get("path") for item in (test_mapping.related_files if test_mapping else []) if item.get("path")],
            "validation_commands": test_mapping.recommended_commands if test_mapping else ["pytest"],
        }

    @staticmethod
    def _build_next_actions(
        failures: list[VerificationResult],
        test_mapping: TestMappingResult | None,
        suggested_commands: list[str],
    ) -> list[str]:
        actions: list[str] = []
        if failures:
            actions.append("classify the failing checks and patch the smallest impacted surface")
        if test_mapping and test_mapping.related_files:
            actions.append(f"inspect {test_mapping.related_files[0].get('path', 'the most relevant file')}")
        if suggested_commands:
            actions.append(f"run {suggested_commands[0]}")
        if test_mapping and test_mapping.dependency_hints:
            actions.append("verify dependent modules after the patch")
        if not actions:
            actions.append("run pytest")
        return actions

    @staticmethod
    def _classify_error(error: str) -> str:
        if not error:
            return "unknown"
        if "missing required argument" in error or "unknown arguments" in error or "invalid argument" in error or "validation" in error:
            return "validation_error"
        if "file_not_found" in error or "not found" in error or "missing resource" in error:
            return "missing_resource"
        if "ambiguous_match" in error or "pattern_not_found" in error or "patch mismatch" in error or "stale patch" in error:
            return "patch_mismatch"
        if "approval" in error:
            return "approval_required"
        if "permission" in error or "unauthorized" in error or "forbidden" in error:
            return "permission_denied"
        if "timeout" in error:
            return "timeout"
        if "rate limit" in error or "too many requests" in error:
            return "rate_limit"
        if "syntaxerror" in error or "indentationerror" in error:
            return "syntax_error"
        if "assertionerror" in error or "test failed" in error:
            return "test_failure"
        return "unexpected_runtime_error"
