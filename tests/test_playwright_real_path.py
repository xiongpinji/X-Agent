import os

import pytest

from backend.app.services.browser.playwright_client import browser_client

# 与 tests/test_browser_service.py 相同的 opt-in 真实浏览器门控：
# sync_playwright 驱动事件循环在测试结束时不回收，会污染后续 asyncio 用例；
# 且本用例断言真实 goto 成功，依赖外网。默认关闭，需要时：
# XAGENT_REAL_BROWSER=1 pytest tests/test_playwright_real_path.py
_REAL_BROWSER = os.environ.get("XAGENT_REAL_BROWSER") == "1"

pytestmark = pytest.mark.skipif(
    not (_REAL_BROWSER and browser_client.has_real_client),
    reason=(
        "requires opt-in real browser (XAGENT_REAL_BROWSER=1) with network "
        "access; fallback/contract path is covered by other suites."
    ),
)


def test_browser_service_creates_recoverable_session() -> None:
    session = browser_client.create_session(trace_id="trace-real", run_id="run-real", tenant_id="tenant-real")
    try:
        assert session.trace_id == "trace-real"
        assert session.run_id == "run-real"
        assert session.tenant_id == "tenant-real"
        assert browser_client.get_session(session.session_id) is session

        goto = browser_client.goto(session.session_id, "https://example.com")
        assert goto.action == "goto"
        assert goto.ok is True
    finally:
        closed = browser_client.close_session(session.session_id)
    assert closed is True
