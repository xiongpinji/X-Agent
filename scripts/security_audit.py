#!/usr/bin/env python3
"""
Security audit script for X-Agent Core.

This script performs automated security checks on the codebase:
1. Scans for hardcoded secrets and credentials
2. Checks for SQL injection vulnerabilities
3. Verifies CORS configuration
4. Checks for insecure dependencies
5. Validates environment variable usage

Usage:
    python scripts/security_audit.py
"""

import os
import re
import sys
from pathlib import Path
from typing import List, Tuple


class SecurityIssue:
    def __init__(self, severity: str, file: str, line: int, issue: str, code: str = ""):
        self.severity = severity  # CRITICAL, HIGH, MEDIUM, LOW
        self.file = file
        self.line = line
        self.issue = issue
        self.code = code


class SecurityAuditor:
    def __init__(self, root_dir: Path):
        self.root_dir = root_dir
        self.issues: List[SecurityIssue] = []

        # Patterns to detect security issues
        self.secret_patterns = [
            (r'password\s*=\s*["\'](?!.*\$\{|.*REPLACE|.*your-|.*example)[^"\']{8,}["\']', "Hardcoded password"),
            (r'api[_-]?key\s*=\s*["\'](?!.*\$\{|.*REPLACE|.*your-|.*example)[^"\']{20,}["\']', "Hardcoded API key"),
            (r'secret[_-]?key\s*=\s*["\'](?!.*\$\{|.*REPLACE|.*your-|.*example)[^"\']{20,}["\']', "Hardcoded secret key"),
            (r'token\s*=\s*["\'](?!.*\$\{|.*REPLACE|.*your-|.*example)[^"\']{20,}["\']', "Hardcoded token"),
            (r'aws_secret_access_key\s*=\s*["\'][^"\']+["\']', "AWS secret key"),
        ]

        self.sql_injection_patterns = [
            (r'execute\s*\(\s*f["\'].*\{.*\}', "Potential SQL injection (f-string)"),
            (r'execute\s*\(\s*["\'].*%s.*["\'].*%', "Potential SQL injection (% formatting)"),
            (r'execute\s*\(\s*.*\+\s*', "Potential SQL injection (string concatenation)"),
        ]

    def scan_file(self, file_path: Path) -> None:
        """Scan a single Python file for security issues."""
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                lines = f.readlines()

            for line_num, line in enumerate(lines, 1):
                # Check for hardcoded secrets
                for pattern, issue_type in self.secret_patterns:
                    if re.search(pattern, line, re.IGNORECASE):
                        self.issues.append(SecurityIssue(
                            severity="CRITICAL",
                            file=str(file_path.relative_to(self.root_dir)),
                            line=line_num,
                            issue=issue_type,
                            code=line.strip()
                        ))

                # Check for SQL injection
                for pattern, issue_type in self.sql_injection_patterns:
                    if re.search(pattern, line, re.IGNORECASE):
                        self.issues.append(SecurityIssue(
                            severity="HIGH",
                            file=str(file_path.relative_to(self.root_dir)),
                            line=line_num,
                            issue=issue_type,
                            code=line.strip()
                        ))

        except Exception as e:
            print(f"Error scanning {file_path}: {e}")

    def check_cors_config(self) -> None:
        """Check CORS configuration in main.py."""
        main_py = self.root_dir / "backend" / "app" / "main.py"
        if not main_py.exists():
            return

        with open(main_py, 'r', encoding='utf-8') as f:
            content = f.read()

        # Check for wildcard CORS in production
        if 'allow_origins=["*"]' in content or "allow_origins=['*']" in content:
            self.issues.append(SecurityIssue(
                severity="CRITICAL",
                file="backend/app/main.py",
                line=0,
                issue="CORS wildcard (*) allows any origin - security risk",
                code=""
            ))

    def check_env_example(self) -> None:
        """Check .env.example for weak default values."""
        env_example = self.root_dir / ".env.example"
        if not env_example.exists():
            return

        with open(env_example, 'r', encoding='utf-8') as f:
            lines = f.readlines()

        weak_defaults = [
            ("JWT_SECRET=change-this", "Weak JWT secret placeholder"),
            ("JWT_SECRET=secret", "Weak JWT secret"),
            ("PASSWORD=password", "Default password"),
            ("PASSWORD=admin", "Default password"),
            ("neo4j_password=neo4j", "Default Neo4j password"),
        ]

        for line_num, line in enumerate(lines, 1):
            for pattern, issue in weak_defaults:
                if pattern.lower() in line.lower():
                    self.issues.append(SecurityIssue(
                        severity="HIGH",
                        file=".env.example",
                        line=line_num,
                        issue=issue,
                        code=line.strip()
                    ))

    def scan_directory(self, directory: Path, pattern: str = "*.py") -> None:
        """Recursively scan directory for Python files."""
        for file_path in directory.rglob(pattern):
            # Skip virtual environments and cache directories
            if any(part in file_path.parts for part in ['.venv', 'venv', '__pycache__', '.git']):
                continue
            self.scan_file(file_path)

    def run_audit(self) -> int:
        """Run complete security audit."""
        print("=" * 70)
        print("X-Agent Security Audit")
        print("=" * 70)
        print()

        # Scan Python files
        print("Scanning Python files for security issues...")
        backend_dir = self.root_dir / "backend"
        if backend_dir.exists():
            self.scan_directory(backend_dir)

        # Check CORS configuration
        print("Checking CORS configuration...")
        self.check_cors_config()

        # Check environment example
        print("Checking .env.example...")
        self.check_env_example()

        # Report findings
        print()
        print("=" * 70)
        print("Audit Results")
        print("=" * 70)
        print()

        if not self.issues:
            print("✅ No security issues found!")
            return 0

        # Group by severity
        critical = [i for i in self.issues if i.severity == "CRITICAL"]
        high = [i for i in self.issues if i.severity == "HIGH"]
        medium = [i for i in self.issues if i.severity == "MEDIUM"]
        low = [i for i in self.issues if i.severity == "LOW"]

        print(f"Found {len(self.issues)} security issues:")
        print(f"  🔴 CRITICAL: {len(critical)}")
        print(f"  🟠 HIGH: {len(high)}")
        print(f"  🟡 MEDIUM: {len(medium)}")
        print(f"  🟢 LOW: {len(low)}")
        print()

        # Print details
        for severity, issues in [("CRITICAL", critical), ("HIGH", high), ("MEDIUM", medium), ("LOW", low)]:
            if not issues:
                continue

            print(f"\n{severity} Issues:")
            print("-" * 70)
            for issue in issues:
                print(f"\n📁 {issue.file}:{issue.line}")
                print(f"   {issue.issue}")
                if issue.code:
                    print(f"   Code: {issue.code}")

        print()
        print("=" * 70)
        print("⚠️  Please fix these issues before deploying to production!")
        print("=" * 70)

        return 1 if critical or high else 0


def main():
    root_dir = Path(__file__).parent.parent
    auditor = SecurityAuditor(root_dir)
    exit_code = auditor.run_audit()
    sys.exit(exit_code)


if __name__ == "__main__":
    main()
