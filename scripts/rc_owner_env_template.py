#!/usr/bin/env python3
"""Render a safe environment template for commercial RC owner gates.

The template is derived from ``rc-owner-gate-plan.json`` and intentionally
contains only variable names and placeholders. It never reads, prints, or stores
the current secret values from the deployment owner's shell.
"""

from __future__ import annotations

import argparse
import json
from dataclasses import asdict, dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
REPORT_DIR = ROOT / ".xagent_runtime" / "reports"
DEFAULT_PLAN = REPORT_DIR / "rc-owner-gate-plan.json"
DEFAULT_EXTERNAL_SMOKE = REPORT_DIR / "rc-external-smoke.json"
DEFAULT_JSON_OUTPUT = REPORT_DIR / "rc-owner-env-template.json"
DEFAULT_ENV_OUTPUT = REPORT_DIR / "rc-owner-env-template.env"
DEFAULT_POWERSHELL_OUTPUT = REPORT_DIR / "rc-owner-env-template.ps1"

PLACEHOLDER = "<set-in-owner-secret-store>"
PROVIDER_PLACEHOLDER = "<openai|deepseek|anthropic|ollama|local>"
GITHUB_ISSUE_PLACEHOLDER = "https://github.com/<owner>/<repo>/issues/<number>"
GITHUB_ACTIONS_RUN_PLACEHOLDER = "https://github.com/<owner>/<repo>/actions/runs/<run-id>"
GITHUB_ACTIONS_HEAD_SHA_PLACEHOLDER = "<40-character-git-commit-sha>"
OLLAMA_MODEL_PLACEHOLDER = "<ollama-model-name>"

VALUE_HINTS = {
    "XAGENT_LLM_BACKEND": PROVIDER_PLACEHOLDER,
    "LLM_BACKEND": PROVIDER_PLACEHOLDER,
    "XAGENT_OLLAMA_MODEL": OLLAMA_MODEL_PLACEHOLDER,
    "OLLAMA_MODEL": OLLAMA_MODEL_PLACEHOLDER,
    "XAGENT_GITHUB_TEST_ISSUE_URL": GITHUB_ISSUE_PLACEHOLDER,
    "GITHUB_TEST_ISSUE_URL": GITHUB_ISSUE_PLACEHOLDER,
    "XAGENT_COMMERCIAL_RC_GITHUB_ACTIONS_RUN_URL": GITHUB_ACTIONS_RUN_PLACEHOLDER,
    "XAGENT_COMMERCIAL_RC_GITHUB_ACTIONS_HEAD_SHA": GITHUB_ACTIONS_HEAD_SHA_PLACEHOLDER,
}

SAFE_PROVIDER_PREFILL_NAMES = {
    "XAGENT_LLM_BACKEND",
    "XAGENT_OLLAMA_BASE_URL",
    "XAGENT_OLLAMA_MODEL",
}


@dataclass(frozen=True)
class EnvTemplateEntry:
    name: str
    value: str
    required_by: list[str]
    aliases: list[str] = field(default_factory=list)
    preferred: bool = True


@dataclass(frozen=True)
class OwnerEnvTemplate:
    status: str
    generated_at: str
    owner_gate_plan: str
    env_groups: list[list[str]]
    entries: list[EnvTemplateEntry]
    command_sequence: list[str]
    errors: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        payload = asdict(self)
        payload["entries"] = [asdict(entry) for entry in self.entries]
        return payload


def _utc_now() -> str:
    return datetime.now(UTC).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _read_plan(path: Path) -> tuple[dict[str, Any] | None, list[str]]:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError:
        return None, [f"owner gate plan is missing: {path}"]
    except json.JSONDecodeError as exc:
        return None, [f"owner gate plan is not valid JSON: {exc}"]
    if not isinstance(payload, dict):
        return None, ["owner gate plan must be a JSON object"]
    return payload, []


def _read_external_smoke(path: Path | None) -> dict[str, Any] | None:
    if path is None:
        return None
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (FileNotFoundError, json.JSONDecodeError):
        return None
    return payload if isinstance(payload, dict) else None


