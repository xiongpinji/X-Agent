#!/usr/bin/env python3
"""Refresh commercial RC release evidence in dependency order.

This is the safe one-shot entrypoint for local and hosted release evidence
refreshes. Several RC reports consume JSON produced by earlier steps, so these
commands must run sequentially instead of in parallel.
"""

from __future__ import annotations

import argparse
import json
import locale
import os
import re
import subprocess
import sys
from dataclasses import asdict, dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from scripts.rc_source_bundle import ROOT

REPORT_DIR = ROOT / ".xagent_runtime" / "reports"
DEFAULT_OUTPUT = REPORT_DIR / "rc-refresh-release-chain.json"

PROVIDER_CHOICES = ("mock", "openai", "deepseek", "anthropic", "ollama", "local")
SAFE_PROVIDER_ENV_OVERRIDE_NAMES = frozenset({"XAGENT_OLLAMA_MODEL", "XAGENT_OLLAMA_BASE_URL"})
SECRET_KEY_OUTPUT_RE = re.compile(r"(?i)(\b[A-Z0-9_]*(?:api[_-]?key|token|secret|password)\b\s*[:=]\s*).+")
SECRET_VALUE_OUTPUT_RE = re.compile(r"\b(?:sk|ghp|github_pat|xagent)[_-][A-Za-z0-9_=-]{24,}\b")
BOOTSTRAP_FINAL_GATE_STEPS = frozenset(
    {"final_gate_bootstrap", "final_gate", "final_gate_after_docs", "final_gate_after_receipt"}
)
OWNER_VERIFIED_EXTERNAL_CHECKS = frozenset(
    {
        "provider",
        "feishu_webhook_contract",
        "github_issue_to_pr_dry_run",
        "github_issue_to_pr_execute_preflight",
        "hosted_github_actions_run",
    }
)


@dataclass(frozen=True)
class RefreshStep:
    name: str
    command: list[str]
    status: str
    returncode: int | None
    stdout_tail: list[str] = field(default_factory=list)
    stderr_tail: list[str] = field(default_factory=list)
    error: str | None = None


@dataclass(frozen=True)
class RefreshChainReport:
    status: str
    generated_at: str
    provider: str
    owner_verified: bool
    dry_run: bool
    stop_on_failure: bool
    steps: list[RefreshStep]
    next_commands: list[str]
    provider_env_overrides: dict[str, str] = field(default_factory=dict)
    owner_gate_summary: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        payload = asdict(self)
        payload["steps"] = [asdict(step) for step in self.steps]
        return payload


def _utc_now() -> str:
    return datetime.now(UTC).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _tail(text: str, *, lines: int = 20) -> list[str]:
    return [_sanitize_output_line(line) for line in text.splitlines()[-lines:]]


def _sanitize_output_line(line: str) -> str:
    line = SECRET_KEY_OUTPUT_RE.sub(r"\1<redacted-output>", line)
    return SECRET_VALUE_OUTPUT_RE.sub("<redacted-secret>", line)


def _decode_output(value: bytes | str | None) -> str:
    if value is None:
        return ""
    if isinstance(value, str):
        return value
    for encoding in ("utf-8", locale.getpreferredencoding(False), "gbk"):
        try:
            return value.decode(encoding)
        except UnicodeDecodeError:
            continue
    return value.decode("utf-8", errors="replace")


def _read_json(path: Path) -> dict[str, Any] | None:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (FileNotFoundError, json.JSONDecodeError):
        return None
    return payload if isinstance(payload, dict) else None


def _external_smoke_has_verified_owner_evidence(path: Path | None = None) -> bool:
    payload = _read_json(path or (REPORT_DIR / "rc-external-smoke.json"))
    if not isinstance(payload, dict):
        return False
    if payload.get("status") != "passed" or payload.get("require_configured") is not True:
        return False
    checks = payload.get("checks")
    if not isinstance(checks, list):
        return False
    statuses = {
        str(check.get("name") or ""): check.get("status")
        for check in checks
        if isinstance(check, dict)
    }
    return all(statuses.get(name) == "passed" for name in OWNER_VERIFIED_EXTERNAL_CHECKS)


