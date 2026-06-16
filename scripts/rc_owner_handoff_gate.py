#!/usr/bin/env python3
"""Validate the commercial RC owner-gate handoff package.

This gate does not complete owner-controlled external checks. It verifies that
the release owner has a coherent, non-secret handoff: gate plan, env templates,
checklist, commands, evidence references, and current action-required state.
"""

from __future__ import annotations

import argparse
import json
import re
from dataclasses import asdict, dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from scripts.rc_source_bundle import ROOT

REPORT_DIR = ROOT / ".xagent_runtime" / "reports"
DEFAULT_OWNER_GATE_PLAN = REPORT_DIR / "rc-owner-gate-plan.json"
DEFAULT_OWNER_ENV_TEMPLATE = REPORT_DIR / "rc-owner-env-template.json"
DEFAULT_OWNER_ENV_FILE = REPORT_DIR / "rc-owner-env-template.env"
DEFAULT_OWNER_ENV_POWERSHELL = REPORT_DIR / "rc-owner-env-template.ps1"
DEFAULT_OWNER_GATE_CHECKLIST = REPORT_DIR / "rc-owner-gate-checklist.json"
DEFAULT_OWNER_GATE_CHECKLIST_MD = REPORT_DIR / "rc-owner-gate-checklist.md"
DEFAULT_OUTPUT = REPORT_DIR / "rc-owner-handoff-gate.json"

REQUIRED_GATES = {
    "provider",
    "feishu_webhook_contract",
    "github_issue_to_pr_dry_run",
    "github_issue_to_pr_execute_preflight",
    "hosted_github_actions_commercial_rc",
}

REQUIRED_COMMAND_TOKENS = {
    "provider": ("rc_external_smoke.py", "--check provider", "--provider", "--require-configured"),
    "feishu_webhook_contract": (
        "rc_external_smoke.py",
        "--check feishu_webhook_contract",
        "--require-configured",
    ),
    "github_issue_to_pr_dry_run": (
        "rc_external_smoke.py",
        "--check github_issue_to_pr_dry_run",
        "--require-configured",
    ),
    "github_issue_to_pr_execute_preflight": (
        "rc_external_smoke.py",
        "--check github_issue_to_pr_dry_run",
        "--check github_issue_to_pr_execute_preflight",
        "--github-execute-preflight",
        "--require-configured",
    ),
    "hosted_github_actions_commercial_rc": (
        "rc_external_smoke.py",
        "--check hosted_github_actions_run",
        "--github-actions-preflight",
        "--require-configured",
    ),
}

REQUIRED_NEXT_COMMAND_TOKENS = (
    "Trigger the hosted Commercial RC Gate workflow",
    "XAGENT_COMMERCIAL_RC_GITHUB_ACTIONS_RUN_URL",
    "XAGENT_COMMERCIAL_RC_GITHUB_ACTIONS_HEAD_SHA",
    "rc_owner_gate_runner.py --gate all",
    "--env-file",
    "rc-owner-env-template.env",
    "rc_external_smoke.py",
    "--require-configured",
    "--github-execute-preflight",
    "--github-actions-preflight",
    "rc_final_gate.py --require-ready-to-tag",
)

REQUIRED_NEXT_COMMAND_ORDER = (
    "Trigger the hosted Commercial RC Gate workflow",
    "XAGENT_COMMERCIAL_RC_GITHUB_ACTIONS_RUN_URL",
    "XAGENT_COMMERCIAL_RC_GITHUB_ACTIONS_HEAD_SHA",
    "rc_owner_gate_runner.py --gate all",
    "rc_external_smoke.py",
    "rc_final_gate.py --require-ready-to-tag",
)

