from fastapi.testclient import TestClient

from backend.app.main import app


def test_tool_list_and_detail_correlation_views() -> None:
    client = TestClient(app, headers={"x-api-key": "bootstrap"})
    tools = client.get("/api/v1/tools")

    assert tools.status_code == 200
    assert tools.json()
