from __future__ import annotations

import json
from pathlib import Path

from scripts.rc_owner_handoff_gate import build_owner_handoff_gate


def _write_json(path: Path, payload: dict[str, object]) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload), encoding="utf-8")
    return path


def _write_text(path: Path, text: str) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")
    return path


def _windows_user_path(*parts: str) -> str:
    return "C:" + "\\" + "Users" + "\\" + "canqu" + "\\" + "\\".join(parts)


STRICT_CRITERIA_BY_GATE = {
    "feishu_webhook_contract": [
        "Invalid and missing Feishu webhook signatures are rejected.",
    ],
    "github_issue_to_pr_execute_preflight": [
        "Disposable GitHub test issue remains open with read_probe.state=open.",
        "Token-authenticated read-only GitHub repository permission probe confirms permissions.push=true.",
        "GitHub token does not expose admin or maintain permissions.",
        "No branch push, PR creation, or issue comment is performed by the smoke.",
    ],
    "hosted_github_actions_commercial_rc": [
        "commercial-rc-linux job succeeds.",
        "commercial-rc-windows-installer job succeeds.",
        "commercial-rc-evidence artifact is attached to the run.",
        "Read-only GitHub Actions run API probe confirms head_sha_verified=true.",
        "Read-only GitHub Actions jobs API probe confirms both required jobs completed successfully.",
        "Read-only GitHub Actions artifacts API probe confirms commercial-rc-evidence is attached.",
    ],
}


def _gate(
    name: str,
    *,
    command: str,
    env_groups: list[list[str]],
    status: str = "action_required",
) -> dict[str, object]:
    return {
        "name": name,
        "status": status,
        "required_env_groups": env_groups,
        "configured_env": [],
        "missing": [] if status == "verified" else [f"Complete {name} with owner resources."],
        "command": command,
        "evidence": [f".xagent_runtime/reports/rc-external-smoke.json: checks[name={name}].status == passed"],
        "completion_criteria": [
            f"{name} is proven by real owner-controlled evidence.",
            *STRICT_CRITERIA_BY_GATE.get(name, []),
        ],
        "notes": ["No secret values are rendered."],
    }


def _paths(tmp_path: Path) -> dict[str, Path]:
    return {
        "plan": tmp_path / "reports" / "rc-owner-gate-plan.json",
        "template": tmp_path / "reports" / "rc-owner-env-template.json",
        "env": tmp_path / "reports" / "rc-owner-env-template.env",
        "ps": tmp_path / "reports" / "rc-owner-env-template.ps1",
        "checklist": tmp_path / "reports" / "rc-owner-gate-checklist.json",
        "markdown": tmp_path / "reports" / "rc-owner-gate-checklist.md",
        "external": tmp_path / "reports" / "rc-external-smoke.json",
        "source": tmp_path / "reports" / "rc-source-bundle.json",
    }


def _external_smoke_checks() -> list[dict[str, object]]:
    return [
        {
            "name": "provider",
            "status": "skipped",
            "missing": ["Start Ollama or set XAGENT_OLLAMA_BASE_URL/OLLAMA_BASE_URL for local-model smoke."],
            "error": "HTTP Error 500: Internal Server Error",
        },
        {
            "name": "feishu_webhook_contract",
            "status": "skipped",
            "missing": [
                "Set XAGENT_FEISHU_APP_ID or FEISHU_APP_ID.",
                "Set XAGENT_FEISHU_APP_SECRET or FEISHU_APP_SECRET.",
                "Set XAGENT_FEISHU_ENCRYPT_KEY or FEISHU_ENCRYPT_KEY for signed event callbacks.",
            ],
        },
        {
            "name": "github_issue_to_pr_dry_run",
            "status": "skipped",
            "missing": ["Set XAGENT_GITHUB_TEST_ISSUE_URL to a disposable test issue URL."],
        },
        {
            "name": "github_issue_to_pr_execute_preflight",
            "status": "skipped",
            "missing": ["Pass --github-execute-preflight to verify execute-mode readiness."],
        },
        {
            "name": "hosted_github_actions_run",
            "status": "skipped",
            "missing": ["Pass --github-actions-preflight to verify the hosted Commercial RC workflow run."],
        },
    ]


