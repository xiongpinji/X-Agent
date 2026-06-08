#!/usr/bin/env python3
"""Build a read-only governance lifecycle report for Skills, plugins, MCP, and hooks.

The report turns the existing X-Agent primitives into a commercial governance
contract. It records lifecycle, permission, dependency, data-access, test, and
rollback metadata without installing plugins, changing MCP servers, executing
hooks, or performing rollbacks.
"""

from __future__ import annotations

import argparse
import json
import re
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any

from scripts.commercial_pilot_core_entrypoints import REPORT_DIR, _utc_now

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_OUTPUT = REPORT_DIR / "governance-lifecycle-report.json"
DEFAULT_MARKDOWN_OUTPUT = REPORT_DIR / "governance-lifecycle-report.md"

LIFECYCLE_STATES = ("draft", "validate", "review", "approve", "promote", "rollback")
GOVERNED_DOMAINS = ("skill", "plugin", "mcp_server", "hook")

CODEX_GOVERNANCE_SOURCES = (
    "https://developers.openai.com/codex/skills",
    "https://developers.openai.com/codex/plugins/build",
    "https://developers.openai.com/codex/mcp",
    "https://developers.openai.com/codex/agent-approvals-security",
)

SECRET_PATTERNS = (
    re.compile(r"\bsk-[A-Za-z0-9_\-]{12,}"),
    re.compile(r"\bgh[pousr]_[A-Za-z0-9_]{20,}"),
    re.compile(r"\bxox[baprs]-[A-Za-z0-9\-]{20,}"),
    re.compile(r"\bBearer\s+[A-Za-z0-9_\-.]{16,}", re.IGNORECASE),
    re.compile(r"-----BEGIN [A-Z ]*PRIVATE KEY-----"),
)


@dataclass(frozen=True)
class GovernanceLifecycleCheck:
    name: str
    status: str
    details: dict[str, Any] = field(default_factory=dict)
    error: str | None = None


@dataclass(frozen=True)
class GovernedLifecycleItem:
    domain: str
    name: str
    current_state: str
    lifecycle_states: list[str]
    permission_scopes: list[str]
    mcp_dependencies: list[str]
    data_access: dict[str, Any]
    test_command: str
    rollback: dict[str, Any]
    approvals: dict[str, Any]
    execution_adapter: dict[str, Any]
    source_refs: list[str]


@dataclass(frozen=True)
class GovernanceLifecycleReport:
    status: str
    generated_at: str
    evidence_type: str
    full_codex_parity_claimed: bool
    dry_run: bool
    mutation_performed: bool
    network_mutation_performed: bool
    owner_gate_required: bool
    lifecycle_states: list[str]
    governed_domains: list[str]
    governed_items: list[GovernedLifecycleItem]
    promotion_gate: dict[str, Any]
    rollback_gate: dict[str, Any]
    checks: list[GovernanceLifecycleCheck]
    official_sources: list[str]
    known_limits: list[str]

    def to_dict(self) -> dict[str, Any]:
        payload = asdict(self)
        payload["governed_items"] = [asdict(item) for item in self.governed_items]
        payload["checks"] = [asdict(check) for check in self.checks]
        return payload


def _redact(value: Any) -> Any:
    if isinstance(value, str):
        redacted = value
        for pattern in SECRET_PATTERNS:
            redacted = pattern.sub("<redacted>", redacted)
        return redacted
    if isinstance(value, dict):
        return {str(key): _redact(item) for key, item in value.items()}
    if isinstance(value, list):
        return [_redact(item) for item in value]
    return value


