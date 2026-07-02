#!/usr/bin/env python3
"""Generate a redaction-safe owner guide for Stage3 domain/TLS evidence.

This helper is intentionally read-only. It does not change DNS, SSH to the
server, edit Nginx, request certificates, dispatch workflows, deploy images, or
record secret values. It only writes a JSON/Markdown checklist that the
owner/operator can follow after choosing a real domain.
"""

from __future__ import annotations

import argparse
import json
from dataclasses import asdict, dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Sequence

from scripts.stage3_https_preflight import (
    DEFAULT_EXPECTED_IP,
    ROOT,
    _display_path,
    _domain_validation_errors,
    _normalize_domain,
)

REPORT_DIR = ROOT / ".xagent_runtime" / "reports"
DEFAULT_OUTPUT_JSON = REPORT_DIR / "stage3-owner-domain-guide-20260618.json"
DEFAULT_OUTPUT_MD = REPORT_DIR / "stage3-owner-domain-guide-20260618.md"
DEFAULT_EXTERNAL_SMOKE_REPORT = REPORT_DIR / "rc-external-smoke.json"
DEFAULT_RELEASE_SHA_PLACEHOLDER = "<OWNER_VERIFIED_HEAD_SHA>"


@dataclass(frozen=True)
class Stage3OwnerGuideCheck:
    name: str
    status: str
    details: dict[str, Any] = field(default_factory=dict)
    error: str | None = None


@dataclass(frozen=True)
class Stage3OwnerDomainGuide:
    status: str
    generated_at: str
    domain: str
    expected_ip: str
    release_sha: str
    release_sha_source: str
    mutation_performed: bool
    deploy_performed: bool
    workflow_dispatch_performed: bool
    raw_secret_values_recorded: bool
    checks: list[Stage3OwnerGuideCheck]
    owner_decisions: list[str]
    operator_steps: list[str]
    server_commands: list[str]
    local_validation_commands: list[str]
    evidence_refs_to_collect: list[str]
    known_limits: list[str]

    def to_dict(self) -> dict[str, Any]:
        payload = asdict(self)
        payload["checks"] = [asdict(check) for check in self.checks]
        return payload


def _utc_now() -> str:
    return datetime.now(UTC).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _check(name: str, passed: bool, *, details: dict[str, Any] | None = None, error: str | None = None) -> Stage3OwnerGuideCheck:
    return Stage3OwnerGuideCheck(
        name=name,
        status="passed" if passed else "failed",
        details=details or {},
        error=None if passed else error,
    )


def _validated_release_sha_from_external_smoke(path: Path = DEFAULT_EXTERNAL_SMOKE_REPORT) -> tuple[str | None, str]:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError:
        return None, f"external smoke report missing: {_display_path(path)}"
    except json.JSONDecodeError as exc:
        return None, f"external smoke report invalid JSON: {exc}"
    checks = payload.get("checks") if isinstance(payload, dict) else None
    if not isinstance(checks, list):
        return None, "external smoke report checks are missing"
    for check in checks:
        if not isinstance(check, dict) or check.get("name") != "hosted_github_actions_run":
            continue
        details = check.get("details") if isinstance(check.get("details"), dict) else {}
        head_sha = details.get("head_sha")
        expected_head_sha = details.get("expected_head_sha")
        if (
            check.get("status") == "passed"
            and details.get("head_sha_verified") is True
            and isinstance(head_sha, str)
            and len(head_sha) == 40
            and all(char in "0123456789abcdef" for char in head_sha.lower())
            and (not isinstance(expected_head_sha, str) or expected_head_sha == head_sha)
        ):
            return head_sha, f"{_display_path(path)} hosted_github_actions_run.head_sha"
        return None, "hosted_github_actions_run is present but head_sha is not verified"
    return None, "hosted_github_actions_run check is missing"


def _nginx_config(domain: str) -> str:
    return (
        "server {\n"
        "  listen 80;\n"
        f"  server_name {domain};\n\n"
        "  location / {\n"
        "    proxy_pass http://127.0.0.1:8899;\n"
        "    proxy_http_version 1.1;\n"
        "    proxy_set_header Host $host;\n"
        "    proxy_set_header X-Real-IP $remote_addr;\n"
        "    proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;\n"
        "    proxy_set_header X-Forwarded-Proto $scheme;\n"
        "  }\n"
        "}\n"
    )


def _server_commands(domain: str) -> list[str]:
    config = _nginx_config(domain).rstrip()
    return [
        "sudo apt-get update",
        "sudo apt-get install -y nginx certbot python3-certbot-nginx",
        "sudo mkdir -p /etc/nginx/sites-available /etc/nginx/sites-enabled",
        "sudo tee /etc/nginx/sites-available/xagent-stage3 >/dev/null <<'NGINX'\n" + config + "\nNGINX",
        "sudo ln -sfn /etc/nginx/sites-available/xagent-stage3 /etc/nginx/sites-enabled/xagent-stage3",
        "sudo nginx -t",
        "sudo systemctl reload nginx",
        f"sudo certbot --nginx -d {domain} --redirect",
        "sudo nginx -t",
        "sudo systemctl reload nginx",
        f"curl -i https://{domain}/health",
        f"curl -i https://{domain}/ready",
    ]