def _provider_prefill_hints(external_smoke: dict[str, Any] | None) -> dict[str, str]:
    if not external_smoke:
        return {}
    checks = external_smoke.get("checks")
    if not isinstance(checks, list):
        return {}
    provider_check = next(
        (
            check
            for check in checks
            if isinstance(check, dict)
            and check.get("name") == "provider"
            and str(check.get("status") or "") in {"passed", "skipped", "failed"}
            and isinstance(check.get("details"), dict)
        ),
        None,
    )
    if provider_check is None:
        return {}

    details = provider_check["details"]
    provider = str(details.get("provider") or "").strip().lower()
    hints: dict[str, str] = {}
    if provider:
        hints["XAGENT_LLM_BACKEND"] = provider
    if provider in {"ollama", "local"}:
        base_url = str(details.get("base_url") or "").strip()
        model = str(details.get("model") or "").strip()
        if base_url:
            hints["XAGENT_OLLAMA_BASE_URL"] = base_url
        if model:
            hints["XAGENT_OLLAMA_MODEL"] = model
    return {name: value for name, value in hints.items() if name in SAFE_PROVIDER_PREFILL_NAMES and value}


def _env_value(name: str, value_hints: dict[str, str] | None = None) -> str:
    if value_hints and name in value_hints:
        return value_hints[name]
    return VALUE_HINTS.get(name, PLACEHOLDER)


def _normalize_env_groups(value: Any) -> list[list[str]]:
    if not isinstance(value, list):
        return []
    groups: list[list[str]] = []
    for group in value:
        if not isinstance(group, list):
            continue
        names = [str(item) for item in group if str(item).strip()]
        if names:
            groups.append(names)
    return groups


def _template_entries(gates: list[dict[str, Any]], value_hints: dict[str, str] | None = None) -> list[EnvTemplateEntry]:
    required_by: dict[str, list[str]] = {}
    aliases_by_name: dict[str, list[str]] = {}
    preferred: dict[str, bool] = {}

    for gate in gates:
        gate_name = str(gate.get("name") or "owner_gate")
        for group in _normalize_env_groups(gate.get("required_env_groups")):
            primary = group[0]
            aliases = group[1:]
            for index, name in enumerate(group):
                required_by.setdefault(name, [])
                if gate_name not in required_by[name]:
                    required_by[name].append(gate_name)
                aliases_by_name.setdefault(name, [])
                related = [item for item in group if item != name]
                aliases_by_name[name].extend(item for item in related if item not in aliases_by_name[name])
                preferred[name] = index == 0 if name not in preferred else preferred[name]
            if primary not in aliases_by_name:
                aliases_by_name[primary] = aliases

    entries = [
        EnvTemplateEntry(
            name=name,
            value=_env_value(name, value_hints),
            required_by=sorted(required_by[name]),
            aliases=sorted(dict.fromkeys(aliases_by_name.get(name, []))),
            preferred=preferred.get(name, True),
        )
        for name in sorted(required_by)
    ]
    return entries


def _template_env_groups(gates: list[dict[str, Any]]) -> list[list[str]]:
    groups: list[list[str]] = []
    seen: set[tuple[str, ...]] = set()
    for gate in gates:
        for group in _normalize_env_groups(gate.get("required_env_groups")):
            key = tuple(group)
            if key not in seen:
                groups.append(group)
                seen.add(key)
    return groups


def build_env_template(plan_path: Path = DEFAULT_PLAN, external_smoke_path: Path | None = None) -> OwnerEnvTemplate:
    plan, errors = _read_plan(plan_path)
    if plan is None:
        return OwnerEnvTemplate(
            status="failed",
            generated_at=_utc_now(),
            owner_gate_plan=str(plan_path),
            env_groups=[],
            entries=[],
            command_sequence=[f"python scripts\\rc_owner_gate_plan.py --output {plan_path}"],
            errors=errors,
        )

    raw_gates = plan.get("gates")
    gates = [item for item in raw_gates if isinstance(item, dict)] if isinstance(raw_gates, list) else []
    template_errors: list[str] = []
    if not gates:
        template_errors.append("owner gate plan contains no gate entries")
    entries = _template_entries(gates, _provider_prefill_hints(_read_external_smoke(external_smoke_path)))
    if not entries:
        template_errors.append("owner gate plan contains no required environment variables")
    next_commands = [str(item) for item in plan.get("next_commands", [])] if isinstance(plan.get("next_commands"), list) else []
    return OwnerEnvTemplate(
        status="failed" if template_errors else "created",
        generated_at=_utc_now(),
        owner_gate_plan=str(plan_path),
        env_groups=_template_env_groups(gates),
        entries=entries,
        command_sequence=[
            "Fill these placeholders in the deployment owner's shell or secret manager.",
            *next_commands,
        ],
        errors=template_errors,
    )


