from fastapi.testclient import TestClient

from backend.app.main import app


def test_memory_item_detail_and_correlation_views() -> None:
    client = TestClient(app, headers={"x-api-key": "bootstrap"})
    stored = client.post(
        "/api/v1/memory",
        json={
            "content": "memory detail test",
            "layer": 3,
            "importance": 0.8,
            "tags": ["detail"],
            "metadata": {"source": "test"},
        },
    ).json()

    memory_id = stored["id"]
    detail = client.get(f"/api/v1/memory/{memory_id}")
    correlation = client.get(f"/api/v1/memory/{memory_id}/correlation")

    assert detail.status_code == 200
    assert correlation.status_code == 200
    assert detail.json()["id"] == memory_id
    assert correlation.json()["memory_id"] == memory_id
    assert correlation.json()["snapshot"]["memory_id"] == memory_id
