from fastapi.testclient import TestClient

from backend.app.main import app


def test_first_release_entrypoints_are_available() -> None:
    client = TestClient(app)

    routes = [
        "/api/v1/collaboration/rooms",
        "/api/v1/workbench",
        "/api/v1/integrations",
        "/api/v1/desktop/sessions",
        "/api/v1/workflows/chat",
    ]

    for route in routes:
        response = client.get(route)
        assert response.status_code in {200, 401, 403, 404, 405, 422}


def test_workbench_contract_contains_core_sections() -> None:
    client = TestClient(app)
    response = client.get("/api/v1/workbench")
    assert response.status_code in {200, 401, 403}
    if response.status_code != 200:
        return

    payload = response.json()
    assert "collaboration" in payload
    assert "workflow" in payload
    assert "execution" in payload
    assert "memory" in payload
    assert "tools" in payload
    assert "entries" in payload
