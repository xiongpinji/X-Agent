#!/usr/bin/env python3
"""Render a no-secret todo list from the Stage3 owner evidence draft.

The Stage3 owner draft is intentionally a blocked template until every
placeholder is replaced by real owner-approved references. This helper makes
that template easier to fill by extracting the remaining fields into a
human-readable checklist. It is read-only: it never edits the draft, deploys,
dispatches workflows, or records secret values.
"""

from __future__ import annotations

import argparse
import json
from dataclasses import asdict, dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Mapping, Sequence

from scripts.commercial_stage3_staging_external_evidence_intake import (
    EXTERNAL_ENVIRONMENT_REQUIRED_FIELDS,
    OBSERVABILITY_REQUIRED_FIELDS,
    PROTECTION_REQUIRED_FIELDS,
)
from scripts.stage3_https_preflight import ROOT, _display_path

REPORT_DIR = ROOT / ".xagent_runtime" / "reports"
DEFAULT_INPUT = REPORT_DIR / "stage3-staging-external-evidence-owner-draft-20260616.json"
DEFAULT_OUTPUT_JSON = REPORT_DIR / "stage3-owner-evidence-todo-20260618.json"
DEFAULT_OUTPUT_MD = REPORT_DIR / "stage3-owner-evidence-todo-20260618.md"

SECTION_FIELDS: dict[str, tuple[str, ...]] = {
    "staging_deploy_run": EXTERNAL_ENVIRONMENT_REQUIRED_FIELDS["staging_deploy_run"],
    "staging_smoke_tests": EXTERNAL_ENVIRONMENT_REQUIRED_FIELDS["staging_smoke_tests"],
    "staging_rollback_rehearsal": EXTERNAL_ENVIRONMENT_REQUIRED_FIELDS["staging_rollback_rehearsal"],
    "staging_observability": OBSERVABILITY_REQUIRED_FIELDS,
    "staging_environment_protection": PROTECTION_REQUIRED_FIELDS,
}

OWNER_DECISION_FIELDS = {
    "staging_observability.alerting.alert_ref",
    "staging_environment_protection.owner_approval.owner",
    "staging_environment_protection.owner_approval.approval_ref",
    "staging_environment_protection.owner_approval.approved_at",
}
CODEX_PREFILL_FIELDS = {
    "staging_environment_protection.external_endpoint.health_ref",
    "staging_environment_protection.external_endpoint.ready_ref",
    "staging_environment_protection.dns_tls.dns_ref",
    "staging_environment_protection.dns_tls.tls_ref",
}
FINAL_TOGGLE_FIELDS = {
    "template_not_external_evidence",
    "staging_environment_protection.secret_binding.redaction_confirmed",
    "staging_environment_protection.deployed_image.not_external_deploy_proof",
}


@dataclass(frozen=True)
class Stage3OwnerTodoItem:
    field: str
    section: str
    category: str
    current_value_kind: str
    instruction: str


@dataclass(frozen=True)
class Stage3OwnerEvidenceTodoReport:
    status: str
    generated_at: str
    input_path: str
    mutation_performed: bool
    deploy_performed: bool
    workflow_dispatch_performed: bool
    raw_secret_values_recorded: bool
    release_sha: str | None
    current_head_sha: str | None
    template_not_external_evidence: bool
    todo_count: int
    items: list[Stage3OwnerTodoItem] = field(default_factory=list)
    blocked_reasons: list[str] = field(default_factory=list)
    next_commands: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        payload = asdict(self)
        payload["items"] = [asdict(item) for item in self.items]
        return payload


def _utc_now() -> str:
    return datetime.now(UTC).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _nested_get(payload: Mapping[str, Any], dotted_path: str) -> Any:
    value: Any = payload
    for part in dotted_path.split("."):
        if not isinstance(value, Mapping) or part not in value:
            return None
        value = value[part]
    return value


def _value_kind(value: Any) -> str:
    if value is None:
        return "missing"
    if isinstance(value, bool):
        return f"boolean:{str(value).lower()}"
    if isinstance(value, str):
        stripped = value.strip()
        if not stripped:
            return "empty"
        if stripped.startswith("<") and stripped.endswith(">"):
            return "placeholder"
        if "PLACEHOLDER" in stripped.upper():
            return "placeholder"
        return "reference"
    if isinstance(value, Sequence) and not isinstance(value, (str, bytes, bytearray)):
        return "empty_list" if len(value) == 0 else "list"
    return type(value).__name__


