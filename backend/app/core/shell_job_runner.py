from __future__ import annotations

import asyncio
import base64
import json
import os
import time
from pathlib import Path
from typing import Any

from backend.app.core.storage import atomic_write_json, dumps_json
from backend.app.settings import PROJECT_ROOT, Settings

RESULT_LOG_PREFIX = "XAGENT_SHELL_JOB_RESULT_JSON_B64="
DEFAULT_TIMEOUT_SECONDS = 5
DEFAULT_MAX_OUTPUT_CHARS = 2_000
DEFAULT_MAX_ARTIFACTS = 20
DEFAULT_MAX_ARTIFACT_BYTES = 8_192


def load_shell_job_payload() -> dict[str, Any]:
    payload_file = os.getenv("XAGENT_SHELL_JOB_PAYLOAD_FILE")
    if payload_file:
        return _loads_payload(Path(payload_file).read_text(encoding="utf-8"), source=payload_file)
    payload = os.getenv("XAGENT_SHELL_JOB_PAYLOAD")
    if payload:
        return _loads_payload(payload, source="XAGENT_SHELL_JOB_PAYLOAD")
    raise RuntimeError("Set XAGENT_SHELL_JOB_PAYLOAD or XAGENT_SHELL_JOB_PAYLOAD_FILE.")


def _loads_payload(raw_payload: str, *, source: str) -> dict[str, Any]:
    try:
        payload = json.loads(raw_payload)
    except json.JSONDecodeError as exc:
        raise ValueError(f"Shell job payload from {source} is not valid JSON: {exc.msg}") from exc
    if not isinstance(payload, dict):
        raise ValueError(f"Shell job payload from {source} must be a JSON object.")
    return payload


async def execute_shell_job_payload(
    payload: dict[str, Any],
    *,
    settings: Settings | Any | None = None,
) -> dict[str, Any]:
    settings = settings or Settings()
    command = payload.get("command")
    if not isinstance(command, str):
        raise ValueError("Shell job payload requires string field: command.")

    sandbox = _settings_path(settings, "shell_tool_sandbox_path", PROJECT_ROOT)
    cwd = _resolve_job_cwd(payload.get("cwd", "."), sandbox=sandbox)
    timeout_seconds = _bounded_int(
        payload.get("timeout_seconds", DEFAULT_TIMEOUT_SECONDS),
        minimum=1,
        maximum=_settings_int(settings, "shell_tool_max_timeout_seconds", 60),
    )
    max_output_chars = _bounded_int(
        payload.get("max_output_chars", DEFAULT_MAX_OUTPUT_CHARS),
        minimum=256,
        maximum=_settings_int(settings, "shell_tool_max_output_chars", 20_000),
    )
    max_artifact_bytes = _settings_int(settings, "shell_tool_max_artifact_bytes", DEFAULT_MAX_ARTIFACT_BYTES)
    max_artifacts = _settings_int(settings, "shell_tool_max_artifacts", DEFAULT_MAX_ARTIFACTS)

    before = _workspace_fingerprint(cwd)
    result = await _run_shell_command(command, cwd=cwd, timeout_seconds=timeout_seconds)
    after = _workspace_fingerprint(cwd)
    artifacts = _collect_artifacts(
        cwd,
        before=before,
        after=after,
        max_artifacts=max_artifacts,
        max_artifact_bytes=max_artifact_bytes,
    )

    return {
        "ok": result["exit_code"] == 0 and result["timed_out"] is False,
        "result": {
            **result,
            "stdout": _tail_text(result["stdout"], max_output_chars),
            "stderr": _tail_text(result["stderr"], max_output_chars),
            "cwd": str(cwd),
            "artifacts": artifacts,
        },
    }


def write_shell_job_result(payload: dict[str, Any]) -> Path:
    output_path = Path(os.getenv("XAGENT_SHELL_JOB_OUTPUT_PATH", str(PROJECT_ROOT / "data" / "shell_job_result.json")))
    atomic_write_json(output_path, payload)
    return output_path


def emit_shell_job_result(payload: dict[str, Any]) -> None:
    encoded = base64.b64encode(
        dumps_json(
            payload,
            separators=(",", ":"),
        ).encode("utf-8")
    ).decode("ascii")
    print(f"{RESULT_LOG_PREFIX}{encoded}", flush=True)