def _local_validation_commands(domain: str, release_sha: str) -> list[str]:
    return [
        f'python scripts/stage3_https_preflight.py --domain "{domain}"',
        (
            "python scripts/commercial_stage3_staging_external_evidence_intake.py "
            "--write-owner-draft "
            f"--current-head-sha {release_sha} "
            f"--release-sha {release_sha} "
            f'--domain "{domain}" '
            "--https-preflight-report .xagent_runtime\\reports\\stage3-https-preflight-20260618.json "
            "--owner xiongpinji "
            "--force"
        ),
        (
            "python scripts/commercial_stage3_staging_external_evidence_intake.py "
            "--input-json .xagent_runtime\\reports\\stage3-staging-external-evidence-owner-draft-20260616.json "
            f"--current-head-sha {release_sha} "
            f"--release-sha {release_sha} "
            "--force"
        ),
        (
            "python scripts/commercial_environment_rehearsal_gate.py "
            "--environment staging "
            f"--current-head-sha {release_sha} "
            f"--release-sha {release_sha}"
        ),
        (
            "python scripts/rc_final_gate.py "
            "--require-ready-to-tag "
            "--require-stage3-rehearsal "
            "--output .xagent_runtime\\reports\\rc-final-gate-stage3-rehearsal-check.json"
        ),
    ]


def build_stage3_owner_domain_guide(
    *,
    domain: str,
    expected_ip: str = DEFAULT_EXPECTED_IP,
    release_sha: str | None = None,
    external_smoke_report: Path = DEFAULT_EXTERNAL_SMOKE_REPORT,
) -> Stage3OwnerDomainGuide:
    normalized_domain, normalization_errors = _normalize_domain(domain)
    domain_errors = [*normalization_errors, *_domain_validation_errors(normalized_domain)]
    domain_ok = not domain_errors
    if release_sha:
        effective_release_sha = release_sha.strip() or DEFAULT_RELEASE_SHA_PLACEHOLDER
        release_sha_source = "cli"
    else:
        detected_sha, source = _validated_release_sha_from_external_smoke(external_smoke_report)
        effective_release_sha = detected_sha or DEFAULT_RELEASE_SHA_PLACEHOLDER
        release_sha_source = source if detected_sha else f"placeholder: {source}"

    checks = [
        _check(
            "domain_shape",
            domain_ok,
            details={
                "domain": normalized_domain,
                "expected_ip": expected_ip,
                "temporary_wildcard_dns_rejected": True,
                "bare_ip_rejected": True,
            },
            error="; ".join(domain_errors),
        ),
        _check(
            "release_sha_source",
            effective_release_sha != DEFAULT_RELEASE_SHA_PLACEHOLDER,
            details={
                "release_sha": effective_release_sha,
                "source": release_sha_source,
                "external_smoke_report": _display_path(external_smoke_report),
            },
            error="owner-verified hosted Actions head_sha could not be auto-detected",
        ),
        _check(
            "read_only_no_mutation",
            True,
            details={
                "dns_mutation_performed": False,
                "server_mutation_performed": False,
                "deploy_performed": False,
                "workflow_dispatch_performed": False,
                "raw_secret_values_recorded": False,
            },
        ),
    ]

    owner_decisions = [
        f"Choose a real owner-controlled DNS name and point its A record to {expected_ip}.",
        "Decide whether first-RC observability uses real broker/trace/error/metrics/alert refs or an explicit owner-approved exception ref.",
        f"Approve the exact release SHA after the five Stage3 evidence reports are ready: {effective_release_sha}.",
    ]
    operator_steps = [
        "Create the DNS A record in the domain provider console.",
        "Configure Nginx on the Stage3 server to proxy the domain to http://127.0.0.1:8899.",
        "Issue a trusted TLS certificate for the domain on port 443.",
        "Run HTTPS /health and /ready probes and keep only redaction-safe command-output references.",
        "Run the local preflight, prefill the owner draft, replace placeholders with refs, and rerun the strict final gate.",
    ]
    evidence_refs = [
        "DNS provider record screenshot or exported record reference, with no secrets.",
        "Nginx site path plus `nginx -t` and reload output reference.",
        "`certbot certificates` or certificate issuer reference for the domain.",
        f"`https://{normalized_domain}/health` probe output showing JSON status `ok`." if domain_ok else "`https://<REAL_DOMAIN>/health` probe output showing JSON status `ok`.",
        f"`https://{normalized_domain}/ready` probe output showing JSON status `ready`." if domain_ok else "`https://<REAL_DOMAIN>/ready` probe output showing JSON status `ready`.",
        "Running Stage3 image reference and digest.",
        "Deploy, smoke, rollback, observability, environment-protection, and owner-approval refs.",
        "Secret variable-name or secret-manager references only, never secret values.",
    ]

    return Stage3OwnerDomainGuide(
        status="stage3_owner_domain_guide_ready" if domain_ok else "stage3_owner_domain_guide_blocked",
        generated_at=_utc_now(),
        domain=normalized_domain,
        expected_ip=expected_ip,
        release_sha=effective_release_sha,
        release_sha_source=release_sha_source,
        mutation_performed=False,
        deploy_performed=False,
        workflow_dispatch_performed=False,
        raw_secret_values_recorded=False,
        checks=checks,
        owner_decisions=owner_decisions,
        operator_steps=operator_steps,
        server_commands=_server_commands(normalized_domain) if domain_ok else [],
        local_validation_commands=_local_validation_commands(normalized_domain, effective_release_sha) if domain_ok else [],
        evidence_refs_to_collect=evidence_refs,
        known_limits=[
            "This guide is not evidence by itself.",
            "This guide does not prove DNS, TLS, deploy, smoke, rollback, observability, or environment protection.",
            "Temporary wildcard DNS such as sslip.io, bare IPs, localhost, and self-signed TLS are not final commercial evidence.",
            "Run stage3_https_preflight.py after the real domain and TLS are configured.",
        ],
    )


