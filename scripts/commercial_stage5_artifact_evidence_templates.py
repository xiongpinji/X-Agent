#!/usr/bin/env python3
"""Generate blocked Stage 5 artifact evidence templates.

These templates are operator work items, not evidence. They intentionally keep
artifact gates blocked until real artifact files, hashes, image digests, and SHA
binding are collected by an owner or environment operator.
"""

from __future__ import annotations

import argparse
import json
import subprocess
from dataclasses import asdict, dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
REPORT_DIR = ROOT / ".xagent_runtime" / "reports"
DEFAULT_OUTPUT_JSON = REPORT_DIR / "controller-stage5-artifact-templates-worker-20260615.json"
DEFAULT_OUTPUT_MD = REPORT_DIR / "controller-stage5-artifact-templates-worker-20260615.md"

TEMPLATE_FILENAMES = (
    "stage5-image-digests-20260615.json",
    "stage5-sbom-20260615.json",
    "stage5-helm-package-20260615.json",
)


@dataclass(frozen=True)
class TemplateWriteResult:
    name: str
    path: str
    status: str
    written: bool
    skipped_existing: bool
    force: bool
    error: str | None = None


@dataclass(frozen=True)
class TemplateWorkerReport:
    status: str
    generated_at: str
    report_dir: str
    current_head_sha: str | None
    release_sha: str | None
    template_not_evidence: bool
    real_evidence_collected: bool
    mutation_performed: bool
    deploy_performed: bool
    owner_approval_created: bool
    templates: list[TemplateWriteResult] = field(default_factory=list)
    artifact_release_gate_expected_status: str = "artifacts_release_blocked"
    artifact_evidence_pack_expected_status: str = "artifact_evidence_pack_blocked"
    next_actions: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        payload = asdict(self)
        payload["templates"] = [asdict(item) for item in self.templates]
        return payload


def _utc_now() -> str:
    return datetime.now(UTC).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _git_head(root: Path = ROOT) -> str | None:
    try:
        completed = subprocess.run(
            ["git", "rev-parse", "HEAD"],
            cwd=root,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=10,
            check=False,
        )
    except (OSError, subprocess.TimeoutExpired):
        return None
    if completed.returncode != 0:
        return None
    return completed.stdout.strip() or None


def _display_path(path: Path, *, root: Path = ROOT) -> str:
    try:
        return str(path.resolve().relative_to(root.resolve()))
    except ValueError:
        return str(path.resolve())


def _existing_file_is_template(path: Path) -> bool:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError, UnicodeDecodeError):
        return False
    if not isinstance(payload, dict):
        return False
    return payload.get("template_not_evidence") is True and payload.get("real_evidence_collected") is False


def _base_template(
    *,
    evidence_name: str,
    filename: str,
    expected_ready_statuses: list[str],
    current_head_sha: str | None,
    release_sha: str | None,
    required_owner_or_operator_actions: list[str],
) -> dict[str, Any]:
    return {
        "status": "blocked",
        "evidence_name": evidence_name,
        "template_filename": filename,
        "template_not_evidence": True,
        "real_evidence_collected": False,
        "mutation_performed": False,
        "deploy_performed": False,
        "owner_approval_created": False,
        "current_head_sha": current_head_sha,
        "release_sha": release_sha,
        "expected_ready_statuses": expected_ready_statuses,
        "required_owner_or_operator_actions": required_owner_or_operator_actions,
        "blocking_reason": (
            "Blocked skeleton only. Replace this file with real artifact evidence "
            "before using it for Stage 5 artifact gates."
        ),
    }


