#!/usr/bin/env python3
"""Run commercial RC runtime smoke checks for X-Agent.

The script starts a mock-provider backend and, by default, a Vite frontend. It
then verifies the first-run product loop through HTTP and writes a JSON report
under ``.xagent_runtime/smoke``. It intentionally avoids real provider tokens.
"""

from __future__ import annotations

import argparse
import json
import os
import socket
import subprocess
import sys
import time
import urllib.error
import urllib.request
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
SMOKE_DIR = ROOT / ".xagent_runtime" / "smoke"
DEFAULT_OUTPUT = SMOKE_DIR / "rc-runtime-smoke.json"
PROXY_KEYS = (
    "ALL_PROXY",
    "all_proxy",
    "HTTP_PROXY",
    "HTTPS_PROXY",
    "http_proxy",
    "https_proxy",
    "ftp_proxy",
    "grpc_proxy",
)


class SmokeError(RuntimeError):
    """Raised when a smoke assertion fails."""


@dataclass(frozen=True)
class SmokeConfig:
    """Runtime smoke configuration."""

    host: str
    backend_port: int
    frontend_port: int
    requested_backend_port: int
    requested_frontend_port: int
    strict_ports: bool
    include_frontend: bool
    startup_timeout_seconds: float
    request_timeout_seconds: float
    output_path: Path

    @property
    def backend_base_url(self) -> str:
        return f"http://{self.host}:{self.backend_port}"

    @property
    def frontend_base_url(self) -> str:
        return f"http://{self.host}:{self.frontend_port}"


def _utc_now() -> str:
    return datetime.now(UTC).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _npm_executable() -> str:
    return "npm.cmd" if os.name == "nt" else "npm"


def _is_port_open(host: str, port: int) -> bool:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.settimeout(0.25)
        return sock.connect_ex((host, port)) == 0


def _find_free_port(host: str) -> int:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.bind((host, 0))
        return int(sock.getsockname()[1])


def _resolve_port(host: str, preferred_port: int, *, strict_ports: bool) -> int:
    if preferred_port < 0:
        raise SmokeError("port must be >= 0")
    if preferred_port == 0:
        return _find_free_port(host)
    if strict_ports or not _is_port_open(host, preferred_port):
        return preferred_port
    return _find_free_port(host)


def _clean_env(extra: dict[str, str] | None = None) -> dict[str, str]:
    env = os.environ.copy()
    for key in PROXY_KEYS:
        env.pop(key, None)
    env.update(
        {
            "PYTHONUTF8": "1",
            "XAGENT_QDRANT_URL": "",
            "XAGENT_LLM_BACKEND": "mock",
            "XAGENT_E2E": "0",
            "XAGENT_REQUIRE_API_KEY": "false",
            "XAGENT_TOOL_EXECUTION_STORE_PATH": str(SMOKE_DIR / "tool-executions.json"),
            "XAGENT_AUDIT_STORE_PATH": str(SMOKE_DIR / "audit.jsonl"),
            "XAGENT_RUN_STORE_PATH": str(SMOKE_DIR / "runs.jsonl"),
            "XAGENT_MEMORY_STORE_PATH": str(SMOKE_DIR / "memory.jsonl"),
        }
    )
    if extra:
        env.update(extra)
    return env


def _start_process(
    *,
    name: str,
    command: list[str],
    cwd: Path,
    env: dict[str, str],
    stdout_path: Path,
    stderr_path: Path,
) -> subprocess.Popen[bytes]:
    stdout_path.parent.mkdir(parents=True, exist_ok=True)
    stdout_file = stdout_path.open("wb")
    stderr_file = stderr_path.open("wb")
    try:
        return subprocess.Popen(
            command,
            cwd=cwd,
            env=env,
            stdout=stdout_file,
            stderr=stderr_file,
            stdin=subprocess.DEVNULL,
        )
    except Exception:
        stdout_file.close()
        stderr_file.close()
        raise SmokeError(f"failed to start {name}: {' '.join(command)}")


def _terminate_process(process: subprocess.Popen[bytes]) -> None:
    if process.poll() is not None:
        return
    if os.name == "nt":
        subprocess.run(
            ["taskkill", "/PID", str(process.pid), "/T", "/F"],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            check=False,
        )
        return
    process.terminate()
    try:
        process.wait(timeout=5)
    except subprocess.TimeoutExpired:
        process.kill()


def _request_json(
    method: str,
    url: str,
    *,
    payload: dict[str, object] | None = None,
    timeout_seconds: float,
) -> dict[str, Any]:
    body = None if payload is None else json.dumps(payload).encode("utf-8")
    headers = {"Content-Type": "application/json"} if payload is not None else {}
    request = urllib.request.Request(url, data=body, headers=headers, method=method)
    try:
        with urllib.request.urlopen(request, timeout=timeout_seconds) as response:
            raw = response.read()
            status = response.status
            content_type = response.headers.get("content-type", "")
    except urllib.error.HTTPError as exc:
        raw = exc.read()
        status = exc.code
        content_type = exc.headers.get("content-type", "")
    text = raw.decode("utf-8", errors="replace")
    parsed: Any = None
    if "json" in content_type:
        try:
            parsed = json.loads(text)
        except json.JSONDecodeError:
            parsed = None
    return {
        "status": status,
        "content_type": content_type,
        "text": text[:1600],
        "json": parsed,
    }


