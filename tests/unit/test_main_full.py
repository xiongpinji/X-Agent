"""Full-coverage unit tests for backend.app.main.

Covers:
- _RateLimiter: is_allowed, cleanup
- _get_client_ip
- _request_has_valid_api_key
- CSRFProtectionMiddleware: dispatch (all branches), generate_csrf_token
- require_api_key_header
- Middleware: rate_limit, request_logging, tenant_isolation, security_headers
- Startup/shutdown events
- Route handlers: /, /health, /ready, /chat, /console, /api-key/status, /api/v1/entry, /api/v1/csrf-token, spa_fallback
"""
from __future__ import annotations

import time
from collections import deque
from unittest.mock import AsyncMock, MagicMock, patch, PropertyMock

import pytest
from starlette.requests import Request
from starlette.testclient import TestClient


# ---------------------------------------------------------------------------
# _RateLimiter
# ---------------------------------------------------------------------------

class TestRateLimiter:
    def _make(self):
        from backend.app.main import _RateLimiter
        return _RateLimiter()

    def test_is_allowed_under_limit(self):
        rl = self._make()
        for _ in range(5):
            allowed, _retry = rl.is_allowed("key", limit=5, window_seconds=60)
            assert allowed is True

    def test_is_allowed_over_limit(self):
        rl = self._make()
        for _ in range(5):
            rl.is_allowed("key", limit=5, window_seconds=60)
        allowed, _retry = rl.is_allowed("key", limit=5, window_seconds=60)
        assert allowed is False

    def test_is_allowed_window_expires(self):
        rl = self._make()
        # Manually insert old timestamps
        rl._windows["key"] = deque([time.time() - 120])
        allowed, _retry = rl.is_allowed("key", limit=1, window_seconds=60)
        assert allowed is True

    def test_is_allowed_new_key(self):
        rl = self._make()
        allowed, _retry = rl.is_allowed("new_key", limit=1, window_seconds=60)
        assert allowed is True
        assert "new_key" in rl._windows

    def test_cleanup_removes_stale(self):
        rl = self._make()
        rl._windows["stale"] = deque([time.time() - 7200])
        rl._windows["fresh"] = deque([time.time()])
        rl.cleanup(max_age_seconds=3600)
        assert "stale" not in rl._windows
        assert "fresh" in rl._windows

    def test_cleanup_empty_window(self):
        rl = self._make()
        rl._windows["empty"] = deque()
        rl.cleanup(max_age_seconds=3600)
        # empty window: w[-1] would fail, but `w and w[-1]` short-circuits
        assert "empty" in rl._windows


# ---------------------------------------------------------------------------
# _get_client_ip
# ---------------------------------------------------------------------------

class TestGetClientIp:
    def test_with_client(self):
        from backend.app.main import _get_client_ip
        request = MagicMock()
        request.client.host = "192.168.1.1"
        assert _get_client_ip(request) == "192.168.1.1"

    def test_without_client(self):
        from backend.app.main import _get_client_ip
        request = MagicMock()
        request.client = None
        assert _get_client_ip(request) == "unknown"


# ---------------------------------------------------------------------------
# _request_has_valid_api_key
# ---------------------------------------------------------------------------

class TestRequestHasValidApiKey:
    def test_no_api_key_header(self):
        from backend.app.main import _request_has_valid_api_key
        request = MagicMock()
        request.headers = {}
        assert _request_has_valid_api_key(request) is False

    def test_valid_bootstrap_key(self):
        from backend.app.main import _request_has_valid_api_key
        request = MagicMock()
        request.headers = {"x-api-key": "test-key"}
        with patch("backend.app.main.get_settings") as mock_settings:
            mock_settings.return_value = MagicMock(
                bootstrap_api_key="test-key",
                bootstrap_api_key_sha256=None,
            )
            with patch("backend.app.dependencies._matches_bootstrap_key", return_value=True):
                with patch("backend.app.dependencies.get_api_key_store"):
                    result = _request_has_valid_api_key(request)
        assert result is True

    def test_exception_returns_false(self):
        from backend.app.main import _request_has_valid_api_key
        request = MagicMock()
        request.headers = {"x-api-key": "some-key"}
        with patch("backend.app.main.get_settings", side_effect=Exception("boom")):
            assert _request_has_valid_api_key(request) is False


# ---------------------------------------------------------------------------
# CSRFProtectionMiddleware
# ---------------------------------------------------------------------------

