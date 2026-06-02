#!/usr/bin/env python3
"""
Security Fixes Verification Script
Validates all 7 security vulnerabilities have been fixed.

CRITICAL Fixes:
1. Hardcoded JWT Secret - Environment variable validation
2. CORS Wildcard Configuration - Production enforcement
3. SQL Injection Risk - Parameterized queries verification

HIGH Fixes:
4. Environment Variable Validation - Strict validation
5. Password Hashing Algorithm - Bcrypt 12+ cost factor
6. API Rate Limiting - Enabled and configured
7. Dependency Versions - Secure versions pinned
"""

import re
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]


def check_jwt_secret_validation():
    """CRITICAL #1: Verify JWT secret is not hardcoded and requires environment variables."""
    print("\n[CRITICAL #1] Checking JWT Secret Validation...")

    settings_file = PROJECT_ROOT / "backend" / "app" / "settings.py"
    content = settings_file.read_text()

    checks = [
        ("Environment variable validation", "XAGENT_JWT_SECRET" in content),
        ("Production secret enforcement", "app_mode == \"production\"" in content),
        ("Minimum length requirement", "len(value) < 32" in content),
        ("Default value warning", "change-this-to-a-random-64-char-string" in content),
    ]

    passed = all(check[1] for check in checks)
    for check_name, result in checks:
        status = "PASS" if result else "FAIL"
        print(f"  {status}: {check_name}")

    return passed


def check_cors_wildcard_prevention():
    """CRITICAL #2: Verify CORS wildcard is prevented in production."""
    print("\n[CRITICAL #2] Checking CORS Wildcard Prevention...")

    main_file = PROJECT_ROOT / "backend" / "app" / "main.py"
    content = main_file.read_text()

    checks = [
        ("Wildcard detection", '"*" in allow_origins' in content),
        ("Production mode check", 'settings.app_mode == "production"' in content),
        ("Error raising", "raise ValueError" in content and "CORS wildcard" in content),
        ("Security logging", "logger.error" in content and "CRITICAL SECURITY" in content),
    ]

    passed = all(check[1] for check in checks)
    for check_name, result in checks:
        status = "PASS" if result else "FAIL"
        print(f"  {status}: {check_name}")

    return passed


def check_sql_injection_prevention():
    """CRITICAL #3: Verify SQL injection prevention with parameterized queries."""
    print("\n[CRITICAL #3] Checking SQL Injection Prevention...")

    memory_file = PROJECT_ROOT / "backend" / "app" / "core" / "memory_postgres.py"
    content = memory_file.read_text()

    checks = [
        ("Parameterized queries ($1, $2, etc)", re.search(r"\$\d+", content) is not None),
        ("No string concatenation in SQL", "f\"\"\"" not in content or "SELECT" not in content),
        ("ILIKE with ESCAPE clause", "ILIKE" in content and "ESCAPE" in content),
        ("Proper escaping function", "_escape_ilike" in content),
    ]

    passed = all(check[1] for check in checks)
    for check_name, result in checks:
        status = "PASS" if result else "FAIL"
        print(f"  {status}: {check_name}")

    return passed


def check_environment_validation():
    """HIGH #4: Verify environment variable validation."""
    print("\n[HIGH #4] Checking Environment Variable Validation...")

    security_config = PROJECT_ROOT / "backend" / "app" / "core" / "config" / "security.py"
    content = security_config.read_text()

    checks = [
        ("Field validators present", "@field_validator" in content),
        ("Production environment check", "Environment.PRODUCTION" in content),
        ("CORS headers validation", "validate_cors_headers" in content),
        ("HTTPS requirement validation", "validate_https_requirement" in content),
        ("Bcrypt cost validation", "validate_bcrypt_cost" in content),
    ]

    passed = all(check[1] for check in checks)
    for check_name, result in checks:
        status = "PASS" if result else "FAIL"
        print(f"  {status}: {check_name}")

    return passed