def _wait_for_http(url: str, *, timeout_seconds: float, request_timeout_seconds: float) -> None:
    deadline = time.monotonic() + timeout_seconds
    last_error = ""
    while time.monotonic() < deadline:
        try:
            response = _request_json("GET", url, timeout_seconds=request_timeout_seconds)
            if response["status"] == 200:
                return
            last_error = f"status={response['status']}"
        except Exception as exc:  # noqa: BLE001 - readiness loop reports last failure
            last_error = str(exc)
        time.sleep(0.5)
    raise SmokeError(f"timed out waiting for {url}: {last_error}")


def _require(condition: bool, message: str) -> None:
    if not condition:
        raise SmokeError(message)


def validate_backend_contract(checks: dict[str, dict[str, Any]]) -> dict[str, bool]:
    """Validate backend smoke response contracts."""

    health = checks["health"]
    ready = checks["ready"]
    chat = checks["chat"]
    workflow_chat = checks["workflow_chat"]
    workflow_payload = workflow_chat.get("json") or {}

    assertions = {
        "health_ok": health["status"] == 200 and (health.get("json") or {}).get("status") == "ok",
        "ready_ok": ready["status"] == 200 and (ready.get("json") or {}).get("status") == "ready",
        "chat_html": chat["status"] == 200 and "text/html" in chat["content_type"] and "X-Agent" in chat["text"],
        "workflow_chat_ok": (
            workflow_chat["status"] == 200
            and bool(workflow_payload.get("run_id"))
            and workflow_payload.get("resource_type") == "workflow_chat"
            and workflow_payload.get("status") in {"accepted", "running", "completed"}
            and workflow_payload.get("approval_required") is False
        ),
    }
    for name, passed in assertions.items():
        _require(passed, f"backend assertion failed: {name}")
    return assertions


def validate_frontend_contract(checks: dict[str, dict[str, Any]]) -> dict[str, bool]:
    """Validate frontend and Vite proxy smoke response contracts."""

    root = checks["root"]
    chat = checks["chat"]
    workbench = checks["proxied_workbench"]
    workbench_payload = workbench.get("json") or {}

    assertions = {
        "frontend_root_html": root["status"] == 200 and "text/html" in root["content_type"] and "X-Agent" in root["text"],
        "frontend_chat_html": chat["status"] == 200 and "text/html" in chat["content_type"] and "X-Agent" in chat["text"],
        "vite_dev_client_injected": "/@vite/client" in root["text"] and "/@vite/client" in chat["text"],
        "api_proxy_workbench": (
            workbench["status"] == 200
            and "console" in workbench_payload
            and any(entry.get("path") == "/chat" for entry in workbench_payload.get("entries", []))
        ),
    }
    for name, passed in assertions.items():
        _require(passed, f"frontend assertion failed: {name}")
    return assertions


def run_backend_checks(config: SmokeConfig) -> tuple[dict[str, dict[str, Any]], dict[str, bool]]:
    checks = {
        "health": _request_json("GET", f"{config.backend_base_url}/health", timeout_seconds=config.request_timeout_seconds),
        "ready": _request_json("GET", f"{config.backend_base_url}/ready", timeout_seconds=config.request_timeout_seconds),
        "chat": _request_json("GET", f"{config.backend_base_url}/chat", timeout_seconds=config.request_timeout_seconds),
        "workflow_chat": _request_json(
            "POST",
            f"{config.backend_base_url}/api/v1/workflows/create/chat",
            payload={"request": "commercial RC runtime smoke", "agent_id": "default-agent"},
            timeout_seconds=config.request_timeout_seconds,
        ),
    }
    return checks, validate_backend_contract(checks)


def run_frontend_checks(config: SmokeConfig) -> tuple[dict[str, dict[str, Any]], dict[str, bool]]:
    checks = {
        "root": _request_json("GET", f"{config.frontend_base_url}/", timeout_seconds=config.request_timeout_seconds),
        "chat": _request_json("GET", f"{config.frontend_base_url}/chat", timeout_seconds=config.request_timeout_seconds),
        "proxied_workbench": _request_json(
            "GET",
            f"{config.frontend_base_url}/api/v1/workbench",
            timeout_seconds=config.request_timeout_seconds,
        ),
    }
    return checks, validate_frontend_contract(checks)


