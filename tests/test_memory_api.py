from fastapi.testclient import TestClient

from backend.app.main import app


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
