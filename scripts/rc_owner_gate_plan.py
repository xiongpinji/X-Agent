#!/usr/bin/env python3
"""Create a machine-readable execution plan for owner-controlled RC gates.

The commercial RC cannot be fully tagged from local-only evidence. This script
turns the remaining external gates into an auditable handoff: required
environment variables, commands, evidence files, and current readiness state.
It never prints or stores secret values.
"""

from __future__ import annotations

import argparse
import json
import os
import re
from dataclasses import asdict, dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
REPORT_DIR = ROOT / ".xagent_runtime" / "reports"
DEFAULT_EXTERNAL_SMOKE = REPORT_DIR / "rc-external-smoke.json"
DEFAULT_SOURCE_BUNDLE = REPORT_DIR / "rc-source-bundle.json"
DEFAULT_OUTPUT = REPORT_DIR / "rc-owner-gate-plan.json"

REAL_PROVIDER_CHOICES = {"openai", "deepseek", "anthropic", "ollama", "local"}
PROVIDER_SENTINEL = "xagent-rc-ok"
GITHUB_ACTIONS_RUN_URL_RE = re.compile(
    r"^https://github\.com/[^/\s]+/[^/\s]+/actions/runs/[0-9]+(?:[/?#][^\s]*)?$"
)
GITHUB_COMMIT_SHA_RE = re.compile(r"^[0-9a-fA-F]{40}$")


@dataclass(frozen=True)
class OwnerGatePlanItem:
    name: str
    status: str
    required_env_groups: list[list[str]]
    configured_env: list[str]
    missing: list[str]
    command: str
    evidence: list[str]
    completion_criteria: list[str]
    notes: list[str] = field(default_factory=list)


@dataclass(frozen=True)
class OwnerGatePlanReport:
    status: str
    generated_at: str
    external_smoke_report: str
    gates: list[OwnerGatePlanItem]
    next_commands: list[str]
    source_bundle_report: str | None = None
    evidence_freshness: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        payload = asdict(self)
        payload["gates"] = [asdict(gate) for gate in self.gates]
        return payload


def _utc_now() -> str:
    return datetime.now(UTC).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _getenv(*names: str) -> str:
    for name in names:
        value = os.getenv(name)
        if value:
            return value
    return ""


def _configured_names(groups: list[list[str]]) -> list[str]:
    configured: list[str] = []
    for group in groups:
        configured.extend(name for name in group if os.getenv(name))
    return sorted(dict.fromkeys(configured))


def _valid_github_actions_run_url(value: str) -> bool:
    return bool(GITHUB_ACTIONS_RUN_URL_RE.fullmatch(value.strip()))


def _valid_git_commit_sha(value: str) -> bool:
    return bool(GITHUB_COMMIT_SHA_RE.fullmatch(value.strip()))


def _read_json(path: Path) -> dict[str, Any] | None:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (FileNotFoundError, json.JSONDecodeError):
        return None
    return payload if isinstance(payload, dict) else None


def _read_external_checks(path: Path) -> dict[str, dict[str, Any]]:
    payload = _read_json(path)
    if payload is None:
        return {}
    checks: dict[str, dict[str, Any]] = {}
    for check in payload.get("checks", []):
        if isinstance(check, dict) and check.get("name"):
            checks[str(check["name"])] = check
    return checks


def _parse_utc_timestamp(value: Any) -> datetime | None:
    if not isinstance(value, str) or not value.strip():
        return None
    try:
        parsed = datetime.fromisoformat(value.strip().replace("Z", "+00:00"))
    except ValueError:
        return None
    if parsed.tzinfo is None:
        return parsed.replace(tzinfo=UTC)
    return parsed.astimezone(UTC)


