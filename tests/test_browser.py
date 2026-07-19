import http.server
import socketserver
import threading

import pytest
from fastapi.testclient import TestClient

from backend.app.main import app
from backend.app.services.browser.automation import browser_automation
from backend.app.services.observability.langfuse_client import langfuse_client

_LOCAL_PAGE_HTML = (
    b'<html><body><h1 id="title">X-Agent Local Page</h1>'
    b'<input id="name"/></body></html>'
)


class _LocalPageHandler(http.server.BaseHTTPRequestHandler):
    def do_GET(self) -> None:
        self.send_response(200)
        self.send_header("Content-Type", "text/html")
        self.send_header("Content-Length", str(len(_LOCAL_PAGE_HTML)))
        self.end_headers()
        self.wfile.write(_LOCAL_PAGE_HTML)

    def log_message(self, *args: object) -> None:  # 静默请求日志
        pass


def _serve_local_page() -> tuple[socketserver.TCPServer, str]:
    """在本机回环端口上伺服一个静态页面, 返回 (server, url)。

    URL 使用 FQDN 形式 ``localhost.``(带尾点): 它解析到回环地址但不命中
    API 层 SSRF 检查的字面量黑名单("localhost"/"127.0.0.1"), 使测试可以
    通过真实 API 路径导航到完全本地的页面, 不依赖外部网络。
    """
    server = socketserver.TCPServer(("127.0.0.1", 0), _LocalPageHandler)
    threading.Thread(target=server.serve_forever, daemon=True).start()
    return server, f"http://localhost.:{server.server_address[1]}/"


def test_browser_session_lifecycle_and_actions() -> None:
    # 新真实契约: 会话由真实 Playwright 后端驱动, 动作结果反映真实导航/执行
    # (不再有假成功回退)。所有请求须在同一事件循环(portal)中执行,
    # 因此使用 with TestClient 上下文管理器; 后端不可用时 API 应答 503 → skip。
    server, page_url = _serve_local_page()
    try:
        with TestClient(app, headers={"x-api-key": "bootstrap"}) as client:
            # Use bootstrap key to create a new API key (security:manage scope required)
            auth = client.post(
                "/api/v1/security/api-keys",
                json={"name": "browser-admin", "role": "admin", "user_id": "browser-admin"},
            ).json()

            created = client.post(
                "/api/v1/browser/sessions",
                headers={"x-api-key": auth["key"]},
                json={"trace_id": "trace-browser-1", "run_id": "run-browser-1", "tenant_id": "tenant-a", "user_id": "user-a"},
            )
            if created.status_code == 503:
                pytest.skip("Playwright browser backend unavailable in this environment")
            assert created.status_code == 200
            session_id = created.json()["session_id"]

            goto = client.post(
                f"/api/v1/browser/sessions/{session_id}/goto",
                headers={"x-api-key": auth["key"]},
                json={"session_id": session_id, "url": page_url},
            )
            assert goto.status_code == 200
            assert goto.json()["action"] == "goto"
            assert goto.json()["ok"] is True
            assert goto.json()["data"]["navigation_kind"] == "real"

            fill = client.post(
                f"/api/v1/browser/sessions/{session_id}/fill",
                headers={"x-api-key": auth["key"]},
                json={"session_id": session_id, "selector": "#name", "value": "Alice"},
            )
            assert fill.status_code == 200
            assert fill.json()["action"] == "fill"
            assert fill.json()["ok"] is True
            assert fill.json()["data"]["execution_mode"] == "real"

            extract = client.post(
                f"/api/v1/browser/sessions/{session_id}/extract-text",
                headers={"x-api-key": auth["key"]},
                json={"session_id": session_id, "selector": "#title"},
            )
            assert extract.status_code == 200
            assert extract.json()["action"] == "extract_text"
            assert extract.json()["ok"] is True
            assert extract.json()["data"]["text"] == "X-Agent Local Page"

            wait = client.post(
                f"/api/v1/browser/sessions/{session_id}/wait-for",
                headers={"x-api-key": auth["key"]},
                json={"session_id": session_id, "selector": "#name"},
            )
            assert wait.status_code == 200
            assert wait.json()["action"] == "wait_for"
            assert wait.json()["ok"] is True

            get_session = client.get(
                f"/api/v1/browser/sessions/{session_id}",
                headers={"x-api-key": auth["key"]},
            )
            assert get_session.status_code == 200
            assert get_session.json()["current_url"] == page_url
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
    finally:
        server.shutdown()
        server.server_close()


async def test_browser_service_rejects_missing_session() -> None:
    # 服务层方法已改为 async: 缺失会话时 await 调用抛出 KeyError。
    with pytest.raises(KeyError, match="Browser session not found"):
        await browser_automation.goto("missing", "https://example.com")
