import os

import pytest

from backend.app.services.browser.playwright_client import browser_client

# 真实浏览器用例默认关闭（opt-in）。本机会话里 sync_playwright 一旦 start，
# 其驱动事件循环在测试结束时不会被回收（backend 侧未暴露 stop），后续
# pytest-asyncio 用例会大面积报
# "Cannot run the event loop while another loop is running"。
# 需要真实跑通时：XAGENT_REAL_BROWSER=1 pytest tests/test_browser_service.py
_REAL_BROWSER = os.environ.get("XAGENT_REAL_BROWSER") == "1"


@pytest.mark.skipif(
    not (_REAL_BROWSER and browser_client.has_real_client),
    reason=(
        "requires opt-in real browser (XAGENT_REAL_BROWSER=1) and a controlled "
        "page containing #name/#submit; example.com has neither."
    ),
)
def test_browser_session_can_record_actions() -> None:
    session = browser_client.create_session(trace_id="trace-1", run_id="run-1")
    try:
        goto = browser_client.goto(session.session_id, "https://example.com")
        fill = browser_client.fill(session.session_id, "#name", "X-Agent")
        click = browser_client.click(session.session_id, "#submit")

        assert goto.ok is True
        assert fill.ok is True
        assert click.ok is True
        assert browser_client.get_session(session.session_id) is not None
        assert browser_client.get_session(session.session_id).current_url == "https://example.com"
        assert len(browser_client.get_session(session.session_id).actions) == 3
    finally:
        browser_client.close_session(session.session_id)


def test_browser_session_close_prevents_further_actions(monkeypatch) -> None:
    # 不启动真实浏览器：将 sync_playwright 置 None，走非托管会话路径，
    # 避免 sync_playwright 驱动的事件循环泄漏污染后续 asyncio 用例。
    monkeypatch.setattr(
        "backend.app.services.browser.playwright_client.sync_playwright", None
    )
    session = browser_client.create_session()

    closed = browser_client.close_session(session.session_id)

    assert closed is True
    assert browser_client.get_session(session.session_id).active is False
