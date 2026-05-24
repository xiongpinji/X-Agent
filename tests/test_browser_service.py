from backend.app.services.browser.playwright_client import browser_client


def test_browser_session_can_record_actions() -> None:
    session = browser_client.create_session(trace_id="trace-1", run_id="run-1")

    goto = browser_client.goto(session.session_id, "https://example.com")
    fill = browser_client.fill(session.session_id, "#name", "X-Agent")
    click = browser_client.click(session.session_id, "#submit")

    assert goto.ok is True
    assert fill.ok is True
    assert click.ok is True
    assert browser_client.get_session(session.session_id) is not None
    assert browser_client.get_session(session.session_id).current_url == "https://example.com"
    assert len(browser_client.get_session(session.session_id).actions) == 3


def test_browser_session_close_prevents_further_actions() -> None:
    session = browser_client.create_session()

    closed = browser_client.close_session(session.session_id)

    assert closed is True
    assert browser_client.get_session(session.session_id).active is False
