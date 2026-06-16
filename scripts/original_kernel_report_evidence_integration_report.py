#!/usr/bin/env python3
"""Validate original-kernel report hygiene and pytest evidence scripts.

This module-level probe uses temporary report fixtures and an injected fake
pytest runner. It does not run broad pytest, mutate existing reports, or wire
the scripts into any mainline entrypoint.
"""

from __future__ import annotations

import argparse
import json
import sys
import tempfile
from dataclasses import asdict, dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from backend.app.core.storage import atomic_write_json
from scripts.check_report_hygiene import check_report_hygiene
from scripts.normalize_report_count_aliases import normalize_report_count_aliases
from scripts.run_pytest_evidence import CommandResult, run_pytest_evidence

REPORT_DIR = ROOT / ".xagent_runtime" / "reports"
DEFAULT_OUTPUT = REPORT_DIR / "original-kernel-report-evidence-integration.json"


@dataclass(frozen=True)
class IntegrationCheck:
    name: str
    status: str
    details: dict[str, Any] = field(default_factory=dict)
    error: str | None = None


def _utc_now() -> str:
    return datetime.now(UTC).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _pytest_evidence_check() -> IntegrationCheck:
    calls: list[tuple[list[str], str, float]] = []
    with tempfile.TemporaryDirectory(prefix="xagent-pytest-evidence-contract-") as tmp:
        source_root = Path(tmp)
        output = source_root / "pytest-evidence.json"

        def fake_runner(command: list[str], cwd: Path, timeout_seconds: float) -> CommandResult:
            calls.append((command, str(cwd), timeout_seconds))
            if "--collect-only" in command:
                return CommandResult(
                    command=command,
                    returncode=0,
                    stdout="\n".join(
                        [
                            "tests/test_alpha.py::test_one",
                            "tests/test_beta.py::test_two",
                            "tests/test_gamma.py::test_three",
                        ]
                    ),
                    stderr="",
                    duration_seconds=0.01,
                )
            return CommandResult(
                command=command,
                returncode=0,
                stdout="passed\n",
                stderr="",
                duration_seconds=0.02,
            )

        payload = run_pytest_evidence(
            source_root=source_root,
            output=output,
            shard_count=2,
            max_nodeids_per_shard=4,
            runner=fake_runner,
        )
        persisted = json.loads(output.read_text(encoding="utf-8"))

    pytest_commands = [call[0] for call in calls[1:]]
    passed = all(
        [
            payload == persisted,
            payload.get("kind") == "pytest_evidence",
            payload.get("ok") is True,
            payload.get("status") == "passed",
            payload.get("summary", {}).get("collected") == 3,
            payload.get("summary", {}).get("completed_shards") == 2,
            payload.get("summary", {}).get("passed_shards") == 2,
            calls[0][0] == [sys.executable, "-m", "pytest", "--collect-only", "-q"],
            all(command[:4] == [sys.executable, "-m", "pytest", "-q"] for command in pytest_commands),
        ]
    )
    return IntegrationCheck(
        name="pytest_evidence_fake_runner_contract",
        status="passed" if passed else "failed",
        details={
            "fake_runner_used": True,
            "real_pytest_execution_performed": False,
            "collect_call_count": 1 if calls else 0,
            "pytest_shard_call_count": max(0, len(calls) - 1),
            "collected": payload.get("summary", {}).get("collected"),
            "completed_shards": payload.get("summary", {}).get("completed_shards"),
            "passed_shards": payload.get("summary", {}).get("passed_shards"),
            "persisted_payload_matches": payload == persisted,
        },
        error=None if passed else "pytest evidence contract did not produce expected fake-runner shard evidence",
    )


def _report_hygiene_check() -> IntegrationCheck:
    with tempfile.TemporaryDirectory(prefix="xagent-report-hygiene-contract-") as tmp:
        source_root = Path(tmp) / "source"
        reports_dir = source_root / ".xagent_runtime" / "reports"
        reports_dir.mkdir(parents=True)

        _write_json(
            reports_dir / "clean-readiness.json",
            {
                "kind": "clean_readiness",
                "ok": True,
                "status": "passed",
                "checks": [],
                "checks_count": 0,
            },
        )
        clean_payload = check_report_hygiene(source_root=source_root, reports_dir=reports_dir)

        _write_json(
            reports_dir / "missing-count-alias.json",
            {
                "kind": "missing_count_alias",
                "ok": True,
                "status": "passed",
                "checks": [],
            },
        )
        dirty_payload = check_report_hygiene(source_root=source_root, reports_dir=reports_dir)

    missing_count_entries = dirty_payload.get("missing_count_alias_artifacts")
    passed = all(
        [
            clean_payload.get("ok") is True,
            clean_payload.get("status") == "passed",
            clean_payload.get("summary", {}).get("issues") == 0,
            dirty_payload.get("ok") is False,
            dirty_payload.get("status") == "failed",
            dirty_payload.get("summary", {}).get("missing_count_alias") == 1,
            isinstance(missing_count_entries, list),
            missing_count_entries
            and missing_count_entries[0].get("missing_count_aliases") == ["checks_count"],
        ]
    )
    return IntegrationCheck(
        name="report_hygiene_contract",
        status="passed" if passed else "failed",
        details={
            "clean_status": clean_payload.get("status"),
            "clean_issue_count": clean_payload.get("summary", {}).get("issues"),
            "dirty_status": dirty_payload.get("status"),
            "dirty_missing_count_alias": dirty_payload.get("summary", {}).get("missing_count_alias"),
            "dirty_issue_count": dirty_payload.get("summary", {}).get("issues"),
        },
        error=None if passed else "report hygiene contract did not distinguish clean and missing-alias reports",
    )


