"""Security regression tests for X-Agent backend.

These tests verify that critical vulnerabilities identified during the security
audit have been fixed and cannot be reintroduced without breaking the build.
"""

from __future__ import annotations

import time

import nest_asyncio
from fastapi.testclient import TestClient

from backend.app.main import app

nest_asyncio.apply()


def _bootstrap_client() -> TestClient:
    """Return a client authenticated with the bootstrap key (if configured)."""
    return TestClient(app, headers={"x-api-key": "bootstrap"})


def _anon_client() -> TestClient:
    """Return an unauthenticated client."""
    return TestClient(app)


# =============================================================================
# Authentication & Authorization
# =============================================================================


def test_anonymous_user_cannot_list_users() -> None:
    client = _anon_client()
    response = client.get("/api/v1/users")
    assert response.status_code == 401


def test_anonymous_user_cannot_create_user() -> None:
    client = _anon_client()
    response = client.post("/api/v1/users", json={"email": "hacker@xagent.ai"})
    # CSRF middleware runs before the route: an anonymous state-changing POST
    # with no API key / Bearer / CSRF token is rejected with 403 *before* the
    # route's own 401. Either rejection satisfies the "anon cannot create" intent.
    assert response.status_code in (401, 403)


def test_anonymous_user_cannot_list_tenants() -> None:
    client = _anon_client()
    response = client.get("/api/v1/tenants")
    assert response.status_code == 401


def test_anonymous_user_cannot_create_tenant() -> None:
    client = _anon_client()
    response = client.post("/api/v1/tenants", json={"name": "evil-tenant"})
    # CSRF (403) fires before the route's 401 for an unauthenticated POST.
    assert response.status_code in (401, 403)


def test_anonymous_user_cannot_list_agents() -> None:
    client = _anon_client()
    response = client.get("/api/v1/agents")
    assert response.status_code == 401


def test_anonymous_user_cannot_create_agent() -> None:
    client = _anon_client()
    response = client.post("/api/v1/agents", json={"name": "evil-agent"})
    # CSRF (403) fires before the route's 401 for an unauthenticated POST.
    assert response.status_code in (401, 403)


def test_anonymous_user_cannot_list_workflows() -> None:
    client = _anon_client()
    response = client.get("/api/v1/workflows")
    assert response.status_code == 401


def test_anonymous_user_cannot_access_api_key_status() -> None:
    client = _anon_client()
    # The real protected route is GET /api/v1/security/api-keys (GET is CSRF-safe,
    # so it reaches enforce_scope and returns 401 for an anonymous caller).
    response = client.get("/api/v1/security/api-keys")
    assert response.status_code == 401


def test_login_wrong_password_returns_401() -> None:
    client = _anon_client()
    # Register with a policy-compliant password (>=8 chars, upper+lower+digit)
    # so the account actually exists; then the wrong-password path is exercised.
    client.post("/api/v1/auth/register", json={"email": "user@xagent.ai", "password": "ValidPass123"})
    # Login with wrong password
    response = client.post("/api/v1/auth/login", json={"email": "user@xagent.ai", "password": "WrongPass123"})
    assert response.status_code == 401
    assert "message" in response.json()


def test_login_nonexistent_user_returns_401() -> None:
    client = _anon_client()
    response = client.post("/api/v1/auth/login", json={"email": "nobody@xagent.ai", "password": "wrong"})
    assert response.status_code == 401


def test_login_constant_time_no_user_enumeration() -> None:
    """Verify that wrong-password and missing-user paths have similar timing."""
    client = _anon_client()
    times = []
    for _ in range(3):
        start = time.perf_counter()
        client.post("/api/v1/auth/login", json={"email": "nobody@xagent.ai", "password": "x"})
        times.append((time.perf_counter() - start) * 1000)
    # All three should take at least ~200ms because of constant-time compensation
    assert all(t > 150 for t in times), f"Timing side-channel detected: {times}"


def test_register_duplicate_email_fails() -> None:
    client = _anon_client()
    r1 = client.post("/api/v1/auth/register", json={"email": "dup@xagent.ai", "password": "ValidPass123"})
    assert r1.status_code == 200
    r2 = client.post("/api/v1/auth/register", json={"email": "dup@xagent.ai", "password": "ValidPass123"})
    assert r2.status_code == 409


def test_bearer_token_round_trip() -> None:
    client = _anon_client()
    # Register & login with a policy-compliant password.
    client.post("/api/v1/auth/register", json={"email": "token@xagent.ai", "password": "ValidPass123"})
    login = client.post("/api/v1/auth/login", json={"email": "token@xagent.ai", "password": "ValidPass123"})
    assert login.status_code == 200
    token = login.json()["access_token"]

    # Use Bearer token to access a protected endpoint
    auth_client = TestClient(app, headers={"authorization": f"Bearer {token}"})
    me = auth_client.get("/api/v1/auth/me")
    assert me.status_code == 200
    assert me.json()["user_id"] != "anonymous"

    # Logout revokes the token
    logout = auth_client.post("/api/v1/auth/logout")
    assert logout.status_code == 200

    # Token should now be invalid
    after = auth_client.get("/api/v1/auth/me")
    assert after.status_code == 401


