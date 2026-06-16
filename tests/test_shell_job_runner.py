import json
import sys
from base64 import b64decode
from datetime import UTC, datetime
from pathlib import Path
from types import SimpleNamespace

from backend.app.core.shell_job_runner import (
    RESULT_LOG_PREFIX,
    emit_shell_job_result,
    execute_shell_job_payload,
    load_shell_job_payload,
    main,
)


def _settings(tmp_path):
    return SimpleNamespace(
        shell_tool_sandbox_path=tmp_path,
        shell_tool_max_timeout_seconds=10,
        shell_tool_max_output_chars=4_000,
        shell_tool_max_artifact_bytes=8_192,
        shell_tool_max_artifacts=20,
    )


async def test_shell_job_runner_executes_payload_and_collects_artifacts(tmp_path) -> None:
    code = "from pathlib import Path; Path('result.txt').write_text('job-ok', encoding='utf-8'); print('job-ok')"

    result = await execute_shell_job_payload(
        {"command": f'"{sys.executable}" -c "{code}"'},
        settings=_settings(tmp_path),
    )

    assert result["ok"] is True
    assert result["result"]["stdout"].strip() == "job-ok"
    assert result["result"]["artifacts"][0]["path"] == "result.txt"
    assert result["result"]["artifacts"][0]["preview"] == "job-ok"


def test_shell_job_runner_main_writes_failure_result(tmp_path, monkeypatch) -> None:
    output_path = tmp_path / "runner-result.json"
    monkeypatch.delenv("XAGENT_SHELL_JOB_PAYLOAD", raising=False)
    monkeypatch.delenv("XAGENT_SHELL_JOB_PAYLOAD_FILE", raising=False)
    monkeypatch.setenv("XAGENT_SHELL_JOB_OUTPUT_PATH", str(output_path))

    exit_code = main()
    payload = json.loads(output_path.read_text(encoding="utf-8"))

    assert exit_code == 1
    assert payload["ok"] is False
    assert "XAGENT_SHELL_JOB_PAYLOAD" in payload["error"]


def test_shell_job_runner_log_emit_serializes_open_payload_values(capsys) -> None:
    emit_shell_job_result(
        {
            "ok": True,
            "completed_at": datetime(2026, 5, 11, 12, 0, tzinfo=UTC),
            "artifact": Path("runtime/result.json"),
        }
    )
    line = capsys.readouterr().out.strip()
    payload = json.loads(b64decode(line.removeprefix(RESULT_LOG_PREFIX)).decode("utf-8"))

    assert payload["completed_at"] == "2026-05-11T12:00:00+00:00"
    assert payload["artifact"] in {"runtime/result.json", "runtime\\result.json"}


def test_shell_job_runner_rejects_malformed_json_payload(monkeypatch) -> None:
    monkeypatch.setenv("XAGENT_SHELL_JOB_PAYLOAD", "{not-json")
    monkeypatch.delenv("XAGENT_SHELL_JOB_PAYLOAD_FILE", raising=False)

    try:
        load_shell_job_payload()
    except ValueError as exc:
        assert "not valid JSON" in str(exc)
        assert "XAGENT_SHELL_JOB_PAYLOAD" in str(exc)
    else:
        raise AssertionError("Expected malformed shell job payload to fail.")


def test_shell_job_runner_rejects_non_object_payload(monkeypatch) -> None:
    monkeypatch.setenv("XAGENT_SHELL_JOB_PAYLOAD", "[]")
    monkeypatch.delenv("XAGENT_SHELL_JOB_PAYLOAD_FILE", raising=False)

    try:
        load_shell_job_payload()
    except ValueError as exc:
        assert "must be a JSON object" in str(exc)
    else:
        raise AssertionError("Expected non-object shell job payload to fail.")


async def test_shell_job_runner_rejects_cwd_outside_sandbox(tmp_path) -> None:
    try:
        await execute_shell_job_payload(
            {"command": f'"{sys.executable}" -c "print(1)"', "cwd": tmp_path.parent},
            settings=_settings(tmp_path),
        )
    except PermissionError as exc:
        assert "within sandbox" in str(exc)
    else:
        raise AssertionError("Expected cwd outside sandbox to fail.")