def _external_notes(gate_name: str) -> list[str]:
    check_names_by_gate = {
        "provider": ("provider",),
        "feishu_webhook_contract": ("feishu_webhook_contract",),
        "github_issue_to_pr_dry_run": ("github_issue_to_pr_dry_run",),
        "github_issue_to_pr_execute_preflight": ("github_issue_to_pr_dry_run", "github_issue_to_pr_execute_preflight"),
        "hosted_github_actions_commercial_rc": ("hosted_github_actions_run",),
    }
    checks_by_name = {str(check["name"]): check for check in _external_smoke_checks()}
    notes: list[str] = []
    for check_name in check_names_by_gate[gate_name]:
        check = checks_by_name[check_name]
        status = str(check["status"])
        notes.append(f"External smoke {check_name} is {status}.")
        for item in check.get("missing", []):
            notes.append(f"External smoke {check_name} missing: {item}")
        if check.get("error"):
            notes.append(f"External smoke {check_name} error: {check['error']}")
    return notes


def _fixture(tmp_path: Path) -> dict[str, Path]:
    paths = _paths(tmp_path)
    _write_json(paths["external"], {"status": "passed", "checks": _external_smoke_checks()})
    _write_json(paths["source"], {"status": "created", "file_count": 1})
    gates = [
        _gate(
            "provider",
            command="python scripts\\rc_external_smoke.py --check provider --provider ollama --require-configured",
            env_groups=[
                ["XAGENT_LLM_BACKEND", "LLM_BACKEND"],
                ["XAGENT_OLLAMA_BASE_URL", "OLLAMA_BASE_URL"],
                ["XAGENT_OLLAMA_MODEL", "OLLAMA_MODEL"],
            ],
        ),
        _gate(
            "feishu_webhook_contract",
            command="python scripts\\rc_external_smoke.py --check feishu_webhook_contract --require-configured",
            env_groups=[
                ["XAGENT_FEISHU_APP_ID", "FEISHU_APP_ID"],
                ["XAGENT_FEISHU_APP_SECRET", "FEISHU_APP_SECRET"],
                ["XAGENT_FEISHU_ENCRYPT_KEY", "FEISHU_ENCRYPT_KEY"],
            ],
        ),
        _gate(
            "github_issue_to_pr_dry_run",
            command="python scripts\\rc_external_smoke.py --check github_issue_to_pr_dry_run --require-configured",
            env_groups=[["XAGENT_GITHUB_TEST_ISSUE_URL", "GITHUB_TEST_ISSUE_URL"]],
        ),
        _gate(
            "github_issue_to_pr_execute_preflight",
            command=(
                "python scripts\\rc_external_smoke.py --check github_issue_to_pr_dry_run "
                "--check github_issue_to_pr_execute_preflight --require-configured --github-execute-preflight"
            ),
            env_groups=[
                ["XAGENT_GITHUB_TOKEN", "GITHUB_TOKEN"],
                ["XAGENT_GITHUB_TEST_ISSUE_URL", "GITHUB_TEST_ISSUE_URL"],
            ],
        ),
        _gate(
            "hosted_github_actions_commercial_rc",
            command=(
                "python scripts\\rc_external_smoke.py --check hosted_github_actions_run "
                "--github-actions-preflight --require-configured"
            ),
            env_groups=[
                ["XAGENT_COMMERCIAL_RC_GITHUB_ACTIONS_RUN_URL"],
                ["XAGENT_COMMERCIAL_RC_GITHUB_ACTIONS_HEAD_SHA"],
                ["XAGENT_GITHUB_TOKEN", "GITHUB_TOKEN"],
            ],
        ),
    ]
    _write_json(
        paths["plan"],
        {
            "status": "action_required",
            "external_smoke_report": str(paths["external"]),
            "source_bundle_report": str(paths["source"]),
            "evidence_freshness": {"required": True, "fresh": True},
            "gates": gates,
            "next_commands": [
                "Set the missing XAGENT_* environment variables in the deployment owner's secret store or shell.",
                "Trigger the hosted Commercial RC Gate workflow on GitHub Actions.",
                (
                    "Set XAGENT_COMMERCIAL_RC_GITHUB_ACTIONS_RUN_URL to the successful hosted run URL in "
                    ".xagent_runtime\\reports\\rc-owner-env-template.env or the owner secret store."
                ),
                (
                    "Set XAGENT_COMMERCIAL_RC_GITHUB_ACTIONS_HEAD_SHA to the exact commit SHA used by the "
                    "successful hosted run in .xagent_runtime\\reports\\rc-owner-env-template.env or the owner secret store."
                ),
                "python scripts\\rc_owner_gate_runner.py --gate all --env-file .xagent_runtime\\reports\\rc-owner-env-template.env",
                "python scripts\\rc_external_smoke.py --provider ollama --require-configured --github-execute-preflight --github-actions-preflight",
                "python scripts\\rc_final_gate.py --require-ready-to-tag",
            ],
        },
    )
    entries = [
        {
            "name": "XAGENT_LLM_BACKEND",
            "value": "<openai|deepseek|anthropic|ollama|local>",
            "required_by": ["provider"],
            "aliases": ["LLM_BACKEND"],
            "preferred": True,
        },
        {
            "name": "XAGENT_OLLAMA_BASE_URL",
            "value": "<set-in-owner-secret-store>",
            "required_by": ["provider"],
            "aliases": ["OLLAMA_BASE_URL"],
            "preferred": True,
        },
        {
            "name": "XAGENT_OLLAMA_MODEL",
            "value": "<set-in-owner-secret-store>",
            "required_by": ["provider"],
            "aliases": ["OLLAMA_MODEL"],
            "preferred": True,
        },
        {
            "name": "XAGENT_FEISHU_APP_ID",
            "value": "<set-in-owner-secret-store>",
            "required_by": ["feishu_webhook_contract"],
            "aliases": ["FEISHU_APP_ID"],
            "preferred": True,
        },
        {
            "name": "XAGENT_FEISHU_APP_SECRET",
            "value": "<set-in-owner-secret-store>",
            "required_by": ["feishu_webhook_contract"],
            "aliases": ["FEISHU_APP_SECRET"],
            "preferred": True,
        },
        {
            "name": "XAGENT_FEISHU_ENCRYPT_KEY",
            "value": "<set-in-owner-secret-store>",
            "required_by": ["feishu_webhook_contract"],
            "aliases": ["FEISHU_ENCRYPT_KEY"],
            "preferred": True,
        },
        {
            "name": "XAGENT_GITHUB_TEST_ISSUE_URL",
            "value": "https://github.com/<owner>/<repo>/issues/<number>",
            "required_by": ["github_issue_to_pr_dry_run", "github_issue_to_pr_execute_preflight"],
            "aliases": ["GITHUB_TEST_ISSUE_URL"],
            "preferred": True,
        },
        {
            "name": "XAGENT_GITHUB_TOKEN",
            "value": "<set-in-owner-secret-store>",
            "required_by": ["github_issue_to_pr_execute_preflight", "hosted_github_actions_commercial_rc"],
            "aliases": ["GITHUB_TOKEN"],
            "preferred": True,
        },
        {
            "name": "XAGENT_COMMERCIAL_RC_GITHUB_ACTIONS_RUN_URL",
            "value": "https://github.com/<owner>/<repo>/actions/runs/<run-id>",
            "required_by": ["hosted_github_actions_commercial_rc"],
            "aliases": [],
            "preferred": True,
        },
        {
            "name": "XAGENT_COMMERCIAL_RC_GITHUB_ACTIONS_HEAD_SHA",
            "value": "<40-character-git-commit-sha>",
            "required_by": ["hosted_github_actions_commercial_rc"],
            "aliases": [],
            "preferred": True,
        },
    ]
    _write_json(
        paths["template"],
        {
            "status": "created",
            "env_groups": [
                group
                for gate in gates
                for group in gate["required_env_groups"]
            ],
            "entries": entries,
            "command_sequence": ["Fill placeholders", "python scripts\\rc_external_smoke.py --require-configured"],
            "errors": [],
        },
    )
    env_lines = "\n".join(f'{entry["name"]}="{entry["value"]}"' for entry in entries)
    ps_lines = "\n".join(f"$env:{entry['name']} = '{entry['value']}'" for entry in entries)
    _write_text(paths["env"], env_lines)
    _write_text(paths["ps"], ps_lines)
    checklist_gates = [
        {
            "name": gate["name"],
            "status": gate["status"],
            "complete": gate["status"] == "verified",
            "action_required": gate["status"] != "verified",
            "required_env_groups": gate["required_env_groups"],
            "configured_env": gate["configured_env"],
            "missing": gate["missing"],
            "command": gate["command"],
            "evidence": gate["evidence"],
            "completion_criteria": gate["completion_criteria"],
            "notes": [*gate["notes"], *_external_notes(str(gate["name"]))],
        }
        for gate in gates
    ]
    _write_json(
        paths["checklist"],
        {
            "status": "action_required",
            "gates": checklist_gates,
            "next_commands": [
                "Set the missing XAGENT_* environment variables in the deployment owner's secret store or shell.",
                "Trigger the hosted Commercial RC Gate workflow on GitHub Actions.",
                (
                    "Set XAGENT_COMMERCIAL_RC_GITHUB_ACTIONS_RUN_URL to the successful hosted run URL in "
                    ".xagent_runtime\\reports\\rc-owner-env-template.env or the owner secret store."
                ),
                (
                    "Set XAGENT_COMMERCIAL_RC_GITHUB_ACTIONS_HEAD_SHA to the exact commit SHA used by the "
                    "successful hosted run in .xagent_runtime\\reports\\rc-owner-env-template.env or the owner secret store."
                ),
                "python scripts\\rc_owner_gate_runner.py --gate all --env-file .xagent_runtime\\reports\\rc-owner-env-template.env",
                "python scripts\\rc_external_smoke.py --provider ollama --require-configured --github-execute-preflight --github-actions-preflight",
                "python scripts\\rc_final_gate.py --require-ready-to-tag",
            ],
            "errors": [],
        },
    )
    markdown = "# X-Agent Commercial RC Owner Gate Checklist\n\n" + "\n".join(
        f"## [ ] {gate['name']}\n\n"
        + "\n".join(
            f"- {env_name}"
            for group in gate["required_env_groups"]
            for env_name in group
        )
        + f"\n\n```powershell\n{gate['command']}\n```"
        + "\n\nCompletion criteria:\n"
        + "\n".join(f"- {item}" for item in gate["completion_criteria"])
        + "\n\nNotes:\n"
        + "\n".join(f"- {note}" for note in _external_notes(str(gate["name"])))
        for gate in gates
    )
    _write_text(paths["markdown"], markdown)
    return paths


