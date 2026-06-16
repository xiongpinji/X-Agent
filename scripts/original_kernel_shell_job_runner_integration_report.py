#!/usr/bin/env python3
"""Validate the original-kernel shell job runner contract without execution.

This module-level probe verifies parsing, sandbox rejection, and result
encoding paths only. It intentionally avoids a valid shell command payload so
``asyncio.create_subprocess_shell`` is never reached.
"""

from __future__ import annotations

import argparse
import asyncio
from base64 import b64decode
import io
import json
from contextlib import redirect_stdout
import sys
from dataclasses import asdict, dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from types import SimpleNamespace
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from backend.app.core.shell_job_runner import (
    RESULT_LOG_PREFIX,
    _loads_payload,
    emit_shell_job_result,
    execute_shell_job_payload,
)
from backend.app.core.storage import atomic_write_json

REPORT_DIR = ROOT / ".xagent_runtime" / "reports"
DEFAULT_OUTPUT = REPORT_DIR / "original-kernel-shell-job-runner-integration.json"


@dataclass(frozen=True)
class IntegrationCheck:
    name: str
    status: str
    details: dict[str, Any] = field(default_factory=dict)
    error: str | None = None


def _utc_now() -> str:
    return datetime.now(UTC).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _settings(sandbox: Path) -> SimpleNamespace:
    return SimpleNamespace(
        shell_tool_sandbox_path=sandbox,
        shell_tool_max_timeout_seconds=10,
        shell_tool_max_output_chars=4_000,
        shell_tool_max_artifact_bytes=8_192,
        shell_tool_max_artifacts=20,
    )


def _payload_parser_check() -> IntegrationCheck:
    parsed = _loads_payload(
        json.dumps(
            {
                "command": "python -c \"print('dry-run contract only')\"",
                "cwd": ".",
                "timeout_seconds": 3,
            }
        ),
        source="inline_contract_payload",
    )

    malformed_rejected = False
    non_object_rejected = False
    try:
        _loads_payload("{not-json", source="inline_contract_payload")
    except ValueError as exc:
        malformed_rejected = "not valid JSON" in str(exc)
    try:
        _loads_payload("[]", source="inline_contract_payload")
    except ValueError as exc:
        non_object_rejected = "must be a JSON object" in str(exc)

    passed = all(
        [
            parsed["command"].startswith("python -c"),
            parsed["cwd"] == ".",
            parsed["timeout_seconds"] == 3,
            malformed_rejected,
            non_object_rejected,
        ]
    )
    return IntegrationCheck(
        name="payload_parser_contract",
        status="passed" if passed else "failed",
        details={
            "valid_payload_parsed": isinstance(parsed, dict),
            "command_present": isinstance(parsed.get("command"), str),
            "malformed_json_rejected": malformed_rejected,
            "non_object_payload_rejected": non_object_rejected,
        },
        error=None if passed else "shell job payload parser contract did not reject invalid payloads",
    )


async def _pre_execution_guard_check(sandbox: Path) -> IntegrationCheck:
    missing_command_rejected = False
    outside_cwd_rejected = False

    try:
        await execute_shell_job_payload(
            {"cwd": "."},
            settings=_settings(sandbox),
        )
    except ValueError as exc:
        missing_command_rejected = "requires string field: command" in str(exc)

    try:
        await execute_shell_job_payload(
            {
                "command": "echo should-not-run",
                "cwd": sandbox.parent,
            },
            settings=_settings(sandbox),
        )
    except PermissionError as exc:
        outside_cwd_rejected = "within sandbox" in str(exc)

    passed = missing_command_rejected and outside_cwd_rejected
    return IntegrationCheck(
        name="pre_execution_guard_contract",
        status="passed" if passed else "failed",
        details={
            "missing_command_rejected_before_execution": missing_command_rejected,
            "outside_cwd_rejected_before_execution": outside_cwd_rejected,
            "valid_command_payload_executed": False,
            "subprocess_reached": False,
        },
        error=None if passed else "shell job pre-execution guards did not reject unsafe payloads",
    )


