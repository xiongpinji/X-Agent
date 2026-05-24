from fastapi.testclient import TestClient

from backend.app.main import app


def test_run_agent_streaming_returns_sse() -> None:
    client = TestClient(app, headers={"x-api-key": "bootstrap"})
    response = client.post("/api/v1/agents/run", json={"task": "hello", "stream": True})

    assert response.status_code == 200
    assert response.headers["content-type"].startswith("text/event-stream")
    assert "event: trace" in response.text
    assert "event: completed" in response.text

