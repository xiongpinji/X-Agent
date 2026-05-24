from fastapi.testclient import TestClient

from backend.app.main import app
from backend.app.services.memory.qdrant_client import vector_client
from backend.app.services.observability.langfuse_client import langfuse_client


def test_ready_reports_browser_qdrant_and_observability_components() -> None:
    client = TestClient(app)
    response = client.get("/ready")

    assert response.status_code in {200, 503}
    components = response.json()["components"]
    assert "browser" in components
    assert "qdrant" in components
    assert "observability" in components


def test_real_client_status_accessors_exist() -> None:
    assert hasattr(vector_client, "has_real_client")
    assert hasattr(langfuse_client, "has_real_client")