REQUIRED_ENV_NAMES = {
    "provider": {"XAGENT_LLM_BACKEND"},
    "feishu_webhook_contract": {"XAGENT_FEISHU_APP_ID", "XAGENT_FEISHU_APP_SECRET", "XAGENT_FEISHU_ENCRYPT_KEY"},
    "github_issue_to_pr_dry_run": {"XAGENT_GITHUB_TEST_ISSUE_URL"},
    "github_issue_to_pr_execute_preflight": {"XAGENT_GITHUB_TOKEN", "XAGENT_GITHUB_TEST_ISSUE_URL"},
    "hosted_github_actions_commercial_rc": {
        "XAGENT_COMMERCIAL_RC_GITHUB_ACTIONS_RUN_URL",
        "XAGENT_COMMERCIAL_RC_GITHUB_ACTIONS_HEAD_SHA",
        "XAGENT_GITHUB_TOKEN",
    },
}

REQUIRED_COMPLETION_CRITERIA_TOKENS = {
    "feishu_webhook_contract": (
        "Invalid and missing Feishu webhook signatures are rejected.",
    ),
    "github_issue_to_pr_execute_preflight": (
        "read_probe.state=open",
        "permissions.push=true",
        "admin or maintain permissions",
        "No branch push, PR creation, or issue comment is performed",
    ),
    "hosted_github_actions_commercial_rc": (
        "commercial-rc-linux",
        "commercial-rc-windows-installer",
        "commercial-rc-evidence",
        "head_sha_verified=true",
        "GitHub Actions jobs API",
        "GitHub Actions artifacts API",
    ),
}

EXTERNAL_CHECKS_BY_GATE = {
    "provider": ("provider",),
    "feishu_webhook_contract": ("feishu_webhook_contract",),
    "github_issue_to_pr_dry_run": ("github_issue_to_pr_dry_run",),
    "github_issue_to_pr_execute_preflight": ("github_issue_to_pr_dry_run", "github_issue_to_pr_execute_preflight"),
    "hosted_github_actions_commercial_rc": ("hosted_github_actions_run",),
}

PLACEHOLDER_MARKERS = (
    "<set-in-owner-secret-store>",
    "<openai|deepseek|anthropic|ollama|local>",
    "https://github.com/<owner>/<repo>/issues/<number>",
    "https://github.com/<owner>/<repo>/actions/runs/<run-id>",
    "<40-character-git-commit-sha>",
)

SECRET_VALUE_PATTERNS = (
    re.compile(r"\b(?:sk|ghp|github_pat|xagent)[_-][A-Za-z0-9_=-]{24,}\b"),
    re.compile(r"\b[A-Za-z0-9_./+=-]{48,}\b"),
)

LOCAL_PATH_PATTERNS = (
    re.compile(r"\b[A-Za-z]:\\Users\\[^\\\r\n]+(?:\\[^\\\r\n]+)+"),
    re.compile(r"/home/[^/\s]+(?:/[^/\s]+)+"),
    re.compile(r"/Users/[^/\s]+(?:/[^/\s]+)+"),
)


@dataclass(frozen=True)
class OwnerHandoffCheck:
    name: str
    status: str
    details: dict[str, Any] = field(default_factory=dict)
    error: str | None = None


@dataclass(frozen=True)
class OwnerHandoffGateReport:
    status: str
    generated_at: str
    inputs: dict[str, str]
    checks: list[OwnerHandoffCheck]
    next_commands: list[str]

    def to_dict(self) -> dict[str, Any]:
        payload = asdict(self)
        payload["checks"] = [asdict(check) for check in self.checks]
        return payload


def _utc_now() -> str:
    return datetime.now(UTC).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _read_json(path: Path) -> tuple[dict[str, Any] | None, str | None]:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError:
        return None, f"missing report: {path}"
    except json.JSONDecodeError as exc:
        return None, f"invalid JSON in {path}: {exc}"
    if not isinstance(payload, dict):
        return None, f"report is not a JSON object: {path}"
    return payload, None


def _read_text(path: Path) -> tuple[str, str | None]:
    try:
        return path.read_text(encoding="utf-8"), None
    except FileNotFoundError:
        return "", f"missing handoff file: {path}"
    except UnicodeDecodeError as exc:
        return "", f"handoff file is not UTF-8 text: {exc}"