def build_template_payloads(
    report_dir: Path = REPORT_DIR,
    current_head_sha: str | None = None,
    release_sha: str | None = None,
) -> dict[str, dict[str, Any]]:
    """Build blocked template payloads keyed by target filename."""

    resolved_head = current_head_sha if current_head_sha is not None else _git_head()
    resolved_release_sha = release_sha if release_sha is not None else resolved_head
    report_dir = Path(report_dir)

    return {
        "stage5-image-digests-20260615.json": {
            **_base_template(
                evidence_name="image_digests",
                filename="stage5-image-digests-20260615.json",
                expected_ready_statuses=["image_digests_ready", "passed"],
                current_head_sha=resolved_head,
                release_sha=resolved_release_sha,
                required_owner_or_operator_actions=[
                    "Build or identify immutable release container images for the selected SHA.",
                    "Collect registry image digests in sha256:<64 hex> form for every required image.",
                    "Replace this template with a real image digest evidence report.",
                ],
            ),
            "image_digests": [],
            "images": [],
            "registry": "<owner/operator registry>",
            "notes": "Do not change status to a ready value until real registry digests are collected.",
        },
        "stage5-sbom-20260615.json": {
            **_base_template(
                evidence_name="sbom",
                filename="stage5-sbom-20260615.json",
                expected_ready_statuses=["sbom_ready", "passed"],
                current_head_sha=resolved_head,
                release_sha=resolved_release_sha,
                required_owner_or_operator_actions=[
                    "Generate the release SBOM for the selected SHA.",
                    "Archive the SBOM artifact under a durable release path.",
                    "Record the SBOM path and sha256 in a real evidence report.",
                ],
            ),
            "sbom_path": "",
            "sha256": "",
            "format": "<spdx|cyclonedx|other>",
            "notes": "Do not change status to a ready value until the SBOM file and sha256 exist.",
        },
        "stage5-helm-package-20260615.json": {
            **_base_template(
                evidence_name="helm_package",
                filename="stage5-helm-package-20260615.json",
                expected_ready_statuses=["helm_package_ready", "passed"],
                current_head_sha=resolved_head,
                release_sha=resolved_release_sha,
                required_owner_or_operator_actions=[
                    "Package the release Helm chart for the selected SHA.",
                    "Archive the chart package under a durable release path.",
                    "Record the Helm package path and sha256 in a real evidence report.",
                ],
            ),
            "helm_package_path": "",
            "chart_package_path": "",
            "package_path": "",
            "sha256": "",
            "notes": "Do not change status to a ready value until the Helm package and sha256 exist.",
        },
    }


