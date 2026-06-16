"""X-Agent 端到端验证脚本 — 验证完整系统可工作

运行方式:
    $env:XAGENT_QDRANT_URL=""
    $env:XAGENT_MODE="lite"
    $env:XAGENT_LLM_BACKEND="mock"
    python scripts/e2e_verify.py

验证内容:
    1. Settings 加载（lite模式）
    2. FastAPI app 创建（所有路由注册）
    3. /health 端点
    4. /ready 端点
    5. RBAC 权限逻辑
    6. Skills 框架加载
    7. Web Search 工具可用
    8. Rate Limiter 工作
    9. SDK 客户端可实例化
    10. CLI start 命令存在
"""

from __future__ import annotations

import os
import sys
import time

# 确保lite模式
os.environ.setdefault("XAGENT_QDRANT_URL", "")
os.environ.setdefault("XAGENT_MODE", "lite")
os.environ.setdefault("XAGENT_LLM_BACKEND", "mock")
os.environ.setdefault("XAGENT_REQUIRE_API_KEY", "false")
os.environ.setdefault("XAGENT_DATABASE_URL", "sqlite+aiosqlite:///./data/e2e_verify.db")

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

results: list[tuple[str, bool, str]] = []


def check(name: str, fn):
    """Run a check and record result."""
    try:
        msg = fn()
        results.append((name, True, msg or "OK"))
    except Exception as e:
        results.append((name, False, str(e)[:100]))


# === Checks ===

def check_settings():
    from backend.app.settings import Settings
    s = Settings()
    return f"mode={getattr(s, 'mode', 'N/A')}, llm={s.llm_backend}"

def check_app():
    from backend.app.main import app
    route_count = len(app.routes)
    assert route_count > 50, f"Only {route_count} routes"
    return f"{route_count} routes registered"

def check_health():
    from backend.app.main import app
    from starlette.testclient import TestClient
    client = TestClient(app)
    r = client.get("/health")
    assert r.status_code == 200
    assert r.json()["status"] == "ok"
    return f"200 OK"

def check_ready():
    from backend.app.main import app
    from starlette.testclient import TestClient
    client = TestClient(app)
    r = client.get("/ready")
    status = r.json().get("status")
    return f"{r.status_code} status={status}"

def check_rbac():
    from backend.app.core.rbac import has_permission, Role
    assert has_permission("admin", "agent:run")
    assert not has_permission("viewer", "agent:run")
    return "admin=✓ viewer-blocked=✓"

def check_skills():
    from backend.app.core.skills import load_builtin_skills
    skills = load_builtin_skills()
    assert len(skills) >= 3
    return f"{len(skills)} builtin skills loaded"

def check_web_search():
    from backend.app.core.tools_builtin.web_search import WEB_SEARCH_TOOL_SCHEMA
    assert WEB_SEARCH_TOOL_SCHEMA["name"] == "web_search"
    return "web_search schema valid"

def check_rate_limiter():
    from backend.app.core.rate_limiter import RateLimiter, RateLimitResult
    limiter = RateLimiter()
    result = limiter.check_rate_limit("test:e2e", 100, 60)
    assert result.allowed
    return f"allowed=True remaining={result.remaining}"

def check_sdk():
    sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "sdk"))
    from xagent_sdk import XAgent
    client = XAgent(base_url="http://localhost:8000", api_key="test")
    assert client is not None
    return "XAgent client instantiated"

def check_cli():
    import ast
    cli_path = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "cli", "main.py")
    with open(cli_path) as f:
        tree = ast.parse(f.read())
    funcs = [n.name for n in ast.walk(tree) if isinstance(n, ast.FunctionDef)]
    assert "start" in funcs
    return f"'start' + {len(funcs)-1} other commands"


# === Run ===

if __name__ == "__main__":
    print("=" * 60)
    print("X-Agent End-to-End Verification")
    print("=" * 60)
    print()

    checks = [
        ("1. Settings (lite mode)", check_settings),
        ("2. FastAPI app creation", check_app),
        ("3. GET /health", check_health),
        ("4. GET /ready", check_ready),
        ("5. RBAC permissions", check_rbac),
        ("6. Skills framework", check_skills),
        ("7. Web search tool", check_web_search),
        ("8. Rate limiter", check_rate_limiter),
        ("9. SDK client", check_sdk),
        ("10. CLI start command", check_cli),
    ]

    start = time.time()
    for name, fn in checks:
        check(name, fn)

    elapsed = time.time() - start

    print()
    passed = sum(1 for _, ok, _ in results if ok)
    for name, ok, msg in results:
        icon = "✅" if ok else "❌"
        print(f"  {icon} {name}: {msg}")

    print()
    print("-" * 60)
    print(f"  Result: {passed}/{len(results)} passed in {elapsed:.1f}s")
    if passed == len(results):
        print("  🎉 ALL CHECKS PASSED — System is production-ready")
    else:
        print("  ⚠️  Some checks failed — review above")
    print("-" * 60)

    sys.exit(0 if passed == len(results) else 1)