def _report(paths: dict[str, Path]):
    return build_owner_handoff_gate(
        owner_gate_plan_path=paths["plan"],
        owner_env_template_path=paths["template"],
        owner_env_file_path=paths["env"],
        owner_env_powershell_path=paths["ps"],
        owner_gate_checklist_path=paths["checklist"],
        owner_gate_checklist_markdown_path=paths["markdown"],
    )


def test_owner_handoff_gate_passes_for_complete_non_secret_handoff(tmp_path: Path) -> None:
    report = _report(_fixture(tmp_path))

    assert report.status == "passed"
    assert {check.name: check.status for check in report.checks}["owner_gate_plan"] == "passed"


def test_owner_handoff_gate_rejects_missing_hosted_actions_preflight_token(tmp_path: Path) -> None:
    paths = _fixture(tmp_path)
    plan = json.loads(paths["plan"].read_text(encoding="utf-8"))
    for gate in plan["gates"]:
        if gate["name"] == "hosted_github_actions_commercial_rc":
            gate["command"] = "python scripts\\rc_external_smoke.py --require-configured"
    _write_json(paths["plan"], plan)

    report = _report(paths)

    assert report.status == "failed"
    check = next(item for item in report.checks if item.name == "owner_gate_plan")
    assert "--github-actions-preflight" in str(check.error)