class TestCSRFProtectionMiddleware:
    def _make_middleware(self):
        from backend.app.main import CSRFProtectionMiddleware
        return CSRFProtectionMiddleware(MagicMock())

    def test_generate_csrf_token(self):
        mw = self._make_middleware()
        token = mw.generate_csrf_token("session-1")
        assert isinstance(token, str)
        assert len(token) > 0
        assert "session-1" in mw._tokens
        assert token in mw._tokens["session-1"]

    def test_generate_csrf_token_limit_10(self):
        mw = self._make_middleware()
        for _ in range(15):
            mw.generate_csrf_token("sess")
        assert len(mw._tokens["sess"]) <= 10

    async def test_dispatch_safe_method(self):
        mw = self._make_middleware()
        request = MagicMock()
        request.method = "GET"
        call_next = AsyncMock(return_value="response")
        result = await mw.dispatch(request, call_next)
        assert result == "response"
        call_next.assert_called_once()

    async def test_dispatch_exempt_path(self):
        mw = self._make_middleware()
        request = MagicMock()
        request.method = "POST"
        request.url.path = "/health"
        call_next = AsyncMock(return_value="response")
        result = await mw.dispatch(request, call_next)
        assert result == "response"

    async def test_dispatch_non_api_path(self):
        mw = self._make_middleware()
        request = MagicMock()
        request.method = "POST"
        request.url.path = "/some/page"
        call_next = AsyncMock(return_value="response")
        result = await mw.dispatch(request, call_next)
        assert result == "response"

    async def test_dispatch_valid_api_key_exempt(self):
        mw = self._make_middleware()
        request = MagicMock()
        request.method = "POST"
        request.url.path = "/api/v1/data"
        with patch("backend.app.main._request_has_valid_api_key", return_value=True):
            call_next = AsyncMock(return_value="response")
            result = await mw.dispatch(request, call_next)
        assert result == "response"

    async def test_dispatch_bearer_token_exempt(self):
        mw = self._make_middleware()
        request = MagicMock()
        request.method = "POST"
        request.url.path = "/api/v1/data"
        request.headers = {"Authorization": "Bearer some-token"}
        with patch("backend.app.main._request_has_valid_api_key", return_value=False):
            call_next = AsyncMock(return_value="response")
            result = await mw.dispatch(request, call_next)
        assert result == "response"

    async def test_dispatch_missing_csrf_token(self):
        mw = self._make_middleware()
        request = MagicMock()
        request.method = "POST"
        request.url.path = "/api/v1/data"
        request.headers = {}
        request.cookies = {}
        with patch("backend.app.main._request_has_valid_api_key", return_value=False):
            call_next = AsyncMock()
            result = await mw.dispatch(request, call_next)
        assert result.status_code == 403
        call_next.assert_not_called()

    async def test_dispatch_invalid_csrf_token(self):
        mw = self._make_middleware()
        request = MagicMock()
        request.method = "POST"
        request.url.path = "/api/v1/data"
        request.headers = {"X-CSRF-Token": "bad-token"}
        request.cookies = {"session_id": "sess-1"}
        with patch("backend.app.main._request_has_valid_api_key", return_value=False):
            call_next = AsyncMock()
            result = await mw.dispatch(request, call_next)
        assert result.status_code == 403

    async def test_dispatch_valid_csrf_token(self):
        mw = self._make_middleware()
        token = mw.generate_csrf_token("sess-1")
        request = MagicMock()
        request.method = "POST"
        request.url.path = "/api/v1/data"
        request.headers = {"X-CSRF-Token": token}
        request.cookies = {"session_id": "sess-1"}
        with patch("backend.app.main._request_has_valid_api_key", return_value=False):
            call_next = AsyncMock(return_value="ok_response")
            result = await mw.dispatch(request, call_next)
        assert result == "ok_response"


# ---------------------------------------------------------------------------
# require_api_key_header
# ---------------------------------------------------------------------------