def _gate_map(payload: dict[str, Any] | None) -> dict[str, dict[str, Any]]:
    gates = (payload or {}).get("gates")
    if not isinstance(gates, list):
        return {}
    return {
        str(gate.get("name")): gate
        for gate in gates
        if isinstance(gate, dict) and gate.get("name")
    }


def _string_list(value: Any) -> list[str]:
    if not isinstance(value, list):
        return []
    return [str(item) for item in value]


def _external_checks_by_name(plan_payload: dict[str, Any] | None) -> dict[str, dict[str, Any]]:
    if plan_payload is None:
        return {}
    external_smoke_report = plan_payload.get("external_smoke_report")
    if not isinstance(external_smoke_report, str) or not external_smoke_report:
        return {}
    path = Path(external_smoke_report)
    resolved = path if path.is_absolute() else ROOT / path
    payload, error = _read_json(resolved)
    if error or payload is None:
        return {}
    checks = payload.get("checks")
    if not isinstance(checks, list):
        return {}
    return {
        str(check.get("name")): check
        for check in checks
        if isinstance(check, dict) and check.get("name")
    }


def _required_external_diagnostics(gate_name: str, checks_by_name: dict[str, dict[str, Any]]) -> list[str]:
    diagnostics: list[str] = []
    for check_name in EXTERNAL_CHECKS_BY_GATE.get(gate_name, (gate_name,)):
        check = checks_by_name.get(check_name)
        if not check:
            continue
        status = str(check.get("status") or "unknown")
        if status == "passed":
            continue
        diagnostics.append(f"External smoke {check_name} is {status}.")
        for item in _string_list(check.get("missing")):
            diagnostics.append(f"External smoke {check_name} missing: {item}")
        error = str(check.get("error") or "")
        if error:
            diagnostics.append(f"External smoke {check_name} error: {error}")
    return diagnostics


def _env_names_from_groups(gate: dict[str, Any]) -> set[str]:
    names: set[str] = set()
    groups = gate.get("required_env_groups")
    if not isinstance(groups, list):
        return names
    for group in groups:
        if isinstance(group, list):
            names.update(str(item) for item in group if str(item))
    return names


def _env_groups(value: Any) -> list[list[str]]:
    if not isinstance(value, list):
        return []
    groups: list[list[str]] = []
    for group in value:
        if not isinstance(group, list):
            continue
        names = [str(item).strip() for item in group if str(item).strip()]
        if names:
            groups.append(names)
    return groups


def _dedupe_env_groups(groups: list[list[str]]) -> list[list[str]]:
    deduped: list[list[str]] = []
    seen: set[tuple[str, ...]] = set()
    for group in groups:
        key = tuple(group)
        if key in seen:
            continue
        seen.add(key)
        deduped.append(group)
    return deduped


def _plan_env_groups(plan_payload: dict[str, Any] | None) -> list[list[str]]:
    groups: list[list[str]] = []
    for gate_name, gate in _gate_map(plan_payload).items():
        if gate_name not in REQUIRED_GATES:
            continue
        groups.extend(_env_groups(gate.get("required_env_groups")))
    return _dedupe_env_groups(groups)


def _template_required_by(template_payload: dict[str, Any] | None) -> dict[str, set[str]]:
    entries = (template_payload or {}).get("entries")
    required_by: dict[str, set[str]] = {}
    if not isinstance(entries, list):
        return required_by
    for entry in entries:
        if not isinstance(entry, dict):
            continue
        name = str(entry.get("name") or "")
        if not name:
            continue
        required_by[name] = set(_string_list(entry.get("required_by")))
    return required_by


def _check_next_command_order(next_commands: list[str], problems: list[str], *, label: str) -> None:
    positions: list[tuple[str, int]] = []
    for token in REQUIRED_NEXT_COMMAND_ORDER:
        index = next((idx for idx, command in enumerate(next_commands) if token in command), -1)
        if index >= 0:
            positions.append((token, index))
    for (previous_token, previous_index), (next_token, next_index) in zip(positions, positions[1:]):
        if previous_index >= next_index:
            problems.append(
                f"{label} next_commands order invalid: {previous_token} must appear before {next_token}"
            )


