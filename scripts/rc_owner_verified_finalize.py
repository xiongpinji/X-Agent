#!/usr/bin/env python3
"""Run the strict owner-verified commercial RC finalization chain.

This script is intentionally a thin orchestrator over the existing RC gates. It
does not create git tags and it does not relax any owner-controlled checks. Its
job is to run the fixed-point owner-verified refresh chain, then summarize the
tag-readiness report without re-running ``rc_final_gate.py`` out of order.
"""

from __future__ import annotations

import argparse
import json
import os
import re
import subprocess
import sys
from dataclasses import asdict, dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
REPORT_DIR = ROOT / ".xagent_runtime" / "reports"
RELEASE_DIR = ROOT / ".xagent_runtime" / "release"
DEFAULT_OUTPUT = REPORT_DIR / "rc-owner-verified-finalize.json"
DEFAULT_REFRESH_CHAIN = REPORT_DIR / "rc-refresh-release-chain.json"
DEFAULT_FINAL_GATE = REPORT_DIR / "rc-final-gate.json"
DEFAULT_EVIDENCE_PACK = REPORT_DIR / "rc-evidence-pack.json"
DEFAULT_RECEIPT = RELEASE_DIR / "x-agent-commercial-rc-receipt.json"
EXAMPLE_RC_TAG_NAME = "x-agent-commercial-rc-20260608"

PROVIDER_CHOICES = ("openai", "deepseek", "anthropic", "ollama", "local")
SAFE_ENV_NAMES = frozenset(
    {
        "XAGENT_LLM_BACKEND",
        "LLM_BACKEND",
        "XAGENT_OPENAI_API_KEY",
        "OPENAI_API_KEY",
        "XAGENT_OPENAI_MODEL",
        "OPENAI_MODEL",
        "XAGENT_OPENAI_BASE_URL",
        "OPENAI_BASE_URL",
        "XAGENT_DEEPSEEK_API_KEY",
        "DEEPSEEK_API_KEY",
        "XAGENT_DEEPSEEK_MODEL",
        "DEEPSEEK_MODEL",
        "XAGENT_DEEPSEEK_BASE_URL",
        "DEEPSEEK_BASE_URL",
        "XAGENT_ANTHROPIC_API_KEY",
        "ANTHROPIC_API_KEY",
        "XAGENT_ANTHROPIC_MODEL",
        "ANTHROPIC_MODEL",
        "XAGENT_OLLAMA_BASE_URL",
        "OLLAMA_BASE_URL",
        "XAGENT_OLLAMA_MODEL",
        "OLLAMA_MODEL",
        "XAGENT_FEISHU_APP_ID",
        "FEISHU_APP_ID",
        "XAGENT_FEISHU_APP_SECRET",
        "FEISHU_APP_SECRET",
        "XAGENT_FEISHU_ENCRYPT_KEY",
        "FEISHU_ENCRYPT_KEY",
        "XAGENT_GITHUB_TEST_ISSUE_URL",
        "GITHUB_TEST_ISSUE_URL",
        "XAGENT_GITHUB_TOKEN",
        "GITHUB_TOKEN",
        "XAGENT_COMMERCIAL_RC_GITHUB_ACTIONS_RUN_URL",
        "XAGENT_COMMERCIAL_RC_GITHUB_ACTIONS_HEAD_SHA",
    }
)
SECRET_KEY_OUTPUT_RE = re.compile(r"(?i)(\b[A-Z0-9_]*(?:api[_-]?key|token|secret|password)\b\s*[:=]\s*).+")
SECRET_VALUE_OUTPUT_RE = re.compile(r"\b(?:sk|ghp|github_pat|xagent)[_-][A-Za-z0-9_=-]{24,}\b")
SENSITIVE_ENV_NAME_RE = re.compile(r"(?i)(api[_-]?key|token|secret|password|encrypt[_-]?key)")
GITHUB_ACTIONS_RUN_URL_RE = re.compile(r"^https://github\.com/[^/]+/[^/]+/actions/runs/\d+/?$")
GIT_COMMIT_SHA_RE = re.compile(r"^[0-9a-fA-F]{40}$")
PLACEHOLDER_MARKERS = (
    "<",
    "TODO",
    "FILL",
    "REPLACE",
    "SET-IN-OWNER-SECRET-STORE",
    "PASTE",
)
OWNER_GATE_ENV_GROUPS: tuple[tuple[str, tuple[str, ...]], ...] = (
    ("feishu_app_id", ("XAGENT_FEISHU_APP_ID", "FEISHU_APP_ID")),
    ("feishu_app_secret", ("XAGENT_FEISHU_APP_SECRET", "FEISHU_APP_SECRET")),
    ("feishu_encrypt_key", ("XAGENT_FEISHU_ENCRYPT_KEY", "FEISHU_ENCRYPT_KEY")),
    ("github_test_issue_url", ("XAGENT_GITHUB_TEST_ISSUE_URL", "GITHUB_TEST_ISSUE_URL")),
    ("github_token", ("XAGENT_GITHUB_TOKEN", "GITHUB_TOKEN")),
    ("github_actions_run_url", ("XAGENT_COMMERCIAL_RC_GITHUB_ACTIONS_RUN_URL",)),
    ("github_actions_head_sha", ("XAGENT_COMMERCIAL_RC_GITHUB_ACTIONS_HEAD_SHA",)),
)