def _default_governed_items() -> list[dict[str, Any]]:
    lifecycle = list(LIFECYCLE_STATES)
    return [
        {
            "domain": "skill",
            "name": "skill_curator_staged_skill",
            "current_state": "review",
            "lifecycle_states": lifecycle,
            "permission_scopes": ["filesystem:staging-write", "skill:analyze", "skill:draft"],
            "mcp_dependencies": [],
            "data_access": {
                "classification": "internal_metadata",
                "allowed_inputs": ["skill manifest", "README", "test metadata"],
                "secret_material_allowed": False,
            },
            "test_command": (
                "python -m pytest tests/test_skill_curator_api.py "
                "-o addopts=\"\" -p no:cov -p no:cacheprovider -q"
            ),
            "rollback": {
                "plan": "Discard staged draft directory and restore previous approved manifest pointer.",
                "artifact_required": "staged_skill_manifest",
                "mutation_performed": False,
                "owner_approval_required": True,
            },
            "approvals": {"promote": "owner_required", "rollback": "owner_required"},
            "execution_adapter": {
                "state": "metadata_only",
                "mutation_enabled": False,
                "blocked_mutations": ["install_skill", "overwrite_approved_skill"],
            },
            "source_refs": ["backend/app/core/skill_curator", "tests/test_skill_curator_api.py"],
        },
        {
            "domain": "plugin",
            "name": "plugin_contract_preview",
            "current_state": "draft",
            "lifecycle_states": lifecycle,
            "permission_scopes": ["plugin:inspect", "plugin:score", "filesystem:staging-read"],
            "mcp_dependencies": [],
            "data_access": {
                "classification": "public_or_internal_metadata",
                "allowed_inputs": ["plugin manifest", "repository metadata", "static scan summary"],
                "secret_material_allowed": False,
            },
            "test_command": (
                "python -m pytest tests/test_plugin_market.py "
                "-o addopts=\"\" -p no:cov -p no:cacheprovider -q"
            ),
            "rollback": {
                "plan": "Remove preview registration and keep the previously approved plugin catalog entry.",
                "artifact_required": "plugin_preview_record",
                "mutation_performed": False,
                "owner_approval_required": True,
            },
            "approvals": {"promote": "owner_required", "rollback": "owner_required"},
            "execution_adapter": {
                "state": "not_implemented_owner_gated",
                "mutation_enabled": False,
                "blocked_mutations": ["install_plugin", "enable_plugin", "network_fetch_plugin"],
            },
            "source_refs": ["backend/app/core/plugin_system.py", "tests/test_plugin_market.py"],
        },
        {
            "domain": "mcp_server",
            "name": "mcp_server_registration",
            "current_state": "validate",
            "lifecycle_states": lifecycle,
            "permission_scopes": ["mcp:discover", "mcp:list_tools", "tool_registry:read"],
            "mcp_dependencies": ["config/mcp_servers.yaml"],
            "data_access": {
                "classification": "tool_metadata",
                "allowed_inputs": ["server name", "tool schema", "health status"],
                "secret_material_allowed": False,
            },
            "test_command": (
                "python -m pytest tests/test_mcp_manager.py "
                "-o addopts=\"\" -p no:cov -p no:cacheprovider -q"
            ),
            "rollback": {
                "plan": "Disable candidate server config and refresh registered tools from the previous healthy snapshot.",
                "artifact_required": "mcp_tool_snapshot",
                "mutation_performed": False,
                "owner_approval_required": True,
            },
            "approvals": {"promote": "owner_required", "rollback": "owner_required"},
            "execution_adapter": {
                "state": "metadata_only",
                "mutation_enabled": False,
                "blocked_mutations": ["start_mcp_server", "write_mcp_config", "execute_mcp_tool"],
            },
            "source_refs": ["backend/app/core/mcp", "tests/test_mcp_manager.py"],
        },
        {
            "domain": "hook",
            "name": "hook_policy_registration",
            "current_state": "review",
            "lifecycle_states": lifecycle,
            "permission_scopes": ["hook:register", "hook:evaluate", "approval:ask"],
            "mcp_dependencies": [],
            "data_access": {
                "classification": "runtime_context_metadata",
                "allowed_inputs": ["tool name", "arguments summary", "hook decision"],
                "secret_material_allowed": False,
            },
            "test_command": (
                "python -m pytest tests/test_hooks_manager.py "
                "-o addopts=\"\" -p no:cov -p no:cacheprovider -q"
            ),
            "rollback": {
                "plan": "Unregister candidate hook policy and restore the previous hook priority order.",
                "artifact_required": "hook_policy_snapshot",
                "mutation_performed": False,
                "owner_approval_required": True,
            },
            "approvals": {"promote": "owner_required", "rollback": "owner_required"},
            "execution_adapter": {
                "state": "metadata_only",
                "mutation_enabled": False,
                "blocked_mutations": ["execute_hook_side_effect", "persist_hook_policy"],
            },
            "source_refs": ["backend/app/core/hooks", "tests/test_hooks_manager.py"],
        },
    ]


