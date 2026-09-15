#!/usr/bin/env python3
"""
Sensitive Information Cleanup Script
Uses git filter-repo to remove sensitive files from Git history
"""

import os
import subprocess
import shutil
from pathlib import Path
from datetime import datetime

PROJECT_DIR = r"D:\AI编程库\项目库\进行中的项目\X-Agent 原创内核计划\X-Agent 原创内核计划"

def backup_git_dir():
    """Backup .git directory before cleanup"""
    git_dir = Path(PROJECT_DIR) / ".git"
    backup_dir = Path(PROJECT_DIR) / f".git.backup.{datetime.now().strftime('%Y%m%d_%H%M%S')}"

    if git_dir.exists():
        print(f"[INFO] Backing up .git directory to {backup_dir}...")
        shutil.copytree(git_dir, backup_dir)
        print(f"[OK] Backup created at {backup_dir}")
        return backup_dir
    return None

def run_command(cmd, cwd=None):
    """Execute a shell command"""
    try:
        result = subprocess.run(
            cmd,
            cwd=cwd or PROJECT_DIR,
            shell=True,
            capture_output=True,
            text=True
        )
        return result.returncode == 0, result.stdout, result.stderr
    except Exception as e:
        return False, "", str(e)

def cleanup_sensitive_files():
    """Remove sensitive files from Git history"""
    print("=" * 60)
    print("X-Agent Sensitive Information Cleanup")
    print("=" * 60)
    print()

    os.chdir(PROJECT_DIR)

    # Check if git filter-repo is available
    success, _, _ = run_command("git filter-repo --version")
    if not success:
        print("[WARNING] git filter-repo not installed")
        print("[INFO] Install with: pip install git-filter-repo")
        print("[INFO] Skipping git history cleanup")
        return

    # Backup .git directory
    backup_dir = backup_git_dir()
    print()

    # Files to remove from history
    sensitive_files = [
        "data/api_keys.json",
        "data/workflows.json",
        "data/approvals.json",
        "x_agent_core.egg-info/",
    ]

    print("[INFO] Removing sensitive files from Git history...")
    print("Files to remove:")
    for file in sensitive_files:
        print(f"  - {file}")
    print()

    # Create filter-repo command
    filter_paths = " ".join([f"--path {file}" for file in sensitive_files])
    cmd = f"git filter-repo --invert-paths {filter_paths} --force"

    print(f"[INFO] Running: {cmd}")
    success, stdout, stderr = run_command(cmd)

    if success:
        print("[OK] Sensitive files removed from history")
        print(stdout)
    else:
        print("[ERROR] Cleanup failed")
        print(stderr)
        if backup_dir:
            print(f"[INFO] Restore from backup: {backup_dir}")
        return False

    print()
    print("[INFO] Verifying cleanup...")

    # Verify files are not in history
    for file in sensitive_files:
        cmd = f"git log --all --full-history -- {file}"
        success, stdout, _ = run_command(cmd)
        if stdout.strip():
            print(f"[WARNING] {file} still found in history")
        else:
            print(f"[OK] {file} removed from history")

    print()
    print("=" * 60)
    print("Cleanup Complete")
    print("=" * 60)
    print()
    print("IMPORTANT: After cleanup, team members must:")
    print("1. Backup their local changes")
    print("2. Delete local repository")
    print("3. Re-clone from remote")
    print()
    if backup_dir:
        print(f"Backup location: {backup_dir}")
    print()

    return True

if __name__ == "__main__":
    try:
        cleanup_sensitive_files()
    except Exception as e:
        print(f"[ERROR] Cleanup failed: {e}")