def render_markdown_report(report: Stage3OwnerDomainGuide) -> str:
    checks = "\n".join(
        f"- {check.name}: `{check.status}`" + (f" - {check.error}" if check.error else "")
        for check in report.checks
    )
    decisions = "\n".join(f"- {item}" for item in report.owner_decisions)
    steps = "\n".join(f"- {item}" for item in report.operator_steps)
    refs = "\n".join(f"- {item}" for item in report.evidence_refs_to_collect)
    limits = "\n".join(f"- {item}" for item in report.known_limits)
    server_commands = "\n\n".join(f"```bash\n{command}\n```" for command in report.server_commands) or "_Blocked until a real owner-controlled domain is provided._"
    local_commands = "\n\n".join(f"```powershell\n{command}\n```" for command in report.local_validation_commands) or "_Blocked until a real owner-controlled domain is provided._"
    return (
        "# Stage3 Owner Domain Guide\n\n"
        f"- Status: `{report.status}`\n"
        f"- Domain: `{report.domain or '<missing>'}`\n"
        f"- Expected IP: `{report.expected_ip}`\n"
        f"- Release SHA: `{report.release_sha}`\n"
        f"- Release SHA source: `{report.release_sha_source}`\n"
        f"- Mutation performed: `{report.mutation_performed}`\n"
        f"- Deploy performed: `{report.deploy_performed}`\n"
        f"- Workflow dispatch performed: `{report.workflow_dispatch_performed}`\n"
        f"- Raw secret values recorded: `{report.raw_secret_values_recorded}`\n\n"
        "## Checks\n\n"
        f"{checks}\n\n"
        "## Owner Decisions\n\n"
        f"{decisions}\n\n"
        "## Operator Steps\n\n"
        f"{steps}\n\n"
        "## Server Commands\n\n"
        f"{server_commands}\n\n"
        "## Local Validation Commands\n\n"
        f"{local_commands}\n\n"
        "## Evidence Refs To Collect\n\n"
        f"{refs}\n\n"
        "## Limits\n\n"
        f"{limits}\n"
    )


def write_reports(
    report: Stage3OwnerDomainGuide,
    *,
    output_json: Path = DEFAULT_OUTPUT_JSON,
    output_md: Path = DEFAULT_OUTPUT_MD,
) -> None:
    output_json.parent.mkdir(parents=True, exist_ok=True)
    output_json.write_text(json.dumps(report.to_dict(), ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    output_md.parent.mkdir(parents=True, exist_ok=True)
    output_md.write_text(render_markdown_report(report), encoding="utf-8")


def parse_args(argv: Sequence[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Generate a no-secret Stage3 owner domain/TLS evidence guide.")
    parser.add_argument("--domain", required=True, help="Real owner-controlled domain, for example xagent.example.com.")
    parser.add_argument("--expected-ip", default=DEFAULT_EXPECTED_IP)
    parser.add_argument(
        "--release-sha",
        default=None,
        help="Owner-verified hosted Actions head SHA for the RC. Defaults to rc-external-smoke.json when verified.",
    )
    parser.add_argument("--external-smoke-report", type=Path, default=DEFAULT_EXTERNAL_SMOKE_REPORT)
    parser.add_argument("--output-json", type=Path, default=DEFAULT_OUTPUT_JSON)
    parser.add_argument("--output-md", type=Path, default=DEFAULT_OUTPUT_MD)
    return parser.parse_args(argv)


def main(argv: Sequence[str] | None = None) -> int:
    args = parse_args(argv)
    report = build_stage3_owner_domain_guide(
        domain=args.domain,
        expected_ip=args.expected_ip,
        release_sha=args.release_sha,
        external_smoke_report=args.external_smoke_report,
    )
    write_reports(report, output_json=args.output_json, output_md=args.output_md)
    print(f"Stage3 owner domain guide status: {report.status}")
    print(f"Domain: {report.domain or '<missing>'}")
    print(f"JSON guide written to {_display_path(args.output_json)}")
    print(f"Markdown guide written to {_display_path(args.output_md)}")
    return 0 if report.status == "stage3_owner_domain_guide_ready" else 1


if __name__ == "__main__":
    raise SystemExit(main())
