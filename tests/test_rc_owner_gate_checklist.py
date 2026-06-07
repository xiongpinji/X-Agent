from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

from scripts.rc_owner_gate_checklist import build_checklist, render_markdown, write_outputs


def _write_plan(path: Path, *, status: str, gates: list[dict[str, object]]) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(
            {
                "status": status,
                "generated_at": "2026-06-06T01:00:00Z",
                "external_smoke_report": str(path.parent / "rc-external-smoke.json"),
                "source_bundle_report": str(path.parent / "rc-source-bundle.json"),
                "evidence_freshness": {
                    "fresh": False,
                    "external_generated_at": "2026-06-06T00:00:00Z",
                    "source_bundle_generated_at": "2026-06-06T01:00:00Z",
                    "problems": ["external smoke evidence is older than the current source bundle"],
                },
                "next_commands": [
                    "python scripts\\rc_owner_gate_runner.py --gate all",
                    "python scripts\\rc_external_smoke.py --require-configured",
                    "python scripts\\rc_final_gate.py --require-ready-to-tag",
                ],
                "gates": gates,
            }
        ),
        encoding="utf-8",
    )
    return path


def _gate(name: str, status: str = "action_required") -> dict[str, object]:
    return {
        "name": name,
        "status": status,
        "required_env_groups": [["XAGENT_SECRET"]],
        "configured_env": ["XAGENT_SECRET"],
        "missing": [] if status == "verified" else ["Set XAGENT_SECRET in the owner secret store."],
        "command": "python scripts\\rc_external_smoke.py --require-configured",
        "evidence": [f".xagent_runtime/reports/rc-external-smoke.json: checks[name={name}].status == passed"],
        "completion_criteria": ["The check is passed by real external evidence."],
        "notes": ["secret value is never rendered"],
    }


def test_checklist_reports_missing_plan(tmp_path: Path) -> None:
    checklist = build_checklist(tmp_path / "missing.json")

    assert checklist.status == "failed"
    assert checklist.errors
    assert checklist.gates == []
    assert "rc_owner_gate_plan.py" in checklist.next_commands[0]


def test_checklist_renders_action_required_handoff_without_secret_values(tmp_path: Path) -> None:
    plan = _write_plan(
        tmp_path / "rc-owner-gate-plan.json",
        status="action_required",
        gates=[
            {
                **_gate("provider"),
                "configured_env": ["XAGENT_OPENAI_API_KEY"],
                "missing": ["Set XAGENT_OPENAI_API_KEY or OPENAI_API_KEY."],
            },
            _gate("hosted_github_actions_commercial_rc"),
        ],
    )

    checklist = build_checklist(plan)
    markdown = render_markdown(checklist)

    assert checklist.status == "action_required"
    assert markdown.startswith("# X-Agent Commercial RC Owner Gate Checklist")
    assert "provider" in markdown
    assert "XAGENT_OPENAI_API_KEY" in markdown
    assert "Required environment variable groups:" in markdown
    assert "XAGENT_SECRET" in markdown
    assert "Set XAGENT_OPENAI_API_KEY" in markdown
    assert "sk-test" not in markdown
    assert "ghp_" not in markdown
    assert "secret value" in markdown
    assert "external smoke evidence is older" in markdown


def test_checklist_is_verified_when_all_gates_verified(tmp_path: Path) -> None:
    plan = _write_plan(
        tmp_path / "rc-owner-gate-plan.json",
        status="verified",
        gates=[
            _gate("provider", "verified"),
            _gate("feishu_webhook_contract", "verified"),
            _gate("github_issue_to_pr_dry_run", "verified"),
            _gate("github_issue_to_pr_execute_preflight", "verified"),
            _gate("hosted_github_actions_commercial_rc", "verified"),
        ],
    )

    checklist = build_checklist(plan)

    assert checklist.status == "verified"
    assert all(gate.complete for gate in checklist.gates)
    assert "Gate completion: `5/5`" in render_markdown(checklist)


def test_checklist_adds_external_smoke_notes_for_ready_to_run_gate(tmp_path: Path) -> None:
    plan = _write_plan(
        tmp_path / "rc-owner-gate-plan.json",
        status="ready_to_run",
        gates=[
            {
                **_gate("provider", "ready_to_run"),
                "missing": [],
                "command": "python scripts\\rc_external_smoke.py --check provider --provider ollama",
            }
        ],
    )
    (tmp_path / "rc-external-smoke.json").write_text(
        json.dumps(
            {
                "status": "passed",
                "checks": [
                    {
                        "name": "provider",
                        "status": "skipped",
                        "missing": ["Start Ollama or set XAGENT_OLLAMA_BASE_URL/OLLAMA_BASE_URL for local-model smoke."],
                        "error": "HTTP Error 500: Internal Server Error",
                    }
                ],
            }
        ),
        encoding="utf-8",
    )

    checklist = build_checklist(plan)
    provider = checklist.gates[0]
    markdown = render_markdown(checklist)

    assert checklist.status == "ready_to_run"
    assert provider.status == "ready_to_run"
    assert "External smoke provider is skipped." in provider.notes
    assert any("Start Ollama" in note for note in provider.notes)
    assert any("HTTP Error 500" in note for note in provider.notes)
    assert "External smoke provider is skipped." in markdown
    assert "HTTP Error 500" in markdown


def test_write_outputs_writes_json_and_markdown(tmp_path: Path) -> None:
    plan = _write_plan(tmp_path / "rc-owner-gate-plan.json", status="verified", gates=[_gate("provider", "verified")])
    checklist = build_checklist(plan)
    json_output = tmp_path / "checklist.json"
    markdown_output = tmp_path / "checklist.md"

    write_outputs(checklist, json_output=json_output, markdown_output=markdown_output)

    payload = json.loads(json_output.read_text(encoding="utf-8"))
    assert payload["status"] == "verified"
    assert markdown_output.read_text(encoding="utf-8").startswith("# X-Agent Commercial RC Owner Gate Checklist")


def test_cli_fail_action_required_returns_nonzero(tmp_path: Path) -> None:
    plan = _write_plan(tmp_path / "rc-owner-gate-plan.json", status="action_required", gates=[_gate("provider")])

    result = subprocess.run(
        [
            sys.executable,
            "scripts/rc_owner_gate_checklist.py",
            "--plan",
            str(plan),
            "--json-output",
            str(tmp_path / "checklist.json"),
            "--markdown-output",
            str(tmp_path / "checklist.md"),
            "--fail-action-required",
        ],
        capture_output=True,
        text=True,
        encoding="utf-8",
    )

    assert result.returncode == 1
    assert "action_required" in result.stdout


def test_cli_fail_action_required_accepts_verified_plan(tmp_path: Path) -> None:
    plan = _write_plan(tmp_path / "rc-owner-gate-plan.json", status="verified", gates=[_gate("provider", "verified")])

    result = subprocess.run(
        [
            sys.executable,
            "scripts/rc_owner_gate_checklist.py",
            "--plan",
            str(plan),
            "--json-output",
            str(tmp_path / "checklist.json"),
            "--markdown-output",
            str(tmp_path / "checklist.md"),
            "--fail-action-required",
        ],
        capture_output=True,
        text=True,
        encoding="utf-8",
    )

    assert result.returncode == 0
    assert "verified" in result.stdout
