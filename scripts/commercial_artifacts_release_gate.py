#!/usr/bin/env python3
"""Validate Stage 5 release artifact evidence.

This gate is read-only with respect to release operations. It verifies that the
release artifact chain has real source bundle, image digest, SBOM, Helm package,
checksum, and release-receipt evidence before the commercial GA final gate can
promote artifacts evidence to ready.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import subprocess
from dataclasses import asdict, dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
REPORT_DIR = ROOT / ".xagent_runtime" / "reports"
RELEASE_DIR = ROOT / ".xagent_runtime" / "release"
DEFAULT_OUTPUT_JSON = REPORT_DIR / "stage5-artifacts-release-gate-20260615.json"
DEFAULT_OUTPUT_MD = REPORT_DIR / "stage5-artifacts-release-gate-20260615.md"

SHA256_RE = re.compile(r"^[a-fA-F0-9]{64}$")
IMAGE_DIGEST_RE = re.compile(r"^sha256:[a-fA-F0-9]{64}$")


@dataclass(frozen=True)
class ArtifactCheck:
    name: str
    status: str
    details: dict[str, Any] = field(default_factory=dict)
    error: str | None = None


@dataclass(frozen=True)
class ArtifactEvidence:
    name: str
    path: str
    status: str | None
    expected_statuses: list[str]
    ready: bool
    artifact_path: str | None = None
    expected_sha256: str | None = None
    actual_sha256: str | None = None
    error: str | None = None


@dataclass(frozen=True)
class ArtifactsReleaseGateReport:
    status: str
    generated_at: str
    current_head_sha: str | None
    release_sha: str | None
    artifacts_release_ready: bool
    mutation_performed: bool
    outbound_message_sent: bool
    deploy_tag_release_performed: bool
    evidence: list[ArtifactEvidence]
    checks: list[ArtifactCheck]
    missing_or_mismatched: list[str]
    next_actions: list[str]
    known_limits: list[str]

    def to_dict(self) -> dict[str, Any]:
        payload = asdict(self)
        payload["evidence"] = [asdict(item) for item in self.evidence]
        payload["checks"] = [asdict(check) for check in self.checks]
        return payload


def _utc_now() -> str:
    return datetime.now(UTC).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _run_git(args: list[str]) -> tuple[str | None, str | None]:
    try:
        completed = subprocess.run(
            ["git", *args],
            cwd=ROOT,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            check=False,
            timeout=10,
        )
    except (OSError, subprocess.TimeoutExpired) as exc:
        return None, str(exc)
    if completed.returncode != 0:
        return None, (completed.stderr or completed.stdout).strip() or f"git exited {completed.returncode}"
    return completed.stdout.strip(), None


def resolve_current_head_sha() -> str | None:
    value, error = _run_git(["rev-parse", "HEAD"])
    return None if error else value


def _display_path(path: Path) -> str:
    try:
        return str(path.resolve().relative_to(ROOT))
    except ValueError:
        return str(path.resolve())


def _read_json(path: Path) -> tuple[dict[str, Any] | None, str | None]:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError:
        return None, f"missing report: {_display_path(path)}"
    except (OSError, json.JSONDecodeError) as exc:
        return None, f"could not read report {_display_path(path)}: {exc}"
    if not isinstance(payload, dict):
        return None, f"report is not a JSON object: {_display_path(path)}"
    return payload, None


def _sha256_file(path: Path) -> tuple[str | None, str | None]:
    try:
        digest = hashlib.sha256()
        with path.open("rb") as handle:
            for chunk in iter(lambda: handle.read(1024 * 1024), b""):
                digest.update(chunk)
    except FileNotFoundError:
        return None, f"artifact file missing: {_display_path(path)}"
    except OSError as exc:
        return None, f"could not read artifact file {_display_path(path)}: {exc}"
    return digest.hexdigest(), None


def _status(payload: dict[str, Any] | None) -> str | None:
    if not payload:
        return None
    value = payload.get("status") or payload.get("package_status") or payload.get("report")
    return str(value) if value is not None else None


def _resolve_artifact_path(raw_path: Any, *, root: Path) -> Path | None:
    if not isinstance(raw_path, str) or not raw_path:
        return None
    path = Path(raw_path)
    return path if path.is_absolute() else root / path


def _first_string(payload: dict[str, Any], keys: tuple[str, ...]) -> str | None:
    for key in keys:
        value = payload.get(key)
        if isinstance(value, str) and value:
            return value
    return None


def _extract_expected_sha(payload: dict[str, Any], keys: tuple[str, ...] = ("sha256", "artifact_sha256")) -> str | None:
    value = _first_string(payload, keys)
    if value:
        return value
    artifact = payload.get("artifact")
    if isinstance(artifact, dict):
        value = _first_string(artifact, keys)
        if value:
            return value
    return None


def _file_evidence(
    *,
    name: str,
    report_path: Path,
    payload: dict[str, Any] | None,
    read_error: str | None,
    expected_statuses: set[str],
    path_keys: tuple[str, ...],
    root: Path,
    sha_keys: tuple[str, ...] = ("sha256", "artifact_sha256"),
) -> ArtifactEvidence:
    status = _status(payload)
    if read_error or payload is None:
        return ArtifactEvidence(
            name=name,
            path=_display_path(report_path),
            status=status,
            expected_statuses=sorted(expected_statuses),
            ready=False,
            error=read_error,
        )
    if status not in expected_statuses:
        return ArtifactEvidence(
            name=name,
            path=_display_path(report_path),
            status=status,
            expected_statuses=sorted(expected_statuses),
            ready=False,
            error=f"expected status {sorted(expected_statuses)}, got {status or '<missing>'}",
        )

    artifact_path = _resolve_artifact_path(_first_string(payload, path_keys), root=root)
    expected_sha = _extract_expected_sha(payload, sha_keys)
    if artifact_path is None:
        return ArtifactEvidence(
            name=name,
            path=_display_path(report_path),
            status=status,
            expected_statuses=sorted(expected_statuses),
            ready=False,
            error=f"missing artifact path field: {', '.join(path_keys)}",
        )
    actual_sha, sha_error = _sha256_file(artifact_path)
    problems: list[str] = []
    if sha_error:
        problems.append(sha_error)
    if not expected_sha or not SHA256_RE.fullmatch(expected_sha):
        problems.append("missing or invalid expected sha256")
    if actual_sha and expected_sha and actual_sha.lower() != expected_sha.lower():
        problems.append("artifact sha256 mismatch")
    return ArtifactEvidence(
        name=name,
        path=_display_path(report_path),
        status=status,
        expected_statuses=sorted(expected_statuses),
        ready=not problems,
        artifact_path=_display_path(artifact_path),
        expected_sha256=expected_sha,
        actual_sha256=actual_sha,
        error="; ".join(problems) if problems else None,
    )


def _source_bundle_evidence(report_path: Path, *, root: Path) -> ArtifactEvidence:
    payload, error = _read_json(report_path)
    return _file_evidence(
        name="source_bundle",
        report_path=report_path,
        payload=payload,
        read_error=error,
        expected_statuses={"created"},
        path_keys=("output_path", "artifact_path", "path"),
        root=root,
        sha_keys=("artifact_sha256", "sha256"),
    )


def _sbom_evidence(report_path: Path, *, root: Path) -> ArtifactEvidence:
    payload, error = _read_json(report_path)
    return _file_evidence(
        name="sbom",
        report_path=report_path,
        payload=payload,
        read_error=error,
        expected_statuses={"sbom_ready", "passed"},
        path_keys=("sbom_path", "output_path", "path"),
        root=root,
    )


def _helm_package_evidence(report_path: Path, *, root: Path) -> ArtifactEvidence:
    payload, error = _read_json(report_path)
    return _file_evidence(
        name="helm_package",
        report_path=report_path,
        payload=payload,
        read_error=error,
        expected_statuses={"helm_package_ready", "passed"},
        path_keys=("helm_package_path", "chart_package_path", "package_path", "output_path", "path"),
        root=root,
    )


def _image_digests_evidence(report_path: Path) -> ArtifactEvidence:
    payload, error = _read_json(report_path)
    expected = {"image_digests_ready", "passed"}
    status = _status(payload)
    if error or payload is None:
        return ArtifactEvidence("image_digests", _display_path(report_path), status, sorted(expected), False, error=error)
    digests = payload.get("image_digests", payload.get("images"))
    if isinstance(digests, dict):
        digest_values = [str(value) for value in digests.values()]
    elif isinstance(digests, list):
        digest_values = []
        for item in digests:
            if isinstance(item, str):
                digest_values.append(item)
            elif isinstance(item, dict):
                value = item.get("digest") or item.get("image_digest") or item.get("sha256")
                if value:
                    digest_values.append(str(value))
    else:
        digest_values = []
    problems: list[str] = []
    if status not in expected:
        problems.append(f"expected status {sorted(expected)}, got {status or '<missing>'}")
    if not digest_values:
        problems.append("missing image digest entries")
    invalid = [value for value in digest_values if not IMAGE_DIGEST_RE.fullmatch(value)]
    if invalid:
        problems.append("invalid image digest format")
    return ArtifactEvidence(
        name="image_digests",
        path=_display_path(report_path),
        status=status,
        expected_statuses=sorted(expected),
        ready=not problems,
        error="; ".join(problems) if problems else None,
    )


def _checksum_entries(payload: dict[str, Any]) -> list[dict[str, Any]]:
    entries = payload.get("checksums")
    if isinstance(entries, dict):
        return [
            {"path": path, "sha256": sha}
            for path, sha in entries.items()
            if isinstance(path, str)
        ]
    if isinstance(entries, list):
        return [entry for entry in entries if isinstance(entry, dict)]
    return []


def _checksums_evidence(report_path: Path, *, root: Path) -> ArtifactEvidence:
    payload, error = _read_json(report_path)
    expected = {"checksums_ready", "passed"}
    status = _status(payload)
    if error or payload is None:
        return ArtifactEvidence("checksums", _display_path(report_path), status, sorted(expected), False, error=error)
    entries = _checksum_entries(payload)
    problems: list[str] = []
    if status not in expected:
        problems.append(f"expected status {sorted(expected)}, got {status or '<missing>'}")
    if not entries:
        problems.append("missing checksum entries")
    mismatches: list[str] = []
    for entry in entries:
        path = _resolve_artifact_path(entry.get("path"), root=root)
        expected_sha = str(entry.get("sha256") or "")
        if path is None:
            mismatches.append("<missing path>")
            continue
        actual_sha, sha_error = _sha256_file(path)
        if sha_error or not SHA256_RE.fullmatch(expected_sha) or actual_sha != expected_sha.lower():
            mismatches.append(_display_path(path))
    if mismatches:
        problems.append(f"checksum mismatch or invalid entry: {', '.join(mismatches)}")
    return ArtifactEvidence(
        name="checksums",
        path=_display_path(report_path),
        status=status,
        expected_statuses=sorted(expected),
        ready=not problems,
        error="; ".join(problems) if problems else None,
    )


def _comparison_path(raw_path: str, *, root: Path) -> Path:
    path = Path(raw_path)
    return path if path.is_absolute() else root / path


def _release_receipt_evidence(report_path: Path, *, source_bundle: ArtifactEvidence, root: Path) -> ArtifactEvidence:
    payload, error = _read_json(report_path)
    expected = {"created"}
    status = _status(payload)
    if error or payload is None:
        return ArtifactEvidence("release_receipt", _display_path(report_path), status, sorted(expected), False, error=error)
    artifact = payload.get("artifact") if isinstance(payload.get("artifact"), dict) else {}
    receipt_sha = str(artifact.get("sha256") or "")
    receipt_path = str(artifact.get("path") or "")
    problems: list[str] = []
    if status not in expected:
        problems.append(f"expected status {sorted(expected)}, got {status or '<missing>'}")
    if not SHA256_RE.fullmatch(receipt_sha):
        problems.append("release receipt artifact sha256 missing or invalid")
    if source_bundle.expected_sha256 and receipt_sha.lower() != source_bundle.expected_sha256.lower():
        problems.append("release receipt sha256 does not match source bundle")
    if source_bundle.artifact_path and receipt_path:
        receipt_artifact_path = _comparison_path(receipt_path, root=root)
        source_artifact_path = _comparison_path(source_bundle.artifact_path, root=root)
        if receipt_artifact_path.resolve() != source_artifact_path.resolve():
            problems.append("release receipt artifact path does not match source bundle")
    return ArtifactEvidence(
        name="release_receipt",
        path=_display_path(report_path),
        status=status,
        expected_statuses=sorted(expected),
        ready=not problems,
        artifact_path=receipt_path or None,
        expected_sha256=source_bundle.expected_sha256,
        actual_sha256=receipt_sha or None,
        error="; ".join(problems) if problems else None,
    )


def _check(name: str, passed: bool, details: dict[str, Any], error: str) -> ArtifactCheck:
    return ArtifactCheck(name=name, status="passed" if passed else "failed", details=details, error=None if passed else error)


def build_artifacts_release_gate(
    *,
    report_dir: Path = REPORT_DIR,
    release_dir: Path = RELEASE_DIR,
    root: Path = ROOT,
    current_head_sha: str | None = None,
    release_sha: str | None = None,
) -> ArtifactsReleaseGateReport:
    resolved_head = current_head_sha or resolve_current_head_sha()
    resolved_release_sha = release_sha or resolved_head

    source_bundle = _source_bundle_evidence(report_dir / "rc-source-bundle.json", root=root)
    evidence = [
        source_bundle,
        _image_digests_evidence(report_dir / "stage5-image-digests-20260615.json"),
        _sbom_evidence(report_dir / "stage5-sbom-20260615.json", root=root),
        _helm_package_evidence(report_dir / "stage5-helm-package-20260615.json", root=root),
        _checksums_evidence(report_dir / "stage5-artifact-checksums-20260615.json", root=root),
        _release_receipt_evidence(
            release_dir / "x-agent-commercial-rc-receipt.json",
            source_bundle=source_bundle,
            root=root,
        ),
    ]
    missing_or_mismatched = [item.name for item in evidence if not item.ready]
    all_evidence_ready = not missing_or_mismatched
    source_release_sha_ready = resolved_release_sha is not None
    ready = all_evidence_ready and source_release_sha_ready
    status = "artifacts_release_ready" if ready else "artifacts_release_blocked"
    checks = [
        _check(
            "required_artifact_evidence_ready",
            all_evidence_ready,
            {"missing_or_mismatched": missing_or_mismatched},
            "required release artifact evidence is missing or mismatched",
        ),
        _check(
            "release_sha_resolved",
            source_release_sha_ready,
            {"current_head_sha": resolved_head, "release_sha": resolved_release_sha},
            "release SHA could not be resolved",
        ),
        _check(
            "gate_has_no_release_side_effects",
            True,
            {"mutation_performed": False, "outbound_message_sent": False, "deploy_tag_release_performed": False},
            "gate attempted a release side effect",
        ),
    ]
    return ArtifactsReleaseGateReport(
        status=status,
        generated_at=_utc_now(),
        current_head_sha=resolved_head,
        release_sha=resolved_release_sha,
        artifacts_release_ready=ready,
        mutation_performed=False,
        outbound_message_sent=False,
        deploy_tag_release_performed=False,
        evidence=evidence,
        checks=checks,
        missing_or_mismatched=missing_or_mismatched,
        next_actions=[
            f"Produce or refresh real artifact evidence for {name}."
            for name in missing_or_mismatched
        ]
        or ["Archive this JSON and Markdown report with the release packet."],
        known_limits=[
            "This gate validates artifact evidence only; it does not build, push, deploy, tag, or publish.",
            "Image digest evidence is validated as immutable sha256 digests; registry reachability remains an external owner gate.",
        ],
    )


def render_markdown_report(report: ArtifactsReleaseGateReport) -> str:
    evidence_lines = "\n".join(
        f"- {item.name}: `{item.status or '<missing>'}` / ready `{item.ready}`"
        + (f" / error: {item.error}" if item.error else "")
        for item in report.evidence
    )
    checks = "\n".join(
        f"- {check.name}: `{check.status}`" + (f" - {check.error}" if check.error else "")
        for check in report.checks
    )
    missing = "\n".join(f"- {name}" for name in report.missing_or_mismatched) or "- none"
    return (
        "# Stage 5 Artifacts Release Gate\n\n"
        f"- Status: `{report.status}`\n"
        f"- Ready: `{report.artifacts_release_ready}`\n"
        f"- Current head SHA: `{report.current_head_sha or '<missing>'}`\n"
        f"- Release SHA: `{report.release_sha or '<missing>'}`\n"
        f"- Generated at: `{report.generated_at}`\n"
        f"- Mutation performed: `{report.mutation_performed}`\n"
        f"- Outbound message sent: `{report.outbound_message_sent}`\n"
        f"- Deploy/tag/release performed: `{report.deploy_tag_release_performed}`\n\n"
        "## Evidence\n\n"
        f"{evidence_lines}\n\n"
        "## Missing Or Mismatched\n\n"
        f"{missing}\n\n"
        "## Checks\n\n"
        f"{checks}\n"
    )


def write_report(report: ArtifactsReleaseGateReport, output_path: Path = DEFAULT_OUTPUT_JSON) -> None:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(report.to_dict(), ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def write_markdown_report(report: ArtifactsReleaseGateReport, output_path: Path = DEFAULT_OUTPUT_MD) -> None:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(render_markdown_report(report), encoding="utf-8")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Validate Stage 5 release artifact evidence.")
    parser.add_argument("--report-dir", type=Path, default=REPORT_DIR)
    parser.add_argument("--release-dir", type=Path, default=RELEASE_DIR)
    parser.add_argument("--root", type=Path, default=ROOT)
    parser.add_argument("--current-head-sha", default=None)
    parser.add_argument("--release-sha", default=None)
    parser.add_argument("--output-json", type=Path, default=DEFAULT_OUTPUT_JSON)
    parser.add_argument("--output-md", type=Path, default=DEFAULT_OUTPUT_MD)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    report = build_artifacts_release_gate(
        report_dir=args.report_dir,
        release_dir=args.release_dir,
        root=args.root,
        current_head_sha=args.current_head_sha,
        release_sha=args.release_sha,
    )
    write_report(report, args.output_json)
    write_markdown_report(report, args.output_md)
    print(f"Stage 5 artifacts release gate status: {report.status}")
    print(f"Release SHA: {report.release_sha or '<missing>'}")
    print(f"Missing or mismatched: {', '.join(report.missing_or_mismatched) or '<none>'}")
    print(f"JSON report written to {args.output_json}")
    print(f"Markdown report written to {args.output_md}")
    for check in report.checks:
        print(f"- {check.name}: {check.status}")
        if check.error:
            print(f"  error: {check.error}")
    return 0 if report.artifacts_release_ready else 1


if __name__ == "__main__":
    raise SystemExit(main())