def test_owner_handoff_gate_rejects_provider_command_without_require_configured(tmp_path: Path) -> None:
    paths = _fixture(tmp_path)
    plan = json.loads(paths["plan"].read_text(encoding="utf-8"))
    for gate in plan["gates"]:
        if gate["name"] == "provider":
            gate["command"] = "python scripts\\rc_external_smoke.py --check provider --provider ollama"
    _write_json(paths["plan"], plan)

    report = _report(paths)

    assert report.status == "failed"
    check = next(item for item in report.checks if item.name == "owner_gate_plan")
    assert "--require-configured" in str(check.error)


def test_owner_handoff_gate_rejects_runner_next_command_without_env_file(tmp_path: Path) -> None:
    paths = _fixture(tmp_path)
    plan = json.loads(paths["plan"].read_text(encoding="utf-8"))
    checklist = json.loads(paths["checklist"].read_text(encoding="utf-8"))
    plan["next_commands"] = [
        "python scripts\\rc_owner_gate_runner.py --gate all" if "rc_owner_gate_runner.py" in command else command
        for command in plan["next_commands"]
    ]
    checklist["next_commands"] = [
        "python scripts\\rc_owner_gate_runner.py --gate all" if "rc_owner_gate_runner.py" in command else command
        for command in checklist["next_commands"]
    ]
    _write_json(paths["plan"], plan)
    _write_json(paths["checklist"], checklist)

    report = _report(paths)

    assert report.status == "failed"
    assert "--env-file" in json.dumps(report.to_dict())


