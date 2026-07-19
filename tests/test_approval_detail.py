from fastapi.testclient import TestClient

from backend.app.main import app


def test_approval_detail_and_correlation_views() -> None:
    client = TestClient(app, headers={"x-api-key": "bootstrap"})
    workflow = client.post(
        "/api/v1/workflows",
        json={
            "name": "Approval flow",
            "nodes": [
                {"id": "input_1", "type": "input", "config": {"key": "name"}},
                {
                    "id": "approval_1",
                    "type": "approval",
                    "config": {"reason": "Need approval", "action": "workflow.node.approve"},
                },
                {"id": "output_1", "type": "output", "config": {"from": "approval_1"}},
            ],
            "edges": [
                {"source": "input_1", "target": "approval_1"},
                {"source": "approval_1", "target": "output_1"},
            ],
        },
    ).json()
    run = client.post(
        f"/api/v1/workflows/{workflow['id']}/run",
        json={"inputs": {"name": "approval"}},
    ).json()

    approval_id = run["outputs"]["approval_id"] if "outputs" in run and run["outputs"] else run.get("pending_approval_id")
    approval_list = client.get("/api/v1/approvals")
    correlation = client.get(f"/api/v1/approvals/{approval_id}/correlation")
    detail = client.get(f"/api/v1/approvals/{approval_id}")

    assert approval_list.status_code == 200
    assert detail.status_code == 200
    assert correlation.status_code == 200
    assert detail.json()["id"] == approval_id
    assert correlation.json()["approval_id"] == approval_id
    assert correlation.json()["snapshot"]["approval_id"] == approval_id
