#!/usr/bin/env python3
"""Render a short no-secret Stage3 owner/operator quickstart.

This report intentionally does not replace the full owner todo. It summarizes
the minimum next actions a non-expert owner/operator should take before the
Stage3 evidence intake can become real evidence.
"""

from __future__ import annotations

import argparse
import json
from dataclasses import asdict, dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from scripts.stage3_owner_evidence_todo import DEFAULT_OUTPUT_JSON as DEFAULT_TODO_JSON
from scripts.stage3_owner_domain_guide import DEFAULT_OUTPUT_JSON as DEFAULT_DOMAIN_GUIDE_JSON
from scripts.stage3_https_preflight import ROOT, _display_path

REPORT_DIR = ROOT / ".xagent_runtime" / "reports"
DEFAULT_OUTPUT_JSON = REPORT_DIR / "stage3-owner-quickstart-20260618.json"
DEFAULT_OUTPUT_MD = REPORT_DIR / "stage3-owner-quickstart-20260618.md"
PLACEHOLDER_DOMAIN = "<REAL_DOMAIN>"
EXAMPLE_DOMAINS = ("example.com", "example.net", "example.org")


@dataclass(frozen=True)
class Stage3OwnerQuickstartStep:
    order: int
    title: str
    owner: str
    action: str
    evidence_to_capture: list[str] = field(default_factory=list)
    done_when: str = ""


@dataclass(frozen=True)
class Stage3OwnerQuickstartReport:
    status: str
    generated_at: str
    todo_input_path: str
    domain_guide_path: str | None
    todo_count: int
    release_sha: str
    mutation_performed: bool
    deploy_performed: bool
    workflow_dispatch_performed: bool
    raw_secret_values_recorded: bool
    steps: list[Stage3OwnerQuickstartStep]
    blocked_until: list[str]
    next_commands: list[str]

    def to_dict(self) -> dict[str, Any]:
        payload = asdict(self)
        payload["steps"] = [asdict(step) for step in self.steps]
        return payload


def _utc_now() -> str:
    return datetime.now(UTC).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _read_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def _optional_domain(payload: dict[str, Any] | None) -> str:
    if not payload:
        return PLACEHOLDER_DOMAIN
    domain = payload.get("domain")
    if isinstance(domain, str) and domain:
        normalized = domain.strip().lower().rstrip(".")
        if normalized.endswith(EXAMPLE_DOMAINS):
            return PLACEHOLDER_DOMAIN
        return domain
    return PLACEHOLDER_DOMAIN


def build_stage3_owner_quickstart(
    *,
    todo_json: Path = DEFAULT_TODO_JSON,
    domain_guide_json: Path | None = DEFAULT_DOMAIN_GUIDE_JSON,
) -> Stage3OwnerQuickstartReport:
    todo_payload = _read_json(todo_json)
    domain_payload: dict[str, Any] | None = None
    if domain_guide_json is not None and domain_guide_json.exists():
        domain_payload = _read_json(domain_guide_json)

    domain = _optional_domain(domain_payload)
    todo_count = int(todo_payload.get("todo_count") or 0)
    release_sha = str(todo_payload.get("release_sha") or "<OWNER_VERIFIED_HEAD_SHA>")

    steps = [
        Stage3OwnerQuickstartStep(
            order=1,
            title="Choose a real domain",
            owner="owner/operator",
            action=f"Use a domain you control and point its DNS A record to 111.228.49.160. Do not use sslip.io, localhost, or a bare IP.",
            evidence_to_capture=["DNS provider record reference showing the A record."],
            done_when=f"`https://{domain}` is the intended public Stage3 base URL.",
        ),
        Stage3OwnerQuickstartStep(
            order=2,
            title="Enable trusted HTTPS",
            owner="operator",
            action="Configure Nginx to proxy the domain to the running Stage3 service and issue a trusted certificate on port 443.",
            evidence_to_capture=["Nginx config path plus `nginx -t`/reload output reference.", "Certificate issuer or certbot output reference."],
            done_when=f"`https://{domain}/health` and `https://{domain}/ready` are reachable without TLS warnings.",
        ),
        Stage3OwnerQuickstartStep(
            order=3,
            title="Run read-only preflight",
            owner="Codex/operator",
            action=f'Run `python scripts/stage3_https_preflight.py --domain "{domain}"` after DNS and HTTPS work.',
            evidence_to_capture=["`.xagent_runtime/reports/stage3-https-preflight-20260618.json` when it reports ready."],
            done_when="The preflight report status is `stage3_https_preflight_ready`.",
        ),
        Stage3OwnerQuickstartStep(
            order=4,
            title="Fill references, not secrets",
            owner="owner/operator + Codex",
            action="Use the full owner todo Markdown to replace placeholders with links, run IDs, image refs, timestamps, and secret variable names only.",
            evidence_to_capture=[_display_path(todo_json), "Deploy, smoke, rollback, observability, environment-protection, and owner approval refs."],
            done_when=f"`template_not_external_evidence=false` only after all {todo_count} todo items are resolved and reviewed.",
        ),
        Stage3OwnerQuickstartStep(
            order=5,
            title="Run Stage3 intake and rehearsal",
            owner="Codex/operator",
            action="Rerun the Stage3 external evidence intake, then run `scripts/commercial_environment_rehearsal_gate.py --environment staging` for the owner-verified release SHA.",
            evidence_to_capture=["Five ready Stage3 evidence reports for deploy, smoke, rollback, observability, and environment protection."],
            done_when="The rehearsal report status is `staging_rehearsal_ready` for the selected release SHA.",
        ),
        Stage3OwnerQuickstartStep(
            order=6,
            title="Run strict final gate",
            owner="Codex",
            action="Run `python scripts/rc_final_gate.py --require-ready-to-tag --require-stage3-rehearsal`.",
            evidence_to_capture=["`.xagent_runtime/reports/rc-final-gate-stage3-rehearsal-check.json`."],
            done_when="The strict final gate status is `ready_for_rc_tag`.",
        ),
    ]

    blocked_until = [
        "real owner-controlled DNS is configured",
        "trusted HTTPS/443 serves `/health` and `/ready`",
        "deploy/smoke/rollback/observability/environment-protection refs are filled",
        "the owner draft contains references only and no raw secret values",
        "strict final gate passes with Stage3 rehearsal required",
    ]
    next_commands = [
        'python scripts/stage3_owner_domain_guide.py --domain "<REAL_DOMAIN>"',
        'python scripts/stage3_https_preflight.py --domain "<REAL_DOMAIN>"',
        "python scripts/stage3_owner_evidence_todo.py",
        "python scripts/rc_final_gate.py --require-ready-to-tag --require-stage3-rehearsal",
    ]

    return Stage3OwnerQuickstartReport(
        status="stage3_owner_quickstart_ready",
        generated_at=_utc_now(),
        todo_input_path=_display_path(todo_json),
        domain_guide_path=_display_path(domain_guide_json) if domain_guide_json else None,
        todo_count=todo_count,
        release_sha=release_sha,
        mutation_performed=False,
        deploy_performed=False,
        workflow_dispatch_performed=False,
        raw_secret_values_recorded=False,
        steps=steps,
        blocked_until=blocked_until,
        next_commands=next_commands,
    )


