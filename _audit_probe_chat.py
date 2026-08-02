"""审计探针3: 实测 Agent 主循环 (/chat) 与工具执行、记忆写入、沙箱执行."""
import json
import os

os.environ.setdefault("XAGENT_LLM_BACKEND", "mock")

from fastapi.testclient import TestClient

from backend.app.main import app

KEY = "xagent-dev-key-2024"
H = {"X-API-Key": KEY}
results = {}

with TestClient(app) as client:
    # 1. 聊天/Agent 主循环 (mock LLM)
    try:
        r = client.post("/chat", headers=H, json={"message": "echo hello", "session_id": "audit-1"}, timeout=60)
        results["POST /chat"] = {"status": r.status_code, "body": r.text[:400].replace("\n", " ")}
    except Exception as e:  # noqa: BLE001
        results["POST /chat"] = {"status": "EXC", "body": str(e)[:300]}

    # 2. 工具执行 (echo 低风险)
    try:
        r = client.post("/api/v1/tools/echo/execute", headers=H, json={"arguments": {"text": "audit"}}, timeout=30)
        results["POST tools/echo/execute"] = {"status": r.status_code, "body": r.text[:300].replace("\n", " ")}
    except Exception as e:  # noqa: BLE001
        results["POST tools/echo/execute"] = {"status": "EXC", "body": str(e)[:300]}

    # 3. 记忆写入+读取
    try:
        r = client.post("/api/v1/memory", headers=H, json={"content": "audit memory probe", "metadata": {"src": "audit"}}, timeout=30)
        results["POST /api/v1/memory"] = {"status": r.status_code, "body": r.text[:300].replace("\n", " ")}
    except Exception as e:  # noqa: BLE001
        results["POST /api/v1/memory"] = {"status": "EXC", "body": str(e)[:300]}

    # 4. 工作流创建
    try:
        r = client.post("/api/v1/workflows", headers=H,
                        json={"name": "audit-wf", "description": "probe", "nodes": [], "edges": []}, timeout=30)
        results["POST /api/v1/workflows"] = {"status": r.status_code, "body": r.text[:300].replace("\n", " ")}
    except Exception as e:  # noqa: BLE001
        results["POST /api/v1/workflows"] = {"status": "EXC", "body": str(e)[:300]}

    # 5. 高风险工具是否触发审批 (write_file)
    try:
        r = client.post("/api/v1/tools/write_file/execute", headers=H,
                        json={"arguments": {"path": "_audit_probe_tmp.txt", "content": "x"}}, timeout=30)
        results["POST tools/write_file/execute"] = {"status": r.status_code, "body": r.text[:300].replace("\n", " ")}
    except Exception as e:  # noqa: BLE001
        results["POST tools/write_file/execute"] = {"status": "EXC", "body": str(e)[:300]}

print(json.dumps(results, ensure_ascii=False, indent=1))
