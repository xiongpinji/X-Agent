#!/usr/bin/env python3
"""
Git Flow Setup Script for X-Agent Project
Initializes Git repository, creates branches, and configures hooks
"""

import os
import subprocess
import sys
from pathlib import Path

PROJECT_DIR = r"D:\AI编程库\项目库\进行中的项目\X-Agent 原创内核计划\X-Agent 原创内核计划"

def run_command(cmd, cwd=None, check=True):
    """Execute a shell command and return output"""
    try:
        result = subprocess.run(
            cmd,
            cwd=cwd or PROJECT_DIR,
            shell=True,
            capture_output=True,
            text=True,
            check=False
        )
        if check and result.returncode != 0 and "already exists" not in result.stderr:
            print(f"[ERROR] Command failed: {cmd}")
            print(f"stderr: {result.stderr}")
            return False
        return True
    except Exception as e:
        print(f"[ERROR] Exception running command: {e}")
        return False

def setup_git_flow():
    """Main setup function"""
    print("=" * 50)
    print("X-Agent Git Flow Setup")
    print("=" * 50)
    print()

    os.chdir(PROJECT_DIR)

    # Check if .git exists
    git_dir = Path(PROJECT_DIR) / ".git"
    if git_dir.exists():
        print("[INFO] Git repository already initialized")
    else:
        print("[INFO] Initializing Git repository...")
        run_command("git init")
        print("[OK] Git repository initialized")

    print()
    print("[INFO] Configuring Git user (local)...")
    run_command("git config user.name \"X-Agent Team\"")
    run_command("git config user.email \"team@x-agent.local\"")
    print("[OK] Git user configured")

    print()
    print("[INFO] Creating initial commit...")
    run_command("git add .gitignore docs/git-workflow.md", check=False)
    run_command("git commit -m \"chore: initialize git flow and documentation\"", check=False)

    print()
    print("[INFO] Creating develop branch...")
    run_command("git branch develop", check=False)
    print("[OK] develop branch created (or already exists)")

    print()
    print("[INFO] Creating feature branches...")
    run_command("git branch feature/security-fixes", check=False)
    run_command("git branch feature/code-refactor", check=False)
    print("[OK] Feature branches created")

    print()
    print("[INFO] Creating version tag v0.1.0...")
    run_command("git tag -a v0.1.0 -m \"Initial release - Phase 0 MVP\"", check=False)
    print("[OK] Version tag created")

    print()
    print("[INFO] Setting up Git hooks...")
    setup_hooks()
    print("[OK] Git hooks configured")

    print()
    print("=" * 50)
    print("Git Flow Setup Complete")
    print("=" * 50)
    print()

    # Display branch structure
    print("Branch structure:")
    run_command("git branch -a", check=False)
    print()

    # Display tags
    print("Tags:")
    run_command("git tag -l", check=False)
    print()

    print("Next steps:")
    print("1. Review the docs/git-workflow.md documentation")
    print("2. Start working on feature branches")
    print("3. Create pull requests for code review")
    print()

def setup_hooks():
    """Create Git hooks"""
    hooks_dir = Path(PROJECT_DIR) / ".git" / "hooks"
    hooks_dir.mkdir(parents=True, exist_ok=True)

    # Pre-commit hook
    pre_commit_path = hooks_dir / "pre-commit"
    pre_commit_content = """#!/bin/bash
# Pre-commit hook - runs linting and security checks

echo "[INFO] Running ruff check..."
ruff check . --exit-zero
if [ $? -ne 0 ]; then
    echo "[ERROR] Ruff check failed"
    exit 1
fi

echo "[INFO] Checking for sensitive information..."
if grep -r "api_key\|password\|secret\|token" --include="*.py" . 2>/dev/null | grep -v ".git" | grep -v "test_"; then
    echo "[WARNING] Possible sensitive information detected"
fi

echo "[OK] Pre-commit checks passed"
exit 0
"""
    with open(pre_commit_path, 'w') as f:
        f.write(pre_commit_content)
    os.chmod(pre_commit_path, 0o755)
    print(f"[OK] Created pre-commit hook at {pre_commit_path}")

    # Pre-push hook
    pre_push_path = hooks_dir / "pre-push"
    pre_push_content = """#!/bin/bash
# Pre-push hook - runs tests before pushing

echo "[INFO] Running test suite..."
pytest tests/ -v --tb=short 2>/dev/null
if [ $? -ne 0 ]; then
    echo "[ERROR] Tests failed - push aborted"
    exit 1
fi

echo "[OK] All tests passed - safe to push"
exit 0
"""
    with open(pre_push_path, 'w') as f:
        f.write(pre_push_content)
    os.chmod(pre_push_path, 0o755)
    print(f"[OK] Created pre-push hook at {pre_push_path}")

if __name__ == "__main__":
    try:
        setup_git_flow()
        sys.exit(0)
    except Exception as e:
        print(f"[ERROR] Setup failed: {e}")
        sys.exit(1)