@dataclass(frozen=True)
class FinalizeStep:
    name: str
    command: list[str]
    status: str
    returncode: int | None
    stdout_tail: list[str] = field(default_factory=list)
    stderr_tail: list[str] = field(default_factory=list)
    error: str | None = None


@dataclass(frozen=True)
class OwnerVerifiedFinalizeReport:
    status: str
    generated_at: str
    provider: str
    dry_run: bool
    expected_commit_sha: str | None
    github_actions_run_url: str | None
    github_actions_head_sha: str | None
    env_file: str | None
    loaded_env_names: list[str]
    skipped_env_names: list[str]
    refresh_chain_status: str | None
    refresh_chain_owner_verified: bool | None
    final_gate_status: str | None
    can_tag_rc_now: bool
    evidence_pack_status: str | None
    release_receipt_status: str | None
    refresh_chain_report_path: str
    steps: list[FinalizeStep]
    next_commands: list[str]

    def to_dict(self) -> dict[str, Any]:
        payload = asdict(self)
        payload["steps"] = [asdict(step) for step in self.steps]
        return payload


def _utc_now() -> str:
    return datetime.now(UTC).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _sanitize_output_line(line: str, secret_values: tuple[str, ...] = ()) -> str:
    for secret_value in secret_values:
        if secret_value:
            line = line.replace(secret_value, "<redacted-secret>")
    line = SECRET_KEY_OUTPUT_RE.sub(r"\1<redacted-output>", line)
    line = SECRET_VALUE_OUTPUT_RE.sub("<redacted-secret>", line)
    return line


def _tail(text: str | bytes | None, limit: int = 20, secret_values: tuple[str, ...] = ()) -> list[str]:
    if text is None:
        return []
    if isinstance(text, bytes):
        text = text.decode("utf-8", errors="replace")
    lines = [
        _sanitize_output_line(line, secret_values=secret_values)
        for line in text.splitlines()
        if line.strip()
    ]
    return lines[-limit:]


def _is_placeholder(value: str) -> bool:
    normalized = value.strip().strip('"').strip("'")
    if not normalized:
        return True
    upper = normalized.upper()
    return any(marker in upper for marker in PLACEHOLDER_MARKERS)


def _parse_env_line(line: str) -> tuple[str, str] | None:
    stripped = line.strip()
    if not stripped or stripped.startswith("#"):
        return None
    if stripped.lower().startswith("export "):
        stripped = stripped[7:].strip()
    if stripped.lower().startswith("$env:"):
        stripped = stripped[5:].strip()
    if "=" not in stripped:
        return None
    name, raw_value = stripped.split("=", 1)
    name = name.strip()
    if not re.fullmatch(r"[A-Za-z_][A-Za-z0-9_]*", name):
        raise ValueError(f"invalid env name: {name!r}")
    value = raw_value.strip()
    if (
        len(value) >= 2
        and ((value[0] == value[-1] == '"') or (value[0] == value[-1] == "'"))
    ):
        value = value[1:-1]
    return name, value