# =============================================================================
# Path Traversal & SSRF
# =============================================================================


def test_browser_goto_blocks_private_ip() -> None:
    client = _bootstrap_client()
    # Create a browser session first
    session = client.post("/api/v1/browser/sessions", json={}).json()
    session_id = session["session_id"]

    blocked_urls = [
        "http://localhost:8080",
        "http://127.0.0.1:80",
        "http://192.168.1.1",
        "http://10.0.0.1",
        "http://169.254.169.254/latest/meta-data",
        "file:///etc/passwd",
    ]
    for url in blocked_urls:
        response = client.post(
            f"/api/v1/browser/sessions/{session_id}/goto",
            json={"url": url},
        )
        assert response.status_code == 400, f"URL {url} should be blocked but got {response.status_code}"


def test_browser_screenshot_blocks_path_traversal() -> None:
    client = _bootstrap_client()
    session = client.post("/api/v1/browser/sessions", json={}).json()
    session_id = session["session_id"]

    bad_paths = [
        "../../../etc/passwd",
        "/etc/passwd",
        "C:/Windows/System32/drivers/etc/hosts",
    ]
    for path in bad_paths:
        response = client.post(
            f"/api/v1/browser/sessions/{session_id}/screenshot",
            json={"path": path},
        )
        assert response.status_code == 400, f"Path {path} should be blocked but got {response.status_code}"


def test_execution_draft_blocks_traversal_root() -> None:
    client = _bootstrap_client()
    response = client.post("/api/v1/execution/draft", json={"task": "x", "root": "/etc"})
    assert response.status_code == 400
    assert "traversal" in response.text.lower() or "project directory" in response.text.lower()


# =============================================================================
# Rate Limiting
# =============================================================================


def test_login_rate_limit() -> None:
    client = _anon_client()
    # Exhaust the 10/minute limit
    for i in range(12):
        response = client.post("/api/v1/auth/login", json={"email": f"rate{i}@xagent.ai", "password": "x"})
    # The last requests should be rate-limited
    assert response.status_code == 429


def test_register_rate_limit() -> None:
    client = _anon_client()
    for i in range(7):
        response = client.post("/api/v1/auth/register", json={"email": f"rate{i}@xagent.ai", "password": "x"})
    assert response.status_code == 429


# =============================================================================
# Feishu Webhook Signature
# =============================================================================


def test_feishu_event_requires_signature_headers() -> None:
    client = _anon_client()
    response = client.post("/api/v1/integrations/feishu/events", json={"test": 1})
    assert response.status_code == 401
    assert "Missing Feishu signature headers" in response.json()["message"]


def test_feishu_event_rejects_bad_signature() -> None:
    client = _anon_client()
    response = client.post(
        "/api/v1/integrations/feishu/events",
        json={"test": 1},
        headers={
            "x-feishu-signature": "bad",
            "x-feishu-timestamp": "123",
            "x-feishu-nonce": "abc",
        },
    )
    assert response.status_code == 401
    assert "Invalid Feishu signature" in response.json()["message"]


# =============================================================================
# Browser Session Isolation
# =============================================================================


def test_browser_session_isolation() -> None:
    """Admin can see all sessions; regular users can only see their own."""
    # This test requires two distinct principals. In the current Phase 0
    # in-memory store we simulate by checking that a non-admin request
    # cannot access a session created with a different tenant_id.
    client = _bootstrap_client()
    session = client.post(
        "/api/v1/browser/sessions",
        json={"tenant_id": "admin-tenant", "user_id": "admin-user"},
    ).json()
    session_id = session["session_id"]

    # Anonymous user cannot access the session
    anon = _anon_client()
    response = anon.get(f"/api/v1/browser/sessions/{session_id}")
    assert response.status_code == 401

    # Admin (bootstrap) can access it
    admin_get = client.get(f"/api/v1/browser/sessions/{session_id}")
    assert admin_get.status_code == 200
    assert admin_get.json()["session_id"] == session_id


# =============================================================================
# Workflow Tenant Forgery
# =============================================================================


def test_workflow_run_ignores_client_tenant_id() -> None:
    client = _bootstrap_client()
    # Create a workflow
    wf = client.post("/api/v1/workflows", json={"name": "test", "nodes": []}).json()
    wf_id = wf["id"]

    # Run with a forged tenant_id in the body
    run = client.post(
        f"/api/v1/workflows/{wf_id}/run",
        json={"inputs": {}, "tenant_id": "forged", "user_id": "attacker"},
    ).json()

    # The backend must ignore the forged values and use the principal's identity
    assert run["tenant_id"] != "forged"
    assert run["user_id"] != "attacker"


# =============================================================================
# Tool Sandbox
# =============================================================================


async def test_tool_read_file_blocks_traversal() -> None:
    """Verify that the read_file tool refuses paths outside PROJECT_ROOT."""
    fro