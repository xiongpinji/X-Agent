from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

from scripts.rc_owner_env_template import build_env_template, render_env, render_powershell


def _write_plan(path: Path) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(
            {
                "status": "action_required",
                "generated_at": "2026-06-06T01:00:00Z",
                "next_commands": [
                    "python scripts\\rc_external_smoke.py --require-configured",
                    "python scripts\\rc_final_gate.py --require-ready-to-tag",
                ],
                "gates": [
                    {
                        "name": "provider",
                        "status": "action_required",
                        "required_env_groups": [
                            ["XAGENT_LLM_BACKEND", "LLM_BACKEND"],
                            ["XAGENT_OPENAI_API_KEY", "OPENAI_API_KEY"],
                            ["XAGENT_OLLAMA_BASE_URL", "OLLAMA_BASE_URL"],
                            ["XAGENT_OLLAMA_MODEL", "OLLAMA_MODEL"],
                        ],
                    },
                    {
                        "name": "feishu_webhook_contract",
                        "status": "action_required",
                        "required_env_groups": [
                            ["XAGENT_FEISHU_APP_ID", "FEISHU_APP_ID"],
                            ["XAGENT_FEISHU_APP_SECRET", "FEISHU_APP_SECRET"],
                            ["XAGENT_FEISHU_ENCRYPT_KEY", "FEISHU_ENCRYPT_KEY"],
                        ],
                    },
                    {
                        "name": "github_issue_to_pr_execute_preflight",
                        "status": "action_required",
                        "required_env_groups": [
                            ["XAGENT_GITHUB_TOKEN", "GITHUB_TOKEN"],
                            ["XAGENT_GITHUB_TEST_ISSUE_URL", "GITHUB_TEST_ISSUE_URL"],
                        ],
                    },
                    {
                        "name": "hosted_github_actions_commercial_rc",
                        "status": "action_required",
                        "required_env_groups": [
                            ["XAGENT_COMMERCIAL_RC_GITHUB_ACTIONS_RUN_URL"],
                            ["XAGENT_COMMERCIAL_RC_GITHUB_ACTIONS_HEAD_SHA"],
                            ["XAGENT_GITHUB_TOKEN", "GITHUB_TOKEN"],
                        ],
                    },
                ],
            }
        ),
        encoding="utf-8",
    )
    return path


def test_env_template_reports_missing_plan(tmp_path: Path) -> None:
    template = build_env_template(tmp_path / "missing.json")

    assert template.status == "failed"
    assert template.errors
    assert template.env_groups == []
    assert template.entries == []
    assert "rc_owner_gate_plan.py" in template.command_sequence[0]


def test_env_template_builds_unique_entries_with_aliases(tmp_path: Path) -> None:
    template = build_env_template(_write_plan(tmp_path / "rc-owner-gate-plan.json"))
    entries = {entry.name: entry for entry in template.entries}

    assert template.status == "created"
    assert entries["XAGENT_LLM_BACKEND"].value == "<openai|deepseek|anthropic|ollama|local>"
    assert "LLM_BACKEND" in entries["XAGENT_LLM_BACKEND"].aliases
    assert entries["XAGENT_OLLAMA_BASE_URL"].value == "<set-in-owner-secret-store>"
    assert "OLLAMA_BASE_URL" in entries["XAGENT_OLLAMA_BASE_URL"].aliases
    assert entries["XAGENT_OLLAMA_MODEL"].value == "<ollama-model-name>"
    assert "OLLAMA_MODEL" in entries["XAGENT_OLLAMA_MODEL"].aliases
    assert entries["XAGENT_GITHUB_TOKEN"].required_by == [
        "github_issue_to_pr_execute_preflight",
        "hosted_github_actions_commercial_rc",
    ]
    assert entries["XAGENT_COMMERCIAL_RC_GITHUB_ACTIONS_HEAD_SHA"].value == "<40-character-git-commit-sha>"
    assert entries["XAGENT_COMMERCIAL_RC_GITHUB_ACTIONS_HEAD_SHA"].required_by == [
        "hosted_github_actions_commercial_rc"
    ]
    assert ["XAGENT_LLM_BACKEND", "LLM_BACKEND"] in template.env_groups
    assert ["XAGENT_GITHUB_TOKEN", "GITHUB_TOKEN"] in template.env_groups
    assert ["XAGENT_COMMERCIAL_RC_GITHUB_ACTIONS_HEAD_SHA"] in template.env_groups
    assert len(entries) == len(template.entries)


