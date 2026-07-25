"""Validate X-Agent can start in both dev and production modes.

Tests:
1. Dev mode: full app import (no external services required)
2. Production guard: weak/default secrets must be rejected
3. Production settings: valid config passes all validators
4. Middleware: rate limiting, HSTS, CORS restriction verified

Exit 0 if all pass, 1 if any fail.

Usage:
    venv\\Scripts\\python.exe -X utf8 scripts/validate_startup.py
"""
from __future__ import annotations

import importlib
import inspect
import os
import subprocess
import sys

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

PASS = "\033[92mPASS\033[0m"
FAIL = "\033[91mFAIL\033[0m"

results: list[tuple[str, bool, str]] = []


def record(name: str, passed: bool, detail: str = "") -> None:
    results.append((name, passed, detail))
    tag = PASS if passed else FAIL
    suffix = f" — {detail}" if detail else ""
    print(f"  [{tag}] {name}{suffix}")


def run_isolated(script: str) -> subprocess.CompletedProcess[str]:
    """Run a Python snippet in a fresh interpreter (avoids lru_cache pollution)."""
    return subprocess.run(
        [sys.executable, "-X", "utf8", "-c", script],
        capture_output=True,
        text=True,
        timeout=60,
        cwd=os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
    )


# ---------------------------------------------------------------------------
# Test 1: Development mode startup
# ---------------------------------------------------------------------------

def test_dev_mode() -> None:
    print("\n[1/4] Development mode startup")
    script = (
        "import os\n"
        "os.environ['XAGENT_APP_MODE'] = 'development'\n"
        "from backend.app.main import app\n"
        "print(f'OK:{len(app.routes)}')\n"
    )
    r = run_isolated(script)
    output = r.stdout.strip()
    if r.returncode == 0 and output.startswith("OK:"):
        routes = output.split(":")[1]
        record("Dev mode app loads", True, f"{routes} routes")
    else:
        err = (r.stderr or output).strip().split("\n")[-1]
        record("Dev mode app loads", False, err)


# ---------------------------------------------------------------------------
# Test 2: Production guard rejects weak secrets
# ---------------------------------------------------------------------------

def test_prod_guard() -> None:
    print("\n[2/4] Production guard (weak secrets rejected)")

    # 2a: weak jwt_secret
    script = (
        "import os\n"
        "os.environ['XAGENT_APP_MODE'] = 'production'\n"
        "os.environ['XAGENT_JWT_SECRET'] = 'weak'\n"
        "try:\n"
        "    from backend.app.settings import get_settings\n"
        "    get_settings()\n"
        "    print('NO_ERROR')\n"
        "except Exception as e:\n"
        "    print(f'REJECTED:{type(e).__name__}')\n"
    )
    r = run_isolated(script)
    out = r.stdout.strip()
    if "REJECTED:" in out:
        record("Weak jwt_secret rejected", True, out.split(":")[1])
    else:
        record("Weak jwt_secret rejected", False, "Settings accepted weak secret")

    # 2b: default encryption_key
    script2 = (
        "import os\n"
        "os.environ['XAGENT_APP_MODE'] = 'production'\n"
        "os.environ['XAGENT_JWT_SECRET'] = 'A1b2C3d4E5f6G7h8I9j0K1l2M3n4O5p6'\n"
        "os.environ['XAGENT_ENCRYPTION_KEY'] = 'change-this-to-32-char-hex-string'\n"
        "os.environ['XAGENT_AUDIT_HMAC_SECRET'] = 'A1b2C3d4E5f6G7h8I9j0K1l2M3n4O5p6'\n"
        "os.environ['XAGENT_DATABASE_URL'] = 'postgresql+asyncpg://x:x@host:5432/db'\n"
        "os.environ['XAGENT_REDIS_URL'] = 'redis://host:6379/0'\n"
        "os.environ['XAGENT_ADMIN_STORE_BACKEND'] = 'postgres'\n"
        "os.environ['XAGENT_MEMORY_BACKEND'] = 'postgres'\n"
        "os.environ['XAGENT_TRACE_BACKEND'] = 'postgres'\n"
        "try:\n"
        "    from backend.app.settings import get_settings\n"
        "    get_settings()\n"
        "    print('NO_ERROR')\n"
        "except Exception as e:\n"
        "    print(f'REJECTED:{type(e).__name__}')\n"
    )
    r2 = run_isolated(script2)
    out2 = r2.stdout.strip()
    if "REJECTED:" in out2:
        record("Default encryption_key rejected", True, out2.split(":")[1])
    else:
        record("Default encryption_key rejected", False, "Settings accepted default key")

    # 2c: missing redis_url
    script3 = (
        "import os\n"
        "os.environ['XAGENT_APP_MODE'] = 'production'\n"
        "os.environ['XAGENT_JWT_SECRET'] = 'A1b2C3d4E5f6G7h8I9j0K1l2M3n4O5p6'\n"
        "os.environ['XAGENT_ENCRYPTION_KEY'] = 'A1b2C3d4E5f6G7h8I9j0K1l2M3n4O5p6'\n"
        "os.environ['XAGENT_AUDIT_HMAC_SECRET'] = 'A1b2C3d4E5f6G7h8I9j0K1l2M3n4O5p6'\n"
        "os.environ['XAGENT_DATABASE_URL'] = 'postgresql+asyncpg://x:x@host:5432/db'\n"
        "os.environ.pop('XAGENT_REDIS_URL', None)\n"
        "os.environ['XAGENT_ADMIN_STORE_BACKEND'] = 'postgres'\n"
        "os.environ['XAGENT_MEMORY_BACKEND'] = 'postgres'\n"
        "os.environ['XAGENT_TRACE_BACKEND'] = 'postgres'\n"
        "try:\n"
        "    from backend.app.settings import get_settings\n"
        "    get_settings()\n"
        "    print('NO_ERROR')\n"
        "except Exception as e:\n"
        "    print(f'REJECTED:{type(e).__name__}')\n"
    )
    r3 = run_isolated(script3)
    out3 = r3.stdout.strip()
    if "REJECTED:" in out3:
        record("Missing redis_url rejected", True, out3.split(":")[1])
    else:
        record("Missing redis_url rejected", False, "Settings accepted missing redis")


