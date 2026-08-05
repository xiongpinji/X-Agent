"""P1-09 批次 D：capability discovery 真实化的回归测试。

背景：/collaboration/agents/discover 原只回静态 default-agent，且在未挂载的
extended_router 上。本次挂载并改为真实枚举 org 花名册 / room 成员 /
spawner 实例 / 隐式 generalist，capability 过滤与 delegation 共用
capability_match 语义。
"""

from __future__ import annotations

from starlette.testclient import TestClient

from backend.app.core.collaboration.store import CollaborationStore
from backend.app.main import app

_HEADERS = {"X-API-Key": "bootstrap"}


def test_discover_enumerates_room_members_and_generalist(monkeypatch) -> None:
    from backend.app.api import collaboration as collab_api

    room_store = CollaborationStore()
    room_store.create_room(
        topic="t", tenant_id="default", created_by="tester", members=["agent-room-1"]
    )
    monkeypatch.setattr(collab_api, "collaboration_store", room_store)

    with TestClient(app) as client:
        resp = client.get("/api/v1/collaboration/agents/discover", headers=_HEADERS)

    assert resp.status_code == 200
    body = resp.json()
    ids = {a["agent_id"] for a in body["agents"]}
    assert "agent-room-1" in ids
    assert "default-agent" in ids
    assert body["sources"].get("room") == 1
    assert body["sources"].get("implicit") == 1


def test_discover_capability_filter_matches_delegation_semantics() -> None:
    with TestClient(app) as client:
        hit = client.get(
            "/api/v1/collaboration/agents/discover",
            params={"capability": "CODE_EXECUTION"},  # 大小写不敏感
            headers=_HEADERS,
        )
        miss = client.get(
            "/api/v1/collaboration/agents/discover",
            params={"capability": "no-such-capability"},
            headers=_HEADERS,
        )

    assert hit.status_code == 200
    assert any(a["agent_id"] == "default-agent" for a in hit.json()["agents"])
    assert miss.status_code == 200
    assert miss.json()["agents"] == []


def test_discover_is_mounted_and_requires_auth() -> None:
    with TestClient(app) as client:
        unauthenticated = client.get("/api/v1/collaboration/agents/discover")

    assert unauthenticated.status_code in (401, 403)