def _check_plan(payload: dict[str, Any] | None, error: str | None) -> OwnerHandoffCheck:
    problems: list[str] = []
    details: dict[str, Any] = {}
    if error:
        problems.append(error)
    gates = _gate_map(payload)
    missing_gates = sorted(REQUIRED_GATES.difference(gates))
    if missing_gates:
        problems.append(f"owner plan missing gates: {', '.join(missing_gates)}")
    details["gate_count"] = len(gates)
    details["missing_gates"] = missing_gates
    if payload is not None:
        status = str(payload.get("status") or "")
        details["status"] = status
        if status not in {"action_required", "ready_to_run", "verified"}:
            problems.append(f"owner plan status is not recognized: {status}")
        freshness = payload.get("evidence_freshness")
        if not isinstance(freshness, dict):
            problems.append("owner plan evidence_freshness is missing")
        elif freshness.get("required") is not True:
            problems.append("owner plan evidence_freshness.required must be true")
        next_commands = _string_list(payload.get("next_commands"))
        for token in REQUIRED_NEXT_COMMAND_TOKENS:
            if not any(token in command for command in next_commands):
                problems.append(f"owner plan next_commands missing token: {token}")
        _check_next_command_order(next_commands, problems, label="owner plan")
        for gate_name, gate in gates.items():
            if gate_name not in REQUIRED_GATES:
                continue
            command = str(gate.get("command") or "")
            for token in REQUIRED_COMMAND_TOKENS[gate_name]:
                if token not in command:
                    problems.append(f"{gate_name} command missing token: {token}")
            env_names = _env_names_from_groups(gate)
            required = REQUIRED_ENV_NAMES[gate_name]
            if not required.issubset(env_names):
                problems.append(f"{gate_name} missing required env names: {', '.join(sorted(required - env_names))}")
            if gate_name == "provider" and "--provider ollama" in command:
                for env_name in ("XAGENT_OLLAMA_BASE_URL", "XAGENT_OLLAMA_MODEL"):
                    if env_name not in env_names:
                        problems.append(f"provider missing local-model env name: {env_name}")
            evidence = _string_list(gate.get("evidence"))
            if not evidence:
                problems.append(f"{gate_name} evidence list is empty")
            criteria = _string_list(gate.get("completion_criteria"))
            if not criteria:
                problems.append(f"{gate_name} completion criteria is empty")
            criteria_text = "\n".join(criteria)
            for token in REQUIRED_COMPLETION_CRITERIA_TOKENS.get(gate_name, ()):
                if token not in criteria_text:
                    problems.append(f"{gate_name} completion criteria missing token: {token}")
    return OwnerHandoffCheck(
        name="owner_gate_plan",
        status="passed" if not problems else "failed",
        details=details,
        error="; ".join(problems) if problems else None,
    )


