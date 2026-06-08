#!/usr/bin/env python3
"""Build the latest Codex-alignment execution matrix for X-Agent.

This report is a planning and governance gate. It records how X-Agent maps to
the current Codex product surface without claiming full Codex parity.
"""

from __future__ import annotations

import argparse
import hashlib
import json
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any

from scripts.commercial_pilot_core_entrypoints import REPORT_DIR, _utc_now

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_OUTPUT = REPORT_DIR / "latest-codex-alignment.json"
DEFAULT_MARKDOWN_OUTPUT = REPORT_DIR / "latest-codex-alignment.md"

CODEX_OFFICIAL_SOURCES = (
    "https://developers.openai.com/codex/codex-manual.md",
    "https://developers.openai.com/codex/cloud/environments",
    "https://developers.openai.com/codex/app/features",
    "https://developers.openai.com/codex/skills",
    "https://developers.openai.com/codex/integrations/github",
    "https://developers.openai.com/codex/integrations/slack",
    "https://developers.openai.com/codex/app-server",
    "https://developers.openai.com/codex/github-action",
    "https://developers.openai.com/codex/sdk",
    "https://developers.openai.com/codex/enterprise/admin-setup",
)

READY_XAGENT_STATUSES = frozenset(
    {
        "aligned_for_pilot_v1",
        "approval_sandbox_admin_contract_ready",
        "contract_first_ready",
        "cloud_task_contract_ready",
        "durable_thread_contract_ready",
        "governance_lifecycle_report_ready",
        "github_review_action_report_ready",
        "partial",
        "sdk_backend_stub_ready",
        "sdk_http_dry_run_adapter_ready",
        "sdk_noninteractive_contract_ready",
        "domestic_feishu_first",
    }
)

NEXT_TASK_DONE_STATUSES = frozenset(
    {
        "aligned_for_pilot_v1",
        "approval_sandbox_admin_contract_ready",
        "cloud_task_contract_ready",
        "contract_first_ready",
        "durable_thread_contract_ready",
        "governance_lifecycle_report_ready",
        "github_review_action_report_ready",
        "sdk_backend_stub_ready",
        "sdk_http_dry_run_adapter_ready",
        "sdk_noninteractive_contract_ready",
    }
)


@dataclass(frozen=True)
class AlignmentEvidenceSpec:
    name: str
    path: Path
    category: str
    required: bool = True
    expected_statuses: frozenset[str] = frozenset()
    expected_evidence_type: str | None = None


@dataclass(frozen=True)
class AlignmentEvidence:
    name: str
    path: str
    category: str
    required: bool
    status: str
    sha256: str | None = None
    size_bytes: int | None = None
    report_status: str | None = None
    evidence_type: str | None = None
    details: dict[str, Any] = field(default_factory=dict)
    error: str | None = None


@dataclass(frozen=True)
class CodexAlignmentCapability:
    capability: str
    codex_surface: str
    priority: str
    xagent_status: str
    evidence: list[str]
    next_task: str
    acceptance_command: str
    official_sources: list[str]
    rationale: str


@dataclass(frozen=True)
class AlignmentCheck:
    name: str
    status: str
    details: dict[str, Any] = field(default_factory=dict)
    error: str | None = None


@dataclass(frozen=True)
class LatestCodexAlignmentReport:
    status: str
    generated_at: str
    evidence_type: str
    full_codex_parity_claimed: bool
    pilot_delivery_status: str | None
    p0_ready_count: int
    p0_total_count: int
    next_p0_tasks: list[str]
    official_sources: list[str]
    capabilities: list[CodexAlignmentCapability]
    evidence: list[AlignmentEvidence]
    checks: list[AlignmentCheck]
    known_limits: list[str]

    def to_dict(self) -> dict[str, Any]:
        payload = asdict(self)
        payload["capabilities"] = [asdict(item) for item in self.capabilities]
        payload["evidence"] = [asdict(item) for item in self.evidence]
        payload["checks"] = [asdict(item) for item in self.checks]
        return payload


def _display_path(path: Path, root: Path) -> str:
    try:
        return str(path.resolve().relative_to(root.resolve()))
    except ValueError:
        return str(path.resolve())


