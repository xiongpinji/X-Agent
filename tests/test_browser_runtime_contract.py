from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

import pytest
from fastapi.testclient import TestClient

from backend.app.api import browser as browser_api
from backend.app.api.errors import XAgentAPIError
from backend.app.core.security import Principal
from backend.app.main import app
from backend.app.services.browser import automation as automation_module
from backend.app.services.browser.automation import (
    BrowserAutomation,
    BrowserUnavailableError,
)
from backend.app.services.browser.playwright_client import (
    PlaywrightBrowserClient,
    chromium_launch_options,
)


def test_browser_readiness_rejects_a_missing_configured_executable(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv(
        "PLAYWRIGHT_CHROMIUM_EXECUTABLE_PATH",
        "/missing/xagent-chromium",
    )

    assert chromium_launch_options(headless=True) == {
        "headless": True,
        "executable_path": "/missing/xagent-chromium",
    }
    assert PlaywrightBrowserClient().has_real_client is False


def test_browser_readiness_requires_an_explicit_executable(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.delenv("PLAYWRIGHT_CHROMIUM_EXECUTABLE_PATH", raising=False)

    assert chromium_launch_options(headless=True) == {"headless": True}
    assert PlaywrightBrowserClient().has_real_client is False


def test_ready_reports_the_real_browser_runtime_as_degraded(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.delenv("PLAYWRIGHT_CHROMIUM_EXECUTABLE_PATH", raising=False)

    response = TestClient(app).get("/ready")

    assert response.status_code in {200, 503}
    assert response.json()["integrations"]["browser"] is False
    assert response.json()["components"]["browser"] == "degraded"


def test_ready_accepts_an_explicit_browser_runtime(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path,
) -> None:
    executable = tmp_path / "chromium"
    executable.write_bytes(b"runtime-probe")
    monkeypatch.setenv("PLAYWRIGHT_CHROMIUM_EXECUTABLE_PATH", str(executable))

    response = TestClient(app).get("/ready")

    assert response.status_code in {200, 503}
    assert response.json()["integrations"]["browser"] is True
    assert response.json()["components"]["browser"] == "ok"


@pytest.mark.asyncio
async def test_browser_api_sanitizes_backend_launch_failures(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    async def fail_create_session(**_kwargs: object) -> None:
        raise BrowserUnavailableError("PRIVATE_BROWSER_PATH must not leak")

    monkeypatch.setattr(browser_api.browser_automation, "create_session", fail_create_session)
    principal = Principal(
        user_id="browser-user",
        tenant_id="browser-tenant",
        role="user",
        authenticated=True,
        scopes=["tools:read"],
    )

    with pytest.raises(XAgentAPIError) as captured:
        await browser_api.create_browser_session(
            browser_api.BrowserSessionCreateRequest(tenant_id="browser-tenant"),
            principal,
        )

    assert captured.value.status_code == 503
    assert captured.value.message == "Browser automation backend unavailable."
    assert "PRIVATE_BROWSER_PATH" not in captured.value.message


@pytest.mark.asyncio
async def test_browser_automation_uses_the_configured_system_chromium(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    executable = "/usr/bin/chromium"
    monkeypatch.setenv("PLAYWRIGHT_CHROMIUM_EXECUTABLE_PATH", executable)

    browser = MagicMock()
    browser.new_page = AsyncMock(return_value=MagicMock())
    browser_type = MagicMock()
    browser_type.launch = AsyncMock(return_value=browser)
    playwright = MagicMock(chromium=browser_type)
    manager = MagicMock()
    manager.start = AsyncMock(return_value=playwright)
    monkeypatch.setattr(automation_module, "async_playwright", lambda: manager)

    automation = BrowserAutomation()
    await automation.initialize(headless=True)

    browser_type.launch.assert_awaited_once_with(
        headless=True,
        executable_path=executable,
    )