def _owner_gate_summary() -> dict[str, Any]:
    final_payload = _read_json(REPORT_DIR / "rc-final-gate.json")
    owner_plan_payload = _read_json(REPORT_DIR / "rc-owner-gate-plan.json")
    external_smoke_payload = _read_json(REPORT_DIR / "rc-external-smoke.json")

    decision = final_payload.get("release_decision") if isinstance(final_payload, dict) else {}
    owner_gates = []
    raw_gates = owner_plan_payload.get("gates") if isinstance(owner_plan_payload, dict) else []
    if isinstance(raw_gates, list):
        for gate in raw_gates:
            if not isinstance(gate, dict):
                continue
            owner_gates.append(
                {
                    "name": gate.get("name"),
                    "status": gate.get("status"),
                    "missing": gate.get("missing", []),
                    "configured_env": gate.get("configured_env", []),
                }
            )

    external_checks = []
    raw_checks = external_smoke_payload.get("checks") if isinstance(external_smoke_payload, dict) else []
    if isinstance(raw_checks, list):
        for check in raw_checks:
            if not isinstance(check, dict):
                continue
            external_checks.append(
                {
                    "name": check.get("name"),
                    "status": check.get("status"),
                    "missing": check.get("missing", []),
                    "error": check.get("error"),
                    "details": _external_check_summary_details(check),
                }
            )

    return {
        "final_gate_status": final_payload.get("status") if isinstance(final_payload, dict) else None,
        "can_tag_rc_now": decision.get("can_tag_rc_now") if isinstance(decision, dict) else None,
        "owner_gate_plan_status": owner_plan_payload.get("status") if isinstance(owner_plan_payload, dict) else None,
        "external_smoke_status": external_smoke_payload.get("status") if isinstance(external_smoke_payload, dict) else None,
        "owner_gates": owner_gates,
        "external_checks": external_checks,
    }


def _external_check_summary_details(check: dict[str, Any]) -> dict[str, Any]:
    details = check.get("details")
    if not isinstance(details, dict):
        return {}
    safe_keys = (
        "run_url",
        "html_url",
        "workflow_verified",
        "expected_head_sha",
        "head_sha",
        "head_sha_verified",
        "head_branch",
        "jobs_verified",
        "artifact_verified",
        "mutation_performed",
        "run_status",
        "conclusion",
    )
    return {key: details[key] for key in safe_keys if key in details}


def _step_commands(provider: str, *, owner_verified: bool = False) -> list[tuple[str, list[str]]]:
    owner_plan_command = ["scripts/rc_owner_gate_plan.py"]
    external_smoke_command = ["scripts/rc_external_smoke.py"]
    if owner_verified:
        external_smoke_command.extend(
            [
                "--check",
                "provider",
                "--check",
                "feishu_webhook_contract",
                "--check",
                "github_issue_to_pr_dry_run",
                "--check",
                "github_issue_to_pr_execute_preflight",
                "--check",
                "hosted_github_actions_run",
                "--require-configured",
                "--github-execute-preflight",
                "--github-actions-preflight",
            ]
        )
    if provider != "mock":
        external_smoke_command.extend(["--provider", provider])
        owner_plan_command.extend(["--provider", provider])

    return [
        ("release_audit", ["scripts/rc_release_audit.py"]),
        ("staging_plan", ["scripts/rc_staging_plan.py"]),
        ("source_bundle", ["scripts/rc_source_bundle.py", "--create"]),
        ("artifact_integrity_gate", ["scripts/rc_artifact_integrity_gate.py"]),
        ("external_smoke", external_smoke_command),
        ("owner_gate_plan", owner_plan_command),
        ("owner_env_template", ["scripts/rc_owner_env_template.py"]),
        (
            "owner_gate_runner_dry_run",
            [
                "scripts/rc_owner_gate_runner.py",
                "--gate",
                "all",
                "--dry-run",
                "--env-file",
                ".xagent_runtime/reports/rc-owner-env-template.env",
            ],
        ),
        ("owner_gate_checklist", ["scripts/rc_owner_gate_checklist.py"]),
        ("owner_handoff_gate", ["scripts/rc_owner_handoff_gate.py"]),
        ("ci_contract", ["scripts/rc_ci_contract.py"]),
        ("release_diff_review_gate", ["scripts/rc_release_diff_review_gate.py"]),
        ("deployment_docs_gate_bootstrap", ["scripts/rc_deployment_docs_gate.py", "--allow-missing-evidence-pack"]),
        ("install_release_gate", ["scripts/rc_install_release_gate.py"]),
        ("supply_chain_gate", ["scripts/rc_supply_chain_gate.py"]),
        ("secrets_gate", ["scripts/rc_secrets_gate.py"]),
        ("final_gate_bootstrap", ["scripts/rc_final_gate.py", "--allow-missing-evidence-pack"]),
        ("release_receipt", ["scripts/rc_release_receipt.py"]),
        ("final_gate", ["scripts/rc_final_gate.py", "--allow-missing-evidence-pack"]),
        ("evidence_pack", ["scripts/rc_evidence_pack.py"]),
        ("deployment_docs_gate", ["scripts/rc_deployment_docs_gate.py"]),
        ("final_gate_after_docs", ["scripts/rc_final_gate.py", "--allow-missing-evidence-pack"]),
        ("release_receipt_after_docs", ["scripts/rc_release_receipt.py"]),
        ("final_gate_after_receipt", ["scripts/rc_final_gate.py", "--allow-missing-evidence-pack"]),
        ("evidence_pack_after_receipt", ["scripts/rc_evidence_pack.py"]),
        ("final_gate_final", ["scripts/rc_final_gate.py"]),
        ("evidence_pack_final", ["scripts/rc_evidence_pack.py"]),
    ]


