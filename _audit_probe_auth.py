"""审计探针2: 带 bootstrap API Key 探测核心认证端点."""
import json

from fastapi.testclient import TestClient

from backend.app.main import app

KEY = "xagent-dev-key-2024"
H = {"X-API-Key": KEY}
results = {}

with TestClient(app) as client:
    probes = [
        ("GET", "/api/v1/agents", None),
        ("GET", "/api/v1/tools", None),
        ("GET", "/api/v1/workflows", None),
        ("GET", "/api/v1/memory/stats", None),
        ("GET", "/api/v1/approvals", None),
        ("GET", "/api/v1/audit/logs", None),
        ("GET", "/api/v1/sandbox/status", None),
        ("GET", "/api/v1/plugins", None),
        ("GET", "/api/v1/skills", None),
        ("GET", "/api/v1/tenants", None),
    ]
    for method, path, body in probes:
        try:
            resp = client.request(method, path, headers=H, json=body)
            results[f"{method} {path}"] = {"status": resp.status_code, "body": resp.text[:300].replace("\n", " ")}
        except Exception as e:  # noqa: BLE001
            results[f"{method} {path}"] = {"status": "EXC", "body": str(e)[:200]}

print(json.dumps(results, ensure_ascii=False, indent=1))