def _result_encoding_check() -> IntegrationCheck:
    stream = io.StringIO()
    with redirect_stdout(stream):
        emit_shell_job_result(
            {
                "ok": True,
                "completed_at": datetime(2026, 6, 1, 12, 0, tzinfo=UTC),
                "artifact": Path("runtime/result.json"),
            }
        )

    line = stream.getvalue().strip()
    payload: dict[str, Any] = {}
    prefix_valid = line.startswith(RESULT_LOG_PREFIX)
    if prefix_valid:
        payload = json.loads(b64decode(line.removeprefix(RESULT_LOG_PREFIX)).decode("utf-8"))

    passed = all(
        [
            prefix_valid,
            payload.get("ok") is True,
            payload.get("completed_at") == "2026-06-01T12:00:00+00:00",
            payload.get("artifact") in {"runtime/result.json", "runtime\\result.json"},
        ]
    )
    return IntegrationCheck(
        name="result_encoding_contract",
        status="passed" if passed else "failed",
        details={
            "prefix_valid": prefix_valid,
            "payload_ok": payload.get("ok"),
            "datetime_serialized": payload.get("completed_at"),
            "path_serialized": payload.get("artifact"),
        },
        error=None if passed else "shell job result encoding contract did not emit parseable payload",
    )


async def build_report(*, sandbox_path: str | Path | None = None) -> dict[str, Any]:
    sandbox = Path(sandbox_path or (ROOT / ".xagent_runtime" / "shell-job-runner-contract-sandbox")).resolve()

    checks = [
        _payload_parser_check(),
        await _pre_execution_guard_check(sandbox),
        _result_encoding_check(),
    ]
    all_passed = all(check.status == "passed" for check in checks)

    return {
        "status": "original_kernel_shell_job_runner_integration_ready" if all_passed else "failed",
        "generated_at": _utc_now(),
        "evidence_type": "original_kernel_shell_job_runner_integration",
        "modules": ["shell_job_runner"],
        "entrypoints_modified": False,
        "api_router_modified": False,
        "control_plane_modified": False,
        "frontend_modified": False,
        "agent_loop_modified": False,
        "backend_core_init_modified": False,
        "mutation_performed": False,
        "report_file_written": False,
        "sandbox_directory_prepared": False,
        "sandbox_path_resolved": str(sandbox),
        "network_mutation_performed": False,
        "agent_execution_enabled": False,
        "shell_command_execution_performed": False,
        "subprocess_execution_performed": False,
        "valid_command_payload_executed": False,
        "real_engineering_task_execution_performed": False,
        "checks": [asdict(check) for check in checks],
        "known_limits": [
            "This report proves shell_job_runner parser, guard, and encoding contracts only.",
            "No valid shell command payload is executed by this report.",
            "No real engineering task, agent run, workflow, or subprocess execution is started.",
            "No API router, agent loop, control plane, frontend, or backend core package entrypoint is wired by this report.",
            "No full Codex parity claim is made by this report.",
        ],
        "next_actions": [
            "After review, stage only the shell_job_runner integration files explicitly.",
            "Use pull_request_delivery as the next dry-run-first module-level integration slice.",
        ],
    }


async def write_report(
    output_path: Path = DEFAULT_OUTPUT,
    *,
    sandbox_path: str | Path | None = None,
) -> dict[str, Any]:
    report = await build_report(sandbox_path=sandbox_path)
    report["report_file_written"] = True
    report["report_path"] = str(output_path)
    atomic_write_json(output_path, report)
    return report


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--output",
        type=Path,
        default=DEFAULT_OUTPUT,
        help="Path to write the JSON integration evidence report.",
    )
    parser.add_argument(
        "--sandbox-path",
        type=Path,
        default=None,
        help="Sandbox directory used only for pre-execution cwd guard checks.",
    )
    return parser.parse_args()


async def async_main() -> int:
    args = parse_args()
    report = await write_report(args.output, sandbox_path=args.sandbox_path)

    print(f"Original kernel shell job runner integration status: {report['status']}")
    print(f"Report written to {args.output}")
    for check in report["checks"]:
        print(f"- {check['name']}: {check['status']}")
        if check.get("error"):
            print(f"  error: {check['error']}")

    return 0 if report["status"] == "original_kernel_shell_job_runner_integration_ready" else 1


def main() -> int:
    return asyncio.run(async_main())


if __name__ == "__main__":
    raise SystemExit(main())
