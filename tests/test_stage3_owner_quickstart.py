from __future__ import annotations

import json
from pathlib import Path

from scripts.stage3_owner_quickstart import build_stage3_owner_quickstart, main, render_markdown_report


def _write_json(path: Path, payload: dict[str, object]) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload), encoding="utf-8")
    return path


def _todo(path: Path) -> Path:
    return _write_json(
        path,
        {
            "status": "stage3_owner_evidence_todo_ready",
            "generated_at": "2026-06-18T00:00:00Z",
            "todo_count": 32,
            "release_sha": "dca6a063e9c21ee5e420d3346c28735b17a92fdf",
            "mutation_performed": False,
            "deploy_performed": False,
            "workflow_dispatch_performed": False,
            "raw_secret_values_recorded": False,
        },
    )


def _domain_guide(path: Path, *, domain: str = "xagent.example.com") -> Path:
    return _write_json(
        path,
        {
            "status": "stage3_owner_domain_guide_ready",
            "domain": domain,
            "expected_ip": "111.228.49.160",
            "release_sha": "dca6a063e9c21ee5e420d3346c28735b17a92fdf",
        },
    )


def test_stage3_owner_quickstart_summarizes_six_no_secret_steps(tmp_path: Path) -> None:
    report = build_stage3_owner_quickstart(
        todo_json=_todo(tmp_path / "todo.json"),
        domain_guide_json=_domain_guide(tmp_path / "guide.json", domain="xagent.customer.test"),
    )

    assert report.status == "stage3_owner_quickstart_ready"
    assert report.todo_count == 32
    assert report.release_sha == "dca6a063e9c21ee5e420d3346c28735b17a92fdf"
    assert report.mutation_performed is False
    assert report.deploy_performed is False
    assert report.workflow_dispatch_performed is False
    assert report.raw_secret_values_recorded is False
    assert [step.order for step in report.steps] == [1, 2, 3, 4, 5, 6]
    assert any("xagent.customer.test" in step.done_when for step in report.steps)
    assert any("no raw secret values" in item for item in report.blocked_until)


def test_stage3_owner_quickstart_keeps_example_domain_as_placeholder(tmp_path: Path) -> None:
    report = build_stage3_owner_quickstart(
        todo_json=_todo(tmp_path / "todo.json"),
        domain_guide_json=_domain_guide(tmp_path / "guide.json"),
    )

    markdown = render_markdown_report(report)

    assert "xagent.example.com" not in markdown
    assert "<REAL_DOMAIN>" in markdown
    assert 'stage3_https_preflight.py --domain "<REAL_DOMAIN>"' in markdown


def test_stage3_owner_quickstart_markdown_has_no_secret_values(tmp_path: Path) -> None:
    report = build_stage3_owner_quickstart(
        todo_json=_todo(tmp_path / "todo.json"),
        domain_guide_json=_domain_guide(tmp_path / "guide.json", domain="xagent.customer.test"),
    )
    markdown = render_markdown_report(report)

    assert "Stage3 Owner Quickstart" in markdown
    assert "Six Steps" in markdown
    assert "sk-" not in markdown
    assert "password=" not in markdown.lower()
    assert "xagent.customer.test" in markdown


def test_stage3_owner_quickstart_cli_writes_reports(tmp_path: Path) -> None:
    output_json = tmp_path / "quickstart.json"
    output_md = tmp_path / "quickstart.md"

    rc = main(
        [
            "--todo-json",
            str(_todo(tmp_path / "todo.json")),
            "--domain-guide-json",
            str(_domain_guide(tmp_path / "guide.json")),
            "--output-json",
            str(output_json),
            "--output-md",
            str(output_md),
        ]
    )

    payload = json.loads(output_json.read_text(encoding="utf-8"))
    markdown = output_md.read_text(encoding="utf-8")
    assert rc == 0
    assert payload["status"] == "stage3_owner_quickstart_ready"
    assert payload["todo_count"] == 32
    assert payload["mutation_performed"] is False
    assert payload["raw_secret_values_recorded"] is False
    assert "strict final gate" in markdown
    assert "rc_final_gate.py --require-ready-to-tag --require-stage3-rehearsal" in markdown