def main() -> int:
    try:
        result = asyncio.run(execute_shell_job_payload(load_shell_job_payload()))
    except Exception as exc:  # noqa: BLE001 - job output must preserve runner failures
        result = {"ok": False, "error": str(exc)}
        write_shell_job_result(result)
        emit_shell_job_result(result)
        return 1
    write_shell_job_result(result)
    emit_shell_job_result(result)
    return 0 if result["ok"] else 1


async def _run_shell_command(command: str, *, cwd: Path, timeout_seconds: int) -> dict[str, Any]:
    started = time.perf_counter()
    process = await asyncio.create_subprocess_shell(
        command,
        cwd=str(cwd),
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
    )
    timed_out = False
    try:
        stdout, stderr = await asyncio.wait_for(process.communicate(), timeout=timeout_seconds)
    except asyncio.TimeoutError:
        timed_out = True
        process.kill()
        stdout, stderr = await process.communicate()
    return {
        "command": command,
        "exit_code": 124 if timed_out else int(process.returncode or 0),
        "timed_out": timed_out,
        "duration_seconds": round(time.perf_counter() - started, 3),
        "stdout": _decode_output(stdout),
        "stderr": _decode_output(stderr) or (f"command timed out after {timeout_seconds} seconds" if timed_out else ""),
    }


def _resolve_job_cwd(value: Any, *, sandbox: Path) -> Path:
    raw = str(value or ".")
    cwd = Path(raw)
    if not cwd.is_absolute():
        cwd = sandbox / cwd
    resolved = cwd.expanduser().resolve()
    sandbox = sandbox.expanduser().resolve()
    try:
        resolved.relative_to(sandbox)
    except ValueError as exc:
        raise PermissionError(f"Shell job cwd must stay within sandbox: {sandbox}") from exc
    resolved.mkdir(parents=True, exist_ok=True)
    return resolved


def _workspace_fingerprint(root: Path) -> dict[str, tuple[int, int]]:
    fingerprint: dict[str, tuple[int, int]] = {}
    if not root.exists():
        return fingerprint
    for path in root.rglob("*"):
        if not path.is_file():
            continue
        try:
            relative = path.relative_to(root).as_posix()
            stat = path.stat()
        except OSError:
            continue
        fingerprint[relative] = (stat.st_mtime_ns, stat.st_size)
    return fingerprint


def _collect_artifacts(
    root: Path,
    *,
    before: dict[str, tuple[int, int]],
    after: dict[str, tuple[int, int]],
    max_artifacts: int,
    max_artifact_bytes: int,
) -> list[dict[str, Any]]:
    changed = [path for path, fingerprint in after.items() if before.get(path) != fingerprint]
    artifacts: list[dict[str, Any]] = []
    for relative in sorted(changed)[: max(0, max_artifacts)]:
        path = root / relative
        try:
            size = path.stat().st_size
        except OSError:
            continue
        artifacts.append(
            {
                "path": relative,
                "size_bytes": size,
                "preview": _read_preview(path, max_bytes=max_artifact_bytes),
            }
        )
    return artifacts


def _read_preview(path: Path, *, max_bytes: int) -> str:
    try:
        payload = path.read_bytes()[: max(0, max_bytes)]
    except OSError:
        return ""
    return payload.decode("utf-8", errors="replace")


def _settings_path(settings: Any, name: str, fallback: Path) -> Path:
    value = getattr(settings, name, None)
    return Path(value) if value else Path(fallback)


def _settings_int(settings: Any, name: str, fallback: int) -> int:
    try:
        return int(getattr(settings, name, fallback))
    except (TypeError, ValueError):
        return fallback


def _bounded_int(value: Any, *, minimum: int, maximum: int) -> int:
    try:
        parsed = int(value)
    except (TypeError, ValueError):
        parsed = minimum
    return max(minimum, min(parsed, max(minimum, maximum)))


def _tail_text(value: str, limit: int) -> str:
    return value if len(value) <= limit else value[-limit:]


def _decode_output(value: bytes | None) -> str:
    if value is None:
        return ""
    return value.decode("utf-8", errors="replace")


if __name__ == "__main__":
    raise SystemExit(main())