def render_env(template: OwnerEnvTemplate) -> str:
    lines = [
        "# X-Agent Commercial RC owner gate environment template",
        "# Generated values are placeholders only; do not commit real secrets.",
        "# Fill one variable from each group; prefer XAGENT_* names.",
        "# Alias variables are alternatives, not additional required secrets.",
        "# Placeholder values are ignored by rc_owner_gate_runner.py.",
        f"# Generated at: {template.generated_at}",
        "",
    ]
    for entry in template.entries:
        alias_text = f" aliases={','.join(entry.aliases)}" if entry.aliases else ""
        gates = ",".join(entry.required_by)
        lines.append(f"# required_by={gates}{alias_text}")
        lines.append(f'{entry.name}="{entry.value}"')
        lines.append("")
    return "\n".join(lines).rstrip() + "\n"


def _escape_powershell(value: str) -> str:
    return value.replace("'", "''")


def render_powershell(template: OwnerEnvTemplate) -> str:
    lines = [
        "# X-Agent Commercial RC owner gate environment template",
        "# Generated values are placeholders only; do not commit real secrets.",
        "# Fill one variable from each group; prefer XAGENT_* names.",
        "# Alias variables are alternatives, not additional required secrets.",
        "# Placeholder values are ignored by rc_owner_gate_runner.py.",
        f"# Generated at: {template.generated_at}",
        "",
    ]
    for entry in template.entries:
        gates = ", ".join(entry.required_by)
        lines.append(f"# Required by: {gates}")
        if entry.aliases:
            lines.append(f"# Aliases: {', '.join(entry.aliases)}")
        lines.append(f"$env:{entry.name} = '{_escape_powershell(entry.value)}'")
        lines.append("")
    return "\n".join(lines).rstrip() + "\n"


def write_outputs(
    template: OwnerEnvTemplate,
    *,
    json_output: Path,
    env_output: Path,
    powershell_output: Path,
) -> None:
    json_output.parent.mkdir(parents=True, exist_ok=True)
    env_output.parent.mkdir(parents=True, exist_ok=True)
    powershell_output.parent.mkdir(parents=True, exist_ok=True)
    json_output.write_text(json.dumps(template.to_dict(), ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    env_output.write_text(render_env(template), encoding="utf-8")
    powershell_output.write_text(render_powershell(template), encoding="utf-8")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Render the X-Agent commercial RC owner env template")
    parser.add_argument("--plan", type=Path, default=DEFAULT_PLAN)
    parser.add_argument("--external-smoke", type=Path, default=DEFAULT_EXTERNAL_SMOKE)
    parser.add_argument("--json-output", type=Path, default=DEFAULT_JSON_OUTPUT)
    parser.add_argument("--env-output", type=Path, default=DEFAULT_ENV_OUTPUT)
    parser.add_argument("--powershell-output", type=Path, default=DEFAULT_POWERSHELL_OUTPUT)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    template = build_env_template(args.plan, external_smoke_path=args.external_smoke)
    write_outputs(
        template,
        json_output=args.json_output,
        env_output=args.env_output,
        powershell_output=args.powershell_output,
    )
    print(f"RC owner env template status: {template.status}")
    print(f"JSON written to {args.json_output}")
    print(f"Env template written to {args.env_output}")
    print(f"PowerShell template written to {args.powershell_output}")
    for entry in template.entries:
        print(f"- {entry.name}: required_by={','.join(entry.required_by)}")
    return 0 if template.status == "created" else 1


if __name__ == "__main__":
    raise SystemExit(main())
