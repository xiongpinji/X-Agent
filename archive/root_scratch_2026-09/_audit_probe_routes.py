"""审计探针: 触发完整启动流程后统计真实路由并探测核心端点."""
import json
import sys

from fastapi.testclient import TestClient

from backend.app.main import app

results = {"startup_error": None, "routes": 0, "probes": {}}

try:
    with TestClient(app) as client:
        results["routes"] = len([r for r in app.routes if hasattr(r, "methods")])
        api_paths = sorted({r.path for r in app.routes if hasattr(r, "methods") and r.path.startswith("/api")})
        results["api_route_count"] = len(api_paths)

        probes = [
            ("GET", "/health"),
            ("GET", "/ready"),
            ("GET", "/api/v1/entry"),
            ("GET", "/metrics"),
            ("GET", "/openapi.json"),
            ("GET", "/api/v1/agents"),
            ("GET", "/api/v1/tools"),
            ("GET", "/api/v1/workflows"),
            ("GET", "/api/v1/memory/stats"),
            ("GET", "/api/v1/audit"),
        ]
        for method, path in probes:
            try:
                resp = client.request(method, path)
                body = resp.text[:200].replace("\n", " ")
                results["probes"][f"{method} {path}"] = {"status": resp.status_code, "body": body}
            except Exception as e:  # noqa: BLE001
                results["probes"][f"{method} {path}"] = {"status": "EXC", "body": str(e)[:200]}

        # openapi 完整路径清单
        try:
            spec = client.get("/openapi.json").json()
            results["openapi_paths"] = len(spec.get("paths", {}))
        except Exception as e:  # noqa: BLE001
            results["openapi_error"] = str(e)[:200]
except Exception as e:  # noqa: BLE001
    results["startup_error"] = f"{type(e).__name__}: {e}"[:500]

print(json.dumps(results, ensure_ascii=False, indent=1))
