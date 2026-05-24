from backend.app.settings import get_settings


def test_real_integration_settings_are_exposed() -> None:
    settings = get_settings()

    assert hasattr(settings, "qdrant_url")
    assert hasattr(settings, "qdrant_api_key")
    assert hasattr(settings, "langfuse_public_key")
    assert hasattr(settings, "langfuse_secret_key")
    assert hasattr(settings, "langfuse_host")
    assert hasattr(settings, "playwright_headless")
