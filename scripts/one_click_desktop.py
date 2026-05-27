from __future__ import annotations

import subprocess
import sys
import time
import webbrowser
from pathlib import Path

import urllib.request

ROOT = Path(__file__).resolve().parents[1]


def run(command: list[str]) -> None:
    subprocess.check_call(command, cwd=ROOT)


def open_frontend() -> None:
    webbrowser.open("http://127.0.0.1:8003/")


def wait_for_backend(url: str, timeout_seconds: int = 30) -> None:
    deadline = time.time() + timeout_seconds
    last_error: Exception | None = None
    while time.time() < deadline:
        try:
            with urllib.request.urlopen(url, timeout=2) as response:
                if 200 <= response.status < 500:
                    return
        except Exception as exc:
            last_error = exc
        time.sleep(0.5)
    raise RuntimeError(f"Backend did not become ready at {url}") from last_error


def bootstrap_only() -> int:
    run([sys.executable, "-m", "pip", "install", "-e", ".[dev]"])
    print("Dependencies installed.")
    return 0


def main() -> int:
    # One-click desktop bootstrap for local single-user mode.
    run([sys.executable, "-m", "pip", "install", "-e", ".[dev]"])
    print("Dependencies installed. Starting X-Agent in desktop single-user mode...")
    server = subprocess.Popen([
        sys.executable,
        "-m",
        "uvicorn",
        "backend.app.main:app",
        "--host",
        "127.0.0.1",
        "--port",
        "8003",
    ], cwd=ROOT)
    try:
        wait_for_backend("http://127.0.0.1:8003/openapi.json")
        open_frontend()
        return server.wait()
    except KeyboardInterrupt:
        server.terminate()
        return 130


if __name__ == "__main__":
    raise SystemExit(main())
