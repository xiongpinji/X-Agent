from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest
from fastapi.testclient import TestClient

import backend.app.main as main_module
from backend.app.core.config.database import DatabaseConfig
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
    assert hasattr(vector_client, "is_reachable")
    assert hasattr(langfuse_client, "has_real_client")


@pytest.mark.parametrize(
    ("database_url", "backend"),
    [
        ("postgresql+asyncpg://user:password@database.internal/xagent", "postgresql"),
        ("sqlite+aiosqlite:///./data/xagent.db", "sqlite"),
    ],
)
def test_database_config_accepts_async_driver_urls(database_url: str, backend: str) -> None:
    config = DatabaseConfig(database_url=database_url)

    assert config.is_postgresql() is (backend == "postgresql")
    assert config.is_sqlite() is (backend == "sqlite")


def test_ready_logs_only_the_component_error_type(monkeypatch, caplog) -> None:
    secret = "private-database-password"

    def fail_audit_store():
        raise RuntimeError(f"postgresql+asyncpg://user:{secret}@database.internal/xagent")

    monkeypatch.setattr(main_module, "get_audit_store", fail_audit_store)

    with caplog.at_level("WARNING"):
        response = TestClient(app).get("/ready")

    assert response.status_code == 503
    assert response.json()["components"]["audit"] == "error"
    assert "RuntimeError" in caplog.text
    assert secret not in caplog.text


def test_ready_degrades_when_the_qdrant_probe_cannot_connect(monkeypatch) -> None:
    probe = AsyncMock(return_value=False)
    monkeypatch.setattr(vector_client, "is_reachable", probe, raising=False)

    response = TestClient(app).get("/ready")

    assert response.status_code in {200, 503}
    assert response.json()["integrations"]["qdrant"] is False
    assert response.json()["components"]["qdrant"] == "degraded"
    probe.assert_awaited_once_with()


@pytest.mark.asyncio
async def test_qdrant_probe_uses_a_bounded_authenticated_http_request(monkeypatch) -> None:
    from backend.app.services.memory import qdrant_client as client_module

    captured: dict[str, object] = {}

    class FakeAsyncClient:
        def __init__(self, *, timeout: float, trust_env: bool) -> None:
            captured["timeout"] = timeout
            captured["trust_env"] = trust_env

        async def __aenter__(self):
            return self

        async def __aexit__(self, *_args: object) -> None:
            return None

        async def get(self, url: str, *, headers: dict[str, str]):
            captured["url"] = url
            captured["headers"] = headers
            return SimpleNamespace(status_code=200)

    monkeypatch.setattr(
        client_module,
        "httpx",
        SimpleNamespace(AsyncClient=FakeAsyncClient),
        raising=False,
    )
    client = client_module.QdrantVectorClient(
        url="https://qdrant.internal/",
        api_key="probe-key",
    )

    assert await client.is_reachable() is True
    assert captured == {
        "timeout": 1.5,
        "trust_env": False,
        "url": "https://qdrant.internal/collections",
        "headers": {"api-key": "probe-key"},
    }