def _evidence_freshness(external_smoke_path: Path, source_bundle_path: Path | None) -> dict[str, Any]:
    if source_bundle_path is None:
        return {"required": False, "fresh": True}

    external_payload = _read_json(external_smoke_path)
    source_payload = _read_json(source_bundle_path)
    external_generated_at = (external_payload or {}).get("generated_at")
    source_generated_at = (source_payload or {}).get("generated_at")
    external_at = _parse_utc_timestamp(external_generated_at)
    source_at = _parse_utc_timestamp(source_generated_at)
    problems: list[str] = []

    if external_payload is None:
        problems.append("external smoke report is missing or invalid")
    if source_payload is None:
        problems.append("source bundle report is missing or invalid")
    if external_payload is not None and external_at is None:
        problems.append("external smoke generated_at is missing or invalid")
    if source_payload is not None and source_at is None:
        problems.append("source bundle generated_at is missing or invalid")
    if external_at is not None and source_at is not None and external_at < source_at:
        problems.append("external smoke evidence is older than the current source bundle")

    return {
        "required": True,
        "fresh": not problems,
        "external_smoke_report": str(external_smoke_path),
        "source_bundle_report": str(source_bundle_path),
        "external_generated_at": external_generated_at,
        "source_bundle_generated_at": source_generated_at,
        "problems": problems,
    }


def _apply_freshness_to_gate(gate: OwnerGatePlanItem, freshness: dict[str, Any]) -> OwnerGatePlanItem:
    if gate.status != "verified" or freshness.get("fresh") is True:
        return gate
    problem = (
        "Rerun scripts\\rc_external_smoke.py after the latest source bundle is generated; "
        + "; ".join(str(item) for item in freshness.get("problems", []))
    )
    return OwnerGatePlanItem(
        name=gate.name,
        status="action_required",
        required_env_groups=gate.required_env_groups,
        configured_env=gate.configured_env,
        missing=[problem],
        command=gate.command,
        evidence=gate.evidence,
        completion_criteria=gate.completion_criteria,
        notes=[
            *gate.notes,
            f"external_generated_at={freshness.get('external_generated_at')}",
            f"source_bundle_generated_at={freshness.get('source_bundle_generated_at')}",
        ],
    )


def _external_verified(checks: dict[str, dict[str, Any]], name: str) -> bool:
    return str((checks.get(name) or {}).get("status") or "") == "passed"


def _external_action_required(checks: dict[str, dict[str, Any]], name: str, label: str) -> list[str]:
    check = checks.get(name) or {}
    status = str(check.get("status") or "")
    if not status or status == "passed":
        return []
    missing: list[str] = []
    raw_missing = check.get("missing")
    if isinstance(raw_missing, list):
        missing.extend(str(item) for item in raw_missing if str(item))
    error = check.get("error")
    if error:
        missing.append(f"{label} smoke did not pass: {error}")
    if not missing:
        missing.append(f"{label} smoke status is {status}; rerun the owner gate smoke before tagging.")
    return missing


def _passed_details(checks: dict[str, dict[str, Any]], name: str) -> dict[str, Any] | None:
    check = checks.get(name) or {}
    if str(check.get("status") or "") != "passed":
        return None
    details = check.get("details")
    return details if isinstance(details, dict) else None


def _provider_verified(checks: dict[str, dict[str, Any]]) -> bool:
    details = _passed_details(checks, "provider")
    if details is None:
        return False
    provider = str(details.get("provider") or "").lower()
    return (
        provider in REAL_PROVIDER_CHOICES
        and provider != "mock"
        and bool(details.get("model"))
        and details.get("sentinel") == PROVIDER_SENTINEL
        and details.get("sentinel_matched") is True
    )


def _feishu_webhook_verified(checks: dict[str, dict[str, Any]]) -> bool:
    details = _passed_details(checks, "feishu_webhook_contract")
    if details is None:
        return False
    return (
        details.get("app_id_configured") is True
        and details.get("app_secret_configured") is True
        and details.get("encrypt_key_configured") is True
        and details.get("valid_signature_accepted") is True
        and details.get("invalid_signature_rejected") is True
        and details.get("missing_signature_rejected") is True
        and details.get("event_accepted") is True
        and details.get("duplicate_rejected") is True
        and details.get("outbound_mocked") is True
        and details.get("mutation_performed") is False
        and bool(details.get("event_id"))
        and bool(details.get("event_type"))
        and details.get("message_id") is not None
    )


def _telegram_bot_verified(checks: dict[str, dict[str, Any]]) -> bool:
    details = _passed_details(checks, "telegram_bot_preflight")
    if details is None:
        return False
    return (
        details.get("token_configured") is True
        and bool(details.get("bot_id"))
        and bool(details.get("bot_username"))
        and details.get("mutation_performed") is False
    )