def render_markdown_report(report: Stage3OwnerQuickstartReport) -> str:
    lines = [
        "# Stage3 Owner Quickstart",
        "",
        f"- Status: `{report.status}`",
        f"- Todo input: `{report.todo_input_path}`",
        f"- Domain guide: `{report.domain_guide_path or 'not provided'}`",
        f"- Release SHA: `{report.release_sha}`",
        f"- Remaining todo count: `{report.todo_count}`",
        f"- Mutation performed: `{report.mutation_performed}`",
        f"- Deploy performed: `{report.deploy_performed}`",
        f"- Workflow dispatch performed: `{report.workflow_dispatch_performed}`",
        f"- Raw secret values recorded: `{report.raw_secret_values_recorded}`",
        "",
        "## Six Steps",
        "",
    ]
    for step in report.steps:
        lines.extend(
            [
                f"### {step.order}. {step.title}",
                "",
                f"- Owner: `{step.owner}`",
                f"- Action: {step.action}",
                f"- Done when: {step.done_when}",
                "- Evidence to capture:",
                *[f"  - {item}" for item in step.evidence_to_capture],
                "",
            ]
        )
    lines.extend(["## Still Blocked Until", ""])
    lines.extend(f"- {item}" for item in report.blocked_until)
    lines.extend(["", "## Next Commands", ""])
    lines.extend(f"- `{command}`" for command in report.next_commands)
    lines.append("")
    return "\n".join(lines)


def write_reports(
    report: Stage3OwnerQuickstartReport,
    *,
    output_json: Path = DEFAULT_OUTPUT_JSON,
    output_md: Path = DEFAULT_OUTPUT_MD,
) -> None:
    output_json.parent.mkdir(parents=True, exist_ok=True)
    output_md.parent.mkdir(parents=True, exist_ok=True)
    output_json.write_text(json.dumps(report.to_dict(), ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    output_md.write_text(render_markdown_report(report), encoding="utf-8")


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Render a short no-secret Stage3 owner/operator quickstart.")
    parser.add_argument("--todo-json", type=Path, default=DEFAULT_TODO_JSON)
    parser.add_argument("--domain-guide-json", type=Path, default=DEFAULT_DOMAIN_GUIDE_JSON)
    parser.add_argument("--output-json", type=Path, default=DEFAULT_OUTPUT_JSON)
    parser.add_argument("--output-md", type=Path, default=DEFAULT_OUTPUT_MD)
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    report = build_stage3_owner_quickstart(
        todo_json=args.todo_json,
        domain_guide_json=args.domain_guide_json,
    )
    write_reports(report, output_json=args.output_json, output_md=args.output_md)
    print(f"Stage3 owner quickstart status: {report.status}")
    print(f"Todo count: {report.todo_count}")
    print(f"JSON quickstart written to {_display_path(args.output_json)}")
    print(f"Markdown quickstart written to {_display_path(args.output_md)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