def test_owner_handoff_gate_rejects_external_next_command_without_all_preflights(tmp_path: Path) -> None:
    paths = _fixture(tmp_path)
    plan = json.loads(paths["plan"].read_text(encoding="utf-8"))
    checklist = json.loads(paths["checklist"].read_text(encoding="utf-8"))
    weak_command = (
        "python scripts\\rc_external_smoke.py --provider ollama "
        "--require-configured --github-actions-preflight"
    )
    plan["next_commands"] = [
        weak_command if "rc_external_smoke.py" in command else command for command in plan["next_commands"]
    ]
    checklist["next_commands"] = [
        weak_command if "rc_external_smoke.py" in command else command for command in checklist["next_commands"]
    ]
    _write_json(paths["plan"], plan)
    _write_json(paths["checklist"], checklist)

    report = _report(paths)

    assert report.status == "failed"
    payload = json.dumps(report.to_dict())
    assert "--github-execute-preflight" in payload


def test_owner_handoff_gate_rejects_actions_preflight_before_hosted_run_url(tmp_path: Path) -> None:
    paths = _fixture(tmp_path)
    plan = json.loads(paths["plan"].read_text(encoding="utf-8"))
    checklist = json.loads(paths["checklist"].read_text(encoding="utf-8"))
    for payload in (plan, checklist):
        commands = list(payload["next_commands"])
        run_url_index = next(index for index, command in enumerate(commands) if "XAGENT_COMMERCIAL_RC_GITHUB_ACTIONS_RUN_URL" in command)
        smoke_index = next(index for index, command in enumerate(commands) if "rc_external_smoke.py" in command)
        commands[run_url_index], commands[smoke_index] = commands[smoke_index], commands[run_url_index]
        payload["next_commands"] = commands
    _write_json(paths["plan"], plan)
    _write_json(paths["checklist"], checklist)

    report = _report(paths)

    assert report.status == "failed"
    payload = json.dumps(report.to_dict())
    assert "next_commands order invalid" in payload
    assert "XAGENT_COMMERCIAL_RC_GITHUB_ACTIONS_RUN_URL" in payload


def test_owner_handoff_gate_rejects_missing_strict_hosted_actions_completion_criteria(tmp_path: Path) -> None:
    paths = _fixture(tmp_path)
    plan = json.loads(paths["plan"].read_text(encoding="utf-8"))
    checklist = json.loads(paths["checklist"].read_text(encoding="utf-8"))
    for payload in (plan, checklist):
        for gate in payload["gates"]:
            if gate["name"] == "hosted_github_actions_commercial_rc":
                gate["completion_criteria"] = [
                    item for item in gate["completion_criteria"] if "commercial-rc-evidence" not in item
                ]
    markdown = paths["markdown"].read_text(encoding="utf-8").replace(
        "- commercial-rc-evidence artifact is attached to the run.\n",
        "",
    )
    markdown = markdown.replace(
        "- Read-only GitHub Actions artifacts API probe confirms commercial-rc-evidence is attached.\n",
        "",
    )
    _write_json(paths["plan"], plan)
    _write_json(paths["checklist"], checklist)
    _write_text(paths["markdown"], markdown)

    report = _report(paths)

    assert report.status == "failed"
    payload = json.dumps(report.to_dict())
    assert "commercial-rc-evidence" in payload