def _category(field: str) -> str:
    if field in FINAL_TOGGLE_FIELDS:
        return "final_toggle"
    if field in CODEX_PREFILL_FIELDS:
        return "codex_prefill"
    if field in OWNER_DECISION_FIELDS:
        return "owner_decision"
    if "secret_binding" in field:
        return "owner_secret_ref"
    return "operator_ref"


def _instruction(field: str, category: str) -> str:
    if category == "final_toggle":
        if field == "template_not_external_evidence":
            return "Set to false only after every placeholder has a real external reference."
        if field.endswith("redaction_confirmed"):
            return "Set to true only after the draft contains variable names or secret-manager refs, never secret values."
        return "Set to false only after the image ref/digest comes from the running Stage3 environment."
    if category == "codex_prefill":
        return "Can be prefilled from a ready stage3_https_preflight.py report after real DNS/TLS exists."
    if category == "owner_decision":
        return "Owner must provide or approve this reference explicitly."
    if category == "owner_secret_ref":
        return "Use secret variable names or secret-manager references only; do not paste secret values."
    if field.endswith("checks"):
        return "Replace blocked template checks with passed external command/check references."
    return "Replace with a redaction-safe external evidence reference."


def _friendly_label(field: str) -> str:
    labels = {
        "template_not_external_evidence": "Final switch: mark the draft as real external evidence only after every item below is done",
        "staging_deploy_run.deploy_ref": "External Stage3 deploy run reference",
        "staging_deploy_run.image_ref": "Image reference used by the external Stage3 deploy",
        "staging_deploy_run.operator": "Operator name for the external Stage3 deploy",
        "staging_deploy_run.completed_at": "UTC completion time for the external Stage3 deploy",
        "staging_smoke_tests.health_ref": "HTTPS /health proof on the real domain",
        "staging_smoke_tests.ready_ref": "HTTPS /ready proof on the real domain",
        "staging_smoke_tests.smoke_ref": "External Stage3 smoke-test run reference",
        "staging_smoke_tests.operator": "Operator name for the external smoke test",
        "staging_smoke_tests.completed_at": "UTC completion time for the external smoke test",
        "staging_rollback_rehearsal.rollback_ref": "External rollback rehearsal reference",
        "staging_rollback_rehearsal.post_rollback_health_ref": "Post-rollback HTTPS /health proof",
        "staging_rollback_rehearsal.post_rollback_ready_ref": "Post-rollback HTTPS /ready proof",
        "staging_rollback_rehearsal.operator": "Operator name for the rollback rehearsal",
        "staging_rollback_rehearsal.completed_at": "UTC completion time for the rollback rehearsal",
        "staging_observability.workflow_event_broker.health_ref": "Workflow/event broker health proof or accepted first-RC reference",
        "staging_observability.langfuse.trace_ref": "Langfuse trace reference or accepted first-RC exception",
        "staging_observability.sentry.event_ref": "Sentry event/project reference or accepted first-RC exception",
        "staging_observability.metrics.metrics_ref": "Metrics dashboard or command-output reference",
        "staging_observability.alerting.alert_ref": "Alerting rule reference or owner-approved first-RC exception",
        "staging_environment_protection.external_endpoint.health_ref": "Codex-prefilled HTTPS /health ref after real DNS/TLS passes",
        "staging_environment_protection.external_endpoint.ready_ref": "Codex-prefilled HTTPS /ready ref after real DNS/TLS passes",
        "staging_environment_protection.external_endpoint.ingress_ref": "Nginx site path plus nginx -t/reload proof",
        "staging_environment_protection.dns_tls.dns_ref": "Codex-prefilled DNS A-record proof after real DNS exists",
        "staging_environment_protection.dns_tls.tls_ref": "Codex-prefilled trusted TLS/certificate proof after real TLS exists",
        "staging_environment_protection.secret_binding.secret_refs": "Secret variable names or secret-manager references only",
        "staging_environment_protection.secret_binding.redaction_confirmed": "Final switch: confirm the draft has references only and no secret values",
        "staging_environment_protection.deployed_image.image_ref": "Running Stage3 image reference",
        "staging_environment_protection.deployed_image.digest": "Running Stage3 image digest",
        "staging_environment_protection.owner_approval.approval_ref": "Owner approval reference for this exact release SHA",
        "staging_environment_protection.owner_approval.approved_at": "UTC owner approval time",
        "staging_environment_protection.deployed_image.not_external_deploy_proof": "Final switch: image proof came from the running Stage3 environment",
    }
    return labels.get(field, field)


