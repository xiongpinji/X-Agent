from __future__ import annotations

import json
from pathlib import Path

from scripts import codex_hermes_gap_matrix as matrix
from scripts.codex_hermes_gap_matrix import (
    CommandOutcome,
    MatrixCheck,
    build_checks,
    run_matrix,
    write_report,
)


def _fake_runner(check: MatrixCheck, root: Path) -> CommandOutcome:
    status = "failed" if check.category == "web_chat" else "passed"
    return CommandOutcome(
        category=check.category,
        name=check.name,
        command=check.command,
        cwd=check.cwd,
        status=status,
        exit_code=1 if status == "failed" else 0,
        duration_seconds=0.01,
        timeout_seconds=check.timeout_seconds,
        stdout_tail="fake output",
        stderr_tail="fake error" if status == "failed" else "",
    )


def test_dry_run_lists_all_required_categories_without_executing(tmp_path: Path) -> None:
    called = False

    def runner(check: MatrixCheck, root: Path) -> CommandOutcome:
        nonlocal called
        called = True
        return _fake_runner(check, root)

    report = run_matrix(dry_run=True, runner=runner, root=tmp_path)

    assert called is False
    assert report["summary"]["overall_status"] == "dry_run"
    assert {check["category"] for check in report["checks"]} == {
        "first_release",
        "web_chat",
        "telegram_loop",
        "github_issue_to_pr",
        "skill_curator",
        "gateway",
        "installer",
        "frontend",
        "docs",
    }
    assert all(check["status"] == "planned" for check in report["checks"])


def test_write_report_records_missing_evidence_and_never_claims_full_parity(
    tmp_path: Path,
) -> None:
    (tmp_path / "tests").mkdir()
    (tmp_path / "frontend" / "src" / "pages").mkdir(parents=True)
    (tmp_path / "frontend" / "package.json").write_text("{}", encoding="utf-8")

    # Add only the first-release evidence. Other categories must remain missing.
    (tmp_path / "tests" / "test_first_release_entrypoints.py").write_text("", encoding="utf-8")
    (tmp_path / "tests" / "test_security.py").write_text("", encoding="utf-8")
    (tmp_path / "frontend" / "src" / "pages" / "ChatPage.tsx").write_text(
        "export default function ChatPage() { return null; }",
        encoding="utf-8",
    )

    report = run_matrix(dry_run=False, runner=_fake_runner, root=tmp_path)
    output = tmp_path / "matrix.json"
    write_report(report, output)

    payload = json.loads(output.read_text(encoding="utf-8"))
    assert payload["summary"]["overall_status"] == "missing_evidence"
    assert payload["summary"]["competitive_parity"]["full_parity_claimed"] is False
    assert payload["summary"]["competitive_parity"]["claim"] == "not_claimed"
    assert any(item["category"] == "skill_curator" for item in payload["missing_evidence"])
    assert any(check["category"] == "web_chat" and check["status"] == "failed" for check in payload["checks"])


def test_build_checks_has_stable_category_order() -> None:
    assert [check.category for check in build_checks()] == [
        "first_release",
        "web_chat",
        "telegram_loop",
        "github_issue_to_pr",
        "skill_curator",
        "gateway",
        "installer",
        "frontend",
        "docs",
    ]


def test_pytest_checks_disable_pytest_timeout_plugin() -> None:
    pytest_checks = [check for check in build_checks() if "-m" in check.command and "pytest" in check.command]

    assert pytest_checks
    for check in pytest_checks:
        assert check.command[0] == "python"
        timeout_index = check.command.index("timeout=0")
        assert check.command[timeout_index - 1] == "-o"
        faulthandler_index = check.command.index("faulthandler_timeout=0")
        assert check.command[faulthandler_index - 1] == "-o"


def test_gap_matrix_report_uses_portable_python_executable(tmp_path: Path) -> None:
    report = run_matrix(dry_run=True, root=tmp_path)

    assert report["python"]["executable"] == "python"
    python_commands = [check["command"] for check in report["checks"] if check["command"][0] == "python"]
    assert python_commands
    assert all(command[0] == "python" for command in python_commands)


def test_gap_matrix_tail_redacts_secret_like_output() -> None:
    text = "XAGENT_GITHUB_TOKEN: ghp_" + ("a" * 40) + "\ncreated sk-" + ("b" * 32)

    tail = matrix._tail(text)

    assert "XAGENT_GITHUB_TOKEN: <redacted-output>" in tail
    assert "created <redacted-secret>" in tail
    assert "ghp_" not in tail
    assert "sk-" not in tail