def _items_from_payload(items: list[dict[str, Any]] | None) -> list[GovernedLifecycleItem]:
    raw_items = items if items is not None else _default_governed_items()
    return [GovernedLifecycleItem(**_redact(item)) for item in raw_items]


def _build_checks(report_payload: dict[str, Any]) -> list[GovernanceLifecycleCheck]:
    items = report_payload["governed_items"]
    observed_states = report_payload["lifecycle_states"]
    observed_domains = sorted({item["domain"] for item in items})
    failed_adapters = [
        item["name"]
        for item in items
        if item["execution_adapter"].get("mutation_enabled") is not False
    ]
    missing_metadata = [
        item["name"]
        for item in items
        if not item["permission_scopes"]
        or "classification" not in item["data_access"]
        or not item["test_command"]
        or not item["rollback"]
    ]
    unapproved_promotions = [
        item["name"]
        for item in items
        if item["approvals"].get("promote") != "owner_required"
        or item["approvals"].get("rollback") != "owner_required"
        or item["rollback"].get("owner_approval_required") is not True
    ]
    return [
        GovernanceLifecycleCheck(
            name="lifecycle_states_complete",
            status="passed" if observed_states == list(LIFECYCLE_STATES) else "failed",
            details={"observed": observed_states, "expected": list(LIFECYCLE_STATES)},
            error=None if observed_states == list(LIFECYCLE_STATES) else "lifecycle state set is incomplete",
        ),
        GovernanceLifecycleCheck(
            name="governed_domains_complete",
            status="passed" if observed_domains == sorted(GOVERNED_DOMAINS) else "failed",
            details={"observed": observed_domains, "expected": sorted(GOVERNED_DOMAINS)},
            error=None if observed_domains == sorted(GOVERNED_DOMAINS) else "one or more governed domains are missing",
        ),
        GovernanceLifecycleCheck(
            name="governance_metadata_complete",
            status="passed" if not missing_metadata else "failed",
            details={"missing_metadata": missing_metadata},
            error=None if not missing_metadata else "one or more governed items are missing required metadata",
        ),
        GovernanceLifecycleCheck(
            name="promote_and_rollback_owner_gated",
            status="passed" if not unapproved_promotions else "failed",
            details={"not_owner_gated": unapproved_promotions},
            error=None if not unapproved_promotions else "promote or rollback can bypass owner approval",
        ),
        GovernanceLifecycleCheck(
            name="dry_run_only",
            status="passed" if report_payload["dry_run"] is True else "failed",
            details={"dry_run": report_payload["dry_run"]},
            error=None if report_payload["dry_run"] is True else "report is not dry-run",
        ),
        GovernanceLifecycleCheck(
            name="no_mutating_adapters",
            status="passed" if not failed_adapters else "failed",
            details={"mutation_enabled": failed_adapters},
            error=None if not failed_adapters else "one or more adapters allow mutation",
        ),
        GovernanceLifecycleCheck(
            name="no_full_codex_parity_claim",
            status="passed" if report_payload["full_codex_parity_claimed"] is False else "failed",
            details={"full_codex_parity_claimed": report_payload["full_codex_parity_claimed"]},
            error=None
            if report_payload["full_codex_parity_claimed"] is False
            else "report claims full Codex parity",
        ),
    ]