def _load_env_file(path: Path | None) -> tuple[dict[str, str], list[str], list[str]]:
    if path is None:
        return {}, [], []
    if not path.exists():
        return {}, [], [f"env file not found: {path}"]

    overrides: dict[str, str] = {}
    skipped: list[str] = []
    errors: list[str] = []
    for line_number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), start=1):
        try:
            parsed = _parse_env_line(line)
        except ValueError as exc:
            errors.append(f"{path}:{line_number}: {exc}")
            continue
        if parsed is None:
            continue
        name, value = parsed
        if name not in SAFE_ENV_NAMES:
            errors.append(f"{path}:{line_number}: unsupported owner env name {name}")
            continue
        if _is_placeholder(value):
            skipped.append(name)
            continue
        overrides[name] = value
    return overrides, sorted(set(skipped)), errors


def _read_json(path: Path) -> dict[str, Any] | None:
    if not path.exists():
        return None
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None
    return payload if isinstance(payload, dict) else None


def _safe_command(command: list[str]) -> list[str]:
    return ["python" if item == sys.executable else item for item in command]


def _current_git_head_sha() -> tuple[str | None, str | None]:
    try:
        result = subprocess.run(
            ["git", "rev-parse", "HEAD"],
            cwd=ROOT,
            capture_output=True,
            text=True,
            encoding="utf-8",
            timeout=10,
        )
    except (OSError, subprocess.TimeoutExpired) as exc:
        return None, f"could not resolve current git HEAD: {exc}"
    if result.returncode != 0:
        error = (result.stderr or result.stdout or "").strip()
        return None, f"could not resolve current git HEAD: {error or f'exit {result.returncode}'}"
    sha = result.stdout
    if isinstance(sha, bytes):
        sha = sha.decode("utf-8", errors="replace")
    sha = sha.strip()
    if not GIT_COMMIT_SHA_RE.fullmatch(sha):
        return None, "git rev-parse HEAD did not return a 40-character git SHA"
    return sha.lower(), None


def _effective_env_value(names: tuple[str, ...], env_overrides: dict[str, str]) -> str:
    for name in names:
        if name in env_overrides and not _is_placeholder(env_overrides[name]):
            return env_overrides[name]
        value = os.environ.get(name, "")
        if value and not _is_placeholder(value):
            return value
    return ""


def _provider_env_groups(provider: str) -> tuple[tuple[str, tuple[str, ...]], ...]:
    if provider == "openai":
        return (("openai_api_key", ("XAGENT_OPENAI_API_KEY", "OPENAI_API_KEY")),)
    if provider == "deepseek":
        return (("deepseek_api_key", ("XAGENT_DEEPSEEK_API_KEY", "DEEPSEEK_API_KEY")),)
    if provider == "anthropic":
        return (("anthropic_api_key", ("XAGENT_ANTHROPIC_API_KEY", "ANTHROPIC_API_KEY")),)
    if provider in {"ollama", "local"}:
        return (
            ("ollama_base_url", ("XAGENT_OLLAMA_BASE_URL", "OLLAMA_BASE_URL")),
            ("ollama_model", ("XAGENT_OLLAMA_MODEL", "OLLAMA_MODEL")),
        )
    return ()


def _sensitive_env_values(env_overrides: dict[str, str]) -> tuple[str, ...]:
    values: set[str] = set()
    for name in set(os.environ).union(env_overrides):
        if not SENSITIVE_ENV_NAME_RE.search(name):
            continue
        override_value = env_overrides.get(name)
        if override_value and not _is_placeholder(override_value):
            values.add(override_value)
        inherited_value = os.environ.get(name, "")
        if inherited_value and not _is_placeholder(inherited_value):
            values.add(inherited_value)
    return tuple(sorted(values, key=len, reverse=True))


