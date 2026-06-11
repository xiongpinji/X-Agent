#!/usr/bin/env python3
"""Validate the minimal original-kernel module integration.

The report intentionally exercises only pure module contracts. It does not
wire API routers, agent loops, control-plane entrypoints, channels, or runtime
execution paths.
"""

from __future__ import annotations

import argparse
import io
import json
import logging
import sys
from dataclasses import asdict, dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from backend.app.core.permission_profiles import PermissionProfile, evaluate_permission
from backend.app.core.storage import atomic_write_json
from backend.app.core.structured_logging import JsonLogFormatter, log_event

REPORT_DIR = ROOT / ".xagent_runtime" / "reports"
DEFAULT_OUTPUT = REPORT_DIR / "original-kernel-minimal-integration.json"


@dataclass(frozen=True)
class IntegrationCheck:
    name: str
    status: str
    details: dict[str, Any] = field(default_factory=dict)
    error: str | None = None


def _utc_now() -> str:
    return datetime.now(UTC).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _permission_profile_check() -> IntegrationCheck:
    profile = PermissionProfile(
        profile_id="original-kernel-minimal",
        description="Minimal import and evaluation contract for mainline integration.",
        allow={
            "read": ["backend/app/core/*.py"],
            "tool": ["pytest"],
            "network": ["docs.internal.example"],
        },
        deny={
            "read": ["backend/app/core/*.secret"],
            "network": ["prod.internal.example"],
        },
    )

    allowed_read = evaluate_permission(profile, "read", "backend\\app\\core\\structured_logging.py")
    denied_read = evaluate_permission(profile, "read", "backend/app/core/token.secret")
    allowed_tool = evaluate_permission(profile, "tool", "pytest")
    denied_network = evaluate_permission(profile, "network", "prod.internal.example")

    passed = all(
        [
            allowed_read.allowed is True,
            denied_read.allowed is False,
            denied_read.effect == "deny",
            allowed_tool.allowed is True,
            denied_network.allowed is False,
            denied_network.effect == "deny",
        ]
    )

    return IntegrationCheck(
        name="permission_profiles_contract",
        status="passed" if passed else "failed",
        details={
            "profile_id": profile.profile_id,
            "read_target_normalized": allowed_read.target,
            "deny_precedence_verified": denied_read.effect == "deny",
            "tool_allowed": allowed_tool.allowed,
            "network_denied": denied_network.allowed is False,
        },
        error=None if passed else "permission profile evaluation did not match the expected allow/deny contract",
    )


def _structured_logging_check() -> IntegrationCheck:
    root_logger = logging.getLogger()
    root_handlers_before = tuple(root_logger.handlers)
    root_level_before = root_logger.level

    stream = io.StringIO()
    logger = logging.getLogger("xagent.original_kernel_minimal_integration")
    logger_handlers_before = list(logger.handlers)
    logger_level_before = logger.level
    logger_propagate_before = logger.propagate
    logger_disabled_before = logger.disabled

    try:
        logger.handlers = []
        logger.setLevel(logging.INFO)
        logger.propagate = False
        logger.disabled = False

        handler = logging.StreamHandler(stream)
        handler.setFormatter(JsonLogFormatter())
        logger.addHandler(handler)

        log_event(
            logger,
            "original_kernel.integration_probe",
            module="structured_logging",
            dry_run=True,
        )
        raw_log_line = stream.getvalue().strip()
        payload = json.loads(raw_log_line)
    finally:
        logger.handlers = logger_handlers_before
        logger.setLevel(logger_level_before)
        logger.propagate = logger_propagate_before
        logger.disabled = logger_disabled_before

    root_handlers_after = tuple(root_logger.handlers)
    root_level_after = root_logger.level
    root_handlers_preserved = root_handlers_after == root_handlers_before
    root_level_preserved = root_level_after == root_level_before

    passed = all(
        [
            payload.get("event") == "original_kernel.integration_probe",
            payload.get("module") == "structured_logging",
            payload.get("dry_run") is True,
            payload.get("level") == "info",
            root_handlers_preserved,
            root_level_preserved,
        ]
    )

    return IntegrationCheck(
        name="structured_logging_contract",
        status="passed" if passed else "failed",
        details={
            "formatter": "JsonLogFormatter",
            "event": payload.get("event"),
            "dry_run": payload.get("dry_run"),
            "root_handler_count_before": len(root_handlers_before),
            "root_handler_count_after": len(root_handlers_after),
            "root_handlers_preserved": root_handlers_preserved,
            "root_level_preserved": root_level_preserved,
        },
        error=None if passed else "structured logging probe failed or changed root logging state",
    )


def build_report() -> dict[str, Any]:
    checks = [_structured_logging_check(), _permission_profile_check()]
    all_passed = all(check.status == "passed" for check in checks)

    return {
        "status": "original_kernel_minimal_integration_ready" if all_passed else "failed",
        "generated_at": _utc_now(),
        "evidence_type": "original_kernel_minimal_integration",
        "modules": ["structured_logging", "permission_profiles"],
        "entrypoints_modified": False,
        "global_logging_configured": False,
        "mutation_performed": False,
        "report_file_written": False,
        "network_mutation_performed": False,
        "agent_execution_enabled": False,
        "write_runner_invoked": False,
        "checks": [asdict(check) for check in checks],
        "known_limits": [
            "This report proves module-level import and contract execution only.",
            "No API router, agent loop, control plane, frontend, or backend core package entrypoint is wired by this report.",
            "No full Codex parity claim is made by this report.",
        ],
        "next_actions": [
            "After review, stage only the minimal integration files explicitly.",
            "Use repo_context and context_pack as the next module-level integration pair.",
        ],
    }


def write_report(output_path: Path = DEFAULT_OUTPUT) -> dict[str, Any]:
    report = build_report()
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
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    report = write_report(args.output)

    print(f"Original kernel minimal integration status: {report['status']}")
    print(f"Report written to {args.output}")
    for check in report["checks"]:
        print(f"- {check['name']}: {check['status']}")
        if check.get("error"):
            print(f"  error: {check['error']}")

    return 0 if report["status"] == "original_kernel_minimal_integration_ready" else 1


if __name__ == "__main__":
    raise SystemExit(main())
