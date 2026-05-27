#!/usr/bin/env python3
"""
Git Normalization Verification Script
Checks if all Git Flow setup tasks are completed
"""

import os
import subprocess
from pathlib import Path

PROJECT_DIR = r"D:\AI编程库\项目库\进行中的项目\X-Agent 原创内核计划\X-Agent 原创内核计划"

class GitFlowVerifier:
    def __init__(self):
        self.project_dir = PROJECT_DIR
        self.git_dir = Path(self.project_dir) / ".git"
        self.hooks_dir = self.git_dir / "hooks"
        self.results = []

    def run_command(self, cmd):
        """Execute a shell command"""
        try:
            result = subprocess.run(
                cmd,
                cwd=self.project_dir,
                shell=True,
                capture_output=True,
                text=True
            )
            return result.returncode == 0, result.stdout.strip()
        except Exception as e:
            return False, str(e)

    def check_git_repo(self):
        """Check if Git repository is initialized"""
        print("[CHECK] Git Repository Initialization")
        if self.git_dir.exists():
            print("  [OK] .git directory exists")
            self.results.append(("Git Repository", True))
            return True
        else:
            print("  [FAIL] .git directory not found")
            self.results.append(("Git Repository", False))
            return False

    def check_gitignore(self):
        """Check if .gitignore is properly configured"""
        print("[CHECK] .gitignore Configuration")
        gitignore_path = Path(self.project_dir) / ".gitignore"

        if not gitignore_path.exists():
            print("  [FAIL] .gitignore not found")
            self.results.append((".gitignore", False))
            return False

        with open(gitignore_path, 'r') as f:
            content = f.read()

        required_entries = [
            "*.egg-info/",
            "dist/",
            "build/",
            "data/api_keys.json",
            "data/workflows.json",
            "data/approvals.json",
        ]

        missing = []
        for entry in required_entries:
            if entry not in content:
                missing.append(entry)

        if missing:
            print(f"  [WARN] Missing entries: {missing}")
            self.results.append((".gitignore", False))
            return False
        else:
            print("  [OK] All required entries present")
            self.results.append((".gitignore", True))
            return True

    def check_branches(self):
        """Check if required branches exist"""
        print("[CHECK] Branch Structure")
        required_branches = [
            "develop",
            "feature/security-fixes",
            "feature/code-refactor",
        ]

        success, output = self.run_command("git branch -a")
        if not success:
            print("  [FAIL] Could not list branches")
            self.results.append(("Branches", False))
            return False

        missing = []
        for branch in required_branches:
            if branch not in output:
                missing.append(branch)
            else:
                print(f"  [OK] {branch} exists")

        if missing:
            print(f"  [FAIL] Missing branches: {missing}")
            self.results.append(("Branches", False))
            return False
        else:
            self.results.append(("Branches", True))
            return True

    def check_tags(self):
        """Check if version tag exists"""
        print("[CHECK] Version Tags")
        success, output = self.run_command("git tag -l")

        if not success:
            print("  [FAIL] Could not list tags")
            self.results.append(("Tags", False))
            return False

        if "v0.1.0" in output:
            print("  [OK] v0.1.0 tag exists")
            self.results.append(("Tags", True))
            return True
        else:
            print("  [FAIL] v0.1.0 tag not found")
            self.results.append(("Tags", False))
            return False

    def check_hooks(self):
        """Check if Git hooks are configured"""
        print("[CHECK] Git Hooks")
        required_hooks = ["pre-commit", "pre-push"]

        if not self.hooks_dir.exists():
            print("  [FAIL] Hooks directory not found")
            self.results.append(("Hooks", False))
            return False

        missing = []
        for hook in required_hooks:
            hook_path = self.hooks_dir / hook
            if hook_path.exists():
                print(f"  [OK] {hook} hook exists")
            else:
                missing.append(hook)

        if missing:
            print(f"  [FAIL] Missing hooks: {missing}")
            self.results.append(("Hooks", False))
            return False
        else:
            self.results.append(("Hooks", True))
            return True

    def check_documentation(self):
        """Check if Git workflow documentation exists"""
        print("[CHECK] Documentation")
        doc_path = Path(self.project_dir) / "docs" / "git-workflow.md"

        if doc_path.exists():
            print("  [OK] git-workflow.md exists")
            self.results.append(("Documentation", True))
            return True
        else:
            print("  [FAIL] git-workflow.md not found")
            self.results.append(("Documentation", False))
            return False

    def check_sensitive_files(self):
        """Check if sensitive files are in .gitignore"""
        print("[CHECK] Sensitive Files Protection")
        gitignore_path = Path(self.project_dir) / ".gitignore"

        with open(gitignore_path, 'r') as f:
            content = f.read()

        sensitive_patterns = [
            "data/api_keys.json",
            "data/workflows.json",
            "data/approvals.json",
        ]

        all_protected = True
        for pattern in sensitive_patterns:
            if pattern in content:
                print(f"  [OK] {pattern} is protected")
            else:
                print(f"  [FAIL] {pattern} is not protected")
                all_protected = False

        self.results.append(("Sensitive Files", all_protected))
        return all_protected

    def print_summary(self):
        """Print verification summary"""
        print()
        print("=" * 60)
        print("VERIFICATION SUMMARY")
        print("=" * 60)
        print()

        passed = sum(1 for _, result in self.results if result)
        total = len(self.results)

        for check_name, result in self.results:
            status = "[OK]" if result else "[FAIL]"
            print(f"{status} {check_name}")

        print()
        print(f"Passed: {passed}/{total}")
        print()

        if passed == total:
            print("[SUCCESS] All Git Flow setup tasks completed!")
            return True
        else:
            print("[WARNING] Some tasks are incomplete")
            return False

    def run_verification(self):
        """Run complete verification"""
        print("=" * 60)
        print("X-Agent Git Flow Verification")
        print("=" * 60)
        print()

        self.check_git_repo()
        print()
        self.check_gitignore()
        print()
        self.check_branches()
        print()
        self.check_tags()
        print()
        self.check_hooks()
        print()
        self.check_documentation()
        print()
        self.check_sensitive_files()
        print()

        return self.print_summary()

def main():
    """Main entry point"""
    try:
        os.chdir(PROJECT_DIR)
        verifier = GitFlowVerifier()
        success = verifier.run_verification()

        if success:
            print("Next steps:")
            print("1. Review docs/git-workflow.md")
            print("2. Start working on feature branches")
            print("3. Create pull requests for code review")
            print()
            return 0
        else:
            print("Please run git_normalization.py to complete setup")
            print()
            return 1
    except Exception as e:
        print(f"[ERROR] Verification failed: {e}")
        return 1

if __name__ == "__main__":
    import sys
    sys.exit(main())