def _read_json(path: Path, root: Path) -> tuple[dict[str, Any] | None, str | None]:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError:
        return None, f"evidence not found: {_display_path(path, root)}"
    except (OSError, json.JSONDecodeError) as exc:
        return None, f"could not read evidence {_display_path(path, root)}: {exc}"
    if not isinstance(payload, dict):
        return None, f"evidence JSON is not an object: {_display_path(path, root)}"
    return payload, None


def _sha256_file(path: Path, root: Path) -> tuple[str | None, int | None, str | None]:
    try:
        data = path.read_bytes()
    except FileNotFoundError:
        return None, None, f"evidence not found: {_display_path(path, root)}"
    except OSError as exc:
        return None, None, f"could not read evidence {_display_path(path, root)}: {exc}"
    return hashlib.sha256(data).hexdigest(), len(data), None


def build_evidence_specs(root: Path = ROOT, report_dir: Path = REPORT_DIR) -> tuple[AlignmentEvidenceSpec, ...]:
    return (
        AlignmentEvidenceSpec(
            "feishu_customer_acceptance_pack",
            report_dir / "commercial-pilot-customer-acceptance-pack.json",
            "runtime_report",
            expected_statuses=frozenset({"customer_acceptance_pack_ready"}),
            expected_evidence_type="commercial_pilot_customer_acceptance_pack",
        ),
        AlignmentEvidenceSpec(
            "github_review_action_report",
            report_dir / "github-review-action-report.json",
            "runtime_report",
            expected_statuses=frozenset({"github_review_action_report_ready"}),
            expected_evidence_type="github_review_action",
        ),
        AlignmentEvidenceSpec(
            "governance_lifecycle_report",
            report_dir / "governance-lifecycle-report.json",
            "runtime_report",
            expected_statuses=frozenset({"governance_lifecycle_report_ready"}),
            expected_evidence_type="skills_plugins_mcp_hooks_governance",
        ),
        AlignmentEvidenceSpec(
            "approval_sandbox_admin_report",
            report_dir / "approval-sandbox-admin-report.json",
            "runtime_report",
            expected_statuses=frozenset({"approval_sandbox_admin_contract_ready"}),
            expected_evidence_type="approval_sandbox_enterprise_admin_contract",
        ),
        AlignmentEvidenceSpec(
            "sdk_noninteractive_report",
            report_dir / "sdk-noninteractive-report.json",
            "runtime_report",
            expected_statuses=frozenset(
                {
                    "sdk_noninteractive_contract_ready",
                    "sdk_backend_stub_ready",
                    "sdk_http_dry_run_adapter_ready",
                }
            ),
            expected_evidence_type="sdk_noninteractive_cli_contract",
        ),
        AlignmentEvidenceSpec(
            "control_plane_protocol",
            root / "docs" / "specs" / "xagent-control-plane-protocol.md",
            "source_doc",
        ),
        AlignmentEvidenceSpec(
            "control_plane_api",
            root / "backend" / "app" / "api" / "control_plane.py",
            "source_api",
        ),
        AlignmentEvidenceSpec(
            "control_plane_protocol_tests",
            root / "tests" / "test_control_plane_protocol.py",
            "source_test",
        ),
        AlignmentEvidenceSpec(
            "feishu_delivery_pack_doc",
            root / "docs" / "FEISHU_PILOT_V1_DELIVERY_PACK.md",
            "source_doc",
        ),
        AlignmentEvidenceSpec("mcp_manager_tests", root / "tests" / "test_mcp_manager.py", "source_test"),
        AlignmentEvidenceSpec("hooks_manager_tests", root / "tests" / "test_hooks_manager.py", "source_test"),
        AlignmentEvidenceSpec("cli_commands_tests", root / "tests" / "test_cli_commands.py", "source_test"),
        AlignmentEvidenceSpec("workbench_thread_tests", root / "tests" / "test_workbench_thread_loop.py", "source_test"),
        AlignmentEvidenceSpec(
            "commercial_workbench_evidence_tests",
            root / "tests" / "test_commercial_pilot_workbench_thread.py",
            "source_test",
        ),
        AlignmentEvidenceSpec(
            "cloud_task_environment_spec",
            root / "docs" / "specs" / "xagent-cloud-task-environment.md",
            "source_doc",
        ),
        AlignmentEvidenceSpec(
            "cloud_task_environment_tests",
            root / "tests" / "test_cloud_task_environment_contract.py",
            "source_test",
        ),
        AlignmentEvidenceSpec("skill_curator_api_tests", root / "tests" / "test_skill_curator_api.py", "source_test"),
        AlignmentEvidenceSpec("approval_tests", root / "tests" / "test_approvals.py", "source_test"),
        AlignmentEvidenceSpec("sandbox_security_tests", root / "tests" / "test_security_sandbox.py", "source_test"),
        AlignmentEvidenceSpec(
            "approval_sandbox_admin_script",
            root / "scripts" / "approval_sandbox_admin_report.py",
            "source_script",
        ),
        AlignmentEvidenceSpec(
            "approval_sandbox_admin_tests",
            root / "tests" / "test_approval_sandbox_admin_report.py",
            "source_test",
        ),
        AlignmentEvidenceSpec(
            "github_review_action_script",
            root / "scripts" / "github_review_action_report.py",
            "source_script",
        ),
        AlignmentEvidenceSpec(
            "github_review_action_report_tests",
            root / "tests" / "test_github_review_action_report.py",
            "source_test",
        ),
        AlignmentEvidenceSpec(
            "governance_lifecycle_report_script",
            root / "scripts" / "governance_lifecycle_report.py",
            "source_script",
        ),
        AlignmentEvidenceSpec(
            "governance_lifecycle_report_tests",
            root / "tests" / "test_governance_lifecycle_report.py",
            "source_test",
        ),
        AlignmentEvidenceSpec("github_issue_to_pr_tests", root / "tests" / "test_issue_to_pr_api.py", "source_test"),
        AlignmentEvidenceSpec("github_cli_tests", root / "tests" / "test_cli_github.py", "source_test"),
        AlignmentEvidenceSpec(
            "sdk_contract_module",
            root / "backend" / "app" / "sdk" / "control_plane.py",
            "source_sdk",
        ),
        AlignmentEvidenceSpec("sdk_cli_command", root / "cli" / "commands" / "sdk_cmd.py", "source_cli"),
        AlignmentEvidenceSpec("sdk_contract_tests", root / "tests" / "test_xagent_sdk_contract.py", "source_test"),
        AlignmentEvidenceSpec(
            "sdk_noninteractive_script",
            root / "scripts" / "sdk_noninteractive_report.py",
            "source_script",
        ),
        AlignmentEvidenceSpec(
            "sdk_noninteractive_tests",
            root / "tests" / "test_sdk_noninteractive_report.py",
            "source_test",
        ),
        AlignmentEvidenceSpec(
            "commercial_rc_workflow",
            root / ".github" / "workflows" / "commercial-rc.yml",
            "source_workflow",
        ),
        AlignmentEvidenceSpec("latest_alignment_plan", root / "docs" / "superpowers" / "plans" / "2026-06-08-latest-codex-alignment-execution.md", "source_doc"),
    )