def write_templates(
    report_dir: Path = REPORT_DIR,
    *,
    current_head_sha: str | None = None,
    release_sha: str | None = None,
    force: bool = False,
) -> list[TemplateWriteResult]:
    payloads = build_template_payloads(
        report_dir=report_dir,
        current_head_sha=current_head_sha,
        release_sha=release_sha,
    )
    report_dir = Path(report_dir)
    report_dir.mkdir(parents=True, exist_ok=True)
    results: list[TemplateWriteResult] = []

    for filename in TEMPLATE_FILENAMES:
        path = report_dir / filename
        if path.exists() and not force:
            results.append(
                TemplateWriteResult(
                    name=payloads[filename]["evidence_name"],
                    path=_display_path(path),
                    status="skipped_existing",
                    written=False,
                    skipped_existing=True,
                    force=force,
                )
            )
            continue
        if path.exists() and force and not _existing_file_is_template(path):
            results.append(
                TemplateWriteResult(
                    name=payloads[filename]["evidence_name"],
                    path=_display_path(path),
                    status="skipped_existing_real_evidence",
                    written=False,
                    skipped_existing=True,
                    force=force,
                    error="existing file is not a blocked template; refusing to overwrite with --force",
                )
            )
            continue

        path.write_text(json.dumps(payloads[filename], ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        results.append(
            TemplateWriteResult(
                name=payloads[filename]["evidence_name"],
                path=_display_path(path),
                status="written",
                written=True,
                skipped_existing=False,
                force=force,
            )
        )

    return results


def _report_status(results: list[TemplateWriteResult]) -> str:
    if not results:
        return "artifact_evidence_templates_unchanged"
    if all(result.status == "dry_run" for result in results):
        return "artifact_evidence_templates_dry_run"
    if any(result.error for result in results):
        return "artifact_evidence_templates_blocked"
    if all(result.written for result in results):
        return "artifact_evidence_templates_written"
    if any(result.written for result in results):
        return "artifact_evidence_templates_partial"
    return "artifact_evidence_templates_unchanged"


def build_worker_report(
    results: list[TemplateWriteResult],
    *,
    report_dir: Path = REPORT_DIR,
    current_head_sha: str | None = None,
    release_sha: str | None = None,
) -> TemplateWorkerReport:
    resolved_head = current_head_sha if current_head_sha is not None else _git_head()
    resolved_release_sha = release_sha if release_sha is not None else resolved_head
    return TemplateWorkerReport(
        status=_report_status(results),
        generated_at=_utc_now(),
        report_dir=_display_path(Path(report_dir)),
        current_head_sha=resolved_head,
        release_sha=resolved_release_sha,
        template_not_evidence=True,
        real_evidence_collected=False,
        mutation_performed=False,
        deploy_performed=False,
        owner_approval_created=False,
        templates=results,
        next_actions=[
            "Owner/operator must replace blocked templates with real artifact evidence.",
            "Artifact release gate and artifact evidence pack must remain blocked while these templates are present.",
        ],
    )


def render_markdown_report(report: TemplateWorkerReport) -> str:
    template_lines = "\n".join(
        f"- {item.name}: `{item.status}` at `{item.path}`"
        for item in report.templates
    ) or "- none"
    return (
        "# Stage 5 Artifact Evidence Templates Worker\n\n"
        f"- Status: `{report.status}`\n"
        f"- Template not evidence: `{report.template_not_evidence}`\n"
        f"- Real evidence collected: `{report.real_evidence_collected}`\n"
        f"- Mutation performed: `{report.mutation_performed}`\n"
        f"- Deploy performed: `{report.deploy_performed}`\n"
        f"- Owner approval created: `{report.owner_approval_created}`\n"
        f"- Current head SHA: `{report.current_head_sha or '<missing>'}`\n"
        f"- Release SHA: `{report.release_sha or '<missing>'}`\n"
        f"- Artifact release gate expected status: `{report.artifact_release_gate_expected_status}`\n"
        f"- Artifact evidence pack expected status: `{report.artifact_evidence_pack_expected_status}`\n\n"
        "## Templates\n\n"
        f"{template_lines}\n"
    )


def write_report(report: TemplateWorkerReport, output_path: Path = DEFAULT_OUTPUT_JSON) -> None:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(report.to_dict(), ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def write_markdown_report(report: TemplateWorkerReport, output_path: Path = DEFAULT_OUTPUT_MD) -> None:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(render_markdown_report(report), encoding="utf-8")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Generate blocked Stage 5 artifact evidence templates.")
    parser.add_argument("--report-dir", type=Path, default=REPORT_DIR)
    parser.add_argument("--current-head-sha", default=None)
    parser.add_argument("--release-sha", default=None)
    parser.add_argument("--force", action="store_true")
    parser.add_argument(
        "--write-templates",
        action="store_true",
        help="Materialize blocked skeleton files. Default is a dry-run summary only.",
    )
    parser.add_argument("--output-json", type=Path, default=DEFAULT_OUTPUT_JSON)
    parser.add_argument("--output-md", type=Path, default=DEFAULT_OUTPUT_MD)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    if args.write_templates:
        results = write_templates(
            args.report_dir,
            current_head_sha=args.current_head_sha,
            release_sha=args.release_sha,
            force=args.force,
        )
    else:
        payloads = build_template_payloads(
            args.report_dir,
            current_head_sha=args.current_head_sha,
            release_sha=args.release_sha,
        )
        results = [
            TemplateWriteResult(
                name=payload["evidence_name"],
                path=_display_path(args.report_dir / filename),
                status="dry_run",
                written=False,
                skipped_existing=False,
                force=args.force,
            )
            for filename, payload in payloads.items()
        ]
    report = build_worker_report(
        results,
        report_dir=args.report_dir,
        current_head_sha=args.current_head_sha,
        release_sha=args.release_sha,
    )
    write_report(report, args.output_json)
    write_markdown_report(report, args.output_md)
    print(f"Stage 5 artifact evidence templates status: {report.status}")
    print(f"Template not evidence: {report.template_not_evidence}")
    print(f"Real evidence collected: {report.real_evidence_collected}")
    print(f"JSON report written to {args.output_json}")
    print(f"Markdown report written to {args.output_md}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