def _github_dry_run_verified(checks: dict[str, dict[str, Any]]) -> bool:
    details = _passed_details(checks, "github_issue_to_pr_dry_run")
    if details is None:
        return False
    repo_full_name = str(details.get("repo_full_name") or "")
    steps = details.get("steps")
    return (
        "/" in repo_full_name
        and isinstance(details.get("issue_number"), int)
        and details.get("issue_number", 0) > 0
        and bool(details.get("branch_name"))
        and details.get("execute_allowed") is False
        and isinstance(steps, list)
        and "draft_pull_request_payload" in steps
    )


def _github_execute_verified(checks: dict[str, dict[str, Any]]) -> bool:
    check = checks.get("github_issue_to_pr_execute_preflight") or {}
    if str(check.get("status") or "") != "passed":
        return False
    details = check.get("details")
    if not isinstance(details, dict):
        return False
    read_probe = details.get("read_probe")
    permission_probe = details.get("permission_probe")
    if not isinstance(read_probe, dict) or not isinstance(permission_probe, dict):
        return False
    permissions = permission_probe.get("permissions")
    if not isinstance(permissions, dict):
        return False
    return (
        read_probe.get("status") == "passed"
        and read_probe.get("state") == "open"
        and permission_probe.get("status") == "passed"
        and details.get("dry_run_status") == "passed"
        and permissions.get("push") is True
        and permission_probe.get("least_privilege") is True
        and details.get("mutation_performed") is False
    )


def _hosted_actions_verified(checks: dict[str, dict[str, Any]]) -> bool:
    details = _passed_details(checks, "hosted_github_actions_run")
    if details is None:
        return False
    run_url = str(details.get("run_url") or details.get("html_url") or "")
    expected_head_sha = str(details.get("expected_head_sha") or "")
    head_sha = str(details.get("head_sha") or "")
    return (
        _valid_github_actions_run_url(run_url)
        and _valid_git_commit_sha(expected_head_sha)
        and _valid_git_commit_sha(head_sha)
        and details.get("run_status") == "completed"
        and details.get("conclusion") == "success"
        and details.get("workflow_verified") is True
        and details.get("head_sha_verified") is True
        and details.get("jobs_verified") is True
        and details.get("artifact_verified") is True
        and details.get("mutation_performed") is False
    )


def _status(verified: bool, missing: list[str]) -> str:
    if verified:
        return "verified"
    return "action_required" if missing else "ready_to_run"