def test_owner_handoff_gate_rejects_missing_hosted_actions_head_sha_env(tmp_path: Path) -> None:
    paths = _fixture(tmp_path)
    plan = json.loads(paths["plan"].read_text(encoding="utf-8"))
    template = json.loads(paths["template"].read_text(encoding="utf-8"))
    checklist = json.loads(paths["checklist"].read_text(encoding="utf-8"))
    for payload in (plan, checklist):
        for gate in payload["gates"]:
            if gate["name"] == "hosted_github_actions_commercial_rc":
                gate["required_env_groups"] = [
                    group
                    for group in gate["required_env_groups"]
                    if group != ["XAGENT_COMMERCIAL_RC_GITHUB_ACTIONS_HEAD_SHA"]
                ]
    template["env_groups"] = [
        group for group in template["env_groups"] if group != ["XAGENT_COMMERCIAL_RC_GITHUB_ACTIONS_HEAD_SHA"]
    ]
    template["entries"] = [
        entry for entry in template["entries"] if entry["name"] != "XAGENT_COMMERCIAL_RC_GITHUB_ACTIONS_HEAD_SHA"
    ]
    markdown = paths["markdown"].read_text(encoding="utf-8").replace(
        "- XAGENT_COMMERCIAL_RC_GITHUB_ACTIONS_HEAD_SHA\n",
        "",
    )
    _write_json(paths["plan"], plan)
    _write_json(paths["template"], template)
    _write_json(paths["checklist"], checklist)
    _write_text(paths["markdown"], markdown)

    report = _report(paths)

    assert report.status == "failed"
    payload = json.dumps(report.to_dict())
    assert "XAGENT_COMMERCIAL_RC_GITHUB_ACTIONS_HEAD_SHA" in payload


def test_owner_handoff_gate_rejects_ollama_provider_without_model_env(tmp_path: Path) -> None:
    paths = _fixture(tmp_path)
    plan = json.loads(paths["plan"].read_text(encoding="utf-8"))
    for gate in plan["gates"]:
        if gate["name"] == "provider":
            gate["required_env_groups"] = [["XAGENT_LLM_BACKEND", "LLM_BACKEND"]]
    _write_json(paths["plan"], plan)

    report = _report(paths)

    assert report.status == "failed"
    check = next(item for item in report.checks if item.name == "owner_gate_plan")
    assert "XAGENT_OLLAMA_MODEL" in str(check.error)


def test_owner_handoff_gate_rejects_missing_template_env_groups(tmp_path: Path) -> None:
    paths = _fixture(tmp_path)
    template = json.loads(paths["template"].read_text(encoding="utf-8"))
    template.pop("env_groups")
    _write_json(paths["template"], template)

    report = _report(paths)

    assert report.status == "failed"
    check = next(item for item in report.checks if item.name == "owner_env_template")
    assert "env template env_groups is missing or empty" in str(check.error)


def test_owner_handoff_gate_rejects_template_env_groups_not_matching_plan(tmp_path: Path) -> None:
    paths = _fixture(tmp_path)
    template = json.loads(paths["template"].read_text(encoding="utf-8"))
    template["env_groups"] = [["XAGENT_LLM_BACKEND", "LLM_BACKEND"], ["XAGENT_UNUSED_SECRET"]]
    _write_json(paths["template"], template)

    report = _report(paths)

    assert report.status == "failed"
    check = next(item for item in report.checks if item.name == "owner_env_template")
    assert "env template env_groups missing owner plan groups" in str(check.error)
    assert "env template env_groups contains groups not declared by owner plan" in str(check.error)


def test_owner_handoff_gate_rejects_secret_like_env_values(tmp_path: Path) -> None:
    paths = _fixture(tmp_path)
    env_text = paths["env"].read_text(encoding="utf-8") + '\nXAGENT_GITHUB_TOKEN="ghp_' + ("a" * 40) + '"\n'
    _write_text(paths["env"], env_text)

    report = _report(paths)

    assert report.status == "failed"
    check = next(item for item in report.checks if item.name == "owner_env_template")
    assert "secret-like" in str(check.error)


