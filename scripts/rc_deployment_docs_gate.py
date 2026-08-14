#!/usr/bin/env python3
"""Validate commercial RC deployment documentation coverage.

The commercial RC should not rely on prose that drifts away from release
evidence. This gate checks the owner-facing deployment docs against the current
machine reports so the handoff stays deployable and honest.
"""

from __future__ import annotations

import argparse
import json
from dataclasses import asdict, dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from scripts.rc_source_bundle import ROOT

REPORT_DIR = ROOT / ".xagent_runtime" / "reports"
RELEASE_DIR = ROOT / ".xagent_runtime" / "release"

DEFAULT_RUNBOOK = ROOT / "docs" / "operations" / "deployment" / "COMMERCIAL_DEPLOYMENT_RUNBOOK.md"
DEFAULT_CHECKLIST = ROOT / "docs" / "operations" / "deployment" / "RC_COMMERCIAL_DEPLOYMENT_CHECKLIST.md"
DEFAULT_INSTALL_QUICKSTART = ROOT / "docs" / "operations" / "setup" / "INSTALL_QUICKSTART.md"
DEFAULT_RELEASE_NOTES = ROOT / "archive" / "process_docs_2026-07-19" / "RELEASE_NOTES.md"
DEFAULT_FINAL_GATE = REPORT_DIR / "rc-final-gate.json"
DEFAULT_RELEASE_RECEIPT = RELEASE_DIR / "x-agent-commercial-rc-receipt.json"
DEFAULT_EVIDENCE_PACK = REPORT_DIR / "rc-evidence-pack.json"
DEFAULT_STAGING_PLAN = REPORT_DIR / "rc-staging-plan.json"
DEFAULT_OUTPUT = REPORT_DIR / "rc-deployment-docs-gate.json"

OWNER_GATE_IDS = (
    "feishu_webhook_contract",
    "github_issue_to_pr_dry_run",
    "github_issue_to_pr_execute_preflight",
    "hosted_github_actions_commercial_rc",
    "refresh_release_chain_owner_verified",
)

RUNBOOK_TOKENS = (
    "not a GA claim",
    "not a full Codex/Hermes parity claim",
    "XAGENT_APP_MODE=production",
    "XAGENT_REQUIRE_API_KEY=true",
    "XAGENT_BOOTSTRAP_API_KEY",
    "prohibited_secret_artifacts",
    "python scripts/rc_final_gate.py --require-ready-to-tag",
    "python scripts/rc_refresh_release_chain.py --provider ollama --ollama-model",
    "--ollama-base-url",
    "--owner-verified",
    "python scripts/rc_evidence_pack.py",
    "--allow-missing-evidence-pack",
    "Final final gate remains strict",
    "python scripts/rc_owner_gate_runner.py --gate all --dry-run --env-file .xagent_runtime/reports/rc-owner-env-template.env",
    "python scripts/rc_external_smoke.py --check provider --provider ollama --require-configured",
    "feishu_webhook_contract",
    "--env-file .xagent_runtime/reports/rc-owner-env-template.env",
    "--github-actions-preflight",
    "python scripts/rc_owner_handoff_gate.py",
    "docker compose --env-file .env.production",
    "kubectl rollout status deployment/xagent-api",
    "ROLLBACK_PROCEDURE.md",
    "XAGENT_COMMERCIAL_RC_GITHUB_ACTIONS_RUN_URL",
    "XAGENT_COMMERCIAL_RC_GITHUB_ACTIONS_HEAD_SHA",
    "40-character hex git commit SHA",
    "github_issue_to_pr_dry_run",
    "--gate github_issue_to_pr_dry_run",
    "read_probe.state=open",
    "status=completed",
    "conclusion=success",
    "head_sha_verified=true",
    "npm ci",
    "local user/runtime path findings",
    "manifest unsafe paths",
    "file hygiene findings",
    "candidate files for local user/runtime path findings",
    "release receipt freshness",
    "approval_request",
    "owner_env_template",
    "owner_gate_checklist",
    "missing_env_groups",
    "unresolved_env_names",
    "owner_gate_unresolved_env_names",
    "Replace owner env template placeholder values",
    "env_preflight",
    "Trigger the hosted Commercial RC Gate workflow",
    "generated_at",
    ".xagent_runtime/",
    "pip-audit",
    "Python vulnerability audit evidence",
    "python -m pip show pip-audit",
)

