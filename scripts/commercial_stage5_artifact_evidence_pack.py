#!/usr/bin/env python3
"""Build a Stage 5 artifact evidence pack for controlled commercial pilot readiness.

This producer is intentionally fail-closed and read-only. It summarizes release
artifact evidence without building, deploying, tagging, publishing, or claiming
that a release has been performed.
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
DEFAULT_OUTPUT_JSON = REPORT_DIR / "stage5-artifact-evidence-pack-20260615.json"
DEFAULT_OUTPUT_MD = REPORT_DIR / "stage5-artifact-evidence-pack-20260615.md"

SHA256_RE = re.compile(r"^[a-fA-F0-9]{64}$")
IMAGE_DIGEST_RE = re.compile(r"^sha256:[a-fA-F0-9]{64}$")


@dataclass(frozen=True)
class EvidenceItem:
    name: str
    status: str
    ready: bool
    source_path: str
    current_head_sha: str | None = None
    release_sha: str | None = None
    artifact_path: str | None = None
    expected_sha256: str | None = None
    actual_sha256: str | None = None
    details: dict[str, Any] = field(default_factory=dict)
    error: str | None = None


@dataclass(frozen=True)
class EvidenceCheck:
    name: str
    status: str
    details: dict[str, Any] = field(default_factory=dict)
    error: str | None = None


@dataclass(frozen=True)
class ArtifactEvidencePack:
    status: str
    generated_at: str
    current_head_sha: str | None
    release_sha: str | None
    controlled_commercial_pilot_ready: bool
    production_ready: bool
    ga_ready: bool
    deploy_performed: bool
    tag_performed: bool
    release_performed: bool
    mutation_performed: bool
    evidence: list[EvidenceItem]
    checks: list[EvidenceCheck]
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


def _run_git(args: list[str], *, root: Path) -> tuple[str | None, str | None]:
    try:
        completed = subprocess.run(
            ["git", *args],
            cwd=root,
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


def resolve_current_head_sha(root: Path = ROOT) -> str | None:
    value, error = _run_git(["rev-parse", "HEAD"], root=root)
    return None if error else value


def _display_path(path: Path, *, root: Path) -> str:
    try:
        return str(path.resolve().relative_to(root.resolve()))
    except ValueError:
        return str(path.resolve())


def _read_json(path: Path, *, root: Path) -> tuple[dict[str, Any] | None, str | None]:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError:
        return None, f"missing report: {_display_path(path, root=root)}"
    except (OSError, json.JSONDecodeError) as exc:
        return None, f"could not read report {_display_path(path, root=root)}: {exc}"
    if not isinstance(payload, dict):
        return None, f"report is not a JSON object: {_display_path(path, root=root)}"
    return payload, None


def _sha256_file(path: Path, *, root: Path) -> tuple[str | None, str | None]:
    try:
        digest = hashlib.sha256()
        with path.open("rb") as handle:
            for chunk in iter(lambda: handle.read(1024 * 1024), b""):
                digest.update(chunk)
    except FileNotFoundError:
        return None, f"artifact file missing: {_display_path(path, root=root)}"
    except OSError as exc:
        return None, f"could not read artifact file {_display_path(path, root=root)}: {exc}"
    return digest.hexdigest(), None


def _status(payload: dict[str, Any] | None) -> str | None:
    if not payload:
        return None
    value = payload.get("status") or payload.get("package_status") or payload.get("report")
    return str(value) if value is not None else None


def _first_string(payload: dict[str, Any], keys: tuple[str, ...]) -> str | None:
    for key in keys:
        value = payload.get(key)
        if isinstance(value, str) and value:
            return value
    artifact = payload.get("artifact")
    if isinstance(artifact, dict):
        for key in keys:
            value = artifact.get(key)
            if isinstance(value, str) and value:
                return value
    return None


def _version_value(payload: dict[str, Any], key: str) -> str | None:
    version_identity = payload.get("version_identity")
    if isinstance(version_identity, dict):
        value = version_identity.get(key)
        if isinstance(value, str) and value:
            return value
    value = payload.get(key)
    return value if isinstance(value, str) and value else None


def _current_head_sha(payload: dict[str, Any]) -> str | None:
    return (
        _version_value(payload, "current_head_sha")
        or _version_value(payload, "head_sha")
        or _version_value(payload, "commit_sha")
    )


def _release_sha(payload: dict[str, Any]) -> str | None:
    return _version_value(payload, "release_sha") or _current_head_sha(payload)


def _sha_binding_errors(
    payload: dict[str, Any],
    *,
    current_head_sha: str | None,
    release_sha: str | None,
) -> tuple[str | None, str | None, list[str]]:
    evidence_head = _current_head_sha(payload)
    evidence_release = _release_sha(payload)
    problems: list[str] = []
    if not evidence_head:
        problems.append("current_head_sha missing")
    elif current_head_sha and evidence_head != current_head_sha:
        problems.append("current_head_sha does not match selected head")
    if not evidence_release:
        problems.append("release_sha missing")
    elif release_sha and evidence_release != release_sha:
        problems.append("release_sha does not match selected release SHA")
    return evidence_head, evidence_release, problems


def _resolve_path(raw_path: Any, *, root: Path) -> Path | None:
    if not isinstance(raw_path, str) or not raw_path:
        return None
    path = Path(raw_path)
    return path if path.is_absolute() else root / path


def _file_evidence(
    *,
    name: str,
    report_path: Path,
    root: Path,
    expected_statuses: set[str],
    path_keys: tuple[str, ...],
    sha_keys: tuple[str, ...],
    current_head_sha: str | None,
    release_sha: str | None,
) -> EvidenceItem:
    payload, read_error = _read_json(report_path, root=root)
    status = _status(payload) or "missing"
    if read_error or payload is None:
        return EvidenceItem(name, status, False, _display_path(report_path, root=root), error=read_error)
    problems: list[str] = []
    evidence_head, evidence_release, sha_problems = _sha_binding_errors(
        payload,
        current_head_sha=current_head_sha,
        release_sha=release_sha,
    )
    problems.extend(sha_problems)
    if status not in expected_statuses:
        problems.append(f"expected status {sorted(expected_statuses)}, got {status}")
    artifact_path = _resolve_path(_first_string(payload, path_keys), root=root)
    expected_sha = _first_string(payload, sha_keys)
    actual_sha: str | None = None
    if artifact_path is None:
        problems.append(f"missing artifact path field: {', '.join(path_keys)}")
    else:
        actual_sha, sha_error = _sha256_file(artifact_path, root=root)
        if sha_error:
            problems.append(sha_error)
    if not expected_sha or not SHA256_RE.fullmatch(expected_sha):
        problems.append("missing or invalid expected sha256")
    if actual_sha and expected_sha and actual_sha.lower() != expected_sha.lower():
        problems.append("sha256 mismatch")
    return EvidenceItem(
        name=name,
        status=status,
        ready=not problems,
        source_path=_display_path(report_path, root=root),
        current_head_sha=evidence_head,
        release_sha=evidence_release,
        artifact_path=_display_path(artifact_path, root=root) if artifact_path else None,
        expected_sha256=expected_sha,
        actual_sha256=actual_sha,
        details={"expected_statuses": sorted(expected_statuses)},
        error="; ".join(problems) if problems else None,
    )


def _image_digest_evidence(
    report_path: Path,
    *,
    root: Path,
    current_head_sha: str | None,
    release_sha: str | None,
) -> EvidenceItem:
    payload, read_error = _read_json(report_path, root=root)
    status = _status(payload) or "missing"
    if read_error or payload is None:
        return EvidenceItem("image_digests", status, False, _display_path(report_path, root=root), error=read_error)
    evidence_head, evidence_release, problems = _sha_binding_errors(
        payload,
        current_head_sha=current_head_sha,
        release_sha=release_sha,
    )
    digests = payload.get("image_digests", payload.get("images"))
    digest_values: list[str] = []
    if isinstance(digests, dict):
        digest_values = [str(value) for value in digests.values()]
    elif isinstance(digests, list):
        for item in digests:
            if isinstance(item, str):
                digest_values.append(item)
            elif isinstance(item, dict):
                value = item.get("digest") or item.get("image_digest") or item.get("sha256")
                if value:
                    digest_values.append(str(value))
    expected_statuses = {"image_digests_ready", "passed"}
    if status not in expected_statuses:
        problems.append(f"expected status {sorted(expected_statuses)}, got {status}")
    if not digest_values:
        problems.append("missing image digest entries")
    invalid = [value for value in digest_values if not IMAGE_DIGEST_RE.fullmatch(value)]
    if invalid:
        problems.append("invalid image digest format")
    return EvidenceItem(
        name="image_digests",
        status=status,
        ready=not problems,
        source_path=_display_path(report_path, root=root),
        current_head_sha=evidence_head,
        release_sha=evidence_release,
        details={"expected_statuses": sorted(expected_statuses), "image_count": len(digest_values)},
        error="; ".join(problems) if problems else None,
    )


def _checksum_entries(payload: dict[str, Any]) -> list[dict[str, Any]]:
    entries = payload.get("checksums")
    if isinstance(entries, dict):
        return [{"path": path, "sha256": sha} for path, sha in entries.items() if isinstance(path, str)]
    if isinstance(entries, list):
        return [entry for entry in entries if isinstance(entry, dict)]
    return []


def _checksums_evidence(
    report_path: Path,
    *,
    root: Path,
    current_head_sha: str | None,
    release_sha: str | None,
) -> EvidenceItem:
    payload, read_error = _read_json(report_path, root=root)
    status = _status(payload) or "missing"
    if read_error or payload is None:
        return EvidenceItem("checksums", status, False, _display_path(report_path, root=root), error=read_error)
    entries = _checksum_entries(payload)
    expected_statuses = {"checksums_ready", "passed"}
    evidence_head, evidence_release, problems = _sha_binding_errors(
        payload,
        current_head_sha=current_head_sha,
        release_sha=release_sha,
    )
    mismatches: list[str] = []
    if status not in expected_statuses:
        problems.append(f"expected status {sorted(expected_statuses)}, got {status}")
    if not entries:
        problems.append("missing checksum entries")
    for entry in entries:
        artifact_path = _resolve_path(entry.get("path"), root=root)
        expected_sha = str(entry.get("sha256") or "")
        if artifact_path is None:
            mismatches.append("<missing path>")
            continue
        actual_sha, sha_error = _sha256_file(artifact_path, root=root)
        if sha_error or not SHA256_RE.fullmatch(expected_sha) or actual_sha != expected_sha.lower():
            mismatches.append(_display_path(artifact_path, root=root))
    if mismatches:
        problems.append(f"checksum mismatch or invalid entry: {', '.join(mismatches)}")
    return EvidenceItem(
        name="checksums",
        status=status,
        ready=not problems,
        source_path=_display_path(report_path, root=root),
        current_head_sha=evidence_head,
        release_sha=evidence_release,
        details={"expected_statuses": sorted(expected_statuses), "checksum_count": len(entries)},
        error="; ".join(problems) if problems else None,
    )


def _check(name: str, passed: bool, details: dict[str, Any], error: str) -> EvidenceCheck:
    return EvidenceCheck(name, "passed" if passed else "failed", details, None if passed else error)


def build_artifact_evidence_pack(
    *,
    report_dir: Path = REPORT_DIR,
    release_dir: Path = RELEASE_DIR,
    root: Path = ROOT,
    current_head_sha: str | None = None,
    release_sha: str | None = None,
) -> ArtifactEvidencePack:
    resolved_head = current_head_sha or resolve_current_head_sha(root)
    resolved_release_sha = release_sha or resolved_head
    evidence = [
        _file_evidence(
            name="source_bundle",
            report_path=report_dir / "rc-source-bundle.json",
            root=root,
            expected_statuses={"created"},
            path_keys=("output_path", "artifact_path", "path"),
            sha_keys=("expected_sha256", "artifact_sha256", "sha256"),
            current_head_sha=resolved_head,
            release_sha=resolved_release_sha,
        ),
        _image_digest_evidence(
            report_dir / "stage5-image-digests-20260615.json",
            root=root,
            current_head_sha=resolved_head,
            release_sha=resolved_release_sha,
        ),
        _file_evidence(
            name="sbom",
            report_path=report_dir / "stage5-sbom-20260615.json",
            root=root,
            expected_statuses={"sbom_ready", "passed"},
            path_keys=("sbom_path", "output_path", "path"),
            sha_keys=("expected_sha256", "sha256", "artifact_sha256"),
            current_head_sha=resolved_head,
            release_sha=resolved_release_sha,
        ),
        _file_evidence(
            name="helm_package",
            report_path=report_dir / "stage5-helm-package-20260615.json",
            root=root,
            expected_statuses={"helm_package_ready", "passed"},
            path_keys=("helm_package_path", "chart_package_path", "package_path", "output_path", "path"),
            sha_keys=("expected_sha256", "sha256", "artifact_sha256"),
            current_head_sha=resolved_head,
            release_sha=resolved_release_sha,
        ),
        _checksums_evidence(
            report_dir / "stage5-artifact-checksums-20260615.json",
            root=root,
            current_head_sha=resolved_head,
            release_sha=resolved_release_sha,
        ),
    ]
    missing_or_mismatched = [item.name for item in evidence if not item.ready]
    evidence_ready = not missing_or_mismatched
    release_sha_bound = bool(resolved_head and resolved_release_sha and resolved_release_sha == resolved_head)
    evidence_sha_bound = all(
        item.current_head_sha == resolved_head and item.release_sha == resolved_release_sha
        for item in evidence
    )
    ready = evidence_ready and release_sha_bound and evidence_sha_bound
    checks = [
        _check(
            "release_sha_bound",
            release_sha_bound,
            {"current_head_sha": resolved_head, "release_sha": resolved_release_sha},
            "release SHA could not be resolved or does not match current head",
        ),
        _check(
            "artifact_evidence_bound_to_release_sha",
            evidence_sha_bound,
            {
                "current_head_sha": resolved_head,
                "release_sha": resolved_release_sha,
                "evidence_current_head_shas": {item.name: item.current_head_sha for item in evidence},
                "evidence_release_shas": {item.name: item.release_sha for item in evidence},
            },
            "artifact evidence reports are not bound to the selected release SHA",
        ),
        _check(
            "required_artifact_evidence_ready",
            evidence_ready,
            {"missing_or_mismatched": missing_or_mismatched},
            "required artifact evidence is missing or mismatched",
        ),
        _check(
            "no_release_side_effects",
            True,
            {"deploy_performed": False, "tag_performed": False, "release_performed": False, "mutation_performed": False},
            "artifact evidence pack attempted a release side effect",
        ),
    ]
    return ArtifactEvidencePack(
        status="artifact_evidence_pack_ready" if ready else "artifact_evidence_pack_blocked",
        generated_at=_utc_now(),
        current_head_sha=resolved_head,
        release_sha=resolved_release_sha,
        controlled_commercial_pilot_ready=ready,
        production_ready=False,
        ga_ready=False,
        deploy_performed=False,
        tag_performed=False,
        release_performed=False,
        mutation_performed=False,
        evidence=evidence,
        checks=checks,
        missing_or_mismatched=missing_or_mismatched,
        next_actions=[
            f"Produce or refresh real Stage 5 artifact evidence for {name}."
            for name in missing_or_mismatched
        ]
        or ["Attach this evidence pack to the controlled commercial pilot release packet."],
        known_limits=[
            "Read-only evidence pack; it does not deploy, tag, publish, push images, or create a release.",
            "Ready means controlled commercial pilot artifact evidence is present for the bound SHA only.",
            "This report does not claim GA readiness, production readiness, or full commercial delivery.",
        ],
    )


def render_markdown_report(pack: ArtifactEvidencePack) -> str:
    evidence_lines = "\n".join(
        f"- {item.name}: `{item.status}` / ready `{item.ready}`"
        + (f" / error: {item.error}" if item.error else "")
        for item in pack.evidence
    )
    checks = "\n".join(
        f"- {check.name}: `{check.status}`" + (f" - {check.error}" if check.error else "")
        for check in pack.checks
    )
    missing = "\n".join(f"- {name}" for name in pack.missing_or_mismatched) or "- none"
    return (
        "# Stage 5 Artifact Evidence Pack\n\n"
        f"- Status: `{pack.status}`\n"
        f"- Controlled commercial pilot ready: `{pack.controlled_commercial_pilot_ready}`\n"
        f"- Production ready: `{pack.production_ready}`\n"
        f"- GA ready: `{pack.ga_ready}`\n"
        f"- Current head SHA: `{pack.current_head_sha or '<missing>'}`\n"
        f"- Release SHA: `{pack.release_sha or '<missing>'}`\n"
        f"- Deploy performed: `{pack.deploy_performed}`\n"
        f"- Tag performed: `{pack.tag_performed}`\n"
        f"- Release performed: `{pack.release_performed}`\n\n"
        "## Evidence\n\n"
        f"{evidence_lines}\n\n"
        "## Missing Or Mismatched\n\n"
        f"{missing}\n\n"
        "## Checks\n\n"
        f"{checks}\n"
    )


def write_report(pack: ArtifactEvidencePack, output_path: Path = DEFAULT_OUTPUT_JSON) -> None:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(pack.to_dict(), ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def write_markdown_report(pack: ArtifactEvidencePack, output_path: Path = DEFAULT_OUTPUT_MD) -> None:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(render_markdown_report(pack), encoding="utf-8")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build a read-only Stage 5 artifact evidence pack.")
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
    pack = build_artifact_evidence_pack(
        report_dir=args.report_dir,
        release_dir=args.release_dir,
        root=args.root,
        current_head_sha=args.current_head_sha,
        release_sha=args.release_sha,
    )
    write_report(pack, args.output_json)
    write_markdown_report(pack, args.output_md)
    print(f"Stage 5 artifact evidence pack status: {pack.status}")
    print(f"Release SHA: {pack.release_sha or '<missing>'}")
    print(f"Missing or mismatched: {', '.join(pack.missing_or_mismatched) or '<none>'}")
    print(f"Deploy/tag/release performed: {pack.deploy_performed}/{pack.tag_performed}/{pack.release_performed}")
    print(f"JSON report written to {args.output_json}")
    print(f"Markdown report written to {args.output_md}")
    return 0 if pack.controlled_commercial_pilot_ready else 1


if __name__ == "__main__":
    raise SystemExit(main())
