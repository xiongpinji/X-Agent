from __future__ import annotations

from pathlib import Path

from scripts.xagent_doctor import CommandResult, run_doctor


def test_doctor_reports_pass_or_warn_with_fake_runner(tmp_path: Path) -> None:
    (tmp_path / "frontend" / "node_modules").mkdir(parents=True)
    (tmp_path / "frontend" / "package.json").write_text("{}", encoding="utf-8")
    (tmp_path / "tests").mkdir()
    (tmp_path / "tests" / "test_first_release_entrypoints.py").write_text("", encoding="utf-8")
    (tmp_path / "tests" / "test_codex_hermes_gap_matrix.py").write_text("", encoding="utf-8")

    def runner(command: list[str], cwd: Path) -> CommandResult:
        return CommandResult(0, "v24.0.0\n", "")

    report = run_doctor(runner=runner, root=tmp_path)

    assert report["status"] in {"pass", "warn"}
    checks = {check["name"]: check for check in report["checks"]}
    assert checks["node"]["status"] == "pass"
    assert checks["frontend_dependencies"]["status"] == "pass"


def test_doctor_reports_missing_frontend_dependencies(tmp_path: Path) -> None:
    (tmp_path / "tests").mkdir()
    (tmp_path / "tests" / "test_first_release_entrypoints.py").write_text("", encoding="utf-8")
    (tmp_path / "tests" / "test_codex_hermes_gap_matrix.py").write_text("", encoding="utf-8")

    def runner(command: list[str], cwd: Path) -> CommandResult:
        return CommandResult(0, "v24.0.0\n", "")

    report = run_doctor(runner=runner, root=tmp_path)

    checks = {check["name"]: check for check in report["checks"]}
    assert report["status"] == "fail"
    assert checks["frontend_dependencies"]["status"] == "fail"
    assert "npm install" in report["next_commands"]