CHECKLIST_TOKENS = (
    "commercial release candidate, not a GA",
    "full competitor-parity claim",
    "RC final gate",
    "RC evidence pack",
    "--allow-missing-evidence-pack",
    "--owner-verified",
    "Final final gate remains strict",
    "RC refresh release chain",
    "RC owner gate runner",
    "RC owner handoff gate",
    "feishu_webhook_contract",
    "--gate github_issue_to_pr_dry_run",
    "must not require",
    "Deployment owner generates and stores final production secrets",
    "prohibited_secret_artifacts",
    "Final staged files match `docs/RC_STAGING_MANIFEST.md`",
    "Installer dry-runs use `npm ci`, not `npm install`",
    "local user/runtime path findings",
    "manifest unsafe paths",
    "tracked-secret, local user/runtime path, manifest unsafe paths,",
    "file hygiene scans",
    "release receipt freshness",
    "approval_request",
    "owner_env_template",
    "owner_gate_checklist",
    "missing_env_groups",
    "unresolved_env_names",
    "owner_gate_unresolved_env_names",
    "Replace owner env template placeholder values",
    "env_preflight",
    "Trigger the hosted Commercial RC Gate workflow",
    "XAGENT_COMMERCIAL_RC_GITHUB_ACTIONS_HEAD_SHA",
    "40-character hex git commit SHA",
    "head_sha_verified=true",
    "read_probe.state=open",
    "generated_at",
    "pip-audit",
    "Python vulnerability audit evidence",
    "python -m pip show pip-audit",
)

QUICKSTART_TOKENS = (
    "powershell -ExecutionPolicy Bypass -File scripts/install-xagent.ps1 -DryRun",
    "sh scripts/install-xagent.sh --dry-run",
    "python scripts/rc_owner_gate_runner.py --gate all --dry-run --env-file .xagent_runtime/reports/rc-owner-env-template.env",
    "python scripts/rc_runtime_smoke.py",
    "docs/COMMERCIAL_DEPLOYMENT_RUNBOOK.md",
)

RELEASE_NOTE_TOKENS = (
    "commercial release candidate, not GA",
    "scripts/rc_final_gate.py",
    "scripts/rc_evidence_pack.py",
    "--allow-missing-evidence-pack",
    "Final final gate remains strict",
    "ready_with_owner_gates",
    "This release does not claim full Codex",
    "docs/RC_STAGING_MANIFEST.md",
    "npm ci",
    "local user/runtime path findings",
    "local user/runtime path scanning",
    "manifest unsafe paths",
    "candidate file hygiene scanning",
    "release receipt freshness",
    "approval_request",
    "prohibited secret artifact paths",
    "owner_env_template",
    "owner_gate_checklist",
    "missing owner env groups",
    "unresolved_env_names",
    "owner_gate_unresolved_env_names",
    "Replace owner env template placeholder values",
    "env_preflight",
    "XAGENT_COMMERCIAL_RC_GITHUB_ACTIONS_HEAD_SHA",
    "40-character hex git commit SHA",
    "head_sha_verified=true",
    "generated_at",
    "pip-audit",
    "Python vulnerability audit evidence",
    "python -m pip show pip-audit",
)

FORBIDDEN_PARITY_CLAIM_TOKENS = (
    "full_parity_claimed=true",
    "full Codex/Hermes parity achieved",
    "complete Codex/Hermes parity",
    "Codex/Hermes parity is complete",
)

FORBIDDEN_RC_TAG_CLAIM_TOKENS = (
    "can_tag_rc_now=true",
    "ready_for_rc_tag",
    "ready to tag the RC now",
)


@dataclass(frozen=True)
class DeploymentDocsCheck:
    name: str
    status: str
    details: dict[str, Any] = field(default_factory=dict)
    error: str | None = None


@dataclass(frozen=True)
class DeploymentDocsGateReport:
    status: str
    generated_at: str
    docs: dict[str, str]
    checks: list[DeploymentDocsCheck]
    next_commands: list[str]

    def to_dict(self) -> dict[str, Any]:
        payload = asdict(self)
        payload["checks"] = [asdict(check) for check in self.checks]
        return payload


def _utc_now() -> str:
    return datetime.now(UTC).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _read_text(path: Path) -> tuple[str, str | None]:
    try:
        return path.read_text(encoding="utf-8"), None
    except FileNotFoundError:
        return "", f"missing document: {path}"
    except UnicodeDecodeError as exc:
        return "", f"document is not UTF-8 text: {exc}"


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