def _evidence_from_spec(
    spec: AlignmentEvidenceSpec,
    root: Path,
) -> tuple[AlignmentEvidence, dict[str, Any] | None]:
    sha256, size_bytes, digest_error = _sha256_file(spec.path, root)
    if digest_error:
        return (
            AlignmentEvidence(
                name=spec.name,
                path=_display_path(spec.path, root),
                category=spec.category,
                required=spec.required,
                status="missing" if spec.required else "optional_missing",
                error=digest_error,
            ),
            None,
        )

    payload: dict[str, Any] | None = None
    report_status: str | None = None
    evidence_type: str | None = None
    details: dict[str, Any] = {}
    status = "present"
    error: str | None = None

    if spec.category == "runtime_report":
        payload, read_error = _read_json(spec.path, root)
        if read_error or payload is None:
            status = "failed" if spec.required else "preview"
            error = read_error or "runtime evidence is unreadable"
        else:
            report_status = payload.get("status") if isinstance(payload.get("status"), str) else None
            evidence_type = payload.get("evidence_type") if isinstance(payload.get("evidence_type"), str) else None
            details = {
                "report_status": report_status,
                "evidence_type": evidence_type,
                "full_codex_parity_claimed": payload.get("full_codex_parity_claimed"),
                "mutation_performed": payload.get("mutation_performed"),
                "outbound_message_sent": payload.get("outbound_message_sent"),
            }
            if payload.get("full_codex_parity_claimed") is True:
                status = "failed"
                error = "runtime evidence claims full Codex parity"
            elif spec.expected_statuses and report_status not in spec.expected_statuses:
                status = "action_required" if spec.required else "preview"
                error = f"runtime evidence status {report_status!r} is not accepted"
            elif spec.expected_evidence_type and evidence_type != spec.expected_evidence_type:
                status = "failed" if spec.required else "preview"
                error = "runtime evidence_type is not accepted"
            else:
                status = "passed" if spec.required else "present"

    return (
        AlignmentEvidence(
            name=spec.name,
            path=_display_path(spec.path, root),
            category=spec.category,
            required=spec.required,
            status=status,
            sha256=sha256,
            size_bytes=size_bytes,
            report_status=report_status,
            evidence_type=evidence_type,
            details=details,
            error=error,
        ),
        payload,
    )


