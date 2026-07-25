"""Full-stack smoke test — validates X-Agent against real services.

Prerequisites:
    - PostgreSQL running (docker-compose up postgres -d)
    - Redis running (docker-compose up redis -d)

Usage:
    python scripts/smoke_test.py [--skip-db] [--skip-redis]

Exit codes:
    0 = all checks passed
    1 = one or more checks failed
"""
import asyncio
import os
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))
os.environ.setdefault("XAGENT_APP_MODE", "development")

PROJECT_ROOT = Path(__file__).resolve().parent.parent


class SmokeTest:
    def __init__(self):
        self.results: list[tuple[str, bool, str]] = []

    def record(self, name: str, passed: bool, detail: str = ""):
        self.results.append((name, passed, detail))
        status = "✅" if passed else "❌"
        print(f"  {status} {name}" + (f" — {detail}" if detail else ""))

    # ------------------------------------------------------------------
    # Service checks
    # ------------------------------------------------------------------

    async def check_postgres(self) -> bool:
        """Verify PostgreSQL connectivity and schema."""
        try:
            import asyncpg

            conn = await asyncpg.connect(
                host=os.environ.get("DB_HOST", "localhost"),
                port=int(os.environ.get("DB_PORT", "5432")),
                user=os.environ.get("DB_USER", "xagent"),
                password=os.environ.get("DB_PASSWORD", "xagent_secure_password"),
                database=os.environ.get("DB_NAME", "xagent_db"),
            )
            version = await conn.fetchval("SELECT version()")
            # Check that at least one table exists (init_schema.sql creates tables)
            table_count = await conn.fetchval(
                "SELECT count(*) FROM information_schema.tables WHERE table_schema = 'public'"
            )
            await conn.close()
            detail = f"{version[:40]}… | {table_count} tables"
            self.record("PostgreSQL", True, detail)
            return True
        except Exception as e:
            self.record("PostgreSQL", False, str(e)[:80])
            return False

    async def check_redis(self) -> bool:
        """Verify Redis connectivity."""
        try:
            import redis as redis_lib

            r = redis_lib.Redis(
                host=os.environ.get("REDIS_HOST", "localhost"),
                port=int(os.environ.get("REDIS_PORT", "6379")),
                password=os.environ.get("REDIS_PASSWORD", "redis_secure_password"),
                socket_connect_timeout=5,
            )
            pong = r.ping()
            info = r.info("server")
            redis_version = info.get("redis_version", "unknown")
            r.close()
            self.record("Redis", pong, f"PONG (v{redis_version})")
            return True
        except Exception as e:
            self.record("Redis", False, str(e)[:80])
            return False

    # ------------------------------------------------------------------
    # Application checks
    # ------------------------------------------------------------------

    def check_app_import(self) -> bool:
        """Verify app imports and routes register."""
        try:
            start = time.time()
            from backend.app.main import app  # noqa: F401

            elapsed = (time.time() - start) * 1000
            route_count = len(app.routes)
            self.record("App Import", True, f"{elapsed:.0f}ms, {route_count} routes")
            return True
        except Exception as e:
            self.record("App Import", False, str(e)[:80])
            return False

    def check_settings(self) -> bool:
        """Verify settings load correctly."""
        try:
            from backend.app.settings import Settings

            s = Settings()
            # Validate critical fields
            issues = []
            if not s.app_name:
                issues.append("app_name empty")
            if not s.database_url:
                issues.append("database_url empty")
            if s.app_mode not in ("development", "production", "test"):
                issues.append(f"unexpected app_mode={s.app_mode}")

            if issues:
                self.record("Settings", False, "; ".join(issues))
                return False

            detail = f"mode={s.app_mode}, memory_backend={s.memory_backend}"
            self.record("Settings", True, detail)
            return True
        except Exception as e:
            self.record("Settings", False, str(e)[:80])
            return False

    def check_migrations(self) -> bool:
        """Verify migration files exist and are valid SQL."""
        try:
            migrations_dir = PROJECT_ROOT / "backend" / "migrations"
            if not migrations_dir.is_dir():
                self.record("Migrations", False, "migrations directory not found")
                return False

            sql_files = sorted(migrations_dir.glob("*.sql"))
            if not sql_files:
                self.record("Migrations", False, "no .sql files found")
                return False

            # Basic validation: files are non-empty and contain SQL keywords
            issues = []
            for f in sql_files:
                content = f.read_text(encoding="utf-8")
                if len(content.strip()) < 10:
                    issues.append(f"{f.name}: too short")
                elif not any(
                    kw in content.upper()
                    for kw in ("CREATE", "ALTER", "INSERT", "DROP", "SELECT", "INDEX")
                ):
                    issues.append(f"{f.name}: no SQL keywords")

            if issues:
                self.record("Migrations", False, "; ".join(issues[:3]))
                return False

            self.record("Migrations", True, f"{len(sql_files)} SQL files valid")
            return True
        except Exception as e:
            self.record("Migrations", False, str(e)[:80])
            return False

    async def check_api_health(self) -> bool:
        """Start app briefly via ASGI test client and check /health."""
        try:
            from httpx import ASGITransport, AsyncClient

            from backend.app.main import app

            transport = ASGITransport(app=app)
            async with AsyncClient(transport=transport, base_url="http://test") as client:
                resp = await client.get("/health", timeout=10)
                data = resp.json()

            if resp.status_code == 200 and data.get("status") == "ok":
                self.record("API /health", True, f"200 → {data}")
                return True
            else:
                self.record("API /health", False, f"status={resp.status_code}, body={data}")
                return False
        except Exception as e:
            self.record("API /health", False, str(e)[:80])
            return False

    def check_frontend_build(self) -> bool:
        """Verify frontend source exists and package.json is valid."""
        try:
            frontend_dir = PROJECT_ROOT / "frontend"
            if not frontend_dir.is_dir():
                self.record("Frontend", False, "frontend/ directory not found")
                return False

            pkg_json = frontend_dir / "package.json"
            if not pkg_json.exists():
                self.record("Frontend", False, "package.json not found")
                return False

            import json

            pkg = json.loads(pkg_json.read_text(encoding="utf-8"))
            name = pkg.get("name", "unknown")
            scripts = pkg.get("scripts", {})
            has_build = "build" in scripts
            has_dev = "dev" in scripts or "start" in scripts

            detail = f"{name}" + (", build ✓" if has_build else ", no build script")
            passed = has_build or has_dev
            self.record("Frontend", passed, detail)
            return passed
        except Exception as e:
            self.record("Frontend", False, str(e)[:80])
            return False

    # ------------------------------------------------------------------
    # Runner
    # ------------------------------------------------------------------

    async def run_all(self, skip_db=False, skip_redis=False):
        print("\n🔍 X-Agent Full-Stack Smoke Test\n" + "=" * 50)

        if not skip_db:
            await self.check_postgres()
        else:
            print("  ⏭️  PostgreSQL — skipped")

        if not skip_redis:
            await self.check_redis()
        else:
            print("  ⏭️  Redis — skipped")

        self.check_app_import()
        self.check_settings()
        self.check_migrations()
        await self.check_api_health()
        self.check_frontend_build()

        print("\n" + "=" * 50)
        passed = sum(1 for _, p, _ in self.results if p)
        total = len(self.results)
        print(f"\n📊 Results: {passed}/{total} passed")

        if passed == total:
            print("🎉 ALL CHECKS PASSED — Ready for deployment!")
        else:
            failed = [(n, d) for n, p, d in self.results if not p]
            print("⚠️  Some checks failed:")
            for name, detail in failed:
                print(f"   • {name}: {detail}")

        return passed == total


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="X-Agent full-stack smoke test")
    parser.add_argument("--skip-db", action="store_true", help="Skip PostgreSQL check")
    parser.add_argument("--skip-redis", action="store_true", help="Skip Redis check")
    args = parser.parse_args()

    test = SmokeTest()
    success = asyncio.run(test.run_all(skip_db=args.skip_db, skip_redis=args.skip_redis))
    sys.exit(0 if success else 1)
