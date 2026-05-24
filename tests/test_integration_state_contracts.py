from backend.app.services.browser.playwright_client import browser_client
from backend.app.services.memory.qdrant_client import vector_client
from backend.app.services.observability.langfuse_client import langfuse_client


def test_integration_clients_expose_real_state_contracts() -> None:
    assert hasattr(browser_client, "has_real_client")
    assert hasattr(vector_client, "has_real_client")
    assert hasattr(langfuse_client, "has_real_client")
    assert isinstance(browser_client.has_real_client, bool)
    assert isinstance(vector_client.has_real_client, bool)
    assert isinstance(langfuse_client.has_real_client, bool)