def _capabilities() -> list[CodexAlignmentCapability]:
    return [
        CodexAlignmentCapability(
            capability="feishu_commercial_pilot_delivery",
            codex_surface="cloud/app task completion and handoff",
            priority="P0",
            xagent_status="aligned_for_pilot_v1",
            evidence=["feishu_customer_acceptance_pack", "feishu_delivery_pack_doc"],
            next_task="Keep the Feishu customer acceptance pack current after every pilot evidence refresh.",
            acceptance_command="python scripts\\commercial_pilot_customer_acceptance_pack.py",
            official_sources=[
                "https://developers.openai.com/codex/app/features",
                "https://developers.openai.com/codex/cloud/environments",
            ],
            rationale="The first domestic pilot has a customer-archivable evidence chain and read-only API contract.",
        ),
        CodexAlignmentCapability(
            capability="app_server_control_plane",
            codex_surface="Codex app-server JSON-RPC protocol",
            priority="P0",
            xagent_status="contract_first_ready",
            evidence=["control_plane_protocol", "control_plane_api", "control_plane_protocol_tests"],
            next_task="Implement concrete adapters behind the control-plane contract, starting with read-only thread/run and runtime evidence adapters.",
            acceptance_command="python -m pytest tests/test_control_plane_protocol.py -o addopts=\"\" -p no:cov -p no:cacheprovider -q",
            official_sources=["https://developers.openai.com/codex/app-server"],
            rationale="The first contract layer exposes auditable control-plane envelope endpoints while keeping mutating adapters gated.",
        ),
        CodexAlignmentCapability(
            capability="threads_worktrees_and_automations",
            codex_surface="Codex app local/worktree/cloud threads and automations",
            priority="P0",
            xagent_status="durable_thread_contract_ready",
            evidence=[
                "control_plane_api",
                "control_plane_protocol_tests",
                "workbench_thread_tests",
                "commercial_workbench_evidence_tests",
            ],
            next_task="Promote the metadata-only worktree and automation fields into real owner-gated adapters after cloud task and scheduler contracts land.",
            acceptance_command="python -m pytest tests/test_control_plane_protocol.py tests/test_workbench_thread_loop.py tests/test_commercial_pilot_workbench_thread.py -o addopts=\"\" -p no:cov -p no:cacheprovider -q",
            official_sources=["https://developers.openai.com/codex/app/features"],
            rationale="Durable thread/read, search, turn-event, approval, evidence, and guarded rollback metadata now have backend contract coverage; real worktree mutation and scheduled automation remain explicitly owner-gated future work.",
        ),
        CodexAlignmentCapability(
            capability="cloud_task_environment",
            codex_surface="Codex cloud environments with setup, cache, and controlled internet access",
            priority="P0",
            xagent_status="cloud_task_contract_ready",
            evidence=["cloud_task_environment_spec", "cloud_task_environment_tests", "commercial_rc_workflow"],
            next_task="Implement the owner-gated hosted runner adapter and smoke report behind this cloud task environment contract.",
            acceptance_command="python -m pytest tests/test_cloud_task_environment_contract.py -o addopts=\"\" -p no:cov -p no:cacheprovider -q",
            official_sources=["https://developers.openai.com/codex/cloud/environments"],
            rationale="The cloud task environment contract now defines checkout identity, setup and maintenance phases, default-deny agent networking, secret boundaries, task loop events, artifact diffs, and evidence export without enabling hosted execution mutation.",
        ),
        CodexAlignmentCapability(
            capability="github_review_and_action_workflows",
            codex_surface="Codex GitHub code review and Codex GitHub Action",
            priority="P0",
            xagent_status="github_review_action_report_ready",
            evidence=[
                "github_review_action_report",
                "github_review_action_script",
                "github_review_action_report_tests",
                "github_issue_to_pr_tests",
                "github_cli_tests",
                "commercial_rc_workflow",
            ],
            next_task="Implement owner-gated GitHub execute adapters for PR creation, review comments, issue comments, and GitHub Action dispatch after dry-run evidence review.",
            acceptance_command="python scripts\\github_review_action_report.py && python -m pytest tests/test_github_review_action_report.py tests/test_issue_to_pr_api.py tests/test_cli_github.py -o addopts=\"\" -p no:cov -p no:cacheprovider -q",
            official_sources=[
                "https://developers.openai.com/codex/integrations/github",
                "https://developers.openai.com/codex/github-action",
            ],
            rationale="X-Agent now packages issue, branch, patch, PR draft, CI, review, and action-gate evidence into a read-only GitHub review/action report; all network mutations remain owner-gated.",
        ),
        CodexAlignmentCapability(
            capability="skills_plugins_and_mcp",
            codex_surface="Codex Skills, plugins, and MCP customization",
            priority="P0",
            xagent_status="governance_lifecycle_report_ready",
            evidence=[
                "governance_lifecycle_report",
                "governance_lifecycle_report_script",
                "governance_lifecycle_report_tests",
                "skill_curator_api_tests",
                "mcp_manager_tests",
                "hooks_manager_tests",
            ],
            next_task="Implement real owner-gated lifecycle adapters for skill promotion, plugin enablement, MCP registration, hook policy persistence, and rollback after governance evidence review.",
            acceptance_command="python scripts\\governance_lifecycle_report.py && python -m pytest tests/test_governance_lifecycle_report.py tests/test_skill_curator_api.py tests/test_mcp_manager.py tests/test_hooks_manager.py -o addopts=\"\" -p no:cov -p no:cacheprovider -q",
            official_sources=[
                "https://developers.openai.com/codex/skills",
                "https://developers.openai.com/codex/plugins/build",
                "https://developers.openai.com/codex/mcp",
            ],
            rationale="X-Agent now packages Skills, plugins, MCP servers, and hooks into a read-only commercial lifecycle report with draft, validate, review, approve, promote, rollback states; real lifecycle mutations remain owner-gated.",
        ),
        CodexAlignmentCapability(
            capability="approval_sandbox_and_enterprise_admin",
            codex_surface="Codex approvals, sandboxing, RBAC, audit, and admin controls",
            priority="P0",
            xagent_status="approval_sandbox_admin_contract_ready",
            evidence=[
                "approval_sandbox_admin_report",
                "approval_sandbox_admin_script",
                "approval_sandbox_admin_tests",
                "approval_tests",
                "sandbox_security_tests",
            ],
            next_task="Implement adapter-level enforcement for the normalized approval subjects across CLI, channel, MCP, browser, and GitHub execute flows after contract evidence review.",
            acceptance_command="python scripts\\approval_sandbox_admin_report.py && python -m pytest tests/test_approval_sandbox_admin_report.py tests/test_approvals.py tests/test_security_sandbox.py -o addopts=\"\" -p no:cov -p no:cacheprovider -q",
            official_sources=[
                "https://developers.openai.com/codex/agent-approvals-security",
                "https://developers.openai.com/codex/enterprise/admin-setup",
            ],
            rationale="X-Agent now normalizes command, file-change, network, MCP elicitation, browser action, channel send, and issue-to-PR execute approvals into one subject and decision contract; adapter execution remains owner-gated.",
        ),
        CodexAlignmentCapability(
            capability="cli_and_programmatic_sdk",
            codex_surface="Codex CLI, non-interactive mode, and Codex SDK",
            priority="P1",
            xagent_status="sdk_http_dry_run_adapter_ready",
            evidence=[
                "sdk_noninteractive_report",
                "sdk_contract_module",
                "sdk_cli_command",
                "sdk_contract_tests",
                "sdk_noninteractive_script",
                "sdk_noninteractive_tests",
                "cli_commands_tests",
                "control_plane_protocol",
                "control_plane_protocol_tests",
            ],
            next_task="Implement owner-approved long-running SDK execution adapters after the dry-run HTTP adapter is reviewed.",
            acceptance_command="python scripts\\sdk_noninteractive_report.py && python -m pytest tests/test_xagent_sdk_contract.py tests/test_sdk_noninteractive_report.py tests/test_cli_commands.py tests/test_control_plane_protocol.py -o addopts=\"\" -p no:cov -p no:cacheprovider -q",
            official_sources=[
                "https://developers.openai.com/codex/noninteractive",
                "https://developers.openai.com/codex/sdk",
            ],
            rationale="X-Agent now exposes SDK-style thread start/resume/run/read envelopes, non-interactive CLI JSON output, an owner-gated backend SDK invoke stub, and a CLI HTTP dry-run adapter for --execute; real agent execution remains disabled.",
        ),
        CodexAlignmentCapability(
            capability="slack_to_domestic_channel_strategy",
            codex_surface="Codex Slack integration",
            priority="P1",
            xagent_status="domestic_feishu_first",
            evidence=["feishu_customer_acceptance_pack"],
            next_task="Keep Slack as non-blocking; extend the Feishu pattern to DingTalk or WeChat Work only after Pilot V1 acceptance.",
            acceptance_command="python scripts\\commercial_pilot_channel_readiness.py",
            official_sources=["https://developers.openai.com/codex/integrations/slack"],
            rationale="Codex supports Slack; X-Agent's first commercial channel is intentionally Feishu for domestic users.",
        ),
        CodexAlignmentCapability(
            capability="ide_app_and_browser_surfaces",
            codex_surface="Codex app, IDE extension, in-app browser, and local Windows sandbox",
            priority="P1",
            xagent_status="not_blocking_pilot_v1",
            evidence=["control_plane_protocol"],
            next_task="Let the separate UI session consume stable backend report APIs before adding IDE/app parity claims.",
            acceptance_command="python -m pytest tests/test_commercial_pilot_api.py -o addopts=\"\" -p no:cov -p no:cacheprovider -q",
            official_sources=[
                "https://developers.openai.com/codex/app/features",
                "https://developers.openai.com/codex/ide",
                "https://developers.openai.com/codex/app/windows",
            ],
            rationale="UI and IDE parity are product surfaces, not blockers for the Feishu backend pilot handoff.",
        ),
    ]


