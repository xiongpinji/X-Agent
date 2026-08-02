from fastapi.testclient import TestClient
from backend.app.main import app

with TestClient(app, headers={"X-API-Key": "xagent-dev-key-2024"}) as c:
    r = c.post("/api/v1/tools/echo/test", json={"parameters": {"message": "hello"}})
    print("echo/test:", r.status_code, r.json())
    # memory stats + real id
    rs = c.get("/api/v1/memory/stats")
    print("memory/stats:", rs.status_code, rs.json())
    store = c.post("/api/v1/memory", json={"content": "probe memory item for stats check", "layer": 3})
    print("store:", store.status_code, store.json())
    mid = store.json().get("id")
    rg = c.get(f"/api/v1/memory/{mid}")
    print("get by id:", rg.status_code, str(rg.json())[:200])
    r404 = c.get("/api/v1/memory/does-not-exist")
    print("missing id:", r404.status_code, str(r404.json())[:120])