def test_env_template_renders_placeholders_without_secret_values(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setenv("XAGENT_OPENAI_API_KEY", "openai-real-value-that-must-not-render")
    monkeypatch.setenv("XAGENT_GITHUB_TOKEN", "github-real-value-that-must-not-render")

    template = build_env_template(_write_plan(tmp_path / "rc-owner-gate-plan.json"))
    env_text = render_env(template)
    ps_text = render_powershell(template)
    combined = env_text + ps_text + json.dumps(template.to_dict())

    assert "XAGENT_OPENAI_API_KEY" in combined
    assert "XAGENT_GITHUB_TOKEN" in combined
    assert "openai-real-value" not in combined
    assert "github-real-value" not in combined
    assert "<set-in-owner-secret-store>" in combined
    assert "https://github.com/<owner>/<repo>/issues/<number>" in combined
    assert "<40-character-git-commit-sha>" in combined


def test_env_template_explains_group_and_alias_semantics(tmp_path: Path) -> None:
    template = build_env_template(_write_plan(tmp_path / "rc-owner-gate-plan.json"))
    env_text = render_env(template)
    ps_text = render_powershell(template)
    payload = template.to_dict()

    assert "Fill one variable from each group; prefer XAGENT_* names." in env_text
    assert "Alias variables are alternatives, not additional required secrets." in env_text
    assert "Placeholder values are ignored by rc_owner_gate_runner.py." in env_text
    assert "Fill one variable from each group; prefer XAGENT_* names." in ps_text
    assert ["XAGENT_FEISHU_ENCRYPT_KEY", "FEISHU_ENCRYPT_KEY"] in payload["env_groups"]


def test_env_template_prefills_verified_ollama_provider_without_secrets(tmp_path: Path) -> None:
    plan = _write_plan(tmp_path / "rc-owner-gate-plan.json")
    external_smoke = tmp_path / "rc-external-smoke.json"
    external_smoke.write_text(
        json.dumps(
            {
                "status": "passed",
                "checks": [
                    {
                        "name": "provider",
                        "status": "passed",
                        "details": {
                            "provider": "ollama",
                            "base_url": "http://127.0.0.1:11435",
                            "model": "qwen2.5:1.5b",
                            "sentinel_matched": True,
                        },
                    },
                    {
                        "name": "github_issue_to_pr_execute_preflight",
                        "status": "skipped",
                        "details": {"token": "fixture-token-must-not-render"},
                    },
                ],
            }
        ),
        encoding="utf-8",
    )

    template = build_env_template(plan, external_smoke_path=external_smoke)
    entries = {entry.name: entry for entry in template.entries}
    combined = render_env(template) + render_powershell(template) + json.dumps(template.to_dict())

    assert entries["XAGENT_LLM_BACKEND"].value == "ollama"
    assert entries["LLM_BACKEND"].value == "<openai|deepseek|anthropic|ollama|local>"
    assert entries["XAGENT_OLLAMA_BASE_URL"].value == "http://127.0.0.1:11435"
    assert entries["OLLAMA_BASE_URL"].value == "<set-in-owner-secret-store>"
    assert entries["XAGENT_OLLAMA_MODEL"].value == "qwen2.5:1.5b"
    assert entries["OLLAMA_MODEL"].value == "<ollama-model-name>"
    assert "fixture-token-must-not-render" not in combined


def test_env_template_prefills_failed_ollama_reproduction_hints(tmp_path: Path) -> None:
    plan = _write_plan(tmp_path / "rc-owner-gate-plan.json")
    external_smoke = tmp_path / "rc-external-smoke.json"
    external_smoke.write_text(
        json.dumps(
            {
                "status": "passed",
                "checks": [
                    {
                        "name": "provider",
                        "status": "skipped",
                        "details": {
                            "provider": "ollama",
                            "base_url": "http://localhost:11434",
                            "model": "qwen2.5:1.5b",
                            "token": "fixture-token-must-not-render",
                        },
                        "missing": ["Reinstall or move the selected model."],
                        "error": "HTTP Error 500",
                    }
                ],
            }
        ),
        encoding="utf-8",
    )

    template = build_env_template(plan, external_smoke_path=external_smoke)
    entries = {entry.name: entry for entry in template.entries}
    combined = render_env(template) + render_powershell(template) + json.dumps(template.to_dict())

    assert entries["XAGENT_LLM_BACKEND"].value == "ollama"
    assert entries["XAGENT_OLLAMA_BASE_URL"].value == "http://localhost:11434"
    assert entries["XAGENT_OLLAMA_MODEL"].value == "qwen2.5:1.5b"
    assert "fixture-token-must-not-render" not in combined


def test_env_template_cli_writes_all_outputs(tmp_path: Path) -> None:
    plan = _write_plan(tmp_path / "rc-owner-gate-plan.json")
    json_output = tmp_path / "owner-env.json"
    env_output = tmp_path / "owner-env.env"
    powershell_output = tmp_path / "owner-env.ps1"

    result = subprocess.run(
        [
            sys.executable,
            "scripts/rc_owner_env_template.py",
            "--plan",
            str(plan),
            "--json-output",
            str(json_output),
            "--env-output",
            str(env_output),
            "--powershell-output",
            str(powershell_output),
        ],
        capture_output=True,
        text=True,
        encoding="utf-8",
    )

    assert result.returncode == 0
    assert "created" in result.stdout
    assert json.loads(json_output.read_text(encoding="utf-8"))["status"] == "created"
    assert env_output.read_text(encoding="utf-8").startswith("# X-Agent Commercial RC owner gate environment template")
    assert powershell_output.read_text(encoding="utf-8").startswith(
        "# X-Agent Commercial RC owner gate environment template"
    )
