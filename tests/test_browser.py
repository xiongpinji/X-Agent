from fastapi.testclient import TestClient

from backend.app.main import app
from backend.app.services.browser.automation import browser_automation
from backend.app.services.observability.langfuse_client import langfuse_client


def test_browser_session_lifecycle_and_actions() -> None:
    client = TestClient(app)
    auth = client.post(
        "/api/v1/security/api-keys",
        json={"name": "browser-admin", "role": "admin", "user_id": "browser-admin"},
    ).json()

    created = client.post(
        "/api/v1/browser/sessions",
        headers={"x-api-key": auth["key"]},
        json={"trace_id": "trace-browser-1", "run_id": "run-browser-1", "tenant_id": "tenant-a", "user_id": "user-a"},
    )
    assert created.status_code == 200
    session_id = created.json()["session_id"]

    goto = client.post(
        f"/api/v1/browser/sessions/{session_id}/goto",
        headers={"x-api-key": auth["key"]},
        json={"session_id": session_id, "url": "https://example.com"},
    )
    assert goto.status_code == 200
    assert goto.json()["action"] == "goto"
    assert goto.json()["ok"] is True

    fill = client.post(
        f"/api/v1/browser/sessions/{session_id}/fill",
        headers={"x-api-key": auth["key"]},
        json={"session_id": session_id, "selector": "#name", "value": "Alice"},
    )
    assert fill.status_code == 200
    assert fill.json()["action"] == "fill"

    extract = client.post(
        f"/api/v1/browser/sessions/{session_id}/extract-text",
        headers={"x-api-key": auth["key"]},
        json={"session_id": session_id, "selector": "body"},
    )
    assert extract.status_code == 200
    assert extract.json()["action"] == "extract_text"

    wait = client.post(
        f"/api/v1/browser/sessions/{session_id}/wait-for",
        headers={"x-api-key": auth["key"]},
        json={"session_id": session_id, "selector": "body"},
    )
    assert wait.status_code == 200
    assert wait.json()["action"] == "wait_for"

    get_session = client.get(
        f"/api/v1/browser/sessions/{session_id}",
        headers={"x-api-key": auth["key"]},
    )
    assert get_session.status_code == 200
    assert get_session.json()["current_url"] == "https://example.com"
    assert len(get_session.json()["actions"]) >= 4

    close = client.post(
        f"/api/v1/browser/sessions/{session_id}/close",
        headers={"x-api-key": auth["key"]},
    )
    assert close.status_code == 200
    assert close.json()["closed"] is True

    assert any(event.type == "browser.session_created" for event in langfuse_client.events())
    assert any(event.type == "browser.goto" for event in langfuse_client.events())
    assert any(event.type == "browser.session_closed" for event in langfuse_client.events())


def test_browser_service_rejects_missing_session() -> None:
    try:
        browser_automation.goto("missing", "https://example.com")
    except KeyError as exc:
        assert "Browser session not found" in str(exc)
    else:
        raise AssertionError("Expected KeyError for missing browser session")
