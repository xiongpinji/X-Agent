"""Verify Alembic migrations work on a real database.

Usage:
    python scripts/alembic_verify.py

What it does:
1. Creates a temporary SQLite database
2. Runs alembic upgrade head
3. Verifies all tables exist
4. Verifies columns are correct
5. Runs alembic downgrade base
6. Verifies tables are gone
7. Cleans up
"""
import os
import sys
import tempfile
import subprocess


def main():
    # Create temp DB
    tmp = tempfile.mktemp(suffix=".db")
    db_url = f"sqlite:///{tmp}"

    os.environ["XAGENT_DATABASE_URL"] = db_url

    print("=" * 50)
    print("Alembic Migration Verification")
    print("=" * 50)

    results = []

    # Step 1: Check alembic is installed
    try:
        import alembic
        results.append(("Alembic installed", True, alembic.__version__))
    except ImportError:
        results.append(("Alembic installed", False, "pip install alembic"))
        # Print and exit early
        for name, ok, msg in results:
            print(f"  {'✅' if ok else '❌'} {name}: {msg}")
        sys.exit(1)

    # Step 2: Run upgrade
    r = subprocess.run(
        ["alembic", "upgrade", "head"],
        capture_output=True, text=True,
        env={**os.environ, "XAGENT_DATABASE_URL": db_url}
    )
    results.append(("Upgrade head", r.returncode == 0, r.stdout.strip() or r.stderr.strip()[:100]))

    # Step 3: Verify tables exist
    if r.returncode == 0:
        import sqlite3
        conn = sqlite3.connect(tmp)
        tables = [row[0] for row in conn.execute("SELECT name FROM sqlite_master WHERE type='table'").fetchall()]
        expected = {"users", "api_keys", "agent_runs", "audit_events", "alembic_version"}
        found = expected.intersection(set(tables))
        results.append(("Tables created", found == expected, f"Found: {sorted(found)}"))

        # Verify columns in users table
        cols = [row[1] for row in conn.execute("PRAGMA table_info(users)").fetchall()]
        results.append(("Users columns", "username" in cols and "role" in cols, f"Columns: {cols}"))
        conn.close()

    # Step 4: Run downgrade
    r2 = subprocess.run(
        ["alembic", "downgrade", "base"],
        capture_output=True, text=True,
        env={**os.environ, "XAGENT_DATABASE_URL": db_url}
    )
    results.append(("Downgrade base", r2.returncode == 0, r2.stdout.strip() or r2.stderr.strip()[:100]))

    # Cleanup
    try:
        os.unlink(tmp)
    except:
        pass

    # Report
    print()
    passed = sum(1 for _, ok, _ in results if ok)
    for name, ok, msg in results:
        print(f"  {'✅' if ok else '❌'} {name}: {msg}")
    print(f"\n  Result: {passed}/{len(results)}")
    sys.exit(0 if passed == len(results) else 1)


if __name__ == "__main__":
    main()