def _doc_token_check(name: str, text: str, error: str | None, tokens: tuple[str, ...]) -> DeploymentDocsCheck:
    problems: list[str] = []
    if error:
        problems.append(error)
    missing = [token for token in tokens if token not in text]
    if missing:
        problems.append(f"{name} missing required tokens: {', '.join(missing)}")
    return DeploymentDocsCheck(
        name=name,
        status="passed" if not problems else "failed",
        details={"missing_tokens": missing, "required_tokens": list(tokens)},
        error="; ".join(problems) if problems else None,
    )


def _find_forbidden_tokens(text: str, tokens: tuple[str, ...]) -> list[str]:
    matches: list[str] = []
    for token in tokens:
        token_lower = token.lower()
        for line in text.splitlines():
            if token_lower not in line.lower():
                continue
            normalized = line.lower().replace("`", "").replace('"', "").replace("'", "")
            if token_lower == "ready_for_rc_tag" and not _is_ready_for_rc_tag_claim(normalized):
                continue
            is_negated_boundary = any(
                marker in normalized
                for marker in (
                    f"not {token_lower}",
                    f"must not {token_lower}",
                    f"never {token_lower}",
                    f"does not {token_lower}",
                )
            )
            if not is_negated_boundary:
                matches.append(token)
                break
    return matches


def _is_ready_for_rc_tag_claim(normalized_line: str) -> bool:
    current_claim_markers = (
        "current final gate status",
        "current local final-gate status",
        "current local final gate",
        "current rc final gate status",
        "current rc final gate",
        "status ready_for_rc_tag",
        "status: ready_for_rc_tag",
        "status is ready_for_rc_tag",
        "status is now ready_for_rc_tag",
    )
    claim_markers = (
        *current_claim_markers,
        "final gate status is",
        "final rc gate status is",
        "final gate reports",
        "final rc gate reports",
        "reports ready_for_rc_tag",
        "report ready_for_rc_tag",
    )
    conditional_markers = (
        "after ",
        "once ",
        "when ",
        "only after ",
        "only ",
        "until ",
        "before ",
        "expected ",
        "target ",
    )
    token_index = normalized_line.find("ready_for_rc_tag")
    current_claim_before_token = any(
        (index := normalized_line.find(marker)) != -1 and index <= token_index
        for marker in current_claim_markers
    )
    stripped = normalized_line.strip().lstrip("-* ").strip()
    conditional_before_token = any(
        (index := normalized_line.find(marker)) != -1 and index < token_index
        for marker in conditional_markers
    )
    if any(marker in normalized_line for marker in claim_markers):
        if any(stripped.startswith(marker) for marker in conditional_markers):
            return False
        if conditional_before_token and not current_claim_before_token:
            return False
        return True
    if any(stripped.startswith(marker) for marker in conditional_markers):
        return False
    if conditional_before_token and not current_claim_before_token:
        return False
    return "ready_for_rc_tag" in normalized_line



def _owner_gate_docs_check(runbook: str, checklist: str, final_payload: dict[str, Any] | None) -> DeploymentDocsCheck:
    problems: list[str] = []
    owner_gates = final_payload.get("owner_gates") if isinstance(final_payload, dict) else []
    pending = [
        str(gate.get("name"))
        for gate in owner_gates
        if isinstance(gate, dict) and gate.get("status") != "verified" and gate.get("name")
    ]
    expected = sorted(dict.fromkeys([*OWNER_GATE_IDS, *pending]))
    for gate_id in expected:
        if gate_id not in runbook:
            problems.append(f"runbook missing owner gate id: {gate_id}")
        if gate_id not in checklist:
            problems.append(f"checklist missing owner gate id: {gate_id}")
    return DeploymentDocsCheck(
        name="owner_gate_docs",
        status="passed" if not problems else "failed",
        details={"pending_owner_gates": expected},
        error="; ".join(problems) if problems else None,
    )