def _required_evidence_check(evidence: list[AlignmentEvidence]) -> AlignmentCheck:
    failed = [item.name for item in evidence if item.required and item.status not in {"present", "passed"}]
    if failed:
        hard_failed = [item.name for item in evidence if item.required and item.status == "failed"]
        return AlignmentCheck(
            name="required_alignment_evidence",
            status="failed" if hard_failed else "action_required",
            details={"missing_or_invalid": failed},
            error="one or more latest Codex-alignment evidence files are missing or invalid",
        )
    return AlignmentCheck(
        name="required_alignment_evidence",
        status="passed",
        details={"count": sum(1 for item in evidence if item.required)},
    )


def _customer_pack_ready_check(customer_pack: dict[str, Any] | None) -> AlignmentCheck:
    actual = customer_pack.get("status") if customer_pack else None
    passed = actual == "customer_acceptance_pack_ready"
    return AlignmentCheck(
        name="feishu_customer_acceptance_pack_ready",
        status="passed" if passed else "action_required",
        details={"actual": actual, "expected": "customer_acceptance_pack_ready"},
        error=None if passed else "Feishu customer acceptance pack is not ready",
    )


def _parity_claim_check(payloads: dict[str, dict[str, Any] | None]) -> AlignmentCheck:
    claimers = [
        name
        for name, payload in payloads.items()
        if isinstance(payload, dict) and payload.get("full_codex_parity_claimed") is True
    ]
    if claimers:
        return AlignmentCheck(
            name="no_full_codex_parity_claim",
            status="failed",
            details={"claiming_evidence": sorted(claimers)},
            error="one or more latest Codex-alignment evidence sources claim full parity",
        )
    return AlignmentCheck(
        name="no_full_codex_parity_claim",
        status="passed",
        details={"full_codex_parity_claimed": False},
    )