def _check_env_template(
    plan_payload: dict[str, Any] | None,
    template_payload: dict[str, Any] | None,
    template_error: str | None,
    env_text: str,
    env_error: str | None,
    ps_text: str,
    ps_error: str | None,
) -> OwnerHandoffCheck:
    problems: list[str] = []
    if template_error:
        problems.append(template_error)
    if env_error:
        problems.append(env_error)
    if ps_error:
        problems.append(ps_error)
    if template_payload is not None and template_payload.get("status") != "created":
        problems.append(f"owner env template status is not created: {template_payload.get('status')}")

    required_by = _template_required_by(template_payload)
    gates = _gate_map(plan_payload)
    for gate_name, gate in gates.items():
        if gate_name not in REQUIRED_GATES:
            continue
        for env_name in REQUIRED_ENV_NAMES[gate_name]:
            if gate_name not in required_by.get(env_name, set()):
                problems.append(f"env template {env_name} is not marked required_by {gate_name}")
            if env_name not in env_text:
                problems.append(f"env file missing variable name: {env_name}")
            if f"$env:{env_name}" not in ps_text:
                problems.append(f"PowerShell env file missing variable name: {env_name}")

    plan_groups = _plan_env_groups(plan_payload)
    template_groups = _dedupe_env_groups(_env_groups((template_payload or {}).get("env_groups")))
    if not template_groups:
        problems.append("env template env_groups is missing or empty")
    missing_groups = [group for group in plan_groups if group not in template_groups]
    extra_groups = [group for group in template_groups if group not in plan_groups]
    if missing_groups:
        formatted = "; ".join("/".join(group) for group in missing_groups)
        problems.append(f"env template env_groups missing owner plan groups: {formatted}")
    if extra_groups:
        formatted = "; ".join("/".join(group) for group in extra_groups)
        problems.append(f"env template env_groups contains groups not declared by owner plan: {formatted}")
    grouped_names = {name for group in template_groups for name in group}
    orphan_entries = sorted(set(required_by).difference(grouped_names))
    if orphan_entries:
        problems.append(f"env template entries are not included in env_groups: {', '.join(orphan_entries)}")

    combined = json.dumps(template_payload or {}, ensure_ascii=False) + env_text + ps_text
    for marker in PLACEHOLDER_MARKERS:
        if marker not in combined:
            problems.append(f"env handoff missing placeholder marker: {marker}")
    findings = _secret_findings(combined)
    if findings:
        problems.append("owner env handoff contains secret-like values")
    local_path_findings = _local_path_findings(combined)
    if local_path_findings:
        problems.append("owner env handoff contains local user/runtime path values")

    return OwnerHandoffCheck(
        name="owner_env_template",
        status="passed" if not problems else "failed",
        details={
            "entry_count": len(required_by),
            "env_group_count": len(template_groups),
            "missing_env_groups": missing_groups,
            "extra_env_groups": extra_groups,
            "secret_findings": findings[:10],
            "local_path_findings": local_path_findings[:10],
        },
        error="; ".join(problems) if problems else None,
    )


def _secret_findings(text: str) -> list[str]:
    findings: list[str] = []
    scrubbed = text
    for marker in PLACEHOLDER_MARKERS:
        scrubbed = scrubbed.replace(marker, "")
    scrubbed = re.sub(r"\b(?:required_by|completion_criteria|configured_env|command_sequence)\b", "", scrubbed)
    for pattern in SECRET_VALUE_PATTERNS:
        for match in pattern.finditer(scrubbed):
            sample = match.group(0)
            if "github.com/" in sample or sample in {"set-in-owner-secret-store"}:
                continue
            if not any(prefix in sample.lower() for prefix in ("sk", "ghp", "github_pat", "xagent")):
                if not re.search(r"[0-9]", sample) or not re.search(r"[A-Z]", sample):
                    continue
            findings.append(sample[:8] + "..." if len(sample) > 8 else "***")
    return findings


def _local_path_findings(text: str) -> list[str]:
    findings: list[str] = []
    seen: set[str] = set()
    for candidate in (text, text.replace("\\\\", "\\")):
        for pattern in LOCAL_PATH_PATTERNS:
            for match in pattern.finditer(candidate):
                sample = match.group(0)
                if sample in seen:
                    continue
                seen.add(sample)
                findings.append(sample[:96] + "..." if len(sample) > 96 else sample)
    return findings