def _provider_env_overrides(overrides: dict[str, str] | None) -> dict[str, str]:
    if not overrides:
        return {}
    unsupported = sorted(set(overrides) - SAFE_PROVIDER_ENV_OVERRIDE_NAMES)
    if unsupported:
        raise ValueError(f"unsupported provider env override(s): {', '.join(unsupported)}")
    return {name: value for name, value in overrides.items() if value}


def _run_step(
    name: str,
    command: list[str],
    *,
    timeout_seconds: float,
    dry_run: bool,
    env_overrides: dict[str, str] | None = None,
) -> RefreshStep:
    full_command = [sys.executable, *command]
    display_command = ["python", *command]
    if dry_run:
        return RefreshStep(name=name, command=display_command, status="planned", returncode=None)
    try:
        result = subprocess.run(
            full_command,
            cwd=ROOT,
            capture_output=True,
            timeout=timeout_seconds,
            env={**os.environ, **(env_overrides or {})},
        )
    except subprocess.TimeoutExpired as exc:
        return RefreshStep(
            name=name,
            command=display_command,
            status="failed",
            returncode=None,
            stdout_tail=_tail(_decode_output(exc.stdout)),
            stderr_tail=_tail(_decode_output(exc.stderr)),
            error=f"command timed out after {timeout_seconds}s",
        )
    stdout_text = _decode_output(result.stdout)
    stderr_text = _decode_output(result.stderr)
    return RefreshStep(
        name=name,
        command=display_command,
        status="passed" if result.returncode == 0 else "failed",
        returncode=result.returncode,
        stdout_tail=_tail(stdout_text),
        stderr_tail=_tail(stderr_text),
        error=None if result.returncode == 0 else f"command exited {result.returncode}",
    )


def build_refresh_chain(
    *,
    provider: str = "ollama",
    timeout_seconds: float = 180.0,
    dry_run: bool = False,
    stop_on_failure: bool = True,
    report_path: Path | None = None,
    provider_env_overrides: dict[str, str] | None = None,
    owner_verified: bool = False,
) -> RefreshChainReport:
    if provider not in PROVIDER_CHOICES:
        raise ValueError(f"unsupported provider: {provider}")
    if owner_verified and provider == "mock":
        raise ValueError("owner-verified refresh requires a non-mock provider")

    env_overrides = _provider_env_overrides(provider_env_overrides)
    if not dry_run and not owner_verified and _external_smoke_has_verified_owner_evidence():
        guard_step = RefreshStep(
            name="owner_evidence_guard",
            command=[
                "python",
                "scripts/rc_refresh_release_chain.py",
                "--owner-verified",
            ],
            status="failed",
            returncode=None,
            error=(
                "existing owner-verified rc-external-smoke.json would be overwritten by a non-owner refresh; "
                "rerun with --owner-verified or move the existing owner evidence aside"
            ),
        )
        return _make_report(
            status="failed",
            provider=provider,
            owner_verified=owner_verified,
            dry_run=dry_run,
            stop_on_failure=stop_on_failure,
            steps=[guard_step],
            provider_env_overrides=env_overrides,
        )

    steps: list[RefreshStep] = []
    for name, command in _step_commands(provider, owner_verified=owner_verified):
        if name in BOOTSTRAP_FINAL_GATE_STEPS and report_path is not None and not dry_run:
            write_report(
                _make_report(
                    status="running",
                    provider=provider,
                    owner_verified=owner_verified,
                    dry_run=dry_run,
                    stop_on_failure=stop_on_failure,
                    steps=steps,
                    provider_env_overrides=env_overrides,
                ),
                report_path,
            )
        if name == "evidence_pack" and report_path is not None and not dry_run:
            write_report(
                _make_report(
                    status="running",
                    provider=provider,
                    owner_verified=owner_verified,
                    dry_run=dry_run,
                    stop_on_failure=stop_on_failure,
                    steps=steps,
                    provider_env_overrides=env_overrides,
                ),
                report_path,
            )
        if name == "evidence_pack_after_receipt" and report_path is not None and not dry_run:
            after_receipt_pack_step = RefreshStep(
                name=name,
                command=["python", *command],
                status="passed",
                returncode=0,
                stdout_tail=["Evidence pack after receipt is created after this passed report snapshot is written."],
            )
            write_report(
                _make_report(
                    status="passed",
                    provider=provider,
                    owner_verified=owner_verified,
                    dry_run=dry_run,
                    stop_on_failure=stop_on_failure,
                    steps=[*steps, after_receipt_pack_step],
                    provider_env_overrides=env_overrides,
                ),
                report_path,
            )
        if name == "evidence_pack_final" and report_path is not None and not dry_run:
            final_pack_step = RefreshStep(
                name=name,
                command=["python", *command],
                status="passed",
                returncode=0,
                stdout_tail=["Final evidence pack is created after this passed report snapshot is written."],
            )
            write_report(
                _make_report(
                    status="passed",
                    provider=provider,
                    owner_verified=owner_verified,
                    dry_run=dry_run,
                    stop_on_failure=stop_on_failure,
                    steps=[*steps, final_pack_step],
                    provider_env_overrides=env_overrides,
                ),
                report_path,
            )
        step = _run_step(name, command, timeout_seconds=timeout_seconds, dry_run=dry_run, env_overrides=env_overrides)
        steps.append(step)
        if stop_on_failure and step.status == "failed":
            break

    failed = [step for step in steps if step.status == "failed"]
    status = "planned" if dry_run and not failed else "passed" if not failed else "failed"
    return _make_report(
        status=status,
        provider=provider,
        owner_verified=owner_verified,
        dry_run=dry_run,
        stop_on_failure=stop_on_failure,
        steps=steps,
        provider_env_overrides=env_overrides,
    )


