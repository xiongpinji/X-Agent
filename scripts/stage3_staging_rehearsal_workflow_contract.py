#!/usr/bin/env python3
"""Validate the Stage 3 staging rehearsal GitHub Actions workflow contract."""

from __future__ import annotations

import argparse
import json
import re
from dataclasses import asdict, dataclass, field
from datetime import UTC, datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_WORKFLOW = ROOT / ".github" / "workflows" / "deploy.yml"
DEFAULT_OUTPUT = ROOT / ".xagent_runtime" / "reports" / "stage3-staging-rehearsal-workflow-contract.json"


@dataclass(frozen=True)
class Requirement:
    id: str
    description: str
    tokens: tuple[str, ...]


@dataclass(frozen=True)
class ForbiddenPattern:
    id: str
    description: str
    token: str


@dataclass(frozen=True)
class ContractFinding:
    id: str
    description: str
    kind: str
    missing_tokens: list[str] = field(default_factory=list)
    matched_token: str | None = None


@dataclass(frozen=True)
class WorkflowContractReport:
    status: str
    generated_at: str
    workflow_path: str
    requirements_checked: int
    forbidden_patterns_checked: int
    findings: list[ContractFinding]

    def to_dict(self) -> dict[str, object]:
        payload = asdict(self)
        payload["findings"] = [asdict(finding) for finding in self.findings]
        return payload


REQUIRED_CONTAINS: tuple[Requirement, ...] = (
    Requirement(
        id="manual_dispatch_inputs",
        description="Workflow is manually dispatched with exact SHA, immutable image, dry-run, confirmation, and URL inputs.",
        tokens=(
            "workflow_dispatch:",
            "release_sha:",
            "image_ref:",
            "image_digest:",
            "staging_url:",
            "dry_run:",
            "confirm_deploy:",
            "rollback_after_smoke:",
        ),
    ),
    Requirement(
        id="minimum_permissions",
        description="Workflow keeps repository token permissions read-only.",
        tokens=("\n    permissions:\n      contents: read",),
    ),
    Requirement(
        id="staging_environment_only",
        description="Jobs bind to the staging environment and staging URL.",
        tokens=("environment:\n      name: staging", "github.event.inputs.staging_url"),
    ),
    Requirement(
        id="exact_sha_checkout",
        description="Workflow checks out and validates the exact requested release SHA.",
        tokens=("ref: ${{ github.event.inputs.release_sha || github.sha }}", "git rev-parse HEAD", '!= "$release_sha"'),
    ),
    Requirement(
        id="immutable_image_guard",
        description="Workflow requires image_ref to include the expected sha256 image digest.",
        tokens=("^sha256:[a-f0-9]{64}$", '[[ "$image_ref" != *"@$image_digest" ]]'),
    ),
    Requirement(
        id="dry_run_default_and_confirmation",
        description="Workflow defaults to dry-run and requires an explicit confirmation phrase for deploy.",
        tokens=(
            "default: 'true'",
            "REQUIRED_STAGE3_CONFIRMATION: confirm-stage3-staging-deploy",
            "confirm_deploy",
        ),
    ),
    Requirement(
        id="secret_name_preflight",
        description="Workflow checks required secret names without recording secret values.",
        tokens=(
            "Stage 3 staging preflight",
            "AWS_ACCESS_KEY_ID",
            "AWS_SECRET_ACCESS_KEY",
            "AWS_REGION",
            "HELM_REPO_URL",
            "STAGING_DATABASE_URL",
            "STAGING_REDIS_URL",
            "STAGING_WORKFLOW_EVENT_RABBITMQ_URL",
            '"secret_values_recorded": False',
        ),
    ),
    Requirement(
        id="guarded_staging_deploy",
        description="Real deploy path is guarded and deploys only to staging.",
        tokens=(
            "steps.stage3-preflight.outputs.deploy_allowed == 'true'",
            "Apply staging Kubernetes secret",
            "kubectl create secret generic xagent-secrets",
            "--dry-run=client",
            "aws eks update-kubeconfig --name xagent-staging",
            "helm upgrade --install xagent xagent/xagent",
            "--namespace staging",
            "deployment/helm/values-staging.yaml",
            "--set secrets.create=false",
            "--set-string secrets.existingSecretName=xagent-secrets",
            "kubectl rollout status deployment/xagent-api -n staging",
            "kubectl rollout status deployment/xagent-worker -n staging",
        ),
    ),
    Requirement(
        id="smoke_and_rollback_evidence",
        description="Workflow emits deploy, smoke, rollback, and preflight evidence artifacts.",
        tokens=(
            "stage3-staging-rehearsal-preflight.json",
            "stage3-staging-rehearsal-deploy-smoke.json",
            "stage3-staging-rehearsal-rollback.json",
            "stage3_staging_deploy_smoke_failed",
            "stage3_staging_rollback_failed",
            "step_outcomes",
            "curl --fail --show-error --silent",
            "kubectl rollout undo deployment/xagent-api -n staging",
            "stage3-staging-rehearsal-evidence",
        ),
    ),
)