def _check_checklist(
    plan_payload: dict[str, Any] | None,
    checklist_payload: dict[str, Any] | None,
    checklist_error: str | None,
    markdown_text: str,
    markdown_error: str | None,
) -> OwnerHandoffCheck:
    problems: list[str] = []
    if checklist_error:
        problems.append(checklist_error)
    if markdown_error:
        problems.append(markdown_error)
    plan_gates = _gate_map(plan_payload)
    checklist_gates = _gate_map(checklist_payload)
    missing = sorted(REQUIRED_GATES.difference(checklist_gates))
    if missing:
        problems.append(f"checklist missing gates: {', '.join(missing)}")
    if checklist_payload is not None:
        status = str(checklist_payload.get("status") or "")
        if status not in {"action_required", "ready_to_run", "verified"}:
            problems.append(f"checklist status is not recognized: {status}")
        if status == "verified" and any(str(gate.get("status") or "") != "verified" for gate in checklist_gates.values()):
            problems.append("checklist status verified but not every gate is verified")
        next_commands = _string_list(checklist_payload.get("next_commands"))
        for token in REQUIRED_NEXT_COMMAND_TOKENS:
            if not any(token in command for command in next_commands):
                problems.append(f"checklist next_commands missing token: {token}")
        _check_next_command_order(next_commands, problems, label="checklist")
    external_checks = _external_checks_by_name(plan_payload)
    for gate_name in REQUIRED_GATES:
        if gate_name not in markdown_text:
            problems.append(f"checklist markdown missing gate name: {gate_name}")
        plan_command = str((plan_gates.get(gate_name) or {}).get("command") or "")
        if plan_command and plan_command not in markdown_text:
            problems.append(f"checklist markdown missing command for {gate_name}")
        for env_name in _env_names_from_groups(plan_gates.get(gate_name) or {}):
            if env_name not in markdown_text:
                problems.append(f"checklist markdown missing required env name for {gate_name}: {env_name}")
        checklist_gate = checklist_gates.get(gate_name) or {}
        checklist_criteria_text = "\n".join(_string_list(checklist_gate.get("completion_criteria")))
        for token in REQUIRED_COMPLETION_CRITERIA_TOKENS.get(gate_name, ()):
            if token not in checklist_criteria_text:
                problems.append(f"checklist {gate_name} completion criteria missing token: {token}")
            if token not in markdown_text:
                problems.append(f"checklist markdown missing completion criteria token for {gate_name}: {token}")
        if str(checklist_gate.get("status") or "") != "verified":
            notes_text = "\n".join(_string_list(checklist_gate.get("notes")))
            for diagnostic in _required_external_diagnostics(gate_name, external_checks):
                if diagnostic not in notes_text:
                    problems.append(f"checklist {gate_name} missing external smoke note: {diagnostic}")
                if diagnostic not in markdown_text:
                    problems.append(f"checklist markdown missing external smoke note for {gate_name}: {diagnostic}")
    findings = _secret_findings(json.dumps(checklist_payload or {}, ensure_ascii=False) + markdown_text)
    if findings:
        problems.append("owner checklist contains secret-like values")
    local_path_findings = _local_path_findings(
        json.dumps(checklist_payload or {}, ensure_ascii=False) + markdown_text
    )
    if local_path_findings:
        problems.append("owner checklist contains local user/runtime path values")
    return OwnerHandoffCheck(
        name="owner_gate_checklist",
        status="passed" if not problems else "failed",
        details={
            "gate_count": len(checklist_gates),
            "secret_findings": findings[:10],
            "local_path_findings": local_path_findings[:10],
        },
        error="; ".join(problems) if problems else None,
    )


def _check_evidence_paths(plan_payload: dict[str, Any] | None) -> OwnerHandoffCheck:
    problems: list[str] = []
    details: dict[str, Any] = {}
    if plan_payload is None:
        problems.append("owner plan is missing")
    else:
        for field_name in ("external_smoke_report", "source_bundle_report"):
            raw = plan_payload.get(field_name)
            if not isinstance(raw, str) or not raw:
                problems.append(f"owner plan {field_name} is missing")
                continue
            path = Path(raw)
            resolved = path if path.is_absolute() else ROOT / path
            details[field_name] = str(resolved)
            if not resolved.is_file():
                problems.append(f"owner plan {field_name} does not exist: {resolved}")
    return OwnerHandoffCheck(
        name="evidence_paths",
        status="passed" if not problems else "failed",
        details=details,
        error="; ".join(problems) if problems else None,
    )