def _owner_env_preflight(
    provider: str,
    env_overrides: dict[str, str],
    *,
    expected_commit_sha: str | None,
) -> FinalizeStep | None:
    missing: list[str] = []
    for _label, names in (*_provider_env_groups(provider), *OWNER_GATE_ENV_GROUPS):
        if not _effective_env_value(names, env_overrides):
            missing.append("/".join(names))

    invalid: list[str] = []
    if not expected_commit_sha:
        invalid.append("expected release commit SHA could not be resolved; pass --expected-commit-sha")
    elif not GIT_COMMIT_SHA_RE.fullmatch(expected_commit_sha):
        invalid.append("--expected-commit-sha must be a 40-character git SHA")
    run_url = _effective_env_value(("XAGENT_COMMERCIAL_RC_GITHUB_ACTIONS_RUN_URL",), env_overrides)
    if run_url and not GITHUB_ACTIONS_RUN_URL_RE.fullmatch(run_url):
        invalid.append("XAGENT_COMMERCIAL_RC_GITHUB_ACTIONS_RUN_URL must be a GitHub Actions run URL")
    head_sha = _effective_env_value(("XAGENT_COMMERCIAL_RC_GITHUB_ACTIONS_HEAD_SHA",), env_overrides)
    if head_sha and not GIT_COMMIT_SHA_RE.fullmatch(head_sha):
        invalid.append("XAGENT_COMMERCIAL_RC_GITHUB_ACTIONS_HEAD_SHA must be a 40-character git SHA")
    elif head_sha and expected_commit_sha and head_sha.lower() != expected_commit_sha.lower():
        invalid.append(
            "XAGENT_COMMERCIAL_RC_GITHUB_ACTIONS_HEAD_SHA must match expected release commit SHA "
            f"({expected_commit_sha.lower()})"
        )

    if not missing and not invalid:
        return None

    problems: list[str] = []
    if missing:
        problems.append(f"missing required owner env groups: {'; '.join(missing)}")
    if invalid:
        problems.append(f"invalid owner env values: {'; '.join(invalid)}")
    return FinalizeStep(
        name="owner_env_preflight",
        command=["owner-env-preflight"],
        status="failed",
        returncode=None,
        error="; ".join(problems),
    )


def _run_refresh_chain(
    *,
    provider: str,
    timeout_seconds: float,
    dry_run: bool,
    refresh_chain_path: Path,
    env_overrides: dict[str, str],
    ollama_model: str | None,
    ollama_base_url: str | None,
    secret_values: tuple[str, ...],
) -> FinalizeStep:
    command = [
        sys.executable,
        "scripts/rc_refresh_release_chain.py",
        "--provider",
        provider,
        "--owner-verified",
        "--timeout",
        str(timeout_seconds),
        "--output",
        str(refresh_chain_path),
    ]
    if ollama_model:
        command.extend(["--ollama-model", ollama_model])
    if ollama_base_url:
        command.extend(["--ollama-base-url", ollama_base_url])
    if dry_run:
        command.append("--dry-run")
    try:
        result = subprocess.run(
            command,
            cwd=ROOT,
            capture_output=True,
            timeout=timeout_seconds * 40,
            env={**os.environ, **env_overrides},
        )
    except subprocess.TimeoutExpired as exc:
        return FinalizeStep(
            name="owner_verified_refresh_chain",
            command=_safe_command(command),
            status="failed",
            returncode=None,
            stdout_tail=_tail(exc.stdout, secret_values=secret_values),
            stderr_tail=_tail(exc.stderr, secret_values=secret_values),
            error=f"command timed out after {timeout_seconds * 40}s",
        )
    return FinalizeStep(
        name="owner_verified_refresh_chain",
        command=_safe_command(command),
        status="passed" if result.returncode == 0 else "failed",
        returncode=result.returncode,
        stdout_tail=_tail(result.stdout, secret_values=secret_values),
        stderr_tail=_tail(result.stderr, secret_values=secret_values),
        error=None if result.returncode == 0 else f"command exited {result.returncode}",
    )


def _status_from_reports(
    *,
    dry_run: bool,
    steps: list[FinalizeStep],
    refresh_chain: dict[str, Any] | None,
    final_gate: dict[str, Any] | None,
    evidence_pack: dict[str, Any] | None,
) -> tuple[str, bool]:
    if any(step.status == "failed" for step in steps):
        return "failed", False
    if dry_run:
        return "planned", False
    if not refresh_chain or refresh_chain.get("status") != "passed":
        return "failed", False
    if refresh_chain.get("owner_verified") is not True:
        return "failed", False
    if not evidence_pack or evidence_pack.get("status") not in {"passed", "created"}:
        return "failed", False
    decision = final_gate.get("release_decision", {}) if isinstance(final_gate, dict) else {}
    can_tag = final_gate.get("status") == "ready_for_rc_tag" and decision.get("can_tag_rc_now") is True
    return ("ready_for_rc_tag" if can_tag else "action_required"), bool(can_tag)