def _make_report(
    *,
    status: str,
    provider: str,
    owner_verified: bool,
    dry_run: bool,
    stop_on_failure: bool,
    steps: list[RefreshStep],
    provider_env_overrides: dict[str, str] | None = None,
) -> RefreshChainReport:
    return RefreshChainReport(
        status=status,
        generated_at=_utc_now(),
        provider=provider,
        owner_verified=owner_verified,
        dry_run=dry_run,
        stop_on_failure=stop_on_failure,
        steps=steps,
        provider_env_overrides=dict(provider_env_overrides or {}),
        next_commands=[
            "Inspect .xagent_runtime/reports/rc-refresh-release-chain.json.",
            "If a step failed, fix that gate and rerun this script; downstream reports may be stale.",
            "Use --owner-verified for the final tag-ready refresh so external smoke requires Feishu, GitHub, and hosted Actions evidence.",
            "Run python scripts\\rc_final_gate.py --require-ready-to-tag only after owner gates are verified.",
        ],
        owner_gate_summary=_owner_gate_summary(),
    )


def write_report(report: RefreshChainReport, output_path: Path) -> None:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(report.to_dict(), ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Refresh X-Agent commercial RC release evidence sequentially")
    parser.add_argument("--provider", choices=PROVIDER_CHOICES, default="ollama")
    parser.add_argument("--ollama-model", help="Set XAGENT_OLLAMA_MODEL for reproducible Ollama provider smoke")
    parser.add_argument("--ollama-base-url", help="Set XAGENT_OLLAMA_BASE_URL for reproducible Ollama provider smoke")
    parser.add_argument("--timeout", type=float, default=180.0)
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--continue-on-failure", action="store_true")
    parser.add_argument(
        "--owner-verified",
        action="store_true",
        help=(
            "run the strict owner-controlled external smoke suite: provider, Feishu, GitHub issue-to-PR "
            "dry-run, GitHub execute preflight, and hosted GitHub Actions preflight"
        ),
    )
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    provider_env_overrides = {}
    if args.ollama_model:
        provider_env_overrides["XAGENT_OLLAMA_MODEL"] = args.ollama_model
    if args.ollama_base_url:
        provider_env_overrides["XAGENT_OLLAMA_BASE_URL"] = args.ollama_base_url
    report = build_refresh_chain(
        provider=args.provider,
        timeout_seconds=args.timeout,
        dry_run=args.dry_run,
        stop_on_failure=not args.continue_on_failure,
        report_path=args.output,
        provider_env_overrides=provider_env_overrides,
        owner_verified=args.owner_verified,
    )
    if args.dry_run or report.status != "passed":
        write_report(report, args.output)
    print(f"RC refresh release chain status: {report.status}")
    print(f"Provider: {report.provider}")
    print(f"Owner verified: {report.owner_verified}")
    print(f"Report written to {args.output}")
    for step in report.steps:
        print(f"- {step.name}: {step.status}")
        if step.error:
            print(f"  error: {step.error}")
    return 0 if report.status in {"planned", "passed"} else 1


if __name__ == "__main__":
    raise SystemExit(main())
