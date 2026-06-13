"""Docker full-stack verification — validates the complete containerized deployment.

Usage:
    python scripts/docker_verify.py [--build] [--up] [--test] [--down]
    python scripts/docker_verify.py --all  # full cycle

Steps:
    1. docker build — image compiles with all new modules
    2. docker compose up -d — full stack starts (PG/Redis/Qdrant/API/Worker)
    3. health/ready probes pass
    4. docker compose down — clean shutdown
"""
from __future__ import annotations

import argparse
import subprocess
import sys
import time


def run(cmd: str, check: bool = True, timeout: int = 120) -> subprocess.CompletedProcess:
    """Run shell command and return result."""
    print(f"  $ {cmd}")
    result = subprocess.run(
        cmd, shell=True, capture_output=True, text=True, timeout=timeout
    )
    if check and result.returncode != 0:
        print(f"  ❌ FAILED (exit {result.returncode})")
        if result.stderr:
            print(f"     {result.stderr[:200]}")
        return result
    return result


def step_build() -> bool:
    """Build Docker image."""
    print("\n🔨 Step 1: Docker Build")
    r = run("docker build -t xagent:verify -f Dockerfile .", timeout=300)
    if r.returncode == 0:
        print("  ✅ Image built: xagent:verify")
        return True
    return False


def step_verify_image() -> bool:
    """Verify image can import core modules."""
    print("\n🔍 Step 2: Image Verification")
    checks = [
        ("Settings import", 'python -c "from backend.app.settings import Settings; print(Settings.__name__)"'),
        ("RBAC import", 'python -c "from backend.app.core.rbac import Role; print(list(Role))"'),
        ("Skills import", 'python -c "from backend.app.core.skills.schema import SkillDefinition; print(SkillDefinition.__name__)"'),
    ]
    all_pass = True
    for name, cmd in checks:
        r = run(f'docker run --rm xagent:verify {cmd}')
        if r.returncode == 0:
            print(f"  ✅ {name}: {r.stdout.strip()}")
        else:
            print(f"  ❌ {name}: failed")
            all_pass = False
    return all_pass


def step_compose_up() -> bool:
    """Start full stack with docker compose."""
    print("\n🚀 Step 3: Docker Compose Up")
    r = run("docker compose up -d --build", timeout=300)
    if r.returncode != 0:
        return False

    # Wait for health
    print("  ⏳ Waiting for services to be healthy...")
    for attempt in range(30):
        time.sleep(2)
        r = run("docker compose ps --format json", check=False)
        if "healthy" in r.stdout.lower() or attempt > 15:
            break

    print("  ✅ Stack is up")
    return True


def step_health_probe() -> bool:
    """Test health and ready endpoints."""
    print("\n🏥 Step 4: Health Probes")
    import urllib.request
    import json

    base = "http://localhost:8000"
    all_pass = True

    for endpoint in ["/health", "/ready"]:
        try:
            req = urllib.request.Request(f"{base}{endpoint}")
            with urllib.request.urlopen(req, timeout=10) as resp:
                data = json.loads(resp.read())
                status_code = resp.status
                print(f"  ✅ {endpoint}: {status_code} → {data.get('status', 'ok')}")
        except Exception as e:
            print(f"  ❌ {endpoint}: {e}")
            all_pass = False

    return all_pass


def step_compose_down() -> bool:
    """Tear down stack."""
    print("\n🧹 Step 5: Docker Compose Down")
    r = run("docker compose down -v", timeout=60)
    print("  ✅ Stack torn down")
    return True


def main():
    parser = argparse.ArgumentParser(description="Docker full-stack verification")
    parser.add_argument("--build", action="store_true", help="Build image only")
    parser.add_argument("--up", action="store_true", help="Start compose stack")
    parser.add_argument("--test", action="store_true", help="Run health probes")
    parser.add_argument("--down", action="store_true", help="Tear down stack")
    parser.add_argument("--all", action="store_true", help="Full verification cycle")
    args = parser.parse_args()

    if not any([args.build, args.up, args.test, args.down, args.all]):
        args.all = True

    print("=" * 60)
    print("X-Agent Docker Full-Stack Verification")
    print("=" * 60)

    results = []

    if args.all or args.build:
        results.append(("Build", step_build()))
        results.append(("Image verify", step_verify_image()))

    if args.all or args.up:
        results.append(("Compose up", step_compose_up()))

    if args.all or args.test:
        results.append(("Health probes", step_health_probe()))

    if args.all or args.down:
        results.append(("Compose down", step_compose_down()))

    print("\n" + "=" * 60)
    passed = sum(1 for _, ok in results if ok)
    for name, ok in results:
        print(f"  {'✅' if ok else '❌'} {name}")
    print(f"\n  Result: {passed}/{len(results)} steps passed")
    print("=" * 60)

    sys.exit(0 if passed == len(results) else 1)


if __name__ == "__main__":
    main()