def _provider_gate(checks: dict[str, dict[str, Any]], explicit_provider: str | None) -> OwnerGatePlanItem:
    provider = (explicit_provider or _getenv("XAGENT_LLM_BACKEND", "LLM_BACKEND") or "mock").lower()
    provider_for_command = provider if provider in REAL_PROVIDER_CHOICES else "<openai|deepseek|anthropic|ollama|local>"
    env_groups = [["XAGENT_LLM_BACKEND", "LLM_BACKEND"]]
    missing: list[str] = []
    notes: list[str] = []

    if provider == "mock":
        missing.append("Set XAGENT_LLM_BACKEND to openai, deepseek, anthropic, ollama, or local.")
    elif provider == "openai":
        env_groups.append(["XAGENT_OPENAI_API_KEY", "OPENAI_API_KEY"])
        env_groups.append(["XAGENT_OPENAI_MODEL", "OPENAI_MODEL"])
        if not _getenv("XAGENT_OPENAI_API_KEY", "OPENAI_API_KEY"):
            missing.append("Set XAGENT_OPENAI_API_KEY or OPENAI_API_KEY.")
    elif provider == "deepseek":
        env_groups.append(["XAGENT_DEEPSEEK_API_KEY", "DEEPSEEK_API_KEY"])
        env_groups.append(["XAGENT_DEEPSEEK_MODEL", "DEEPSEEK_MODEL"])
        if not _getenv("XAGENT_DEEPSEEK_API_KEY", "DEEPSEEK_API_KEY"):
            missing.append("Set XAGENT_DEEPSEEK_API_KEY or DEEPSEEK_API_KEY.")
    elif provider == "anthropic":
        env_groups.append(["XAGENT_ANTHROPIC_API_KEY", "ANTHROPIC_API_KEY"])
        env_groups.append(["XAGENT_ANTHROPIC_MODEL", "ANTHROPIC_MODEL"])
        if not _getenv("XAGENT_ANTHROPIC_API_KEY", "ANTHROPIC_API_KEY"):
            missing.append("Set XAGENT_ANTHROPIC_API_KEY or ANTHROPIC_API_KEY.")
    elif provider in {"ollama", "local"}:
        env_groups.append(["XAGENT_OLLAMA_BASE_URL", "OLLAMA_BASE_URL"])
        env_groups.append(["XAGENT_OLLAMA_MODEL", "OLLAMA_MODEL"])
        notes.append("Local-model smoke also requires the Ollama-compatible service to be running.")
        notes.append("Before rerunning provider smoke, prove the selected model can generate with `ollama run <model>`.")
        notes.append('Diagnostic command: `ollama run <model> "Reply with exactly: xagent-rc-ok"`.')
        notes.append(
            "If Ollama reports a model load failure, move OLLAMA_MODELS to an ASCII-only local directory, "
            "restart Ollama, and rerun provider smoke."
        )
    else:
        missing.append(f"Unsupported provider {provider!r}; choose one real provider.")

    status_passed = _external_verified(checks, "provider")
    verified = _provider_verified(checks)
    if status_passed and not verified:
        missing.append(
            "Rerun scripts\\rc_external_smoke.py with a real provider; provider evidence must include "
            "provider, model, sentinel=xagent-rc-ok, and sentinel_matched=true."
        )
    if not verified:
        missing.extend(_external_action_required(checks, "provider", "Provider"))
    missing = list(dict.fromkeys(missing))
    return OwnerGatePlanItem(
        name="provider",
        status=_status(verified, missing),
        required_env_groups=env_groups,
        configured_env=_configured_names(env_groups),
        missing=[] if verified else missing,
        command=(
            f"python scripts\\rc_external_smoke.py --check provider --provider {provider_for_command} "
            "--require-configured"
        ),
        evidence=[".xagent_runtime/reports/rc-external-smoke.json: checks[name=provider].status == passed"],
        completion_criteria=[
            "A non-mock provider is selected.",
            "The provider check returns status=passed with model and latency details.",
            "For Ollama/local, the selected model has been proven with `ollama run <model>` before RC tagging.",
            "For Ollama/local model load failures, OLLAMA_MODELS is on an ASCII-only local path and Ollama was restarted.",
        ],
        notes=notes,
    )


def _feishu_gate(checks: dict[str, dict[str, Any]]) -> OwnerGatePlanItem:
    env_groups = [
        ["XAGENT_FEISHU_APP_ID", "FEISHU_APP_ID"],
        ["XAGENT_FEISHU_APP_SECRET", "FEISHU_APP_SECRET"],
        ["XAGENT_FEISHU_ENCRYPT_KEY", "FEISHU_ENCRYPT_KEY"],
    ]
    missing: list[str] = []
    if not _getenv("XAGENT_FEISHU_APP_ID", "FEISHU_APP_ID"):
        missing.append("Set XAGENT_FEISHU_APP_ID or FEISHU_APP_ID.")
    if not _getenv("XAGENT_FEISHU_APP_SECRET", "FEISHU_APP_SECRET"):
        missing.append("Set XAGENT_FEISHU_APP_SECRET or FEISHU_APP_SECRET.")
    if not _getenv("XAGENT_FEISHU_ENCRYPT_KEY", "FEISHU_ENCRYPT_KEY"):
        missing.append("Set XAGENT_FEISHU_ENCRYPT_KEY or FEISHU_ENCRYPT_KEY for signed event callbacks.")
    webhook_status_passed = _external_verified(checks, "feishu_webhook_contract")
    verified = _feishu_webhook_verified(checks)
    if webhook_status_passed and not verified:
        missing.append(
            "Rerun Feishu webhook contract smoke; evidence must include app_id_configured=true, "
            "app_secret_configured=true, encrypt_key_configured=true, valid_signature_accepted=true, "
            "invalid_signature_rejected=true, missing_signature_rejected=true, event_accepted=true, "
            "duplicate_rejected=true, event_id, event_type, message_id, and mutation_performed=false."
        )
    return OwnerGatePlanItem(
        name="feishu_webhook_contract",
        status=_status(verified, missing),
        required_env_groups=env_groups,
        configured_env=_configured_names(env_groups),
        missing=[] if verified else missing,
        command="python scripts\\rc_external_smoke.py --check feishu_webhook_contract --require-configured",
        evidence=[
            ".xagent_runtime/reports/rc-external-smoke.json: checks[name=feishu_webhook_contract].status == passed",
        ],
        completion_criteria=[
            "Feishu app ID, app secret, and event encrypt key are configured.",
            "Official Feishu/Lark callback signature headers verify with the configured encrypt key.",
            "Invalid and missing Feishu webhook signatures are rejected.",
            "Inbound Feishu message events are accepted and recorded once.",
            "The smoke performs no outbound Feishu message send or external mutation.",
        ],
        notes=[
            "This RC requires Feishu as the domestic channel gate; Telegram remains optional and is not required for tagging.",
            "The contract smoke validates signed event ingestion only; customer live delivery remains an enablement gate.",
        ],
    )