def _overclaim_boundary_docs_check(
    runbook: str,
    checklist: str,
    notes: str,
    final_payload: dict[str, Any] | None,
) -> DeploymentDocsCheck:
    problems: list[str] = []
    decision = final_payload.get("release_decision") if isinstance(final_payload, dict) else {}
    if not isinstance(decision, dict):
        decision = {}
    full_parity_claimed = bool(final_payload.get("full_parity_claimed")) if isinstance(final_payload, dict) else False
    can_tag_rc_now = bool(decision.get("can_tag_rc_now"))
    forbidden_tokens: tuple[str, ...] = ()
    if not full_parity_claimed:
        forbidden_tokens = (*forbidden_tokens, *FORBIDDEN_PARITY_CLAIM_TOKENS)
    if not can_tag_rc_now:
        forbidden_tokens = (*forbidden_tokens, *FORBIDDEN_RC_TAG_CLAIM_TOKENS)

    matches: dict[str, list[str]] = {}
    for text_name, text in (("runbook", runbook), ("checklist", checklist), ("release_notes", notes)):
        found = _find_forbidden_tokens(text, forbidden_tokens)
        if found:
            matches[text_name] = found
            problems.append(f"{text_name} contains unsupported release claim tokens: {', '.join(found)}")

    return DeploymentDocsCheck(
        name="overclaim_boundary_docs",
        status="passed" if not problems else "failed",
        details={
            "full_parity_claimed": full_parity_claimed,
            "can_tag_rc_now": can_tag_rc_now,
            "forbidden_matches": matches,
        },
        error="; ".join(problems) if problems else None,
    )


def _release_state_docs_check(
    runbook: str,
    checklist: str,
    notes: str,
    final_payload: dict[str, Any] | None,
    final_error: str | None,
    *,
    allow_bootstrap_final_gate: bool = False,
) -> DeploymentDocsCheck:
    problems: list[str] = []
    details: dict[str, Any] = {}
    if final_error:
        if allow_bootstrap_final_gate:
            details["final_gate_bootstrap_allowed"] = True
            details["bootstrap_reason"] = final_error
        else:
            problems.append(final_error)
    if final_payload is not None:
        status = str(final_payload.get("status") or "")
        decision = final_payload.get("release_decision") if isinstance(final_payload.get("release_decision"), dict) else {}
        full_parity = bool(final_payload.get("full_parity_claimed"))
        bootstrap_blockers = _final_gate_bootstrap_blockers(final_payload)
        bootstrap_allowed = allow_bootstrap_final_gate and bool(bootstrap_blockers)
        details = {
            "final_status": status,
            "can_tag_rc_now": decision.get("can_tag_rc_now"),
            "full_parity_claimed": full_parity,
            "final_gate_bootstrap_allowed": bootstrap_allowed,
            "bootstrap_blockers": bootstrap_blockers,
        }
        if full_parity:
            problems.append("final gate claims full parity")
        if not bootstrap_allowed:
            for text_name, text in (("runbook", runbook), ("checklist", checklist), ("release_notes", notes)):
                if status and status not in text:
                    problems.append(f"{text_name} does not mention current final gate status {status}")
        for text_name, text in (("runbook", runbook), ("checklist", checklist), ("release_notes", notes)):
            if "full_parity_claimed=false" not in text and "does not claim full" not in text:
                problems.append(f"{text_name} does not preserve no-full-parity boundary")
    return DeploymentDocsCheck(
        name="release_state_docs",
        status="passed" if not problems else "failed",
        details=details,
        error="; ".join(problems) if problems else None,
    )


def _final_gate_bootstrap_blockers(final_payload: dict[str, Any]) -> list[str]:
    if final_payload.get("status") not in {"failed", "ready_with_receipt_refresh_required"}:
        return []
    local_gates = final_payload.get("local_gates")
    if not isinstance(local_gates, list):
        return []
    blockers: list[str] = []
    for gate in local_gates:
        if not isinstance(gate, dict):
            continue
        gate_name = str(gate.get("name") or "")
        gate_details = gate.get("details") if isinstance(gate.get("details"), dict) else {}
        if gate_name == "release_receipt" and gate_details.get("refresh_required") is True:
            blockers.append(gate_name)
        elif gate_name == "evidence_pack" and (
            gate_details.get("bootstrap_allowed") is True
            or "evidence pack" in str(gate.get("error") or "").lower()
            or "evidence_pack_freshness" in str(gate.get("error") or "").lower()
        ):
            blockers.append(gate_name)
        elif gate.get("ok") is not True:
            return []
    return sorted(dict.fromkeys(blockers))