def build_owner_verified_finalize(
    *,
    provider: str = "ollama",
    timeout_seconds: float = 180.0,
    dry_run: bool = False,
    env_file: Path | None = None,
    ollama_model: str | None = None,
    ollama_base_url: str | None = None,
    github_actions_run_url: str | None = None,
    github_actions_head_sha: str | None = None,
    expected_commit_sha: str | None = None,
    reports_dir: Path = REPORT_DIR,
    release_dir: Path = RELEASE_DIR,
) -> OwnerVerifiedFinalizeReport:
    if provider not in PROVIDER_CHOICES:
        raise ValueError(f"unsupported provider: {provider}")

    env_overrides, skipped_env_names, env_errors = _load_env_file(env_file)
    if ollama_model:
        env_overrides["XAGENT_OLLAMA_MODEL"] = ollama_model
    if ollama_base_url:
        env_overrides["XAGENT_OLLAMA_BASE_URL"] = ollama_base_url
    if github_actions_run_url:
        env_overrides["XAGENT_COMMERCIAL_RC_GITHUB_ACTIONS_RUN_URL"] = github_actions_run_url
    if github_actions_head_sha:
        env_overrides["XAGENT_COMMERCIAL_RC_GITHUB_ACTIONS_HEAD_SHA"] = github_actions_head_sha

    requested_expected_sha = expected_commit_sha.lower() if expected_commit_sha else None
    resolved_expected_sha: str | None = requested_expected_sha
    expected_sha_error: str | None = None
    if not dry_run:
        current_head_sha, expected_sha_error = _current_git_head_sha()
        if current_head_sha and requested_expected_sha and requested_expected_sha != current_head_sha:
            expected_sha_error = (
                "--expected-commit-sha must match current git HEAD "
                f"({current_head_sha})"
            )
        resolved_expected_sha = requested_expected_sha or current_head_sha

    resolved_github_actions_run_url = (
        _effective_env_value(("XAGENT_COMMERCIAL_RC_GITHUB_ACTIONS_RUN_URL",), env_overrides) or None
    )
    resolved_github_actions_head_sha = (
        _effective_env_value(("XAGENT_COMMERCIAL_RC_GITHUB_ACTIONS_HEAD_SHA",), env_overrides) or None
    )
    if resolved_github_actions_head_sha:
        resolved_github_actions_head_sha = resolved_github_actions_head_sha.lower()

    steps: list[FinalizeStep] = []
    refresh_chain_path = (
        reports_dir / "rc-owner-verified-finalize-refresh-chain-dry-run.json"
        if dry_run
        else reports_dir / "rc-refresh-release-chain.json"
    )
    final_gate_path = reports_dir / "rc-final-gate.json"
    evidence_pack_path = reports_dir / "rc-evidence-pack.json"
    receipt_path = release_dir / "x-agent-commercial-rc-receipt.json"

    preflight = None
    if not dry_run and not env_errors:
        if expected_sha_error:
            preflight = FinalizeStep(
                name="owner_env_preflight",
                command=["owner-env-preflight"],
                status="failed",
                returncode=None,
                error=expected_sha_error,
            )
        else:
            preflight = _owner_env_preflight(
                provider,
                env_overrides,
                expected_commit_sha=resolved_expected_sha,
            )
    if env_errors:
        steps.append(
            FinalizeStep(
                name="owner_env_file",
                command=[str(env_file) if env_file else "<env-file>"],
                status="failed",
                returncode=None,
                error="; ".join(env_errors),
            )
        )
    elif preflight is not None:
        steps.append(preflight)
    else:
        steps.append(
            _run_refresh_chain(
                provider=provider,
                timeout_seconds=timeout_seconds,
                dry_run=dry_run,
                refresh_chain_path=refresh_chain_path,
                env_overrides=env_overrides,
                ollama_model=ollama_model,
                ollama_base_url=ollama_base_url,
                secret_values=_sensitive_env_values(env_overrides),
            )
        )

    refresh_chain = _read_json(refresh_chain_path)
    final_gate = _read_json(final_gate_path)
    evidence_pack = _read_json(evidence_pack_path)
    receipt = _read_json(receipt_path)
    status, can_tag = _status_from_reports(
        dry_run=dry_run,
        steps=steps,
        refresh_chain=refresh_chain,
        final_gate=final_gate,
        evidence_pack=evidence_pack,
    )
    return OwnerVerifiedFinalizeReport(
        status=status,
        generated_at=_utc_now(),
        provider=provider,
        dry_run=dry_run,
        expected_commit_sha=resolved_expected_sha,
        github_actions_run_url=resolved_github_actions_run_url,
        github_actions_head_sha=resolved_github_actions_head_sha,
        env_file=str(env_file) if env_file else None,
        loaded_env_names=sorted(env_overrides),
        skipped_env_names=skipped_env_names,
        refresh_chain_status=refresh_chain.get("status") if refresh_chain else None,
        refresh_chain_owner_verified=refresh_chain.get("owner_verified") if refresh_chain else None,
        final_gate_status=final_gate.get("status") if final_gate else None,
        can_tag_rc_now=can_tag,
        evidence_pack_status=evidence_pack.get("status") if evidence_pack else None,
        release_receipt_status=receipt.get("status") if receipt else None,
        refresh_chain_report_path=str(refresh_chain_path),
        steps=steps,
        next_commands=_next_commands(
            status=status,
            provider=provider,
            expected_commit_sha=resolved_expected_sha,
        ),
    )


