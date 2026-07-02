from fastapi import Request
from fastapi.testclient import TestClient

from backend.app.core.contracts import RunContext
from backend.app.core.memory import MemorySystem
from backend.app.core.security import Principal, ROLE_SCOPES
from backend.app.dependencies import get_current_principal, get_memory
from backend.app.main import app


def _tenant_principal(tenant_id: str) -> Principal:
    return Principal(
        tenant_id=tenant_id,
        user_id=f"{tenant_id}-user",
        agent_id=f"{tenant_id}-agent",
        request_id=f"{tenant_id}-request",
        trace_id=f"{tenant_id}-trace",
        permission_scope=list(ROLE_SCOPES["admin"]),
        role="admin",
        scopes=list(ROLE_SCOPES["admin"]),
        authenticated=True,
    )


def _principal_from_header(request: Request) -> Principal:
    return _tenant_principal(request.headers.get("x-test-tenant", "tenant-a"))


class _FallbackSearchMemory:
    def __init__(self, memory: MemorySystem) -> None:
        self._memory = memory

    async def search(self, *args, **kwargs):  # noqa: ANN002, ANN003
        return []

    def layer_items(self, layer: int):
        return self._memory.layer_items(layer)

    def layer_profile(self, layer: int):
        return self._memory.layer_profile(layer)

    def layer_summary(self, tenant_id: str | None = None):
        return self._memory.layer_summary(tenant_id=tenant_id)

    def layer_roles(self):
        return self._memory.layer_roles()

    def session_items(self, session_id: str):
        return self._memory.session_items(session_id)

    def session_summary(self, session_id: str):
        return self._memory.session_summary(session_id)

    def session_memory_layers(self, session_id: str):
        return self._memory.session_memory_layers(session_id)

    def session_count(self, tenant_id: str | None = None):
        return self._memory.session_count(tenant_id=tenant_id)

    def snapshot(self, tenant_id: str | None = None):
        return self._memory.snapshot(tenant_id=tenant_id)


def test_memory_api_store_search_and_consolidate() -> None:
    client = TestClient(app, headers={"x-api-key": "bootstrap"})

    stored = client.post(
        "/api/v1/memory",
        json={
            "content": "memory api stores searchable workflow context",
            "layer": 3,
            "importance": 0.8,
            "tags": ["workflow"],
        },
    )
    search = client.post(
        "/api/v1/memory/search",
        json={"query": "workflow context", "layers": [3], "include_scores": True},
    )
    consolidated = client.post(
        "/api/v1/memory/consolidate",
        json={"source_layers": [3], "target_layer": 2, "max_items": 5},
    )

    assert stored.status_code == 200
    assert stored.json()["id"]
    assert search.status_code == 200
    assert search.json()["items"][0]["content"] == "memory api stores searchable workflow context"
    assert search.json()["hits"][0]["score"] > 0
    assert consolidated.status_code == 200
    assert consolidated.json()["source_count"] >= 1
    assert consolidated.json()["target_memory_id"]

    count = client.get("/api/v1/memory/count")
    assert count.status_code == 200
    assert count.json()["count"] >= 1
    assert isinstance(count.json()["layers"], list)


def test_authenticated_viewer_can_search_memory_but_not_write() -> None:
    client = TestClient(app, headers={"x-api-key": "bootstrap"})
    created = client.post(
        "/api/v1/security/api-keys",
        json={"name": "memory-viewer", "role": "viewer", "user_id": "viewer-memory"},
    ).json()

    search = client.post(
        "/api/v1/memory/search",
        headers={"x-api-key": created["key"]},
        json={"query": "anything"},
    )
    write = client.post(
        "/api/v1/memory",
        headers={"x-api-key": created["key"]},
        json={"content": "blocked write"},
    )

    assert search.status_code == 200
    assert write.status_code == 403
    assert write.json()["code"] == "authorization_failed"


def test_memory_collection_routes_are_tenant_scoped() -> None:
    memory = MemorySystem()
    tenant_a = _tenant_principal("tenant-a")
    tenant_b = _tenant_principal("tenant-b")
    context_a = RunContext(
        tenant_id=tenant_a.tenant_id,
        user_id=tenant_a.user_id,
        agent_id=tenant_a.agent_id,
        request_id=tenant_a.request_id,
        trace_id=tenant_a.trace_id,
        permission_scope=tenant_a.permission_scope,
    )
    context_b = RunContext(
        tenant_id=tenant_b.tenant_id,
        user_id=tenant_b.user_id,
        agent_id=tenant_b.agent_id,
        request_id=tenant_b.request_id,
        trace_id=tenant_b.trace_id,
        permission_scope=tenant_b.permission_scope,
    )

    async def _seed() -> str:
        await memory.store(
            context_a,
            "tenant a visible note",
            layer=3,
            session_id="tenant-a-session",
        )
        await memory.store(
            context_b,
            "tenant b hidden orchid",
            layer=3,
            session_id="tenant-b-session",
        )
        return "tenant-b-session"

    import asyncio

    tenant_b_session_id = asyncio.run(_seed())
    previous_overrides = dict(app.dependency_overrides)
    app.dependency_overrides[get_current_principal] = _principal_from_header
    app.dependency_overrides[get_memory] = lambda: _FallbackSearchMemory(memory)
    try:
        client = TestClient(app, headers={"x-api-key": "bootstrap", "x-test-tenant": "tenant-a"})

        layer_detail = client.get("/api/v1/memory/layers/3")
        assert layer_detail.status_code == 200
        layer_body = layer_detail.json()
        assert layer_body["count"] == 1
        assert [item["tenant_id"] for item in layer_body["items"]] == ["tenant-a"]
        assert "tenant b hidden orchid" not in str(layer_body)

        count = client.get("/api/v1/memory/count")
        assert count.status_code == 200
        assert count.json()["count"] == 1
        assert count.json()["session_count"] == 1

        fallback_search = client.post(
            "/api/v1/memory/search",
            json={"query": "orchid", "layers": [3], "top_k": 10},
        )
        assert fallback_search.status_code == 200
        assert fallback_search.json()["items"] == []
        visible_search = client.post(
            "/api/v1/memory/search",
            json={"query": "visible", "layers": [3], "top_k": 10},
        )
        assert visible_search.status_code == 200
        visible_body = visible_search.json()
        assert [item["tenant_id"] for item in visible_body["items"]] == ["tenant-a"]
        assert "tenant b hidden orchid" not in str(visible_body)

        cross_session = client.get(f"/api/v1/memory/sessions/{tenant_b_session_id}")
        assert cross_session.status_code == 404
    finally:
        app.dependency_overrides.clear()
        app.dependency_overrides.update(previous_overrides)