def _github_dry_run_gate(checks: dict[str, dict[str, Any]]) -> OwnerGatePlanItem:
    env_groups = [["XAGENT_GITHUB_TEST_ISSUE_URL", "GITHUB_TEST_ISSUE_URL"]]
    missing = []
    if not _getenv("XAGENT_GITHUB_TEST_ISSUE_URL", "GITHUB_TEST_ISSUE_URL"):
        missing.append("Set XAGENT_GITHUB_TEST_ISSUE_URL to a disposable test issue URL.")
    status_passed = _external_verified(checks, "github_issue_to_pr_dry_run")
    verified = _github_dry_run_verified(checks)
    if status_passed and not verified:
        missing.append(
            "Rerun GitHub dry-run smoke; evidence must include repo_full_name, positive issue_number, "
            "branch_name, execute_allowed=false, and draft_pull_request_payload in plan steps."
        )
    return OwnerGatePlanItem(
        name="github_issue_to_pr_dry_run",
        status=_status(verified, missing),
        required_env_groups=env_groups,
        configured_env=_configured_names(env_groups),
        missing=[] if verified else missing,
        command="python scripts\\rc_external_smoke.py --check github_issue_to_pr_dry_run --require-configured",
        evidence=[
            ".xagent_runtime/reports/rc-external-smoke.json: checks[name=github_issue_to_pr_dry_run].status == passed"
        ],
        completion_criteria=[
            "Disposable issue URL parses successfully.",
            "Dry-run plan is generated with execute_allowed=false.",
        ],
    )


def _github_execute_gate(checks: dict[str, dict[str, Any]]) -> OwnerGatePlanItem:
    env_groups = [
        ["XAGENT_GITHUB_TOKEN", "GITHUB_TOKEN"],
        ["XAGENT_GITHUB_TEST_ISSUE_URL", "GITHUB_TEST_ISSUE_URL"],
    ]
    missing: list[str] = []
    if not _getenv("XAGENT_GITHUB_TOKEN", "GITHUB_TOKEN"):
        missing.append("Set XAGENT_GITHUB_TOKEN or GITHUB_TOKEN.")
    if not _getenv("XAGENT_GITHUB_TEST_ISSUE_URL", "GITHUB_TEST_ISSUE_URL"):
        missing.append("Set XAGENT_GITHUB_TEST_ISSUE_URL to a disposable test issue URL.")
    status_passed = _external_verified(checks, "github_issue_to_pr_execute_preflight")
    verified = _github_execute_verified(checks)
    if status_passed and not verified:
        missing.append(
            "Rerun scripts\\rc_external_smoke.py --github-execute-preflight; execute evidence must include "
            "read_probe.status=passed, read_probe.state=open, permission_probe.status=passed, "
            "permission_probe.permissions.push=true, permission_probe.least_privilege=true, "
            "no overbroad admin/maintain permissions, and mutation_performed=false."
        )
    return OwnerGatePlanItem(
        name="github_issue_to_pr_execute_preflight",
        status=_status(verified, missing),
        required_env_groups=env_groups,
        configured_env=_configured_names(env_groups),
        missing=[] if verified else missing,
        command=(
            "python scripts\\rc_external_smoke.py --check github_issue_to_pr_dry_run "
            "--check github_issue_to_pr_execute_preflight --require-configured --github-execute-preflight"
        ),
        evidence=[
            ".xagent_runtime/reports/rc-external-smoke.json: checks[name=github_issue_to_pr_execute_preflight].status == passed"
        ],
        completion_criteria=[
            "Token-authenticated read-only GitHub issue API probe passes.",
            "Disposable GitHub test issue remains open with read_probe.state=open.",
            "Token-authenticated read-only GitHub repository permission probe confirms permissions.push=true.",
            "GitHub token does not expose admin or maintain permissions.",
            "No branch push, PR creation, or issue comment is performed by the smoke.",
        ],
    )