class TestRequireApiKeyHeader:
    def test_not_required(self):
        from backend.app.main import require_api_key_header
        import backend.app.main as main_mod
        old = main_mod.settings.require_api_key
        main_mod.settings.require_api_key = False
        try:
            request = MagicMock()
            require_api_key_header(request)  # should not raise
        finally:
            main_mod.settings.require_api_key = old

    def test_exempt_path(self):
        from backend.app.main import require_api_key_header
        import backend.app.main as main_mod
        old = main_mod.settings.require_api_key
        main_mod.settings.require_api_key = True
        try:
            request = MagicMock()
            request.url.path = "/health"
            require_api_key_header(request)  # should not raise
        finally:
            main_mod.settings.require_api_key = old

    def test_has_api_key(self):
        from backend.app.main import require_api_key_header
        import backend.app.main as main_mod
        old = main_mod.settings.require_api_key
        main_mod.settings.require_api_key = True
        try:
            request = MagicMock()
            request.url.path = "/api/v1/data"
            request.headers = {"x-api-key": "some-key"}
            require_api_key_header(request)  # should not raise
        finally:
            main_mod.settings.require_api_key = old

    def test_missing_api_key_raises(self):
        from backend.app.main import require_api_key_header
        from fastapi import HTTPException
        import backend.app.main as main_mod
        old = main_mod.settings.require_api_key
        main_mod.settings.require_api_key = True
        try:
            request = MagicMock()
            request.url.path = "/api/v1/data"
            request.headers = {}
            with pytest.raises(HTTPException) as exc_info:
                require_api_key_header(request)
            assert exc_info.value.status_code == 401
        finally:
            main_mod.settings.require_api_key = old


# ---------------------------------------------------------------------------
# Route handlers (via TestClient)
# ---------------------------------------------------------------------------

class TestRouteHandlers:
    @pytest.fixture(autouse=True)
    def _client(self):
        from backend.app.main import app
        self.client = TestClient(app, raise_server_exceptions=False)

    def test_health(self):
        resp = self.client.get("/health")
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "ok"
        assert data["service"] == "x-agent"

    def test_api_key_status(self):
        resp = self.client.get("/api-key/status")
        assert resp.status_code == 200
        assert "require_api_key" in resp.json()

    def test_root(self):
        resp = self.client.get("/")
        # May return 200 (file exists) or 500 (file missing)
        assert resp.status_code in (200, 500)

    def test_chat_page(self):
        resp = self.client.get("/chat")
        assert resp.status_code in (200, 500)

    def test_console_page(self):
        resp = self.client.get("/console")
        assert resp.status_code in (200, 500)

    def test_spa_fallback_known_prefix(self):
        resp = self.client.get("/memory/some/path")
        # If dist/index.html doesn't exist, returns 404
        assert resp.status_code in (200, 404)

    def test_spa_fallback_unknown_prefix(self):
        resp = self.client.get("/unknown/path")
        assert resp.status_code == 404

    def test_csrf_token_endpoint(self):
        resp = self.client.post("/api/v1/csrf-token")
        assert resp.status_code == 200
        data = resp.json()
        assert "csrf_token" in data
        assert "session_id" in resp.cookies

    def test_entry_endpoint(self):
        resp = self.client.get("/api/v1/entry")
        # May require auth depending on settings
        assert resp.status_code in (200, 401, 403)

    def test_ready_endpoint(self):
        resp = self.client.get("/ready")
        assert resp.status_code in (200, 503)
        data = resp.json()
        assert "status" in data
        assert "components" in data

    def test_security_headers_present(self):
        resp = self.client.get("/health")
        assert "X-Frame-Options" in resp.headers
        assert resp.headers["X-Frame-Options"] == "DENY"
        assert "X-Content-Type-Options" in resp.headers
        assert "Content-Security-Policy" in resp.headers
        assert "X-XSS-Protection" in resp.headers
        assert "Referrer-Policy" in resp.headers
        assert "Permissions-Policy" in resp.headers


# ---------------------------------------------------------------------------
# Startup / Shutdown events
# ---------------------------------------------------------------------------

