"""X-Agent Quick Start — start backend + seed demo data + open browser.

Usage:
    python scripts/quickstart.py [--no-browser] [--port 8000] [--skip-seed]

Flow:
    1. Check prerequisites (Python version, venv)
    2. Seed demo data
    3. Start uvicorn in background
    4. Wait for health check
    5. Print access URLs
    6. Optionally open browser
"""

import argparse
import os
import platform
import subprocess
import sys
import time
import urllib.error
import urllib.request
import webbrowser
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
DEFAULT_PORT = 8000
HEALTH_TIMEOUT = 30  # seconds


def _print_banner() -> None:
    print("""
╔══════════════════════════════════════════════════════════╗
║            X-Agent Quick Start                          ║
║       Customer Demo Environment Launcher                ║
╚══════════════════════════════════════════════════════════╝
""")


def _print_step(step: int, msg: str) -> None:
    print(f"\n[{step}/6] {msg}")
    print("-" * 50)


def _print_ok(msg: str) -> None:
    print(f"  ✓ {msg}")


def _print_err(msg: str) -> None:
    print(f"  ✗ {msg}")


def _print_info(msg: str) -> None:
    print(f"  → {msg}")


# ---------------------------------------------------------------------------
# Step 1: Check prerequisites
# ---------------------------------------------------------------------------


def check_prerequisites() -> bool:
    """Verify Python version and environment."""
    _print_step(1, "Checking prerequisites...")

    # Python version
    major, minor = sys.version_info[:2]
    if (major, minor) < (3, 10):
        _print_err(f"Python 3.10+ required, found {major}.{minor}")
        return False
    _print_ok(f"Python {major}.{minor}.{sys.version_info[2]}")

    # Check if running in venv
    in_venv = hasattr(sys, "real_prefix") or (
        hasattr(sys, "base_prefix") and sys.base_prefix != sys.prefix
    )
    if in_venv:
        _print_ok("Virtual environment detected")
    else:
        _print_info("Not running in a virtual environment (recommended)")

    # Check key dependencies
    try:
        import fastapi  # noqa: F401
        _print_ok("FastAPI installed")
    except ImportError:
        _print_err("FastAPI not found. Run: pip install -r requirements.txt")
        return False

    try:
        import uvicorn  # noqa: F401
        _print_ok("Uvicorn installed")
    except ImportError:
        _print_err("Uvicorn not found. Run: pip install uvicorn")
        return False

    return True


# ---------------------------------------------------------------------------
# Step 2: Seed demo data
# ---------------------------------------------------------------------------


def seed_demo_data(reset: bool = False) -> bool:
    """Run the seed script to populate demo data."""
    _print_step(2, "Seeding demo data...")

    seed_script = PROJECT_ROOT / "scripts" / "seed_demo.py"
    if not seed_script.exists():
        _print_err(f"Seed script not found: {seed_script}")
        return False

    cmd = [sys.executable, "-X", "utf8", str(seed_script)]
    if reset:
        cmd.append("--reset")

    try:
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            cwd=str(PROJECT_ROOT),
            timeout=60,
        )
        if result.returncode == 0:
            _print_ok("Demo data seeded successfully")
            # Print last few meaningful lines
            lines = [l for l in result.stdout.strip().split("\n") if l.strip()]
            for line in lines[-5:]:
                _print_info(line.strip())
            return True
        else:
            _print_err(f"Seed script failed (exit code {result.returncode})")
            if result.stderr:
                for line in result.stderr.strip().split("\n")[-3:]:
                    _print_err(f"  {line}")
            return False
    except subprocess.TimeoutExpired:
        _print_err("Seed script timed out")
        return False
    except Exception as e:
        _print_err(f"Failed to run seed script: {e}")
        return False


# ---------------------------------------------------------------------------
# Step 3: Start uvicorn
# ---------------------------------------------------------------------------


def start_server(port: int) -> subprocess.Popen | None:
    """Start uvicorn server in background."""
    _print_step(3, f"Starting X-Agent server on port {port}...")

    # Check if port is already in use
    try:
        req = urllib.request.Request(f"http://localhost:{port}/health")
        with urllib.request.urlopen(req, timeout=2) as resp:
            if resp.status == 200:
                _print_ok(f"Server already running on port {port}")
                return None  # No process to manage
    except Exception:
        pass  # Port is free, continue

    # Determine Python executable
    python_exe = sys.executable

    cmd = [
        python_exe, "-X", "utf8", "-m", "uvicorn",
        "backend.app.main:app",
        "--host", "0.0.0.0",
        "--port", str(port),
        "--log-level", "warning",
    ]

    env = os.environ.copy()
    env["PYTHONUTF8"] = "1"

    try:
        process = subprocess.Popen(
            cmd,
            cwd=str(PROJECT_ROOT),
            env=env,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
        )
        _print_ok(f"Server process started (PID: {process.pid})")
        return process
    except Exception as e:
        _print_err(f"Failed to start server: {e}")
        return None


