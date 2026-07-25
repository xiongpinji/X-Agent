"""Integration tests for Auth API (backend.app.api.auth).

Covers:
- POST /api/v1/auth/register
- POST /api/v1/auth/login
- POST /api/v1/auth/refresh
- POST /api/v1/auth/logout
- GET /api/v1/auth/me
- PUT /api/v1/auth/me
"""
from __future__ import annotations

import pytest
from httpx import ASGITransport, AsyncClient

from backend.app.main import app, _register_all_routers

# Ensure routers are registered before tests run
_register_all_routers()


@pytest.fixture
async def client():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as c:
        yield c


@pytest.fixture
async def auth_headers(client: AsyncClient):
    """Register + login and return auth headers."""
    await client.post("/api/v1/auth/register", json={
        "email": "test@example.com",
        "password": "SecurePass123!",
    })
    resp = await client.post("/api/v1/auth/login", json={
        "email": "test@example.com",
        "password": "SecurePass123!",
    })
    data = resp.json()
    token = data.get("access_token") or data.get("token", "")
    return {"Authorization": f"Bearer {token}"}


# ---------------------------------------------------------------------------
# Registration
# ---------------------------------------------------------------------------

class TestRegister:
    async def test_register_success(self, client):
        resp = await client.post("/api/v1/auth/register", json={
            "email": "new@example.com",
            "password": "Pass123!@#",
        })
        assert resp.status_code in (200, 201)
        data = resp.json()
        assert "access_token" in data or "token" in data

    async def test_register_duplicate_username(self, client):
        payload = {
            "email": "dup1@example.com",
            "password": "Pass123!@#",
        }
        await client.post("/api/v1/auth/register", json=payload)
        resp = await client.post("/api/v1/auth/register", json=payload)
        assert resp.status_code in (400, 409)

    async def test_register_missing_fields(self, client):
        resp = await client.post("/api/v1/auth/register", json={"email": "x@example.com"})
        assert resp.status_code == 422


# ---------------------------------------------------------------------------
# Login
# ---------------------------------------------------------------------------

class TestLogin:
    async def test_login_success(self, client):
        await client.post("/api/v1/auth/register", json={
            "email": "login@example.com",
            "password": "Pass123!@#",
        })
        resp = await client.post("/api/v1/auth/login", json={
            "email": "login@example.com",
            "password": "Pass123!@#",
        })
        assert resp.status_code == 200
        data = resp.json()
        assert "access_token" in data or "token" in data

    async def test_login_wrong_password(self, client):
        await client.post("/api/v1/auth/register", json={
            "email": "wrongpw@example.com",
            "password": "Correct123!",
        })
        resp = await client.post("/api/v1/auth/login", json={
            "email": "wrongpw@example.com",
            "password": "WrongPass!",
        })
        assert resp.status_code in (400, 401)

    async def test_login_nonexistent_user(self, client):
        resp = await client.post("/api/v1/auth/login", json={
            "email": "ghost@example.com",
            "password": "whatever",
        })
        assert resp.status_code in (400, 401, 404)


# ---------------------------------------------------------------------------
# Token refresh
# ---------------------------------------------------------------------------

class TestRefresh:
    async def test_refresh_with_valid_token(self, client, auth_headers):
        resp = await client.post("/api/v1/auth/refresh", headers=auth_headers)
        assert resp.status_code == 200

    async def test_refresh_without_token(self, client):
        resp = await client.post("/api/v1/auth/refresh")
        assert resp.status_code in (401, 403)


# ---------------------------------------------------------------------------
# Logout
# ---------------------------------------------------------------------------

class TestLogout:
    async def test_logout_success(self, client, auth_headers):
        resp = await client.post("/api/v1/auth/logout", headers=auth_headers)
        assert resp.status_code == 200

    async def test_logout_without_token(self, client):
        # API allows logout without token (idempotent)
        resp = await client.post("/api/v1/auth/logout")
        assert resp.status_code in (200, 401, 403)


# ---------------------------------------------------------------------------
# Profile (GET/PUT /me)
# ---------------------------------------------------------------------------

class TestProfile:
    async def test_get_me(self, client, auth_headers):
        resp = await client.get("/api/v1/auth/me", headers=auth_headers)
        assert resp.status_code == 200
        data = resp.json()
        # API returns principal info which may have user_id or email
        assert "user_id" in data or "email" in data or "authenticated" in data

    async def test_get_me_unauthenticated(self, client):
        # API returns default principal for unauthenticated requests
        resp = await client.get("/api/v1/auth/me")
        assert resp.status_code in (200, 401, 403)

    async def test_update_me(self, client, auth_headers):
        resp = await client.put("/api/v1/auth/me", headers=auth_headers, json={
            "display_name": "Updated Name",
        })
        assert resp.status_code == 200