def _group_title(category: str) -> str:
    titles = {
        "owner_decision": "Owner Decisions You Must Approve",
        "operator_ref": "Operator Evidence To Capture",
        "codex_prefill": "Codex Can Prefill After Real DNS/TLS",
        "owner_secret_ref": "Secret References Only",
        "final_toggle": "Final Switches After Review",
    }
    return titles.get(category, category)


def _group_hint(category: str) -> str:
    hints = {
        "owner_decision": "Choose or approve these references. Do not paste secrets.",
        "operator_ref": "These are links, command-output references, run IDs, timestamps, or image refs from the real Stage3 environment.",
        "codex_prefill": "After a real domain and trusted HTTPS work, Codex can fill these from stage3_https_preflight.py output.",
        "owner_secret_ref": "Use variable names or secret-manager paths only. Never paste token, key, password, private key, cookie, or DSN values.",
        "final_toggle": "Change these only after every reference is real and reviewed.",
    }
    return hints.get(category, "Replace placeholders with redaction-safe references.")


def _render_grouped_items(report: Stage3OwnerEvidenceTodoReport) -> str:
    if not report.items:
        return "- No remaining owner/operator actions detected."
    categories = ("owner_decision", "operator_ref", "codex_prefill", "owner_secret_ref", "final_toggle")
    sections: list[str] = []
    for category in categories:
        items = [item for item in report.items if item.category == category]
        if not items:
            continue
        lines = [
            f"### {_group_title(category)}",
            "",
            _group_hint(category),
            "",
        ]
        lines.extend(
            f"- {_friendly_label(item.field)}\n  - Field: `{item.field}`\n  - Current: `{item.current_value_kind}`\n  - Action: {item.instruction}"
            for item in items
        )
        sections.append("\n".join(lines))
    return "\n\n".join(sections)


def _field_needs_action(payload: Mapping[str, Any], field: str) -> bool:
    if field == "template_not_external_evidence":
        return payload.get("template_not_external_evidence") is not False
    value = _nested_get(payload, field)
    kind = _value_kind(value)
    if field == "staging_observability.workflow_event_broker.broker_kind":
        return kind in {"missing", "empty", "empty_list"}
    if field == "staging_environment_protection.secret_binding.secret_refs":
        return (
            kind in {"missing", "empty", "placeholder", "empty_list"}
            or _nested_get(payload, "staging_environment_protection.secret_binding.redaction_confirmed") is not True
        )
    if field.endswith("redaction_confirmed"):
        return value is not True
    if field.endswith("not_external_deploy_proof"):
        return value is not False
    if field.endswith("checks"):
        return not _checks_all_passed(value)
    return kind in {"missing", "empty", "placeholder", "empty_list"}


def _checks_all_passed(value: Any) -> bool:
    if not isinstance(value, Sequence) or isinstance(value, (str, bytes, bytearray)) or not value:
        return False
    for item in value:
        if not isinstance(item, Mapping) or item.get("status") != "passed":
            return False
    return True


def build_stage3_owner_evidence_todo(input_path: Path = DEFAULT_INPUT) -> Stage3OwnerEvidenceTodoReport:
    blocked_reasons: list[str] = []
    try:
        payload = json.loads(input_path.read_text(encoding="utf-8"))
    except FileNotFoundError:
        payload = {}
        blocked_reasons.append(f"input draft is missing: {_display_path(input_path)}")
    except json.JSONDecodeError as exc:
        payload = {}
        blocked_reasons.append(f"input draft is invalid JSON: {exc}")
    if not isinstance(payload, Mapping):
        payload = {}
        blocked_reasons.append("input draft is not a JSON object")

    fields: list[str] = ["template_not_external_evidence"]
    for section, required_fields in SECTION_FIELDS.items():
        fields.extend(f"{section}.{field_name}" for field_name in required_fields)
    fields.extend(
        [
            "staging_environment_protection.deployed_image.not_external_deploy_proof",
        ]
    )

    items: list[Stage3OwnerTodoItem] = []
    for field_name in dict.fromkeys(fields):
        if not _field_needs_action(payload, field_name):
            continue
        category = _category(field_name)
        section = field_name.split(".", 1)[0]
        items.append(
            Stage3OwnerTodoItem(
                field=field_name,
                section=section,
                category=category,
                current_value_kind=_value_kind(_nested_get(payload, field_name)),
                instruction=_instruction(field_name, category),
            )
        )

    if payload.get("template_not_external_evidence") is True:
        blocked_reasons.append("draft is still marked template_not_external_evidence=true")
    if items:
        blocked_reasons.append(f"{len(items)} fields still need real external references or final toggles")

    return Stage3OwnerEvidenceTodoReport(
        status="stage3_owner_evidence_todo_ready" if items else "stage3_owner_evidence_todo_clear",
        generated_at=_utc_now(),
        input_path=_display_path(input_path),
        mutation_performed=False,
        deploy_performed=False,
        workflow_dispatch_performed=False,
        raw_secret_values_recorded=False,
        release_sha=payload.get("release_sha") if isinstance(payload.get("release_sha"), str) else None,
        current_head_sha=payload.get("current_head_sha") if isinstance(payload.get("current_head_sha"), str) else None,
        template_not_external_evidence=payload.get("template_not_external_evidence") is True,
        todo_count=len(items),
        items=items,
        blocked_reasons=blocked_reasons,
        next_commands=[
            "Fill the owner draft with real external references only.",
            "Rerun commercial_stage3_staging_external_evidence_intake.py after all todo items are resolved.",
            "Rerun commercial_environment_rehearsal_gate.py and strict rc_final_gate.py only after intake is ready.",
        ],
    )