def build_governance_lifecycle_report(
    governed_items: list[dict[str, Any]] | None = None,
) -> GovernanceLifecycleReport:
    items = _items_from_payload(governed_items)
    report_payload: dict[str, Any] = {
        "status": "governance_lifecycle_report_ready",
        "generated_at": _utc_now(),
        "evidence_type": "skills_plugins_mcp_hooks_governance",
        "full_codex_parity_claimed": False,
        "dry_run": True,
        "mutation_performed": False,
        "network_mutation_performed": False,
        "owner_gate_required": True,
        "lifecycle_states": list(LIFECYCLE_STATES),
        "governed_domains": list(GOVERNED_DOMAINS),
        "governed_items": [asdict(item) for item in items],
        "promotion_gate": {
            "required_state_before_promote": "approve",
            "owner_approval_required": True,
            "tests_required": True,
            "mutation_enabled": False,
        },
        "rollback_gate": {
            "required_artifact": "previous_approved_snapshot",
            "owner_approval_required": True,
            "mutation_enabled": False,
        },
        "official_sources": list(CODEX_GOVERNANCE_SOURCES),
        "known_limits": [
            "This report is read-only and does not install, enable, or remove skills or plugins.",
            "MCP server registration, tool execution, and config writes remain owner-gated future adapters.",
            "Hook execution side effects and persisted hook policy changes are not performed.",
            "Rollback is described as metadata only; no file, plugin, MCP, or hook rollback mutation is performed.",
            "Full Codex Skills, plugins, MCP, and hooks parity is not claimed.",
        ],
    }
    checks = _build_checks(report_payload)
    if any(check.status == "failed" for check in checks):
        report_payload["status"] = "governance_lifecycle_report_blocked"
    return GovernanceLifecycleReport(
        governed_items=items,
        checks=checks,
        **{key: value for key, value in report_payload.items() if key not in {"governed_items"}},
    )


def render_markdown_report(report: GovernanceLifecycleReport) -> str:
    items = "\n".join(
        (
            f"- `{item.domain}` `{item.name}`: state `{item.current_state}`, "
            f"test `{item.test_command}`, adapter `{item.execution_adapter['state']}`"
        )
        for item in report.governed_items
    )
    checks = "\n".join(f"- {check.name}: `{check.status}`" for check in report.checks)
    limits = "\n".join(f"- {item}" for item in report.known_limits)
    sources = "\n".join(f"- {source}" for source in report.official_sources)
    return (
        "# X-Agent Governance Lifecycle Report\n\n"
        f"- Status: `{report.status}`\n"
        f"- Generated at: `{report.generated_at}`\n"
        f"- Dry run: `{report.dry_run}`\n"
        f"- Mutation performed: `{report.mutation_performed}`\n"
        f"- Network mutation performed: `{report.network_mutation_performed}`\n"
        f"- Full Codex parity claimed: `{report.full_codex_parity_claimed}`\n\n"
        "## Lifecycle States\n\n"
        f"`{' -> '.join(report.lifecycle_states)}`\n\n"
        "## Governed Items\n\n"
        f"{items}\n\n"
        "## Checks\n\n"
        f"{checks}\n\n"
        "## Official Codex Sources\n\n"
        f"{sources}\n\n"
        "## Known Limits\n\n"
        f"{limits}\n"
    )


def write_report(report: GovernanceLifecycleReport, output_path: Path = DEFAULT_OUTPUT) -> None:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(report.to_dict(), ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def write_markdown_report(
    report: GovernanceLifecycleReport,
    output_path: Path = DEFAULT_MARKDOWN_OUTPUT,
) -> None:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(render_markdown_report(report), encoding="utf-8")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--markdown-output", type=Path, default=DEFAULT_MARKDOWN_OUTPUT)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    report = build_governance_lifecycle_report()
    write_report(report, args.output)
    write_markdown_report(report, args.markdown_output)
    print(f"Governance lifecycle report status: {report.status}")
    print(f"JSON report written to {args.output}")
    print(f"Markdown report written to {args.markdown_output}")
    print(f"Full Codex parity claimed: {report.full_codex_parity_claimed}")
    print(f"Mutation performed: {report.mutation_performed}")
    for check in report.checks:
        print(f"- {check.name}: {check.status}")
        if check.error:
            print(f"  error: {check.error}")
    return 0 if report.status == "governance_lifecycle_report_ready" else 1


if __name__ == "__main__":
    raise SystemExit(main())
