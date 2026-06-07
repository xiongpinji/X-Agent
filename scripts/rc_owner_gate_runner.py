#!/usr/bin/env python3
"""Run owner-controlled commercial RC gates through a safe command allowlist.

The owner checklist explains what must be run. This runner makes those commands
less error-prone without turning skipped checks into success: it executes only
known, non-mutating ``rc_external_smoke.py`` preflight combinations and then
refreshes the owner gate plan/checklist/handoff reports from the resulting
evidence.
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

from scripts.rc_source_bundle import ROOT

REPORT_DIR = ROOT / ".xagent_runtime" / "reports"
DEFAULT_OWNER_GATE_PLAN = REPORT_DIR / "rc-owner-gate-plan.json"
DEFAULT_OWNER_ENV_FILE = REPORT_DIR / "rc-owner-env-template.env"
DEFAULT_OUTPUT = REPORT_DIR / "rc-owner-gate-runner.json"
SECRET_KEY_OUTPUT_RE = re.compile(r"(?i)(\b[A-Z0-9_]*(?:api[_-]?key|token|secret|password)\b\s*[:=]\s*).+")
SECRET_VALUE_OUTPUT_RE = re.compile(r"\b(?:sk|ghp|github_pat|xagent)[_-][A-Za-z0-9_=-]{24,}\b")

GATE_COMMANDS: dict[str, list[str]] = {
    "provider": [
        "scripts/rc_external_smoke.py",
        "--check",
        "provider",
        "--provider",
        "ollama",
        "--require-configured",
    ],
    "feishu_webhook_contract": [
        "scripts/rc_external_smoke.py",
        "--check",
        "feishu_webhook_contract",
        "--require-configured",
    ],
    "github_issue_to_pr_dry_run": [
        "scripts/rc_external_smoke.py",
        "--check",
        "github_issue_to_pr_dry_run",
        "--require-configured",
    ],
    "github_issue_to_pr_execute_preflight": [
        "scripts/rc_external_smoke.py",
        "--check",
        "github_issue_to_pr_dry_run",
        "--check",
        "github_issue_to_pr_execute_preflight",
        "--github-execute-preflight",
        "--require-configured",
    ],
    "hosted_github_actions_commercial_rc": [
        "scripts/rc_external_smoke.py",
        "--check",
        "hosted_github_actions_run",
        "--github-actions-preflight",
        "--require-configured",
    ],
    "all": [
        "scripts/rc_external_smoke.py",
        "--provider",
        "ollama",
        "--github-execute-preflight",
        "--github-actions-preflight",
        "--require-configured",
    ],
}

REFRESH_COMMANDS: tuple[list[str], ...] = (
    ["scripts/rc_owner_gate_plan.py"],
    ["scripts/rc_owner_env_template.py"],
    ["scripts/rc_owner_gate_checklist.py"],
    ["scripts/rc_owner_handoff_gate.py"],
    ["scripts/rc_final_gate.py"],
)


@dataclass(frozen=True)
class OwnerGateRunStep:
    name: str
    command: list[str]
    status: str
    returncode: int | None
    stdout_tail: list[str] = field(default_factory=list)
    stderr_tail: list[str] = field(default_factory=list)
    error: str | None = None


@dataclass(frozen=True)
class OwnerGateRunnerReport:
    status: str
    generated_at: str
    selected_gate: str
    dry_run: bool
    steps: list[OwnerGateRunStep]
    next_commands: list[str]
    env_file: str | None = None
    loaded_env_names: list[str] = field(default_factory=list)
    unresolved_env_names: list[str] = field(default_factory=list)
    owner_gate_env_names: list[str] = field(default_factory=list)
    owner_gate_unresolved_env_names: list[str] = field(default_factory=list)
    owner_gate_command: list[str] = field(default_factory=list)
    required_env_groups: list[list[str]] = field(default_factory=list)
    missing_env_groups: list[list[str]] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        payload = asdict(self)
        payload["steps"] = [asdict(step) for step in self.steps]
        return payload


def _utc_now() -> str:
    return datetime.now(UTC).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _read_json(path: Path) -> dict[str, Any] | None:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (FileNotFoundError, json.JSONDecodeError):
        return None
    return payload if isinstance(payload, dict) else None


def _selected_provider(plan_path: Path) -> str:
    payload = _read_json(plan_path)
    if not payload:
        return "ollama"
    gates = payload.get("gates")
    if not isinstance(gates, list):
        return "ollama"
    provider_gate = next(
        (gate for gate in gates if isinstance(gate, dict) and gate.get("name") == "provider"),
        None,
    )
    command = str((provider_gate or {}).get("command") or "")
    if "--provider " not in command:
        return "ollama"
    provider = command.split("--provider ", 1)[1].split()[0].strip()
    return provider if provider in {"openai", "deepseek", "anthropic", "ollama", "local"} else "ollama"


def _command_for_gate(gate: str, *, plan_path: Path) -> list[str]:
    if gate not in GATE_COMMANDS:
        raise ValueError(f"unsupported owner gate: {gate}")
    command = list(GATE_COMMANDS[gate])
    if gate in {"provider", "all"}:
        provider = _selected_provider(plan_path)
        if "--provider" in command:
            index = command.index("--provider")
            command[index + 1] = provider
    return command


def _tail(text: str | bytes | None, *, lines: int = 20) -> list[str]:
    if text is None:
        return []
    if isinstance(text, bytes):
        text = text.decode("utf-8", errors="replace")
    return [_sanitize_output_line(line) for line in text.splitlines()[-lines:]]


def _sanitize_output_line(line: str) -> str:
    line = SECRET_KEY_OUTPUT_RE.sub(r"\1<redacted-output>", line)
    return SECRET_VALUE_OUTPUT_RE.sub("<redacted-secret>", line)


def _strip_env_value(value: str) -> str:
    value = value.strip()
    if len(value) >= 2 and value[0] == value[-1] and value[0] in {"'", '"'}:
        return value[1:-1]
    return value


def _is_placeholder_env_value(value: str) -> bool:
    return not value or ("<" in value and ">" in value)


def _safe_env_file_label(path: Path | None) -> str | None:
    if path is None:
        return None
    try:
        relative = path.resolve().relative_to(ROOT.resolve())
    except ValueError:
        return path.name
    return str(relative).replace("\\", "/")


def _allowed_env_names(plan_path: Path) -> set[str]:
    payload = _read_json(plan_path)
    gates = (payload or {}).get("gates")
    if not isinstance(gates, list):
        return set()
    names: set[str] = set()
    for gate in gates:
        if not isinstance(gate, dict):
            continue
        groups = gate.get("required_env_groups")
        if not isinstance(groups, list):
            continue
        for group in groups:
            if isinstance(group, list):
                names.update(str(item) for item in group if str(item).strip())
    return names


def _allowed_env_names_for_gate(plan_path: Path, gate_name: str) -> set[str]:
    if gate_name == "all":
        return _allowed_env_names(plan_path)
    payload = _read_json(plan_path)
    gates = (payload or {}).get("gates")
    if not isinstance(gates, list):
        return set()
    for gate in gates:
        if not isinstance(gate, dict) or gate.get("name") != gate_name:
            continue
        names: set[str] = set()
        groups = gate.get("required_env_groups")
        if not isinstance(groups, list):
            return names
        for group in groups:
            if isinstance(group, list):
                names.update(str(item) for item in group if str(item).strip())
        return names
    return set()


def _required_env_groups_for_gate(plan_path: Path, gate_name: str) -> list[list[str]]:
    payload = _read_json(plan_path)
    gates = (payload or {}).get("gates")
    if not isinstance(gates, list):
        return []
    groups: list[list[str]] = []
    seen: set[tuple[str, ...]] = set()
    for gate in gates:
        if not isinstance(gate, dict):
            continue
        if gate_name != "all" and gate.get("name") != gate_name:
            continue
        raw_groups = gate.get("required_env_groups")
        if not isinstance(raw_groups, list):
            continue
        for raw_group in raw_groups:
            if not isinstance(raw_group, list):
                continue
            group = [str(item).strip() for item in raw_group if str(item).strip()]
            key = tuple(group)
            if group and key not in seen:
                seen.add(key)
                groups.append(group)
    return groups


def _configured_env_names(env_overrides: dict[str, str]) -> set[str]:
    names = {
        name
        for name, value in os.environ.items()
        if str(name).strip() and not _is_placeholder_env_value(str(value))
    }
    names.update(name for name, value in env_overrides.items() if not _is_placeholder_env_value(value))
    return names


def _missing_env_groups(required_groups: list[list[str]], env_overrides: dict[str, str]) -> list[list[str]]:
    configured_names = _configured_env_names(env_overrides)
    return [group for group in required_groups if not any(name in configured_names for name in group)]


def _display_command(command: list[str]) -> list[str]:
    return ["python", *command]


def _runner_command(gate: str, env_file_path: Path | None) -> str:
    command = f"python scripts\\rc_owner_gate_runner.py --gate {gate}"
    env_label = _safe_env_file_label(env_file_path) if env_file_path else str(DEFAULT_OWNER_ENV_FILE.relative_to(ROOT))
    return f"{command} --env-file {env_label}"


def _next_commands_for_gate(
    *,
    gate: str,
    env_file_path: Path | None,
    missing_env_groups: list[list[str]],
    unresolved_env_names: list[str],
    failed: bool,
) -> list[str]:
    commands: list[str] = ["Inspect .xagent_runtime/reports/rc-owner-gate-runner.json."]
    if unresolved_env_names:
        names = ", ".join(unresolved_env_names)
        commands.append(f"Replace owner env template placeholder values for: {names}.")
    if missing_env_groups:
        groups = "; ".join("/".join(group) for group in missing_env_groups)
        commands.append(f"Fill one variable from each missing owner env group in the owner env template: {groups}.")
    if failed or missing_env_groups:
        commands.append(_runner_command(gate, env_file_path))
    else:
        commands.append("Run python scripts\\rc_final_gate.py --require-ready-to-tag only after every owner gate is verified.")
    return commands


def _load_env_file(
    path: Path | None,
    *,
    allowed_names: set[str] | None = None,
) -> tuple[dict[str, str], list[str], list[str]]:
    if path is None:
        return {}, [], []
    try:
        lines = path.read_text(encoding="utf-8").splitlines()
    except FileNotFoundError:
        return {}, ["env file is missing"], []
    except UnicodeDecodeError as exc:
        return {}, [f"env file is not UTF-8 text: {exc}"], []

    values: dict[str, str] = {}
    errors: list[str] = []
    unresolved: list[str] = []
    for line_number, raw_line in enumerate(lines, start=1):
        line = raw_line.strip()
        if not line or line.startswith("#"):
            continue
        if line.startswith("export "):
            line = line[len("export ") :].strip()
        if "=" not in line:
            errors.append(f"env file line {line_number} is not KEY=value")
            continue
        name, raw_value = line.split("=", 1)
        name = name.strip()
        if not name or not name.replace("_", "").isalnum() or not name[0].isalpha():
            errors.append(f"env file line {line_number} has an invalid variable name")
            continue
        if allowed_names is not None and name not in allowed_names:
            errors.append(f"env file line {line_number} variable is not allowed by owner gate plan: {name}")
            continue
        value = _strip_env_value(raw_value)
        if _is_placeholder_env_value(value):
            unresolved.append(name)
            continue
        values[name] = value
    return values, errors, sorted(dict.fromkeys(unresolved))


def _run_step(
    name: str,
    command: list[str],
    *,
    timeout_seconds: float,
    dry_run: bool,
    env_overrides: dict[str, str] | None = None,
) -> OwnerGateRunStep:
    full_command = [sys.executable, *command]
    display_command = ["python", *command]
    if dry_run:
        return OwnerGateRunStep(name=name, command=display_command, status="planned", returncode=None)
    try:
        result = subprocess.run(
            full_command,
            cwd=ROOT,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=timeout_seconds,
            env={**os.environ, **(env_overrides or {})},
        )
    except subprocess.TimeoutExpired as exc:
        return OwnerGateRunStep(
            name=name,
            command=display_command,
            status="failed",
            returncode=None,
            stdout_tail=_tail(exc.stdout or ""),
            stderr_tail=_tail(exc.stderr or ""),
            error=f"command timed out after {timeout_seconds}s",
        )
    return OwnerGateRunStep(
        name=name,
        command=display_command,
        status="passed" if result.returncode == 0 else "failed",
        returncode=result.returncode,
        stdout_tail=_tail(result.stdout),
        stderr_tail=_tail(result.stderr),
        error=None if result.returncode == 0 else f"command exited {result.returncode}",
    )


def build_owner_gate_runner(
    *,
    gate: str,
    plan_path: Path = DEFAULT_OWNER_GATE_PLAN,
    timeout_seconds: float = 120.0,
    dry_run: bool = False,
    refresh: bool = True,
    env_file_path: Path | None = None,
) -> OwnerGateRunnerReport:
    steps: list[OwnerGateRunStep] = []
    allowed_env_names = _allowed_env_names(plan_path) if env_file_path is not None else None
    env_overrides, env_errors, unresolved_env_names = _load_env_file(env_file_path, allowed_names=allowed_env_names)
    owner_gate_allowed_names = _allowed_env_names_for_gate(plan_path, gate) if env_file_path is not None else set(env_overrides)
    owner_gate_env_overrides = {
        name: value for name, value in env_overrides.items() if name in owner_gate_allowed_names
    }
    owner_gate_unresolved_env_names = sorted(
        name for name in unresolved_env_names if name in owner_gate_allowed_names
    )
    required_env_groups = _required_env_groups_for_gate(plan_path, gate)
    missing_env_groups = _missing_env_groups(required_env_groups, owner_gate_env_overrides)
    smoke_command = _command_for_gate(gate, plan_path=plan_path)
    if env_errors:
        steps.append(
            OwnerGateRunStep(
                name="env_file",
                command=[_safe_env_file_label(env_file_path) or "<env-file>"],
                status="failed",
                returncode=None,
                error="; ".join(env_errors),
            )
        )
        return OwnerGateRunnerReport(
            status="failed",
            generated_at=_utc_now(),
            selected_gate=gate,
            dry_run=dry_run,
            steps=steps,
            next_commands=["Fix the env file format and rerun this command."],
            env_file=_safe_env_file_label(env_file_path),
            loaded_env_names=sorted(env_overrides),
            unresolved_env_names=unresolved_env_names,
            owner_gate_env_names=sorted(owner_gate_env_overrides),
            owner_gate_unresolved_env_names=owner_gate_unresolved_env_names,
            owner_gate_command=_display_command(smoke_command),
            required_env_groups=required_env_groups,
            missing_env_groups=missing_env_groups,
        )
    if missing_env_groups and not dry_run:
        formatted = "; ".join("/".join(group) for group in missing_env_groups)
        steps.append(
            OwnerGateRunStep(
                name="env_preflight",
                command=["owner_gate_env_preflight"],
                status="failed",
                returncode=None,
                error=f"missing required env groups: {formatted}",
            )
        )
        return OwnerGateRunnerReport(
            status="failed",
            generated_at=_utc_now(),
            selected_gate=gate,
            dry_run=dry_run,
            steps=steps,
            next_commands=_next_commands_for_gate(
                gate=gate,
                env_file_path=env_file_path,
                missing_env_groups=missing_env_groups,
                unresolved_env_names=owner_gate_unresolved_env_names,
                failed=True,
            ),
            env_file=_safe_env_file_label(env_file_path),
            loaded_env_names=sorted(env_overrides),
            unresolved_env_names=unresolved_env_names,
            owner_gate_env_names=sorted(owner_gate_env_overrides),
            owner_gate_unresolved_env_names=owner_gate_unresolved_env_names,
            owner_gate_command=_display_command(smoke_command),
            required_env_groups=required_env_groups,
            missing_env_groups=missing_env_groups,
        )
    steps.append(
        _run_step(
            f"owner_gate:{gate}",
            smoke_command,
            timeout_seconds=timeout_seconds,
            dry_run=dry_run,
            env_overrides=owner_gate_env_overrides,
        )
    )
    if refresh and (dry_run or steps[-1].status == "passed"):
        for command in REFRESH_COMMANDS:
            steps.append(
                _run_step(
                    f"refresh:{Path(command[0]).stem}",
                    command,
                    timeout_seconds=timeout_seconds,
                    dry_run=dry_run,
                    env_overrides=env_overrides,
                )
            )
    failed = [step for step in steps if step.status == "failed"]
    status = "planned" if dry_run and not failed else "passed" if not failed else "failed"
    return OwnerGateRunnerReport(
        status=status,
        generated_at=_utc_now(),
        selected_gate=gate,
        dry_run=dry_run,
        steps=steps,
        next_commands=_next_commands_for_gate(
            gate=gate,
            env_file_path=env_file_path,
            missing_env_groups=missing_env_groups,
            unresolved_env_names=owner_gate_unresolved_env_names,
            failed=bool(failed),
        ),
        env_file=_safe_env_file_label(env_file_path),
        loaded_env_names=sorted(env_overrides),
        unresolved_env_names=unresolved_env_names,
        owner_gate_env_names=sorted(owner_gate_env_overrides),
        owner_gate_unresolved_env_names=owner_gate_unresolved_env_names,
        owner_gate_command=_display_command(smoke_command),
        required_env_groups=required_env_groups,
        missing_env_groups=missing_env_groups,
    )


def write_report(report: OwnerGateRunnerReport, output_path: Path) -> None:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(report.to_dict(), ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run X-Agent commercial RC owner gates safely")
    parser.add_argument(
        "--gate",
        choices=sorted(GATE_COMMANDS),
        default="all",
        help="owner gate to run through the allowlisted preflight command",
    )
    parser.add_argument("--plan", type=Path, default=DEFAULT_OWNER_GATE_PLAN)
    parser.add_argument("--timeout", type=float, default=120.0)
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument(
        "--env-file",
        type=Path,
        default=None,
        help=f"load non-placeholder KEY=value entries from an owner env file, for example {DEFAULT_OWNER_ENV_FILE}",
    )
    parser.add_argument("--no-refresh", action="store_true", help="do not refresh owner/final reports after smoke")
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    report = build_owner_gate_runner(
        gate=args.gate,
        plan_path=args.plan,
        timeout_seconds=args.timeout,
        dry_run=args.dry_run,
        refresh=not args.no_refresh,
        env_file_path=args.env_file,
    )
    write_report(report, args.output)
    print(f"RC owner gate runner status: {report.status}")
    print(f"Selected gate: {report.selected_gate}")
    if report.env_file:
        print(f"Env file: {report.env_file}")
        print(f"Loaded env names: {','.join(report.loaded_env_names) if report.loaded_env_names else '<none>'}")
        print(
            "Owner gate env names: "
            f"{','.join(report.owner_gate_env_names) if report.owner_gate_env_names else '<none>'}"
        )
    if report.missing_env_groups:
        formatted = "; ".join("/".join(group) for group in report.missing_env_groups)
        print(f"Missing env groups: {formatted}")
    print(f"Report written to {args.output}")
    for step in report.steps:
        print(f"- {step.name}: {step.status}")
        if step.error:
            print(f"  error: {step.error}")
    return 0 if report.status in {"planned", "passed"} else 1


if __name__ == "__main__":
    raise SystemExit(main())
