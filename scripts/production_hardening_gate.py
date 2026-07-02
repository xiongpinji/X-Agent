#!/usr/bin/env python3
"""Fail-closed production configuration hardening gate.

This gate is intentionally read-only. It scans deployment configuration for
known production hardening hazards, writes a JSON report, and does not repair
Docker, Helm, Kubernetes, or secret manifests.
"""

from __future__ import annotations

import argparse
import json
import re
from dataclasses import asdict, dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from typing import Iterable

ROOT = Path(__file__).resolve().parents[1]
REPORT_DIR = ROOT / ".xagent_runtime" / "reports"
DEFAULT_OUTPUT = REPORT_DIR / "production-hardening-gate.json"
READY_STATUS = "ready"
BLOCKED_STATUS = "blocked"
DEFAULT_MODE = "report-only"

PRODUCTION_EXTENSIONS = {".yaml", ".yml", ".env", ".conf", ".ini", ".txt"}
PLACEHOLDER_SECRET_MARKERS = (
    "change-me-in-production",
    "placeholder",
    "changeme",
    "change_me",
)
TRUTHY_VALUES = {"true", "1", "yes", "y", "on", "enabled"}


@dataclass(frozen=True)
class Finding:
    rule: str
    path: str
    line: int
    severity: str
    message: str
    evidence: str


@dataclass(frozen=True)
class RuleSummary:
    name: str
    status: str
    finding_count: int
    description: str


@dataclass(frozen=True)
class ProductionHardeningReport:
    status: str
    generated_at: str
    evidence_type: str
    mode: str
    production_hardened: bool
    read_only: bool
    mutation_performed: bool
    deploy_config_modified: bool
    secret_written: bool
    scanned_paths: list[str]
    rules: list[RuleSummary]
    findings: list[Finding]
    blocking_reasons: list[str]
    claim_boundary: dict[str, object] = field(default_factory=dict)
    next_actions: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, object]:
        return asdict(self)


def _utc_now() -> str:
    return datetime.now(UTC).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _display_path(path: Path, root: Path) -> str:
    try:
        return str(path.resolve().relative_to(root.resolve())).replace("\\", "/")
    except ValueError:
        return str(path.resolve()).replace("\\", "/")


def _iter_existing(paths: Iterable[Path]) -> list[Path]:
    return sorted(dict.fromkeys(path for path in paths if path.exists()))


def default_scan_paths(root: Path = ROOT) -> list[Path]:
    deployment = root / "deployment"
    paths: list[Path] = []
    paths.extend(
        [
            root / "docker-compose.yml",
            root / "docker-compose.yaml",
        ]
    )
    if deployment.exists():
        for extension in PRODUCTION_EXTENSIONS:
            paths.extend(deployment.rglob(f"*{extension}"))
    return _iter_existing(path for path in paths if path.is_file())


def _read_lines(path: Path) -> list[str]:
    try:
        return path.read_text(encoding="utf-8").splitlines()
    except UnicodeDecodeError:
        return path.read_text(encoding="utf-8", errors="replace").splitlines()


def _is_comment(line: str) -> bool:
    return line.lstrip().startswith("#")


def _finding(rule: str, path: Path, root: Path, line_number: int, message: str, evidence: str) -> Finding:
    return Finding(
        rule=rule,
        path=_display_path(path, root),
        line=line_number,
        severity="blocking",
        message=message,
        evidence=evidence.strip(),
    )


def _no_scan_finding(root: Path) -> Finding:
    return Finding(
        rule="no_production_config_scanned",
        path=_display_path(root, root),
        line=0,
        severity="blocking",
        message="Production hardening gate must scan at least one deployment configuration file.",
        evidence="scanned_paths: <none>",
    )


def _scan_latest_images(path: Path, root: Path, lines: list[str]) -> list[Finding]:
    findings: list[Finding] = []
    for line_number, line in enumerate(lines, start=1):
        if _is_comment(line):
            continue
        if re.search(r":latest(?:\s|$|[\"'#])", line):
            findings.append(
                _finding(
                    "no_latest_images",
                    path,
                    root,
                    line_number,
                    "Production deployment configuration must pin image tags instead of using :latest.",
                    line,
                )
            )
    return findings


