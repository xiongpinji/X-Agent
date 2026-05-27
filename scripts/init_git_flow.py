#!/usr/bin/env python3
"""
Initialize Git Flow branching strategy for X-Agent Core.

This script sets up the Git Flow branching model:
- Creates develop branch from main
- Sets up branch protection rules (instructions)
- Creates initial feature branch structure

Usage:
    python scripts/init_git_flow.py
"""

import subprocess
import sys
from pathlib import Path


def run_command(cmd: list[str], check: bool = True) -> tuple[int, str, str]:
    """Run a shell command and return exit code, stdout, stderr."""
    try:
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            check=check
        )
        return result.returncode, result.stdout, result.stderr
    except subprocess.CalledProcessError as e:
        return e.returncode, e.stdout, e.stderr


def check_git_repo() -> bool:
    """Check if current directory is a git repository."""
    code, _, _ = run_command(["git", "rev-parse", "--git-dir"], check=False)
    return code == 0


def get_current_branch() -> str:
    """Get the current git branch name."""
    code, stdout, _ = run_command(["git", "branch", "--show-current"])
    return stdout.strip() if code == 0 else ""


def branch_exists(branch_name: str) -> bool:
    """Check if a branch exists."""
    code, _, _ = run_command(["git", "rev-parse", "--verify", branch_name], check=False)
    return code == 0


def create_branch(branch_name: str, from_branch: str = None) -> bool:
    """Create a new branch."""
    if branch_exists(branch_name):
        print(f"✓ Branch '{branch_name}' already exists")
        return True

    cmd = ["git", "checkout", "-b", branch_name]
    if from_branch:
        cmd.append(from_branch)

    code, _, stderr = run_command(cmd, check=False)
    if code == 0:
        print(f"✓ Created branch '{branch_name}'")
        return True
    else:
        print(f"✗ Failed to create branch '{branch_name}': {stderr}")
        return False


def checkout_branch(branch_name: str) -> bool:
    """Checkout a branch."""
    code, _, stderr = run_command(["git", "checkout", branch_name], check=False)
    if code == 0:
        print(f"✓ Checked out branch '{branch_name}'")
        return True
    else:
        print(f"✗ Failed to checkout branch '{branch_name}': {stderr}")
        return False


def main():
    print("=" * 70)
    print("Git Flow Initialization for X-Agent Core")
    print("=" * 70)
    print()

    # Check if we're in a git repository
    if not check_git_repo():
        print("✗ Error: Not a git repository")
        print("  Run 'git init' first")
        sys.exit(1)

    print("✓ Git repository detected")
    print()

    # Get current branch
    current_branch = get_current_branch()
    print(f"Current branch: {current_branch}")
    print()

    # Ensure we're on main branch
    if current_branch != "main" and current_branch != "master":
        print("Switching to main branch...")
        if not checkout_branch("main"):
            if not checkout_branch("master"):
                print("✗ Error: Could not find main or master branch")
                sys.exit(1)

    # Create develop branch
    print("Creating develop branch...")
    if not create_branch("develop", "main"):
        sys.exit(1)

    print()
    print("=" * 70)
    print("Git Flow Setup Complete!")
    print("=" * 70)
    print()
    print("Branch structure:")
    print("  main     - Production-ready code (protected)")
    print("  develop  - Integration branch (protected)")
    print()
    print("Feature branch naming:")
    print("  feature/* - New features (branch from develop)")
    print("  bugfix/*  - Bug fixes (branch from develop)")
    print("  hotfix/*  - Urgent fixes (branch from main)")
    print("  release/* - Release preparation (branch from develop)")
    print()
    print("Next steps:")
    print("1. Push branches to remote:")
    print("   git push -u origin main")
    print("   git push -u origin develop")
    print()
    print("2. Set up branch protection on GitHub/GitLab:")
    print("   - Protect 'main' branch:")
    print("     • Require pull request reviews (minimum 2)")
    print("     • Require status checks to pass")
    print("     • Require branches to be up to date")
    print("     • Do not allow force pushes")
    print("   - Protect 'develop' branch:")
    print("     • Require pull request reviews (minimum 1)")
    print("     • Require status checks to pass")
    print()
    print("3. Create your first feature branch:")
    print("   git checkout develop")
    print("   git checkout -b feature/your-feature-name")
    print()
    print("4. When ready to merge:")
    print("   - Create PR from feature/* to develop")
    print("   - After review, merge to develop")
    print("   - For release, create PR from develop to main")
    print()


if __name__ == "__main__":
    main()
