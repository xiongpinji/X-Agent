from __future__ import annotations

import subprocess
import sys
import time
import webbrowser
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def run(command: list[str]) -> None:
    subprocess.check_call(command, cwd=ROOT)


def open_frontend() -> None:
    webbrowser.open("http://127.0.0.1:8000/")


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
        "8000",
    ], cwd=ROOT)
    try:
        time.sleep(2.5)
        open_frontend()
        return server.wait()
    except KeyboardInterrupt:
        server.terminate()
        return 130


if __name__ == "__main__":
    raise SystemExit(main())