def _redact_secret_evidence(line: str) -> str:
    key_value = re.match(r"^(\s*-?\s*[A-Za-z0-9_.-]+\s*[:=]\s*)(.*?)(\s+#.*)?$", line)
    if key_value:
        prefix = key_value.group(1).strip()
        return f"{prefix} <redacted>"
    return "<redacted secret evidence>"


def _scan_placeholder_secrets(path: Path, root: Path, lines: list[str]) -> list[Finding]:
    if "secret" not in path.name.lower():
        return []
    findings: list[Finding] = []
    for line_number, line in enumerate(lines, start=1):
        if _is_comment(line):
            continue
        lower = line.lower()
        if any(marker in lower for marker in PLACEHOLDER_SECRET_MARKERS):
            findings.append(
                _finding(
                    "no_placeholder_production_secrets",
                    path,
                    root,
                    line_number,
                    "Production Secret manifests must not track placeholder secret values.",
                    _redact_secret_evidence(line),
                )
            )
    return findings


def _scan_api_key_required(path: Path, root: Path, lines: list[str]) -> list[Finding]:
    findings: list[Finding] = []
    pending_key_line: int | None = None
    pending_key_text = ""
    for line_number, line in enumerate(lines, start=1):
        if _is_comment(line):
            continue
        if "XAGENT_REQUIRE_API_KEY" in line:
            if re.search(r"\$\{XAGENT_REQUIRE_API_KEY:-\s*false\s*\}", line, re.IGNORECASE) or re.search(
                r"XAGENT_REQUIRE_API_KEY\s*[:=]\s*[\"']?false[\"']?(?:\s|$|#)",
                line,
                re.IGNORECASE,
            ):
                findings.append(
                    _finding(
                        "require_api_key_default_true",
                        path,
                        root,
                        line_number,
                        "Production API key enforcement must not default to false.",
                        line,
                    )
                )
            pending_key_line = line_number
            pending_key_text = line
            continue
        if pending_key_line is not None:
            if re.match(r"\s*(value|default)\s*:\s*[\"']?false[\"']?(?:\s|$|#)", line, re.IGNORECASE):
                findings.append(
                    _finding(
                        "require_api_key_default_true",
                        path,
                        root,
                        line_number,
                        "Production API key enforcement must not default to false.",
                        f"{pending_key_text} / {line}",
                    )
                )
            if line and not line.startswith((" ", "\t", "-")):
                pending_key_line = None
                pending_key_text = ""
    return findings


def _truthy_default_pattern(name: str) -> re.Pattern[str]:
    truthy = "|".join(sorted(TRUTHY_VALUES))
    return re.compile(rf"\$\{{{re.escape(name)}:-\s*(?:{truthy})\s*\}}", re.IGNORECASE)


def _scan_trust_all_certificates(path: Path, root: Path, lines: list[str]) -> list[Finding]:
    findings: list[Finding] = []
    direct_pattern = re.compile(
        r"TRUST_ALL_CERTIFICATES\s*[:=]\s*[\"']?(true|1|yes|y|on|enabled)[\"']?(?:\s|$|#)",
        re.IGNORECASE,
    )
    default_pattern = _truthy_default_pattern("TRUST_ALL_CERTIFICATES")
    for line_number, line in enumerate(lines, start=1):
        if _is_comment(line):
            continue
        compact = line.strip()
        lower = compact.lower()
        risky_neo4j_trust = lower.startswith("trust:") and "trust_all_certificates" in lower
        if direct_pattern.search(line) or default_pattern.search(line) or risky_neo4j_trust:
            findings.append(
                _finding(
                    "no_trust_all_certificates",
                    path,
                    root,
                    line_number,
                    "Production deployment configuration must not enable or default to TRUST_ALL_CERTIFICATES.",
                    line,
                )
            )
    return findings