def _count_alias_normalization_check() -> IntegrationCheck:
    with tempfile.TemporaryDirectory(prefix="xagent-count-alias-contract-") as tmp:
        source_root = Path(tmp) / "source"
        reports_dir = source_root / ".xagent_runtime" / "reports"
        reports_dir.mkdir(parents=True)
        report_path = reports_dir / "pytest-evidence.json"
        original = {
            "kind": "pytest_evidence",
            "ok": True,
            "status": "passed",
            "shards": [],
        }
        _write_json(report_path, original)

        output = reports_dir / "report-count-alias-normalization.json"
        payload = normalize_report_count_aliases(
            source_root=source_root,
            reports_dir=reports_dir,
            output=output,
            dry_run=True,
        )
        preserved = json.loads(report_path.read_text(encoding="utf-8")) == original
        persisted = json.loads(output.read_text(encoding="utf-8"))

    passed = all(
        [
            preserved,
            payload == persisted,
            payload.get("kind") == "report_count_alias_normalization",
            payload.get("ok") is True,
            payload.get("status") == "planned",
            payload.get("dry_run") is True,
            payload.get("summary", {}).get("reports_scanned") == 1,
            payload.get("summary", {}).get("reports_updated") == 1,
            payload.get("summary", {}).get("count_aliases_added") == 1,
            payload.get("updated_reports_count") == 1,
        ]
    )
    return IntegrationCheck(
        name="count_alias_normalization_dry_run_contract",
        status="passed" if passed else "failed",
        details={
            "dry_run": payload.get("dry_run"),
            "status": payload.get("status"),
            "source_report_preserved": preserved,
            "reports_scanned": payload.get("summary", {}).get("reports_scanned"),
            "reports_updated": payload.get("summary", {}).get("reports_updated"),
            "count_aliases_added": payload.get("summary", {}).get("count_aliases_added"),
            "persisted_payload_matches": payload == persisted,
        },
        error=None if passed else "count alias normalization dry-run contract did not preserve source reports",
    )


def build_report() -> dict[str, Any]:
    checks = [
        _pytest_evidence_check(),
        _report_hygiene_check(),
        _count_alias_normalization_check(),
    ]
    all_passed = all(check.status == "passed" for check in checks)

    return {
        "status": "original_kernel_report_evidence_integration_ready" if all_passed else "failed",
        "generated_at": _utc_now(),
        "evidence_type": "original_kernel_report_evidence_integration",
        "modules": [
            "run_pytest_evidence",
            "check_report_hygiene",
            "normalize_report_count_aliases",
        ],
        "entrypoints_modified": False,
        "api_router_modified": False,
        "control_plane_modified": False,
        "frontend_modified": False,
        "agent_loop_modified": False,
        "backend_core_init_modified": False,
        "mutation_performed": False,
        "report_file_written": False,
        "existing_reports_modified": False,
        "temporary_files_written": True,
        "network_mutation_performed": False,
        "agent_execution_enabled": False,
        "broad_pytest_execution_performed": False,
        "real_pytest_execution_performed": False,
        "fake_pytest_runner_used": True,
        "count_alias_normalization_dry_run": True,
        "report_hygiene_scan_performed": True,
        "checks": [asdict(check) for check in checks],
        "known_limits": [
            "This report proves report hygiene and pytest evidence script contracts only.",
            "Pytest evidence uses an injected fake runner; no real pytest process or broad test execution is started.",
            "Count alias normalization is exercised in dry-run mode against temporary reports.",
            "No existing .xagent_runtime report files are modified by this report.",
            "No API router, agent loop, control plane, frontend, or backend core package entrypoint is wired by this report.",
            "No full Codex parity claim is made by this report.",
        ],
        "next_actions": [
            "After review, stage only the report-evidence integration files explicitly.",
            "Prepare a final original-kernel module integration summary before any mainline wiring.",
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

    print(f"Original kernel report evidence integration status: {report['status']}")
    print(f"Report written to {args.output}")
    for check in report["checks"]:
        print(f"- {check['name']}: {check['status']}")
        if check.get("error"):
            print(f"  error: {check['error']}")

    return 0 if report["status"] == "original_kernel_report_evidence_integration_ready" else 1


def _write_json(path: Path, payload: dict[str, Any]) -> None:
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


if __name__ == "__main__":
    raise SystemExit(main())