def _mutation_boundary_check(payloads: dict[str, dict[str, Any] | None]) -> AlignmentCheck:
    customer_pack = payloads.get("feishu_customer_acceptance_pack")
    if customer_pack is None:
        return AlignmentCheck(
            name="commercial_pilot_no_mutation_boundary",
            status="action_required",
            details={"missing_inputs": ["feishu_customer_acceptance_pack"]},
            error="commercial pilot mutation boundary cannot be checked until the customer acceptance pack is available",
        )

    observed: dict[str, dict[str, Any]] = {
        "feishu_customer_acceptance_pack": {
            "mutation_performed": customer_pack.get("mutation_performed"),
            "outbound_message_sent": customer_pack.get("outbound_message_sent"),
        }
    }
    for name, payload in payloads.items():
        if name == "feishu_customer_acceptance_pack" or payload is None:
            continue
        if "mutation_performed" in payload or "network_mutation_performed" in payload:
            observed[name] = {
                "mutation_performed": payload.get("mutation_performed"),
                "network_mutation_performed": payload.get("network_mutation_performed"),
            }
    offenders = [
        f"{name}.{key}"
        for name, values in observed.items()
        for key, value in values.items()
        if value is not False
    ]
    if offenders:
        return AlignmentCheck(
            name="commercial_pilot_no_mutation_boundary",
            status="failed",
            details={"observed": observed, "offenders": offenders},
            error="commercial pilot evidence must remain read-only for this alignment gate",
        )
    return AlignmentCheck(name="commercial_pilot_no_mutation_boundary", status="passed", details=observed)