def _artifact_handoff_check(
    runbook: str,
    checklist: str,
    notes: str,
    receipt_payload: dict[str, Any] | None,
    receipt_error: str | None,
    pack_payload: dict[str, Any] | None,
    pack_error: str | None,
    *,
    allow_missing_evidence_pack: bool = False,
) -> DeploymentDocsCheck:
    problems: list[str] = []
    details: dict[str, Any] = {}
    if receipt_error and not allow_missing_evidence_pack:
        problems.append(receipt_error)
    if pack_error and not allow_missing_evidence_pack:
        problems.append(pack_error)
    artifact = receipt_payload.get("artifact") if isinstance(receipt_payload, dict) else {}
    artifact_path = str((artifact or {}).get("path") or "")
    artifact_sha = str((artifact or {}).get("sha256") or "")
    pack_path = str((pack_payload or {}).get("output_path") or "")
    pack_sha = str((pack_payload or {}).get("pack_sha256") or "")
    details = {
        "artifact_path": artifact_path,
        "artifact_sha256_present": len(artifact_sha) == 64,
        "evidence_pack_path": pack_path,
        "evidence_pack_sha256_present": len(pack_sha) == 64,
        "release_receipt_bootstrap_allowed": allow_missing_evidence_pack
        and (bool(receipt_error) or not artifact_path or len(artifact_sha) != 64),
        "evidence_pack_bootstrap_allowed": allow_missing_evidence_pack
        and (bool(pack_error) or not pack_path or len(pack_sha) != 64),
    }
    if (not artifact_path or len(artifact_sha) != 64) and not allow_missing_evidence_pack:
        problems.append("release receipt artifact path/sha256 is incomplete")
    if (not pack_path or len(pack_sha) != 64) and not allow_missing_evidence_pack:
        problems.append("evidence pack output path/sha256 is incomplete")
    handoff_tokens = (
        "x-agent-commercial-rc-receipt.json",
        ".zip.sha256",
        "rc_evidence_pack.py",
        ".xagent_runtime/release/",
    )
    docs = {
        "runbook": runbook,
        "checklist": checklist,
        "release_notes": notes,
    }
    missing_by_doc: dict[str, list[str]] = {
        doc_name: [token for token in handoff_tokens if token not in text]
        for doc_name, text in docs.items()
    }
    for doc_name, missing in missing_by_doc.items():
        if missing:
            problems.append(f"{doc_name} missing artifact handoff tokens: {', '.join(missing)}")
    details["missing_tokens_by_doc"] = missing_by_doc
    return DeploymentDocsCheck(
        name="artifact_handoff_docs",
        status="passed" if not problems else "failed",
        details=details,
        error="; ".join(problems) if problems else None,
    )


def _staging_plan_docs_check(
    checklist: str,
    staging_payload: dict[str, Any] | None,
    staging_error: str | None,
) -> DeploymentDocsCheck:
    problems: list[str] = []
    details: dict[str, Any] = {}
    if staging_error:
        problems.append(staging_error)
    if staging_payload is not None:
        status = str(staging_payload.get("status") or "")
        file_count = staging_payload.get("file_count")
        command_count = staging_payload.get("command_count")
        details = {
            "status": status,
            "file_count": file_count,
            "command_count": command_count,
        }
        if status != "planned":
            problems.append(f"staging plan status is not planned: {status}")
        if not isinstance(file_count, int) or file_count <= 0:
            problems.append("staging plan file_count is missing or invalid")
        if not isinstance(command_count, int) or command_count <= 0:
            problems.append("staging plan command_count is missing or invalid")
        if isinstance(file_count, int) and f"planned {file_count} files" not in checklist:
            problems.append(f"checklist missing current staging file count: planned {file_count} files")
        if isinstance(command_count, int) and f"across {command_count} commands" not in checklist:
            problems.append(f"checklist missing current staging command count: across {command_count} commands")
    return DeploymentDocsCheck(
        name="staging_plan_docs",
        status="passed" if not problems else "failed",
        details=details,
        error="; ".join(problems) if problems else None,
    )


