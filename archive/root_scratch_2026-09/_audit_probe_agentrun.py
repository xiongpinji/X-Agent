"""审计探针4: 实测 Agent 主循环 POST /api/v1/agents/run 与工具 test 端点."""
import json
import os
import sys

backend = sys.argv[1] if len(sys.argv) > 1 else "mock"
os.environ["XAGENT_LLM_BACKEND"] = backend

from fastapi.testclient import TestClient

from backend.app.main import app

KEY = "xagent-dev-key-2024"
H = {"X-API-Key": KEY}
results = {"llm_backend": backend}

with TestClient(app) as client:
    try:
        r = client.post("/api/v1/agents/run", headers=H,
                        json={"message": "What is 2+2? Answer briefly."}, timeout=180)
        results["POST /api/v1/agents/run"] = {"status": r.status_code, "body": r.text[:600].replace("\n", " ")}
    except Exception as e:  # noqa: BLE001
        results["POST /api/v1/agents/run"] = {"status": "EXC", "body": str(e)[:400]}

    try:
        r = client.post("/api/v1/tools/echo/test", headers=H, json={"arguments": {"text": "probe"}}, timeout=30)
        results["POST /api/v1/tools/echo/test"] = {"status": r.status_code, "body": r.text[:300].replace("\n", " ")}
    except Exception as e:  # noqa: BLE001
        results["POST /api/v1/tools/echo/test"] = {"status": "EXC", "body": str(e)[:300]}

print(json.dumps(results, ensure_ascii=False, indent=1))