def _source_coverage_check(capabilities: list[CodexAlignmentCapability]) -> AlignmentCheck:
    missing = [item.capability for item in capabilities if not item.official_sources]
    if missing:
        return AlignmentCheck(
            name="codex_official_source_coverage",
            status="failed",
            details={"missing_sources": missing},
            error="each latest Codex-alignment capability must cite official Codex sources",
        )
    unique_sources = sorted({source for item in capabilities for source in item.official_sources})
    return AlignmentCheck(
        name="codex_official_source_coverage",
        status="passed",
        details={"source_count": len(unique_sources), "sources": unique_sources},
    )


def _p0_task_board_check(capabilities: list[CodexAlignmentCapability]) -> AlignmentCheck:
    p0 = [item for item in capabilities if item.priority == "P0"]
    incomplete = [
        item.capability
        for item in p0
        if not item.next_task or not item.acceptance_command or not item.evidence
    ]
    if incomplete:
        return AlignmentCheck(
            name="p0_task_board_complete",
            status="action_required",
            details={"incomplete": incomplete},
            error="one or more P0 capabilities are missing next task, acceptance command, or evidence mapping",
        )
    return AlignmentCheck(
        name="p0_task_board_complete",
        status="passed",
        details={"p0_count": len(p0)},
    )


def _overall_status(checks: list[AlignmentCheck]) -> str:
    if any(check.status == "failed" for check in checks):
        return "latest_codex_alignment_blocked"
    if any(check.status == "action_required" for check in checks):
        return "latest_codex_alignment_action_required"
    return "latest_codex_alignment_plan_ready"