def build_owner_handoff_gate(
    *,
    owner_gate_plan_path: Path = DEFAULT_OWNER_GATE_PLAN,
    owner_env_template_path: Path = DEFAULT_OWNER_ENV_TEMPLATE,
    owner_env_file_path: Path = DEFAULT_OWNER_ENV_FILE,
    owner_env_powershell_path: Path = DEFAULT_OWNER_ENV_POWERSHELL,
    owner_gate_checklist_path: Path = DEFAULT_OWNER_GATE_CHECKLIST,
    owner_gate_checklist_markdown_path: Path = DEFAULT_OWNER_GATE_CHECKLIST_MD,
) -> OwnerHandoffGateReport:
    plan_payload, plan_error = _read_json(owner_gate_plan_path)
    template_payload, template_error = _read_json(owner_env_template_path)
    checklist_payload, checklist_error = _read_json(owner_gate_checklist_path)
    env_text, env_error = _read_text(owner_env_file_path)
    ps_text, ps_error = _read_text(owner_env_powershell_path)
    markdown_text, markdown_error = _read_text(owner_gate_checklist_markdown_path)

    checks = [
        _check_plan(plan_payload, plan_error),
        _check_env_template(plan_payload, template_payload, template_error, env_text, env_error, ps_text, ps_error),
        _check_checklist(plan_payload, checklist_payload, checklist_error, markdown_text, markdown_error),
        _check_evidence_paths(plan_payload),
    ]
    return OwnerHandoffGateReport(
        status="passed" if all(check.status == "passed" for check in checks) else "failed",
        generated_at=_utc_now(),
        inputs={
            "owner_gate_plan": str(owner_gate_plan_path),
            "owner_env_template": str(owner_env_template_path),
            "owner_env_file": str(owner_env_file_path),
            "owner_env_powershell": str(owner_env_powershell_path),
            "owner_gate_checklist": str(owner_gate_checklist_path),
            "owner_gate_checklist_markdown": str(owner_gate_checklist_markdown_path),
        },
        checks=checks,
        next_commands=[
            "Give rc-owner-env-template.* and rc-owner-gate-checklist.md to the deployment owner.",
            "Run the owner checklist commands with real owner-controlled Feishu/GitHub/Actions resources.",
            "Rerun python scripts\\rc_final_gate.py --require-ready-to-tag after owner gates are verified.",
        ],
    )


def write_report(report: OwnerHandoffGateReport, output_path: Path) -> None:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(report.to_dict(), ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Validate the X-Agent commercial RC owner-gate handoff")
    parser.add_argument("--owner-gate-plan", type=Path, default=DEFAULT_OWNER_GATE_PLAN)
    parser.add_argument("--owner-env-template", type=Path, default=DEFAULT_OWNER_ENV_TEMPLATE)
    parser.add_argument("--owner-env-file", type=Path, default=DEFAULT_OWNER_ENV_FILE)
    parser.add_argument("--owner-env-powershell", type=Path, default=DEFAULT_OWNER_ENV_POWERSHELL)
    parser.add_argument("--owner-gate-checklist", type=Path, default=DEFAULT_OWNER_GATE_CHECKLIST)
    parser.add_argument("--owner-gate-checklist-markdown", type=Path, default=DEFAULT_OWNER_GATE_CHECKLIST_MD)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    report = build_owner_handoff_gate(
        owner_gate_plan_path=args.owner_gate_plan,
        owner_env_template_path=args.owner_env_template,
        owner_env_file_path=args.owner_env_file,
        owner_env_powershell_path=args.owner_env_powershell,
        owner_gate_checklist_path=args.owner_gate_checklist,
        owner_gate_checklist_markdown_path=args.owner_gate_checklist_markdown,
    )
    write_report(report, args.output)
    print(f"RC owner handoff gate status: {report.status}")
    print(f"Report written to {args.output}")
    for check in report.checks:
        print(f"- {check.name}: {check.status}")
        if check.error:
            print(f"  error: {check.error}")
    return 0 if report.status == "passed" else 1


if __name__ == "__main__":
    raise SystemExit(main())