def scan_path(path: Path, root: Path) -> list[Finding]:
    lines = _read_lines(path)
    findings: list[Finding] = []
    findings.extend(_scan_latest_images(path, root, lines))
    findings.extend(_scan_placeholder_secrets(path, root, lines))
    findings.extend(_scan_api_key_required(path, root, lines))
    findings.extend(_scan_trust_all_certificates(path, root, lines))
    return findings


def _rule_summaries(findings: list[Finding]) -> list[RuleSummary]:
    descriptions = {
        "no_production_config_scanned": "Require at least one production deployment configuration file to be scanned.",
        "no_latest_images": "Disallow :latest image tags in production deployment configuration.",
        "no_placeholder_production_secrets": "Disallow placeholder values in production Secret manifests.",
        "require_api_key_default_true": "Disallow production defaults that turn API key enforcement off.",
        "no_trust_all_certificates": "Disallow TRUST_ALL_CERTIFICATES being enabled or default-enabled in production config.",
    }
    return [
        RuleSummary(
            name=name,
            status=BLOCKED_STATUS if count else READY_STATUS,
            finding_count=count,
            description=description,
        )
        for name, description in descriptions.items()
        for count in [sum(1 for finding in findings if finding.rule == name)]
    ]


def _next_actions(findings: list[Finding]) -> list[str]:
    if not findings:
        return ["Keep this gate read-only and wire it into CI after owner approval."]
    rules = sorted({finding.rule for finding in findings})
    return [f"Owner must remediate production hardening rule: {rule}." for rule in rules]


def build_production_hardening_report(
    *,
    root: Path = ROOT,
    output_path: Path = DEFAULT_OUTPUT,
    scan_paths: list[Path] | None = None,
    mode: str = DEFAULT_MODE,
) -> ProductionHardeningReport:
    root = root.resolve()
    paths = scan_paths if scan_paths is not None else default_scan_paths(root)
    findings: list[Finding] = []
    if paths:
        for path in paths:
            findings.extend(scan_path(path, root))
    else:
        findings.append(_no_scan_finding(root))
    blocking_reasons = sorted({finding.rule for finding in findings})
    status = BLOCKED_STATUS if blocking_reasons else READY_STATUS
    return ProductionHardeningReport(
        status=status,
        generated_at=_utc_now(),
        evidence_type="production_hardening_gate",
        mode=mode,
        production_hardened=status == READY_STATUS,
        read_only=True,
        mutation_performed=False,
        deploy_config_modified=False,
        secret_written=False,
        scanned_paths=[_display_path(path, root) for path in paths],
        rules=_rule_summaries(findings),
        findings=findings,
        blocking_reasons=blocking_reasons,
        claim_boundary={
            "allowed_when_blocked": "report current production hardening blockers only",
            "forbidden_when_blocked": [
                "production hardened",
                "production ready",
                "commercial delivery complete",
                "deployment configuration remediated",
                "secret values rotated",
            ],
            "output_path": _display_path(output_path, root),
        },
        next_actions=_next_actions(findings),
    )


def write_report(report: ProductionHardeningReport, output_path: Path = DEFAULT_OUTPUT) -> None:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(
        json.dumps(report.to_dict(), ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=ROOT)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--mode", choices=[DEFAULT_MODE], default=DEFAULT_MODE)
    parser.add_argument(
        "--allow-blocked",
        action="store_true",
        help="Return success after writing a blocked report.",
    )
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    report = build_production_hardening_report(
        root=args.root,
        output_path=args.output,
        mode=args.mode,
    )
    write_report(report, args.output)
    print(f"Production hardening gate status: {report.status}")
    print(f"Production hardened: {report.production_hardened}")
    print(f"Findings: {len(report.findings)}")
    print(f"Blocking reasons: {', '.join(report.blocking_reasons) or '<none>'}")
    print(f"Report written to {args.output}")
    return 0 if report.production_hardened or args.allow_blocked else 1


if __name__ == "__main__":
    raise SystemExit(main())