def build_latest_codex_alignment_report(
    *,
    root: Path = ROOT,
    report_dir: Path = REPORT_DIR,
    evidence_specs: tuple[AlignmentEvidenceSpec, ...] | None = None,
) -> LatestCodexAlignmentReport:
    specs = evidence_specs or build_evidence_specs(root=root, report_dir=report_dir)
    evidence_items: list[AlignmentEvidence] = []
    payloads: dict[str, dict[str, Any] | None] = {}
    for spec in specs:
        evidence, payload = _evidence_from_spec(spec, root)
        evidence_items.append(evidence)
        payloads[spec.name] = payload

    capabilities = _capabilities()
    customer_pack = payloads.get("feishu_customer_acceptance_pack")
    p0_capabilities = [item for item in capabilities if item.priority == "P0"]
    p0_ready = [
        item
        for item in p0_capabilities
        if item.xagent_status in READY_XAGENT_STATUSES
    ]
    checks = [
        _required_evidence_check(evidence_items),
        _customer_pack_ready_check(customer_pack),
        _parity_claim_check(payloads),
        _mutation_boundary_check(payloads),
        _source_coverage_check(capabilities),
        _p0_task_board_check(capabilities),
    ]
    status = _overall_status(checks)
    next_p0_tasks = [
        f"{item.capability}: {item.next_task}"
        for item in p0_capabilities
        if item.xagent_status not in NEXT_TASK_DONE_STATUSES
    ]

    return LatestCodexAlignmentReport(
        status=status,
        generated_at=_utc_now(),
        evidence_type="latest_codex_alignment",
        full_codex_parity_claimed=False,
        pilot_delivery_status=customer_pack.get("status") if customer_pack else None,
        p0_ready_count=len(p0_ready),
        p0_total_count=len(p0_capabilities),
        next_p0_tasks=next_p0_tasks,
        official_sources=list(CODEX_OFFICIAL_SOURCES),
        capabilities=capabilities,
        evidence=evidence_items,
        checks=checks,
        known_limits=[
            "This report is a latest-Codex alignment plan and evidence map, not a full parity claim.",
            "Feishu Pilot V1 is deliverable, but Codex cloud, app-server, IDE/app, SDK, and enterprise admin parity remain staged work.",
            "The report consumes existing local evidence and does not call GitHub, Slack, Feishu, or OpenAI services.",
            "Generated runtime reports under .xagent_runtime are not staged by default.",
        ],
    )


def render_markdown_report(report: LatestCodexAlignmentReport) -> str:
    checks = "\n".join(f"- {check.name}: `{check.status}`" for check in report.checks)
    capabilities = "\n".join(
        (
            f"- {item.capability} ({item.priority}): `{item.xagent_status}` - "
            f"{item.next_task}"
        )
        for item in report.capabilities
    )
    p0_tasks = "\n".join(f"- {item}" for item in report.next_p0_tasks)
    evidence = "\n".join(
        f"- {item.name}: `{item.status}` / `{item.sha256 or '<missing-sha256>'}` / `{item.path}`"
        for item in report.evidence
    )
    sources = "\n".join(f"- {source}" for source in report.official_sources)
    limits = "\n".join(f"- {item}" for item in report.known_limits)
    return (
        "# X-Agent Latest Codex Alignment Report\n\n"
        f"- Status: `{report.status}`\n"
        f"- Generated at: `{report.generated_at}`\n"
        f"- Pilot delivery status: `{report.pilot_delivery_status}`\n"
        f"- P0 ready count: `{report.p0_ready_count}/{report.p0_total_count}`\n"
        f"- Full Codex parity claimed: `{report.full_codex_parity_claimed}`\n\n"
        "## Capability Matrix\n\n"
        f"{capabilities}\n\n"
        "## Next P0 Tasks\n\n"
        f"{p0_tasks}\n\n"
        "## Checks\n\n"
        f"{checks}\n\n"
        "## Evidence\n\n"
        f"{evidence}\n\n"
        "## Official Codex Sources\n\n"
        f"{sources}\n\n"
        "## Known Limits\n\n"
        f"{limits}\n"
    )


def write_report(report: LatestCodexAlignmentReport, output_path: Path = DEFAULT_OUTPUT) -> None:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(report.to_dict(), ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def write_markdown_report(report: LatestCodexAlignmentReport, output_path: Path = DEFAULT_MARKDOWN_OUTPUT) -> None:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(render_markdown_report(report), encoding="utf-8")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--markdown-output", type=Path, default=DEFAULT_MARKDOWN_OUTPUT)
    parser.add_argument("--report-dir", type=Path, default=REPORT_DIR)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    report = build_latest_codex_alignment_report(report_dir=args.report_dir)
    write_report(report, args.output)
    write_markdown_report(report, args.markdown_output)
    print(f"Latest Codex alignment status: {report.status}")
    print(f"Pilot delivery status: {report.pilot_delivery_status or '<missing>'}")
    print(f"P0 ready count: {report.p0_ready_count}/{report.p0_total_count}")
    print(f"JSON report written to {args.output}")
    print(f"Markdown report written to {args.markdown_output}")
    print(f"Full Codex parity claimed: {report.full_codex_parity_claimed}")
    for check in report.checks:
        print(f"- {check.name}: {check.status}")
        if check.error:
            print(f"  error: {check.error}")
    return 0 if report.status == "latest_codex_alignment_plan_ready" else 1


if __name__ == "__main__":
    raise SystemExit(main())