def run_smoke(config: SmokeConfig) -> dict[str, Any]:
    """Run backend and optional frontend smoke checks."""

    start = time.perf_counter()
    SMOKE_DIR.mkdir(parents=True, exist_ok=True)
    processes: list[subprocess.Popen[bytes]] = []
    logs = {
        "backend_stdout": str(SMOKE_DIR / "rc-backend.out.log"),
        "backend_stderr": str(SMOKE_DIR / "rc-backend.err.log"),
    }
    report: dict[str, Any] = {
        "generated_at": _utc_now(),
        "backend_base_url": config.backend_base_url,
        "frontend_base_url": config.frontend_base_url if config.include_frontend else None,
        "ports": {
            "backend": config.backend_port,
            "frontend": config.frontend_port if config.include_frontend else None,
            "requested_backend": config.requested_backend_port,
            "requested_frontend": config.requested_frontend_port if config.include_frontend else None,
            "strict": config.strict_ports,
        },
        "status": "failed",
        "checks": {},
        "assertions": {},
        "logs": logs,
    }

    try:
        _require(not _is_port_open(config.host, config.backend_port), f"backend port already in use: {config.backend_port}")
        backend = _start_process(
            name="backend",
            command=[
                sys.executable,
                "-m",
                "uvicorn",
                "backend.app.main:app",
                "--host",
                config.host,
                "--port",
                str(config.backend_port),
            ],
            cwd=ROOT,
            env=_clean_env(),
            stdout_path=Path(logs["backend_stdout"]),
            stderr_path=Path(logs["backend_stderr"]),
        )
        processes.append(backend)
        _wait_for_http(
            f"{config.backend_base_url}/health",
            timeout_seconds=config.startup_timeout_seconds,
            request_timeout_seconds=config.request_timeout_seconds,
        )
        backend_checks, backend_assertions = run_backend_checks(config)
        report["checks"]["backend"] = backend_checks
        report["assertions"]["backend"] = backend_assertions

        if config.include_frontend:
            _require(
                not _is_port_open(config.host, config.frontend_port),
                f"frontend port already in use: {config.frontend_port}",
            )
            logs.update(
                {
                    "frontend_stdout": str(SMOKE_DIR / "rc-frontend.out.log"),
                    "frontend_stderr": str(SMOKE_DIR / "rc-frontend.err.log"),
                }
            )
            frontend = _start_process(
                name="frontend",
                command=[
                    _npm_executable(),
                    "run",
                    "dev",
                    "--",
                    "--host",
                    config.host,
                    "--port",
                    str(config.frontend_port),
                    "--strictPort",
                ],
                cwd=ROOT / "frontend",
                env=_clean_env({"VITE_API_URL": config.backend_base_url}),
                stdout_path=Path(logs["frontend_stdout"]),
                stderr_path=Path(logs["frontend_stderr"]),
            )
            processes.append(frontend)
            _wait_for_http(
                f"{config.frontend_base_url}/",
                timeout_seconds=config.startup_timeout_seconds,
                request_timeout_seconds=config.request_timeout_seconds,
            )
            frontend_checks, frontend_assertions = run_frontend_checks(config)
            report["checks"]["frontend"] = frontend_checks
            report["assertions"]["frontend"] = frontend_assertions

        report["status"] = "passed"
        return report
    except Exception as exc:  # noqa: BLE001 - report all smoke failures
        report["error"] = str(exc)
        return report
    finally:
        for process in reversed(processes):
            _terminate_process(process)
        report["duration_seconds"] = round(time.perf_counter() - start, 3)


def write_report(report: dict[str, Any], output_path: Path) -> None:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def parse_args() -> SmokeConfig:
    parser = argparse.ArgumentParser(description="Run X-Agent commercial RC runtime smoke checks")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--backend-port", type=int, default=8765)
    parser.add_argument("--frontend-port", type=int, default=5174)
    parser.add_argument("--strict-ports", action="store_true", help="fail instead of falling back when a requested port is in use")
    parser.add_argument("--backend-only", action="store_true", help="skip Vite frontend smoke")
    parser.add_argument("--startup-timeout", type=float, default=45.0)
    parser.add_argument("--request-timeout", type=float, default=10.0)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    args = parser.parse_args()
    backend_port = _resolve_port(args.host, args.backend_port, strict_ports=args.strict_ports)
    frontend_port = _resolve_port(args.host, args.frontend_port, strict_ports=args.strict_ports)
    return SmokeConfig(
        host=args.host,
        backend_port=backend_port,
        frontend_port=frontend_port,
        requested_backend_port=args.backend_port,
        requested_frontend_port=args.frontend_port,
        strict_ports=args.strict_ports,
        include_frontend=not args.backend_only,
        startup_timeout_seconds=args.startup_timeout,
        request_timeout_seconds=args.request_timeout,
        output_path=args.output,
    )


def main() -> int:
    config = parse_args()
    report = run_smoke(config)
    write_report(report, config.output_path)
    print(f"RC runtime smoke status: {report['status']}")
    print(f"Report written to {config.output_path}")
    if report["status"] != "passed":
        print(f"Error: {report.get('error', 'unknown failure')}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