FORBIDDEN_CONTAINS: tuple[ForbiddenPattern, ...] = (
    ForbiddenPattern(
        id="no_production_environment",
        description="Stage 3 workflow must not bind to production.",
        token="name: production",
    ),
    ForbiddenPattern(
        id="no_production_secrets",
        description="Stage 3 workflow must not reference production secrets.",
        token="PRODUCTION_",
    ),
    ForbiddenPattern(
        id="no_prod_secrets",
        description="Stage 3 workflow must not reference PROD-prefixed secrets.",
        token="PROD_",
    ),
    ForbiddenPattern(
        id="no_release_creation",
        description="Stage 3 workflow must not create releases.",
        token="actions/create-release",
    ),
    ForbiddenPattern(
        id="no_gh_release",
        description="Stage 3 workflow must not create releases.",
        token="gh release",
    ),
    ForbiddenPattern(
        id="no_git_tag",
        description="Stage 3 workflow must not create tags.",
        token="git tag",
    ),
    ForbiddenPattern(
        id="no_git_push",
        description="Stage 3 workflow must not push source changes.",
        token="git push",
    ),
    ForbiddenPattern(
        id="no_broad_staging",
        description="Stage 3 workflow must not stage broad worktree contents.",
        token="git add .",
    ),
    ForbiddenPattern(
        id="no_raw_database_url_helm_value",
        description="Stage 3 workflow must not pass raw database URLs through Helm values.",
        token="--set-string secrets.databaseUrl=",
    ),
    ForbiddenPattern(
        id="no_raw_redis_url_helm_value",
        description="Stage 3 workflow must not pass raw Redis URLs through Helm values.",
        token="--set-string secrets.redisUrl=",
    ),
    ForbiddenPattern(
        id="no_raw_api_key_helm_value",
        description="Stage 3 workflow must not pass raw API keys through Helm values.",
        token="--set-string secrets.apiKey=",
    ),
    ForbiddenPattern(
        id="no_raw_jwt_secret_helm_value",
        description="Stage 3 workflow must not pass raw JWT secrets through Helm values.",
        token="--set-string secrets.jwtSecret=",
    ),
    ForbiddenPattern(
        id="no_raw_encryption_key_helm_value",
        description="Stage 3 workflow must not pass raw encryption keys through Helm values.",
        token="--set-string secrets.encryptionKey=",
    ),
    ForbiddenPattern(
        id="no_raw_audit_hmac_secret_helm_value",
        description="Stage 3 workflow must not pass raw audit HMAC secrets through Helm values.",
        token="--set-string secrets.auditHmacSecret=",
    ),
    ForbiddenPattern(
        id="no_raw_langfuse_public_key_helm_value",
        description="Stage 3 workflow must not pass raw Langfuse public keys through Helm values.",
        token="--set-string secrets.langfusePublicKey=",
    ),
    ForbiddenPattern(
        id="no_raw_langfuse_secret_key_helm_value",
        description="Stage 3 workflow must not pass raw Langfuse secret keys through Helm values.",
        token="--set-string secrets.langfuseSecretKey=",
    ),
    ForbiddenPattern(
        id="no_raw_sentry_dsn_helm_value",
        description="Stage 3 workflow must not pass raw Sentry DSNs through Helm values.",
        token="--set-string secrets.sentryDsn=",
    ),
    ForbiddenPattern(
        id="no_raw_workflow_event_rabbitmq_url_helm_value",
        description="Stage 3 workflow must not pass raw RabbitMQ URLs through Helm values.",
        token="--set-string secrets.workflowEventRabbitmqUrl=",
    ),
)


