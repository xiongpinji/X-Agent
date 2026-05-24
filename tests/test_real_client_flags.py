from backend.app.services.browser.playwright_client import browser_client
from backend.app.services.memory.qdrant_client import vector_client
from backend.app.services.observability.langfuse_client import langfuse_client


def test_real_client_flags_exist_and_are_boolean_like() -> None:
    assert isinstance(browser_client.has_real_client, bool)
    assert isinstance(vector_client.has_real_client, bool)
    assert isinstance(langfuse_client.has_real_client, bool)