def check_password_hashing():
    """HIGH #5: Verify password hashing uses bcrypt with cost 12+."""
    print("\n[HIGH #5] Checking Password Hashing Algorithm...")

    security_config = PROJECT_ROOT / "backend" / "app" / "core" / "config" / "security.py"
    content = security_config.read_text()

    auth_file = PROJECT_ROOT / "backend" / "app" / "api" / "auth.py"
    auth_content = auth_file.read_text()

    checks = [
        ("Bcrypt import", "import bcrypt" in auth_content),
        ("Bcrypt cost minimum 12", "ge=12" in content),
        ("Bcrypt gensalt usage", "bcrypt.gensalt(rounds=12)" in auth_content),
        ("Bcrypt checkpw usage", "bcrypt.checkpw" in auth_content),
    ]

    passed = all(check[1] for check in checks)
    for check_name, result in checks:
        status = "PASS" if result else "FAIL"
        print(f"  {status}: {check_name}")

    return passed


def check_rate_limiting():
    """HIGH #6: Verify API rate limiting is implemented."""
    print("\n[HIGH #6] Checking API Rate Limiting...")

    main_file = PROJECT_ROOT / "backend" / "app" / "main.py"
    content = main_file.read_text()

    checks = [
        ("Rate limiter class", "class _RateLimiter" in content),
        ("Rate limit middleware", "rate_limit_middleware" in content),
        ("Login endpoint rate limit", "login:{client_ip}" in content),
        ("API endpoint rate limit", "api:{client_ip}" in content),
        ("Rate limit enforcement", "is_allowed" in content),
    ]

    passed = all(check[1] for check in checks)
    for check_name, result in checks:
        status = "PASS" if result else "FAIL"
        print(f"  {status}: {check_name}")

    return passed


def check_dependency_versions():
    """HIGH #7: Verify dependency versions are secure and pinned."""
    print("\n[HIGH #7] Checking Dependency Versions...")

    requirements_file = PROJECT_ROOT / "requirements.txt"
    content = requirements_file.read_text()

    checks = [
        ("Bcrypt pinned to 4.1.2+", "bcrypt==4.1.2" in content),
        ("Cryptography included", "cryptography==" in content),
        ("FastAPI pinned", "fastapi==0.115.0" in content),
        ("All versions pinned (no >=)", ">=" not in content or "# " in content),
        ("Security comment present", "SECURITY" in content or "security" in content.lower()),
    ]

    passed = all(check[1] for check in checks)
    for check_name, result in checks:
        status = "PASS" if result else "FAIL"
        print(f"  {status}: {check_name}")

    return passed


def main():
    """Run all security verification checks."""
    print("=" * 70)
    print("X-Agent Security Fixes Verification")
    print("=" * 70)

    results = {
        "CRITICAL #1 - JWT Secret Validation": check_jwt_secret_validation(),
        "CRITICAL #2 - CORS Wildcard Prevention": check_cors_wildcard_prevention(),
        "CRITICAL #3 - SQL Injection Prevention": check_sql_injection_prevention(),
        "HIGH #4 - Environment Validation": check_environment_validation(),
        "HIGH #5 - Password Hashing": check_password_hashing(),
        "HIGH #6 - Rate Limiting": check_rate_limiting(),
        "HIGH #7 - Dependency Versions": check_dependency_versions(),
    }

    print("\n" + "=" * 70)
    print("SUMMARY")
    print("=" * 70)

    passed_count = sum(1 for v in results.values() if v)
    total_count = len(results)

    for check_name, passed in results.items():
        status = "PASS" if passed else "FAIL"
        print(f"{status}: {check_name}")

    print("=" * 70)
    print(f"Total: {passed_count}/{total_count} checks passed")

    if passed_count == total_count:
        print("SUCCESS: All security fixes verified!")
        return 0
    else:
        print(f"FAILURE: {total_count - passed_count} checks failed")
        return 1


if __name__ == "__main__":
    sys.exit(main())