# ---------------------------------------------------------------------------
# Step 4: Wait for health check
# ---------------------------------------------------------------------------


def wait_for_health(port: int, timeout: int = HEALTH_TIMEOUT) -> bool:
    """Poll health endpoint until server is ready."""
    _print_step(4, f"Waiting for server to be ready (timeout: {timeout}s)...")

    start = time.time()
    url = f"http://localhost:{port}/health"

    while time.time() - start < timeout:
        try:
            req = urllib.request.Request(url)
            with urllib.request.urlopen(req, timeout=3) as resp:
                if resp.status == 200:
                    elapsed = time.time() - start
                    _print_ok(f"Server is healthy (took {elapsed:.1f}s)")
                    return True
        except (urllib.error.URLError, OSError, ConnectionError):
            pass
        time.sleep(0.5)
        # Progress indicator
        elapsed = int(time.time() - start)
        if elapsed % 5 == 0 and elapsed > 0:
            _print_info(f"Still waiting... ({elapsed}s)")

    _print_err(f"Server did not become healthy within {timeout}s")
    return False


# ---------------------------------------------------------------------------
# Step 5: Print access URLs
# ---------------------------------------------------------------------------


def print_urls(port: int) -> None:
    """Display access URLs for the user."""
    _print_step(5, "Access URLs")

    print(f"""
  ┌─────────────────────────────────────────────────────┐
  │  X-Agent Demo Environment Ready!                    │
  ├─────────────────────────────────────────────────────┤
  │                                                     │
  │  Web UI:      http://localhost:{port}                │
  │  API Docs:    http://localhost:{port}/docs           │
  │  Health:      http://localhost:{port}/health         │
  │  Metrics:     http://localhost:{port}/metrics        │
  │                                                     │
  │  Demo Data:                                         │
  │    • 3 Agents (Code/Data/Web)                       │
  │    • 2 Workflows (Report/Review)                    │
  │    • 5 Goals with checkpoints                       │
  │    • Sample memories                                │
  │                                                     │
  └─────────────────────────────────────────────────────┘
""")


# ---------------------------------------------------------------------------
# Step 6: Open browser
# ---------------------------------------------------------------------------


def open_browser(port: int) -> None:
    """Optionally open the web UI in default browser."""
    _print_step(6, "Opening browser...")
    url = f"http://localhost:{port}"
    try:
        webbrowser.open(url)
        _print_ok(f"Opened {url}")
    except Exception:
        _print_info(f"Could not open browser. Visit: {url}")


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------


def main() -> None:
    parser = argparse.ArgumentParser(description="X-Agent Quick Start for customer demos")
    parser.add_argument("--no-browser", action="store_true", help="Don't open browser automatically")
    parser.add_argument("--port", type=int, default=DEFAULT_PORT, help=f"Server port (default: {DEFAULT_PORT})")
    parser.add_argument("--skip-seed", action="store_true", help="Skip demo data seeding")
    parser.add_argument("--reset", action="store_true", help="Reset demo data before seeding")
    args = parser.parse_args()

    _print_banner()

    # Step 1: Prerequisites
    if not check_prerequisites():
        sys.exit(1)

    # Step 2: Seed data
    if not args.skip_seed:
        if not seed_demo_data(reset=args.reset):
            _print_info("Continuing without demo data...")

    # Step 3: Start server
    server_process = start_server(args.port)

    # Step 4: Health check
    if not wait_for_health(args.port):
        if server_process:
            server_process.terminate()
        sys.exit(1)

    # Step 5: Print URLs
    print_urls(args.port)

    # Step 6: Open browser
    if not args.no_browser:
        open_browser(args.port)

    # Keep running
    print("  Press Ctrl+C to stop the server.\n")
    try:
        if server_process:
            server_process.wait()
        else:
            # Server was already running; just idle
            while True:
                time.sleep(1)
    except KeyboardInterrupt:
        print("\n  Shutting down...")
        if server_process:
            server_process.terminate()
            server_process.wait(timeout=5)
        print("  Done. Goodbye!\n")


if __name__ == "__main__":
    main()