def _next_commands(*, status: str, provider: str, expected_commit_sha: str | None) -> list[str]:
    if status == "ready_for_rc_tag":
        expected = expected_commit_sha or "<expected-release-commit-sha>"
        return [
            "Review .xagent_runtime/reports/rc-owner-verified-finalize.json.",
            f"Confirm the hosted Actions head SHA and release commit are {expected}.",
            "Verify any existing RC tag points at that SHA before handoff: "
            f"python scripts\\rc_tag_consistency_gate.py --expected-commit-sha {expected} "
            f"--tag-name {EXAMPLE_RC_TAG_NAME} --require-match.",
            "Do not force-update pushed tags without owner approval.",
        ]
    if status == "planned":
        return [
            "Rerun this script without --dry-run in the owner PowerShell session.",
            "Keep owner secrets in environment variables or an owner-controlled env file; do not paste them into chat.",
        ]
    return [
        "Inspect .xagent_runtime/reports/rc-owner-verified-finalize.json.",
        "Fix the failed owner or release gate and rerun this script.",
        f"Expected command shape: python scripts\\rc_owner_verified_finalize.py --provider {provider}",
    ]


def write_report(report: OwnerVerifiedFinalizeReport, output_path: Path) -> None:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(report.to_dict(), ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Finalize the owner-verified X-Agent commercial RC")
    parser.add_argument("--provider", choices=PROVIDER_CHOICES, default="ollama")
    parser.add_argument("--timeout", type=float, default=180.0)
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--env-file", type=Path, default=None)
    parser.add_argument("--ollama-model")
    parser.add_argument("--ollama-base-url")
    parser.add_argument("--github-actions-run-url")
    parser.add_argument("--github-actions-head-sha")
    parser.add_argument(
        "--expected-commit-sha",
        help="expected release commit SHA; defaults to git rev-parse HEAD",
    )
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    report = build_owner_verified_finalize(
        provider=args.provider,
        timeout_seconds=args.timeout,
        dry_run=args.dry_run,
        env_file=args.env_file,
        ollama_model=args.ollama_model,
        ollama_base_url=args.ollama_base_url,
        github_actions_run_url=args.github_actions_run_url,
        github_actions_head_sha=args.github_actions_head_sha,
        expected_commit_sha=args.expected_commit_sha,
    )
    write_report(report, args.output)
    print(f"RC owner-verified finalize status: {report.status}")
    print(f"Provider: {report.provider}")
    print(f"Report written to {args.output}")
    if report.expected_commit_sha:
        print(f"Expected release commit SHA: {report.expected_commit_sha}")
    if report.github_actions_run_url:
        print(f"Hosted GitHub Actions run: {report.github_actions_run_url}")
    if report.github_actions_head_sha:
        print(f"Hosted GitHub Actions head SHA: {report.github_actions_head_sha}")
    if report.env_file:
        print(f"Env file: {report.env_file}")
        print(f"Loaded env names: {','.join(report.loaded_env_names) if report.loaded_env_names else '<none>'}")
        if report.skipped_env_names:
            print(f"Skipped placeholder env names: {','.join(report.skipped_env_names)}")
    print(f"Final gate: {report.final_gate_status}")
    print(f"Can tag RC now: {report.can_tag_rc_now}")
    for step in report.steps:
        print(f"- {step.name}: {step.status}")
        if step.error:
            print(f"  error: {step.error}")
    return 0 if report.status in {"ready_for_rc_tag", "planned"} else 1


if __name__ == "__main__":
    raise SystemExit(main())
