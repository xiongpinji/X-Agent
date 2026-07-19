from backend.app.services.browser.playwright_client import browser_client


def test_browser_service_creates_recoverable_session() -> None:
    session = browser_client.create_session(trace_id="trace-real", run_id="run-real", tenant_id="tenant-real")

    assert session.trace_id == "trace-real"
    assert session.run_id == "run-real"
    assert session.tenant_id == "tenant-real"
    assert browser_client.get_session(session.session_id) is session

    goto = browser_client.goto(session.session_id, "https://example.com")
    assert goto.action == "goto"
    assert goto.ok is True

    closed = browser_client.close_session(session.session_id)
    assert closed is True
