from __future__ import annotations

import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DIST = ROOT / "dist"
SPEC = ROOT / "packaging" / "xagent-desktop.spec"


def run(command: list[str]) -> None:
    subprocess.check_call(command, cwd=ROOT)


def main() -> int:
    DIST.mkdir(exist_ok=True)
    run([sys.executable, "-m", "pip", "install", "-e", ".[dev]"])
    run([sys.executable, "-m", "compileall", "backend", "scripts"])
    if SPEC.exists():
        print(f"Found packaging spec: {SPEC}")
        print("Run your desktop bundler with the spec file to build a native package.")
        print("The spec already points at the startup page, index page, logo, icon, launch URL, and single-user mode.")
    else:
        print("No native packaging spec found yet.")
        print("The app is ready for a desktop bundler such as PyInstaller or Briefcase.")
    print(f"Output directory: {DIST}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