def test_owner_handoff_gate_rejects_secret_like_powershell_values(tmp_path: Path) -> None:
    paths = _fixture(tmp_path)
    ps_text = paths["ps"].read_text(encoding="utf-8") + '\n$env:XAGENT_GITHUB_TOKEN="ghp_' + ("b" * 40) + '"\n'
    _write_text(paths["ps"], ps_text)

    report = _report(paths)

    assert report.status == "failed"
    check = next(item for item in report.checks if item.name == "owner_env_template")
    assert "secret-like" in str(check.error)


def test_owner_handoff_gate_rejects_local_path_env_values(tmp_path: Path) -> None:
    paths = _fixture(tmp_path)
    local_runtime = _windows_user_path("AppData", "Local", "xagent", "runtime")
    env_text = paths["env"].read_text(encoding="utf-8") + f'\nXAGENT_OLLAMA_BASE_URL="{local_runtime}"\n'
    _write_text(paths["env"], env_text)

    report = _report(paths)

    assert report.status == "failed"
    check = next(item for item in report.checks if item.name == "owner_env_template")
    assert "local user/runtime path" in str(check.error)
    assert check.details["local_path_findings"]


def test_owner_handoff_gate_rejects_local_path_checklist_values(tmp_path: Path) -> None:
    paths = _fixture(tmp_path)
    checklist = json.loads(paths["checklist"].read_text(encoding="utf-8"))
    checklist["gates"][0]["notes"].append(
        "Owner evidence path: " + _windows_user_path("AppData", "Local", "xagent", "reports")
    )
    _write_json(paths["checklist"], checklist)

    report = _report(paths)

    assert report.status == "failed"
    check = next(item for item in report.checks if item.name == "owner_gate_checklist")
    assert "local user/runtime path" in str(check.error)
    assert check.details["local_path_findings"]


def test_owner_handoff_gate_rejects_missing_evidence_file(tmp_path: Path) -> None:
    paths = _fixture(tmp_path)
    paths["external"].unlink()

    report = _report(paths)

    assert report.status == "failed"
    check = next(item for item in report.checks if item.name == "evidence_paths")
    assert "does not exist" in str(check.error)


def test_owner_handoff_gate_rejects_checklist_missing_gate(tmp_path: Path) -> None:
    paths = _fixture(tmp_path)
    checklist = json.loads(paths["checklist"].read_text(encoding="utf-8"))
    checklist["gates"] = [
        gate for gate in checklist["gates"] if gate["name"] != "feishu_webhook_contract"
    ]
    _write_json(paths["checklist"], checklist)

    report = _report(paths)

    assert report.status == "failed"
    check = next(item for item in report.checks if item.name == "owner_gate_checklist")
    assert "feishu_webhook_contract" in str(check.error)


def test_owner_handoff_gate_rejects_checklist_missing_required_env_name(tmp_path: Path) -> None:
    paths = _fixture(tmp_path)
    markdown = paths["markdown"].read_text(encoding="utf-8").replace("XAGENT_GITHUB_TEST_ISSUE_URL", "")
    _write_text(paths["markdown"], markdown)

    report = _report(paths)

    assert report.status == "failed"
    check = next(item for item in report.checks if item.name == "owner_gate_checklist")
    assert "XAGENT_GITHUB_TEST_ISSUE_URL" in str(check.error)


def test_owner_handoff_gate_rejects_checklist_missing_external_smoke_diagnostics(tmp_path: Path) -> None:
    paths = _fixture(tmp_path)
    checklist = json.loads(paths["checklist"].read_text(encoding="utf-8"))
    for gate in checklist["gates"]:
        if gate["name"] == "provider":
            gate["notes"] = ["No secret values are rendered."]
    _write_json(paths["checklist"], checklist)
    markdown = paths["markdown"].read_text(encoding="utf-8").replace("External smoke provider is skipped.", "")
    _write_text(paths["markdown"], markdown)

    report = _report(paths)

    assert report.status == "failed"
    check = next(item for item in report.checks if item.name == "owner_gate_checklist")
    assert "checklist provider missing external smoke note" in str(check.error)
    assert "checklist markdown missing external smoke note for provider" in str(check.error)
