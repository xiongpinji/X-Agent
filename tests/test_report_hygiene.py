from __future__ import annotations

import ast
import json
import zipfile
from pathlib import Path

from scripts.check_report_hygiene import check_report_hygiene


def test_report_hygiene_passes_clean_structured_reports(tmp_path: Path) -> None:
    source_root = tmp_path / "source"
    reports_dir = source_root / ".xagent_runtime" / "reports"
    reports_dir.mkdir(parents=True)
    _write_json(
        reports_dir / "commercial-pilot-readiness.json",
        {
            "kind": "commercial_pilot_readiness",
            "ok": True,
            "status": "passed",
            "checks": [],
            "checks_count": 0,
        },
    )
    (reports_dir / "commercial-pilot-readiness.md").write_text("# Ready\n", encoding="utf-8")
    _write_zip(reports_dir / "commercial-pilot-pack.zip", {"readme.md": "clean package"})

    payload = check_report_hygiene(source_root=source_root, reports_dir=reports_dir)

    assert payload["ok"] is True
    assert payload["status"] == "passed"
    assert payload["summary"]["json_reports"] == 1
    assert payload["summary"]["text_artifacts"] == 1
    assert payload["summary"]["package_artifacts"] == 1
    assert payload["summary"]["issues"] == 0


def test_report_hygiene_fails_json_missing_status_and_ok(tmp_path: Path) -> None:
    source_root = tmp_path / "source"
    reports_dir = source_root / ".xagent_runtime" / "reports"
    reports_dir.mkdir(parents=True)
    _write_json(reports_dir / "latest-codex-alignment.json", {"kind": "latest_codex_alignment"})

    payload = check_report_hygiene(source_root=source_root, reports_dir=reports_dir)

    assert payload["ok"] is False
    assert payload["summary"]["missing_status_or_ok"] == 1
    assert payload["missing_status_or_ok_artifacts"] == [
        {
            "name": "latest-codex-alignment.json",
            "path": ".xagent_runtime/reports/latest-codex-alignment.json",
            "payload_kind": "latest_codex_alignment",
            "payload_ok": None,
            "payload_status": None,
        }
    ]


def test_report_hygiene_fails_top_level_lists_without_count_alias(tmp_path: Path) -> None:
    source_root = tmp_path / "source"
    reports_dir = source_root / ".xagent_runtime" / "reports"
    reports_dir.mkdir(parents=True)
    _write_json(
        reports_dir / "rc-final-gate.json",
        {
            "kind": "rc_final_gate",
            "ok": True,
            "status": "passed",
            "checks": [],
            "next_actions": [],
            "next_actions_count": 0,
        },
    )

    payload = check_report_hygiene(source_root=source_root, reports_dir=reports_dir)

    assert payload["ok"] is False
    assert payload["summary"]["missing_count_alias"] == 1
    assert payload["missing_count_alias_artifacts"] == [
        {
            "name": "rc-final-gate.json",
            "path": ".xagent_runtime/reports/rc-final-gate.json",
            "missing_count_aliases": ["checks_count"],
        }
    ]


def test_report_hygiene_redacts_secret_like_values_in_names_and_content(tmp_path: Path) -> None:
    source_root = tmp_path / "source"
    reports_dir = source_root / ".xagent_runtime" / "reports"
    reports_dir.mkdir(parents=True)
    leaked_token = "sk-" + "leakedsecretvalue1234567890"
    _write_json(
        reports_dir / f"rc-secret-{leaked_token}.json",
        {
            "kind": "rc_secret_gate",
            "ok": False,
            "status": "failed",
            "detail": f"remove {leaked_token}",
        },
    )

    payload = check_report_hygiene(source_root=source_root, reports_dir=reports_dir)
    encoded = json.dumps(payload)

    assert payload["ok"] is False
    assert payload["summary"]["secret_like_token_artifacts"] == 1
    assert leaked_token not in encoded
    assert "<redacted-secret-like-token>" in encoded
    assert payload["secret_like_token_artifacts"][0]["secret_like_tokens_count"] == 1


def test_report_hygiene_scans_text_members_inside_zip_without_echoing_content(tmp_path: Path) -> None:
    source_root = tmp_path / "source"
    reports_dir = source_root / ".xagent_runtime" / "reports"
    reports_dir.mkdir(parents=True)
    leaked_token = "sk-" + "zipleakedsecretvalue123456"
    _write_zip(reports_dir / "rc-source-bundle.zip", {"runbook.md": f"remove {leaked_token}"})

    payload = check_report_hygiene(source_root=source_root, reports_dir=reports_dir)
    encoded = json.dumps(payload)

    assert payload["ok"] is False
    assert payload["summary"]["secret_like_token_artifacts"] == 1
    assert payload["summary"]["secret_like_tokens"] == 1
    assert payload["secret_like_token_artifacts"][0]["secret_like_archive_members_count"] == 1
    assert leaked_token not in encoded
    assert "runbook.md" not in encoded