def build_deployment_docs_gate(
    *,
    runbook_path: Path = DEFAULT_RUNBOOK,
    checklist_path: Path = DEFAULT_CHECKLIST,
    install_quickstart_path: Path = DEFAULT_INSTALL_QUICKSTART,
    release_notes_path: Path = DEFAULT_RELEASE_NOTES,
    final_gate_path: Path = DEFAULT_FINAL_GATE,
    release_receipt_path: Path = DEFAULT_RELEASE_RECEIPT,
    evidence_pack_path: Path = DEFAULT_EVIDENCE_PACK,
    staging_plan_path: Path = DEFAULT_STAGING_PLAN,
    allow_missing_evidence_pack: bool = False,
) -> DeploymentDocsGateReport:
    runbook, runbook_error = _read_text(runbook_path)
    checklist, checklist_error = _read_text(checklist_path)
    quickstart, quickstart_error = _read_text(install_quickstart_path)
    notes, notes_error = _read_text(release_notes_path)
    final_payload, final_error = _read_json(final_gate_path)
    receipt_payload, receipt_error = _read_json(release_receipt_path)
    pack_payload, pack_error = _read_json(evidence_pack_path)
    staging_payload, staging_error = _read_json(staging_plan_path)

    checks = [
        _doc_token_check("runbook_document", runbook, runbook_error, RUNBOOK_TOKENS),
        _doc_token_check("checklist_document", checklist, checklist_error, CHECKLIST_TOKENS),
        _doc_token_check("install_quickstart", quickstart, quickstart_error, QUICKSTART_TOKENS),
        _doc_token_check("release_notes", notes, notes_error, RELEASE_NOTE_TOKENS),
        _owner_gate_docs_check(runbook, checklist, final_payload),
        _release_state_docs_check(
            runbook,
            checklist,
            notes,
            final_payload,
            final_error,
            allow_bootstrap_final_gate=allow_missing_evidence_pack,
        ),
        _overclaim_boundary_docs_check(runbook, checklist, notes, final_payload),
        _staging_plan_docs_check(checklist, staging_payload, staging_error),
        _artifact_handoff_check(
            runbook,
            checklist,
            notes,
            receipt_payload,
            receipt_error,
            pack_payload,
            pack_error,
            allow_missing_evidence_pack=allow_missing_evidence_pack,
        ),
    ]
    status = "passed" if all(check.status == "passed" for check in checks) else "failed"
    return DeploymentDocsGateReport(
        status=status,
        generated_at=_utc_now(),
        docs={
            "runbook": str(runbook_path),
            "checklist": str(checklist_path),
            "install_quickstart": str(install_quickstart_path),
            "release_notes": str(release_notes_path),
            "staging_plan": str(staging_plan_path),
        },
        checks=checks,
        next_commands=[
            "Refresh deployment docs after owner gates, final gate, receipt, or evidence pack changes.",
            "Run python scripts\\rc_deployment_docs_gate.py before rc_final_gate.py.",
            "Do not tag the RC until rc_final_gate.py --require-ready-to-tag passes.",
        ],
    )


def write_report(report: DeploymentDocsGateReport, output_path: Path) -> None:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(report.to_dict(), ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Validate X-Agent commercial RC deployment docs")
    parser.add_argument("--runbook", type=Path, default=DEFAULT_RUNBOOK)
    parser.add_argument("--checklist", type=Path, default=DEFAULT_CHECKLIST)
    parser.add_argument("--install-quickstart", type=Path, default=DEFAULT_INSTALL_QUICKSTART)
    parser.add_argument("--release-notes", type=Path, default=DEFAULT_RELEASE_NOTES)
    parser.add_argument("--final-gate", type=Path, default=DEFAULT_FINAL_GATE)
    parser.add_argument("--release-receipt", type=Path, default=DEFAULT_RELEASE_RECEIPT)
    parser.add_argument("--evidence-pack", type=Path, default=DEFAULT_EVIDENCE_PACK)
    parser.add_argument("--staging-plan", type=Path, default=DEFAULT_STAGING_PLAN)
    parser.add_argument(
        "--allow-missing-evidence-pack",
        action="store_true",
        help="bootstrap mode for refresh chains; default docs gate remains strict",
    )
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    report = build_deployment_docs_gate(
        runbook_path=args.runbook,
        checklist_path=args.checklist,
        install_quickstart_path=args.install_quickstart,
        release_notes_path=args.release_notes,
        final_gate_path=args.final_gate,
        release_receipt_path=args.release_receipt,
        evidence_pack_path=args.evidence_pack,
        staging_plan_path=args.staging_plan,
        allow_missing_evidence_pack=args.allow_missing_evidence_pack,
    )
    write_report(report, args.output)
    print(f"RC deployment docs gate status: {report.status}")
    print(f"Report written to {args.output}")
    for check in report.checks:
        print(f"- {check.name}: {check.status}")
        if check.error:
            print(f"  error: {check.error}")
    return 0 if report.status == "passed" else 1


if __name__ == "__main__":
    raise SystemExit(main())