def _hosted_ci_gate(checks: dict[str, dict[str, Any]]) -> OwnerGatePlanItem:
    run_url = _getenv("XAGENT_COMMERCIAL_RC_GITHUB_ACTIONS_RUN_URL")
    expected_head_sha = _getenv("XAGENT_COMMERCIAL_RC_GITHUB_ACTIONS_HEAD_SHA").strip()
    valid_run_url = _valid_github_actions_run_url(run_url)
    valid_expected_head_sha = _valid_git_commit_sha(expected_head_sha)
    run_status_passed = _external_verified(checks, "hosted_github_actions_run")
    run_verified = _hosted_actions_verified(checks)
    verified = bool(run_url) and valid_run_url and run_verified
    missing = []
    if not run_url:
        missing.append("Run .github/workflows/commercial-rc.yml on hosted GitHub Actions and attach the successful run URL.")
    elif not valid_run_url:
        missing.append("Set XAGENT_COMMERCIAL_RC_GITHUB_ACTIONS_RUN_URL to a valid GitHub Actions run URL.")
    if not expected_head_sha:
        missing.append("Set XAGENT_COMMERCIAL_RC_GITHUB_ACTIONS_HEAD_SHA to the commit SHA used by the hosted run.")
    elif not valid_expected_head_sha:
        missing.append("Set XAGENT_COMMERCIAL_RC_GITHUB_ACTIONS_HEAD_SHA to a 40-character hex git commit SHA.")
    if run_url and valid_run_url and valid_expected_head_sha and not run_verified:
        missing.append(
            "Run scripts\\rc_external_smoke.py --github-actions-preflight to verify the hosted GitHub Actions "
            "run, workflow identity, head SHA, required jobs, and evidence artifact."
        )
    if run_status_passed and not run_verified:
        missing.append(
            "Rerun hosted GitHub Actions preflight; evidence must include a valid run_url, "
            "run_status=completed, conclusion=success, workflow_verified=true, "
            "head_sha_verified=true, jobs_verified=true, artifact_verified=true, and mutation_performed=false."
        )
    return OwnerGatePlanItem(
        name="hosted_github_actions_commercial_rc",
        status="verified" if verified else "action_required" if missing else "ready_to_run",
        required_env_groups=[
            ["XAGENT_COMMERCIAL_RC_GITHUB_ACTIONS_RUN_URL"],
            ["XAGENT_COMMERCIAL_RC_GITHUB_ACTIONS_HEAD_SHA"],
            ["XAGENT_GITHUB_TOKEN", "GITHUB_TOKEN"],
        ],
        configured_env=_configured_names(
            [
                ["XAGENT_COMMERCIAL_RC_GITHUB_ACTIONS_RUN_URL"],
                ["XAGENT_COMMERCIAL_RC_GITHUB_ACTIONS_HEAD_SHA"],
                ["XAGENT_GITHUB_TOKEN", "GITHUB_TOKEN"],
            ]
        ),
        missing=missing,
        command=(
            "python scripts\\rc_external_smoke.py --check hosted_github_actions_run "
            "--github-actions-preflight --require-configured"
        ),
        evidence=[
            "Hosted GitHub Actions run for .github/workflows/commercial-rc.yml completes successfully.",
            "XAGENT_COMMERCIAL_RC_GITHUB_ACTIONS_RUN_URL records the successful run URL.",
            "XAGENT_COMMERCIAL_RC_GITHUB_ACTIONS_HEAD_SHA records the expected hosted run commit SHA.",
            ".xagent_runtime/reports/rc-external-smoke.json: checks[name=hosted_github_actions_run].status == passed",
        ],
        completion_criteria=[
            "commercial-rc-linux job succeeds.",
            "commercial-rc-windows-installer job succeeds.",
            "commercial-rc-evidence artifact is attached to the run.",
            "Read-only GitHub Actions run API probe confirms status=completed and conclusion=success.",
            "Read-only GitHub Actions run API probe confirms head_sha_verified=true.",
            "Read-only GitHub Actions jobs API probe confirms both required jobs completed successfully.",
            "Read-only GitHub Actions artifacts API probe confirms commercial-rc-evidence is attached.",
        ],
        notes=[
            "This script validates the hosted CI evidence URL shape and requires rc_external_smoke.py to query run, jobs, and artifacts.",
            f"run_url_shape_valid={valid_run_url}",
            f"run_status_verified={run_verified}",
        ],
    )