def render_markdown_report(report: Stage3OwnerEvidenceTodoReport) -> str:
    items = "\n".join(
        f"- `{item.field}` ({item.category}, {item.current_value_kind}): {item.instruction}"
        for item in report.items
    ) or "- No remaining todo items detected."
    grouped_items = _render_grouped_items(report)
    reasons = "\n".join(f"- {reason}" for reason in report.blocked_reasons) or "- None"
    commands = "\n".join(f"- `{command}`" for command in report.next_commands)
    return (
        "# Stage3 Owner Evidence Todo\n\n"
        f"- Status: `{report.status}`\n"
        f"- Input: `{report.input_path}`\n"
        f"- Release SHA: `{report.release_sha or '<missing>'}`\n"
        f"- Current HEAD SHA: `{report.current_head_sha or '<missing>'}`\n"
        f"- Template flag still set: `{report.template_not_external_evidence}`\n"
        f"- Todo count: `{report.todo_count}`\n"
        f"- Mutation performed: `{report.mutation_performed}`\n"
        f"- Deploy performed: `{report.deploy_performed}`\n"
        f"- Workflow dispatch performed: `{report.workflow_dispatch_performed}`\n"
        f"- Raw secret values recorded: `{report.raw_secret_values_recorded}`\n\n"
        "## What To Do Next\n\n"
        "1. Do not edit secret values into any file. Use variable names, secret-manager references, links, run IDs, or command-output references only.\n"
        "2. Handle the grouped items below. Codex can help with the `codex_prefill` and most `operator_ref` items after a real domain and trusted HTTPS are available.\n"
        "3. Change the final switches only after every item is filled and reviewed.\n\n"
        "## Grouped Todo\n\n"
        f"{grouped_items}\n\n"
        "## Field Detail\n\n"
        f"{items}\n\n"
        "## Blocked Reasons\n\n"
        f"{reasons}\n\n"
        "## Next Commands\n\n"
        f"{commands}\n"
    )


def write_reports(
    report: Stage3OwnerEvidenceTodoReport,
    *,
    output_json: Path = DEFAULT_OUTPUT_JSON,
    output_md: Path = DEFAULT_OUTPUT_MD,
) -> None:
    output_json.parent.mkdir(parents=True, exist_ok=True)
    output_json.write_text(json.dumps(report.to_dict(), ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    output_md.parent.mkdir(parents=True, exist_ok=True)
    output_md.write_text(render_markdown_report(report), encoding="utf-8")


def parse_args(argv: Sequence[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Render remaining no-secret todos from the Stage3 owner evidence draft.")
    parser.add_argument("--input-json", type=Path, default=DEFAULT_INPUT)
    parser.add_argument("--output-json", type=Path, default=DEFAULT_OUTPUT_JSON)
    parser.add_argument("--output-md", type=Path, default=DEFAULT_OUTPUT_MD)
    return parser.parse_args(argv)


def main(argv: Sequence[str] | None = None) -> int:
    args = parse_args(argv)
    report = build_stage3_owner_evidence_todo(args.input_json)
    write_reports(report, output_json=args.output_json, output_md=args.output_md)
    print(f"Stage3 owner evidence todo status: {report.status}")
    print(f"Todo count: {report.todo_count}")
    print(f"JSON todo written to {_display_path(args.output_json)}")
    print(f"Markdown todo written to {_display_path(args.output_md)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