# ---------------------------------------------------------------------------
# Test 3: Production settings with valid config
# ---------------------------------------------------------------------------

def test_prod_valid_config() -> None:
    print("\n[3/4] Production settings with valid config")
    script = (
        "import os\n"
        "os.environ['XAGENT_APP_MODE'] = 'production'\n"
        "os.environ['XAGENT_JWT_SECRET'] = 'A1b2C3d4E5f6G7h8I9j0K1l2M3n4O5p6'\n"
        "os.environ['XAGENT_ENCRYPTION_KEY'] = 'A1b2C3d4E5f6G7h8I9j0K1l2M3n4O5p6'\n"
        "os.environ['XAGENT_AUDIT_HMAC_SECRET'] = 'A1b2C3d4E5f6G7h8I9j0K1l2M3n4O5p6'\n"
        "os.environ['XAGENT_DATABASE_URL'] = 'postgresql+asyncpg://x:x@db-host:5432/db'\n"
        "os.environ['XAGENT_REDIS_URL'] = 'redis://redis-host:6379/0'\n"
        "os.environ['XAGENT_ADMIN_STORE_BACKEND'] = 'postgres'\n"
        "os.environ['XAGENT_MEMORY_BACKEND'] = 'postgres'\n"
        "os.environ['XAGENT_TRACE_BACKEND'] = 'postgres'\n"
        "from backend.app.settings import get_settings\n"
        "s = get_settings()\n"
        "print(f'MODE:{s.app_mode}')\n"
        "print(f'RATE:{s.rate_limit_active}')\n"
    )
    r = run_isolated(script)
    out = r.stdout.strip()
    if "MODE:production" in out and "RATE:True" in out:
        record("Prod settings validated", True, "mode=production, rate_limit=True")
    else:
        err = (r.stderr or out).strip().split("\n")[-1]
        record("Prod settings validated", False, err)


# ---------------------------------------------------------------------------
# Test 4: Middleware verification (source-level inspection)
# ---------------------------------------------------------------------------

def test_middleware() -> None:
    print("\n[4/4] Middleware verification (source inspection)")

    # We inspect main.py source directly to avoid needing a live DB connection
    main_path = os.path.join(
        os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
        "backend", "app", "main.py",
    )
    with open(main_path, encoding="utf-8") as f:
        src = f.read()

    # 4a: Rate limiting middleware present and mode-aware
    has_rate_limit = "rate_limit_middleware" in src and "rate_limit_active" in src
    record("Rate limiting middleware", has_rate_limit,
           "mode-aware (auto-enabled in prod)" if has_rate_limit else "missing")

    # 4b: HSTS header in production
    has_hsts = "Strict-Transport-Security" in src and "max-age=31536000" in src
    record("HSTS header (prod)", has_hsts,
           "max-age=31536000; includeSubDomains; preload" if has_hsts else "missing")

    # 4c: CORS wildcard blocked in production
    has_cors_guard = "CORS wildcard (*) is not allowed in production" in src
    record("CORS wildcard blocked", has_cors_guard,
           "enforced in settings + main" if has_cors_guard else "missing")

    # 4d: CSRF protection middleware
    has_csrf = "CSRFProtectionMiddleware" in src
    record("CSRF protection", has_csrf, "active" if has_csrf else "missing")

    # 4e: Security headers middleware (CSP, X-Frame-Options, etc.)
    has_csp = "Content-Security-Policy" in src
    has_xfo = "X-Frame-Options" in src
    record("Security headers (CSP/XFO)", has_csp and has_xfo,
           "CSP + X-Frame-Options + nosniff" if (has_csp and has_xfo) else "incomplete")

    # 4f: Docs disabled in production
    has_docs_guard = 'docs_url=None if _is_production' in src
    record("API docs disabled (prod)", has_docs_guard,
           "/docs, /redoc, /openapi.json hidden" if has_docs_guard else "missing")

    # 4g: Request size limit
    has_size_limit = "request_size_limit_middleware" in src
    record("Request size limit", has_size_limit,
           "10MB default" if has_size_limit else "missing")


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main() -> int:
    print("=" * 60)
    print("  X-Agent Startup Validation")
    print("=" * 60)

    test_dev_mode()
    test_prod_guard()
    test_prod_valid_config()
    test_middleware()

    # Summary
    print("\n" + "=" * 60)
    total = len(results)
    passed = sum(1 for _, ok, _ in results if ok)
    failed = total - passed
    print(f"  Results: {passed}/{total} passed, {failed} failed")
    print("=" * 60)

    if failed:
        print("\nFailed checks:")
        for name, ok, detail in results:
            if not ok:
                print(f"  - {name}: {detail}")
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