def test_report_hygiene_fails_unknown_artifacts(tmp_path: Path) -> None:
    source_root = tmp_path / "source"
    reports_dir = source_root / ".xagent_runtime" / "reports"
    reports_dir.mkdir(parents=True)
    (reports_dir / "unexpected.bin").write_bytes(b"binary")

    payload = check_report_hygiene(source_root=source_root, reports_dir=reports_dir)

    assert payload["ok"] is False
    assert payload["summary"]["unknown_artifacts"] == 1
    assert payload["issue_artifacts"][0]["name"] == "unexpected.bin"


def test_report_hygiene_can_scope_artifacts_by_name_glob(tmp_path: Path) -> None:
    source_root = tmp_path / "source"
    reports_dir = source_root / ".xagent_runtime" / "reports"
    reports_dir.mkdir(parents=True)
    _write_json(
        reports_dir / "commercial-delivery-task-board.json",
        {"status": "ready", "tasks": [], "tasks_count": 0},
    )
    _write_json(reports_dir / "old-report.json", {"tasks": []})

    payload = check_report_hygiene(
        source_root=source_root,
        reports_dir=reports_dir,
        include_globs=["commercial-delivery-*.json"],
    )

    assert payload["ok"] is True
    assert payload["include_globs"] == ["commercial-delivery-*.json"]
    assert payload["include_globs_count"] == 1
    assert payload["summary"]["artifacts"] == 1
    assert payload["artifacts"][0]["name"] == "commercial-delivery-task-board.json"


def test_report_hygiene_can_exclude_output_artifact(tmp_path: Path) -> None:
    source_root = tmp_path / "source"
    reports_dir = source_root / ".xagent_runtime" / "reports"
    reports_dir.mkdir(parents=True)
    _write_json(
        reports_dir / "commercial-delivery-task-board.json",
        {"status": "ready", "tasks": [], "tasks_count": 0},
    )
    output = reports_dir / "commercial-delivery-report-hygiene.json"
    _write_json(output, {"status": "failed", "artifacts": []})

    payload = check_report_hygiene(
        source_root=source_root,
        reports_dir=reports_dir,
        include_globs=["commercial-delivery-*.json"],
        exclude_paths=[output],
    )

    assert payload["ok"] is True
    assert payload["summary"]["artifacts"] == 1
    assert [artifact["name"] for artifact in payload["artifacts"]] == [
        "commercial-delivery-task-board.json"
    ]


def test_commercial_delivery_to_dicts_emit_count_aliases_for_top_level_lists() -> None:
    missing: list[str] = []
    scripts_dir = Path(__file__).resolve().parents[1] / "scripts"
    for script_path in sorted(scripts_dir.glob("commercial_delivery_*.py")):
        source = script_path.read_text(encoding="utf-8")
        tree = ast.parse(source)
        for node in ast.walk(tree):
            if not isinstance(node, ast.ClassDef):
                continue
            list_fields = [
                statement.target.id
                for statement in node.body
                if isinstance(statement, ast.AnnAssign)
                and isinstance(statement.target, ast.Name)
                and ast.unparse(statement.annotation).startswith("list[")
            ]
            if not list_fields:
                continue
            to_dict = next(
                (
                    statement
                    for statement in node.body
                    if isinstance(statement, ast.FunctionDef) and statement.name == "to_dict"
                ),
                None,
            )
            if to_dict is None:
                continue
            body = ast.get_source_segment(source, to_dict) or ""
            has_dynamic_alias_loop = 'payload[f"{name}_count"]' in body
            for field_name in list_fields:
                has_literal_alias = (
                    f'"{field_name}_count"' in body or f"'{field_name}_count'" in body
                )
                if not (has_dynamic_alias_loop or has_literal_alias):
                    missing.append(f"{script_path.name}:{node.name}.{field_name}_count")

    assert missing == []


def _write_json(path: Path, payload: dict) -> None:
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def _write_zip(path: Path, members: dict[str, str]) -> None:
    with zipfile.ZipFile(path, "w") as archive:
        for name, content in members.items():
            archive.writestr(name, content)