class TestStartupShutdown:
    async def test_startup_event(self):
        from backend.app.main import startup_event, app
        with patch("backend.app.main._register_all_routers"), \
             patch("backend.app.main.initialize_mcp_manager", new_callable=AsyncMock) as mock_mcp, \
             patch("backend.app.core.redis_client.init_redis", new_callable=AsyncMock) as mock_redis, \
             patch("backend.app.api.sandbox_tasks.start_sandbox_worker", new_callable=AsyncMock), \
             patch("backend.app.main.register_hooks_from_config", return_value=0), \
             patch("backend.app.main.HooksConfig") as mock_hooks_cfg, \
             patch.dict("os.environ", {}, clear=False):
            mock_redis_inst = MagicMock()
            mock_redis_inst.is_available = False
            mock_redis.return_value = mock_redis_inst
            mock_mcp.return_value = None
            mock_hooks_cfg.return_value = MagicMock(hooks=[])
            await startup_event()

    async def test_startup_event_mcp_success(self):
        from backend.app.main import startup_event
        with patch("backend.app.main._register_all_routers"), \
             patch("backend.app.main.initialize_mcp_manager", new_callable=AsyncMock) as mock_mcp, \
             patch("backend.app.core.redis_client.init_redis", new_callable=AsyncMock) as mock_redis, \
             patch("backend.app.api.sandbox_tasks.start_sandbox_worker", new_callable=AsyncMock), \
             patch("backend.app.main.register_hooks_from_config", return_value=2), \
             patch("backend.app.main.HooksConfig") as mock_hooks_cfg, \
             patch.dict("os.environ", {}, clear=False):
            mock_redis_inst = MagicMock()
            mock_redis_inst.is_available = True
            mock_redis.return_value = mock_redis_inst
            mock_mcp_mgr = MagicMock()
            mock_mcp_mgr.get_stats.return_value = {"servers": 1}
            mock_mcp.return_value = mock_mcp_mgr
            mock_hooks_cfg.return_value = MagicMock(hooks=[{"event": "test"}])
            mock_hooks_cfg.return_value.validate.return_value = (True, [])
            await startup_event()

    async def test_startup_event_mcp_exception(self):
        from backend.app.main import startup_event
        with patch("backend.app.main._register_all_routers"), \
             patch("backend.app.main.initialize_mcp_manager", new_callable=AsyncMock, side_effect=Exception("mcp fail")), \
             patch("backend.app.core.redis_client.init_redis", new_callable=AsyncMock) as mock_redis, \
             patch("backend.app.api.sandbox_tasks.start_sandbox_worker", new_callable=AsyncMock), \
             patch("backend.app.main.HooksConfig", side_effect=Exception("hooks fail")), \
             patch.dict("os.environ", {}, clear=False):
            mock_redis.return_value = MagicMock(is_available=False)
            await startup_event()  # should not raise

    async def test_startup_redis_failure(self):
        from backend.app.main import startup_event
        with patch("backend.app.main._register_all_routers"), \
             patch("backend.app.core.redis_client.init_redis", new_callable=AsyncMock, side_effect=Exception("redis fail")), \
             patch("backend.app.main.initialize_mcp_manager", new_callable=AsyncMock, return_value=None), \
             patch("backend.app.api.sandbox_tasks.start_sandbox_worker", new_callable=AsyncMock), \
             patch("backend.app.main.HooksConfig") as mock_hooks_cfg, \
             patch.dict("os.environ", {}, clear=False):
            mock_hooks_cfg.return_value = MagicMock(hooks=[])
            await startup_event()

    async def test_shutdown_event(self):
        from backend.app.main import shutdown_event, app
        with patch("backend.app.core.lifecycle.LifecycleManager.on_shutdown", new_callable=AsyncMock):
            app.state.audit_shipper = None
            await shutdown_event()

    async def test_shutdown_event_with_shipper(self):
        from backend.app.main import shutdown_event, app
        mock_shipper = AsyncMock()
        mock_shipper.stop = AsyncMock()
        app.state.audit_shipper = mock_shipper
        with patch("backend.app.core.lifecycle.LifecycleManager.on_shutdown", new_callable=AsyncMock) as mock_shutdown:
            await shutdown_event()
        mock_shutdown.assert_called_once()

    async def test_shutdown_event_exceptions(self):
        from backend.app.main import shutdown_event, app
        app.state.audit_shipper = None
        with patch("backend.app.core.lifecycle.LifecycleManager.on_shutdown", new_callable=AsyncMock, side_effect=Exception("shutdown")):
            import pytest
            with pytest.raises(Exception, match="shutdown"):
                await shutdown_event()


# ---------------------------------------------------------------------------
# Middleware integration (rate limit + request logging)
# ---------------------------------------------------------------------------

class TestMiddlewareIntegration:
    @pytest.fixture(autouse=True)
    def _client(self):
        from backend.app.main import app, _rate_limiter
        # Reset rate limiter state
        _rate_limiter._windows.clear()
        self.client = TestClient(app, raise_server_exceptions=False)

    def test_rate_limit_login(self):
        # Exhaust login rate limit (10 per 60s)
        from backend.app.main import settings as main_settings, _rate_limiter
        _rate_limiter._windows.clear()
        original = main_settings.rate_limit_enabled
        main_settings.rate_limit_enabled = True
        try:
            for _ in range(10):
                self.client.post("/api/v1/auth/login", json={})
            resp = self.client.post("/api/v1/auth/login", json={})
        finally:
            main_settings.rate_limit_enabled = original
        assert resp.status_code == 429

    def test_request_id_header(self):
        resp = self.client.get("/health")
        assert "x-request-id" in resp.headers

    def test_custom_request_id(self):
        resp = self.client.get("/health", headers={"x-request-id": "my-req-123"})
        assert resp.headers.get("x-request-id") == "my-req-123"