def build_owner_gate_plan(
    *,
    external_smoke_path: Path = DEFAULT_EXTERNAL_SMOKE,
    source_bundle_path: Path | None = None,
    provider: str | None = None,
) -> OwnerGatePlanReport:
    checks = _read_external_checks(external_smoke_path)
    freshness = _evidence_freshness(external_smoke_path, source_bundle_path)
    gates = [
        _provider_gate(checks, provider),
        _feishu_gate(checks),
        _github_dry_run_gate(checks),
        _github_execute_gate(checks),
        _hosted_ci_gate(checks),
    ]
    gates = [_apply_freshness_to_gate(gate, freshness) for gate in gates]
    if all(gate.status == "verified" for gate in gates):
        status = "verified"
    elif any(gate.status == "action_required" for gate in gates):
        status = "action_required"
    else:
        status = "ready_to_run"
    provider_for_command = (provider or _getenv("XAGENT_LLM_BACKEND", "LLM_BACKEND") or "<provider>").lower()
    if provider_for_command == "mock":
        provider_for_command = "<provider>"
    return OwnerGatePlanReport(
        status=status,
        generated_at=_utc_now(),
        external_smoke_report=str(external_smoke_path),
        gates=gates,
        next_commands=[
            "Set the missing XAGENT_* environment variables in the deployment owner's secret store or shell.",
            "Trigger the hosted Commercial RC Gate workflow on GitHub Actions.",
            (
                "Set XAGENT_COMMERCIAL_RC_GITHUB_ACTIONS_RUN_URL to the successful hosted run URL in "
                ".xagent_runtime\\reports\\rc-owner-env-template.env or the owner secret store."
            ),
            (
                "Set XAGENT_COMMERCIAL_RC_GITHUB_ACTIONS_HEAD_SHA to the exact commit SHA used by the "
                "successful hosted run in .xagent_runtime\\reports\\rc-owner-env-template.env or the owner secret store."
            ),
            "python scripts\\rc_owner_gate_runner.py --gate all --env-file .xagent_runtime\\reports\\rc-owner-env-template.env",
            f"python scripts\\rc_external_smoke.py --provider {provider_for_command} --require-configured "
            "--github-execute-preflight --github-actions-preflight",
            "python scripts\\rc_final_gate.py --require-ready-to-tag",
        ],
        source_bundle_report=str(source_bundle_path) if source_bundle_path is not None else None,
        evidence_freshness=freshness,
    )


def write_report(report: OwnerGatePlanReport, output_path: Path) -> None:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(report.to_dict(), ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Create the X-Agent commercial RC owner gate execution plan")
    parser.add_argument("--external-smoke", type=Path, default=DEFAULT_EXTERNAL_SMOKE)
    parser.add_argument("--source-bundle", type=Path, default=DEFAULT_SOURCE_BUNDLE)
    parser.add_argument("--provider", choices=["openai", "deepseek", "anthropic", "ollama", "local"])
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    report = build_owner_gate_plan(
        external_smoke_path=args.external_smoke,
        source_bundle_path=args.source_bundle,
        provider=args.provider,
    )
    write_report(report, args.output)
    print(f"RC owner gate plan status: {report.status}")
    print(f"Report written to {args.output}")
    for gate in report.gates:
        print(f"- {gate.name}: {gate.status}")
        for item in gate.missing:
            print(f"  missing: {item}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
