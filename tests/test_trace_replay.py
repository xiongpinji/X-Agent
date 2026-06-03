from fastapi.testclient import TestClient

from backend.app.main import app


def test_trace_replay_and_debug_views() -> None:
    client = TestClient(app, headers={"x-api-key": "bootstrap"})
    run = client.post(
        "/api/v1/agents/run",
        json={"task": "trace replay test", "context": {}},
    ).json()

    replay = client.get(f"/api/v1/traces/{run['trace_id']}/replay")
    debug = client.get(f"/api/v1/traces/{run['trace_id']}/debug")

    assert replay.status_code == 200
    assert debug.status_code == 200
    replay_json = replay.json()
    debug_json = debug.json()

    # Both endpoints return a build_linked_summary envelope. The trace_id is
    # available as resource_id at the top level; related_resources and debug
    # info are nested inside the envelope structure.
    assert replay_json["resource_id"] == run["trace_id"]
    assert debug_json["resource_id"] == run["trace_id"]
    assert replay_json["resource_type"] == "trace_replay"
    assert debug_json["resource_type"] == "trace_debug"
    # The agent run may or may not invoke tools depending on the task; verify
    # the shape (list of dicts) rather than asserting emptiness.
    assert isinstance(replay_json["snapshot"]["related_resources"]["tool_executions"], list)
    assert "failure_points" in debug_json["linked_summaries"]["primary"]["debug"]