def _utc_now() -> str:
    return datetime.now(UTC).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _strip_yaml_comment(line: str) -> str:
    in_single = False
    in_double = False
    escaped = False
    for index, char in enumerate(line):
        if escaped:
            escaped = False
            continue
        if char == "\\" and in_double:
            escaped = True
            continue
        if char == "'" and not in_double:
            in_single = not in_single
            continue
        if char == '"' and not in_single:
            in_double = not in_double
            continue
        if char == "#" and not in_single and not in_double and (index == 0 or line[index - 1].isspace()):
            return line[:index].rstrip()
    return line


def _normalize_workflow_text(text: str) -> str:
    normalized = text.replace("\r\n", "\n").replace("\\", "/")
    return "\n".join(_strip_yaml_comment(line) for line in normalized.splitlines())


def _stage3_workflow_text(text: str) -> str:
    marker = "\n  deploy-staging:"
    start = text.find(marker)
    if start == -1:
        return ""
    next_job = re.search(r"\n  [A-Za-z0-9_-]+:", text[start + len(marker) :])
    if next_job is None:
        return text[start:]
    return text[start : start + len(marker) + next_job.start()]


def run_contract(workflow_path: Path = DEFAULT_WORKFLOW) -> WorkflowContractReport:
    findings: list[ContractFinding] = []
    try:
        text = _normalize_workflow_text(workflow_path.read_text(encoding="utf-8"))
    except FileNotFoundError:
        findings.append(
            ContractFinding(
                id="workflow_missing",
                description="Stage 3 staging rehearsal workflow file is missing.",
                kind="required",
                missing_tokens=[str(workflow_path)],
            )
        )
        text = ""

    stage3_text = _stage3_workflow_text(text)
    combined_text = text + "\n" + stage3_text

    for requirement in REQUIRED_CONTAINS:
        missing = [token for token in requirement.tokens if token not in combined_text]
        if missing:
            findings.append(
                ContractFinding(
                    id=requirement.id,
                    description=requirement.description,
                    kind="required",
                    missing_tokens=missing,
                )
            )

    for forbidden in FORBIDDEN_CONTAINS:
        if forbidden.token in stage3_text:
            findings.append(
                ContractFinding(
                    id=forbidden.id,
                    description=forbidden.description,
                    kind="forbidden",
                    matched_token=forbidden.token,
                )
            )

    return WorkflowContractReport(
        status="passed" if not findings else "failed",
        generated_at=_utc_now(),
        workflow_path=str(workflow_path),
        requirements_checked=len(REQUIRED_CONTAINS),
        forbidden_patterns_checked=len(FORBIDDEN_CONTAINS),
        findings=findings,
    )


def write_report(report: WorkflowContractReport, output_path: Path) -> None:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(report.to_dict(), ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Validate the Stage 3 staging rehearsal workflow contract")
    parser.add_argument("--workflow", type=Path, default=DEFAULT_WORKFLOW)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    report = run_contract(args.workflow)
    write_report(report, args.output)
    print(f"Stage 3 staging rehearsal workflow contract status: {report.status}")
    print(f"Workflow: {report.workflow_path}")
    print(f"Requirements checked: {report.requirements_checked}")
    print(f"Report written to {args.output}")
    if report.findings:
        print("Findings:")
        for finding in report.findings:
            detail = ", ".join(finding.missing_tokens) if finding.missing_tokens else finding.matched_token or ""
            print(f"- {finding.id}: {detail}")
    return 0 if report.status == "passed" else 1


if __name__ == "__main__":
    raise SystemExit(main())
