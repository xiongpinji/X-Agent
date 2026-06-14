from __future__ import annotations

import os
from unittest.mock import patch

import pytest
from typer.testing import CliRunner

from backend.app.core.database import normalize_async_database_url
from backend.app.settings import DEFAULT_LITE_DATABASE_URL, Settings, get_settings
from cli.main import app


@pytest.fixture(autouse=True)
def isolate_lite_mode_environment(monkeypatch):
    keys = (
        "XAGENT_MODE",
        "XAGENT_APP_MODE",
        "XAGENT_DATABASE_URL",
        "XAGENT_REDIS_URL",
        "XAGENT_QDRANT_URL",
        "XAGENT_REQUIRE_API_KEY",
    )
    original = {key: os.environ.get(key) for key in keys}
    get_settings.cache_clear()
    yield
    for key, value in original.items():
        if value is None:
            os.environ.pop(key, None)
        else:
            os.environ[key] = value
    get_settings.cache_clear()


def test_settings_lite_mode_forces_no_docker_defaults(monkeypatch) -> None:
    monkeypatch.setenv("XAGENT_MODE", "lite")
    monkeypatch.setenv("XAGENT_DATABASE_URL", "postgresql+asyncpg://user:pass@localhost/db")
    monkeypatch.setenv("XAGENT_REDIS_URL", "redis://localhost:6379/0")
    monkeypatch.setenv("XAGENT_QDRANT_URL", "http://localhost:6333")
    monkeypatch.setenv("XAGENT_REQUIRE_API_KEY", "true")

    settings = Settings()

    assert settings.mode == "lite"
    assert settings.app_mode == "development"
    assert settings.database_url == DEFAULT_LITE_DATABASE_URL
    assert settings.redis_url is None
    assert settings.qdrant_url == ""
    assert settings.require_api_key is False
    assert settings.memory_backend == "memory"


def test_sqlite_url_is_normalized_for_async_engine() -> None:
    assert normalize_async_database_url("sqlite:///./data/xagent.db") == "sqlite+aiosqlite:///./data/xagent.db"
    assert normalize_async_database_url("sqlite+aiosqlite:///./data/xagent.db") == "sqlite+aiosqlite:///./data/xagent.db"


def test_cli_start_lite_sets_runtime_env(monkeypatch) -> None:
    for key in (
        "XAGENT_MODE",
        "XAGENT_APP_MODE",
        "XAGENT_DATABASE_URL",
        "XAGENT_REDIS_URL",
        "XAGENT_QDRANT_URL",
    ):
        monkeypatch.delenv(key, raising=False)

    runner = CliRunner()
    with patch("uvicorn.run") as run:
        result = runner.invoke(app, ["start", "--mode", "lite", "--host", "127.0.0.1", "--port", "8765"])

    assert result.exit_code == 0
    assert os.environ["XAGENT_MODE"] == "lite"
    assert os.environ["XAGENT_DATABASE_URL"] == "sqlite+aiosqlite:///~/.xagent/data.db"
    assert os.environ["XAGENT_REDIS_URL"] == ""
    assert os.environ["XAGENT_QDRANT_URL"] == ""
    run.assert_called_once()
    assert run.call_args.kwargs["host"] == "127.0.0.1"
    assert run.call_args.kwargs["port"] == 8765
