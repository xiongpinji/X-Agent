"""Security tests for authentication system."""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from backend.app.api.auth import (
    _check_account_lockout,
    _clear_login_failures,
    _record_login_failure,
    _login_failures,
    _revoked_tokens,
    _token_expiry,
    _token_users,
)
from backend.app.core.admin import UserCreateRequest, user_store
from backend.app.core.contracts import ErrorCode


@pytest.fixture
def client():
    """Create test client."""
    from backend.app.main import app
    return TestClient(app)


@pytest.fixture(autouse=True)
def cleanup():
    """Reset all mutable auth state before and after each test.

    The auth module keeps process-global dicts/sets for login-failure tracking
    and token storage. Clearing only ``user_store`` leaves ``_login_failures``
    populated, so a test that drives an account into lockout (5 failures) leaves
    the next test reusing the same email pre-locked → spurious 429 (and a
    KeyError on ``access_token`` when a 429 body has no token). Reset every
    shared container so each test starts from a clean slate.
    """
    user_store._records.clear()
    _login_failures.clear()
    _revoked_tokens.clear()
    _token_expiry.clear()
    _token_users.clear()
    yield
    user_store._records.clear()
    _login_failures.clear()
    _revoked_tokens.clear()
    _token_expiry.clear()
    _token_users.clear()


class TestAuthenticationSecurity:
    """Test authentication security features."""

    def test_password_validation_minimum_length(self, client):
        """Test that passwords must be at least 8 characters."""
        response = client.post(
            "/api/v1/auth/register",
            json={"email": "test@example.com", "password": "Short1"},
        )
        assert response.status_code == 400
        assert "at least 8 characters" in response.json()["message"]

    def test_password_validation_uppercase(self, client):
        """Test that passwords must contain uppercase letters."""
        response = client.post(
            "/api/v1/auth/register",
            json={"email": "test@example.com", "password": "lowercase123"},
        )
        assert response.status_code == 400
        assert "uppercase" in response.json()["message"]

    def test_password_validation_lowercase(self, client):
        """Test that passwords must contain lowercase letters."""
        response = client.post(
            "/api/v1/auth/register",
            json={"email": "test@example.com", "password": "UPPERCASE123"},
        )
        assert response.status_code == 400
        assert "lowercase" in response.json()["message"]

    def test_password_validation_digit(self, client):
        """Test that passwords must contain digits."""
        response = client.post(
            "/api/v1/auth/register",
            json={"email": "test@example.com", "password": "NoDigitsHere"},
        )
        assert response.status_code == 400
        assert "digit" in response.json()["message"]

    def test_valid_registration(self, client):
        """Test successful registration with valid password."""
        response = client.post(
            "/api/v1/auth/register",
            json={"email": "test@example.com", "password": "ValidPass123"},
        )
        assert response.status_code == 200
        data = response.json()
        assert "access_token" in data
        assert "refresh_token" in data
        assert data["user"]["email"] == "test@example.com"

    def test_duplicate_registration_prevented(self, client):
        """Test that duplicate email registration is prevented."""
        # First registration
        response1 = client.post(
            "/api/v1/auth/register",
            json={"email": "test@example.com", "password": "ValidPass123"},
        )
        assert response1.status_code == 200

        # Second registration with same email
        response2 = client.post(
            "/api/v1/auth/register",
            json={"email": "test@example.com", "password": "ValidPass456"},
        )
        assert response2.status_code == 409

    def test_login_with_valid_credentials(self, client):
        """Test successful login with valid credentials."""
        # Register user
        client.post(
            "/api/v1/auth/register",
            json={"email": "test@example.com", "password": "ValidPass123"},
        )

        # Login
        response = client.post(
            "/api/v1/auth/login",
            json={"email": "test@example.com", "password": "ValidPass123"},
        )
        assert response.status_code == 200
        data = response.json()
        assert "access_token" in data
        assert "refresh_token" in data

    def test_login_with_invalid_password(self, client):
        """Test login fails with invalid password."""
        # Register user
        client.post(
            "/api/v1/auth/register",
            json={"email": "test@example.com", "password": "ValidPass123"},
        )

        # Login with wrong password
        response = client.post(
            "/api/v1/auth/login",
            json={"email": "test@example.com", "password": "WrongPass123"},
        )
        assert response.status_code == 401

    def test_account_lockout_after_failed_attempts(self, client):
        """Test account lockout after 5 failed login attempts."""
        # Register user
        client.post(
            "/api/v1/auth/register",
            json={"email": "test@example.com", "password": "ValidPass123"},
        )

        # Make 5 failed login attempts
        for _ in range(5):
            response = client.post(
                "/api/v1/auth/login",
                json={"email": "test@example.com", "password": "WrongPass123"},
            )
            assert response.status_code == 401

        # 6th attempt should be locked
        response = client.post(
            "/api/v1/auth/login",
            json={"email": "test@example.com", "password": "ValidPass123"},
        )
        assert response.status_code == 429
        assert "locked" in response.json()["message"].lower()

    def test_login_failures_cleared_on_success(self, client):
        """Test that login failures are cleared after successful login."""
        # Register user
        client.post(
            "/api/v1/auth/register",
            json={"email": "test@example.com", "password": "ValidPass123"},
        )

        # Make 2 failed attempts
        for _ in range(2):
            client.post(
                "/api/v1/auth/login",
                json={"email": "test@example.com", "password": "WrongPass123"},
            )

        # Successful login
        response = client.post(
            "/api/v1/auth/login",
            json={"email": "test@example.com", "password": "ValidPass123"},
        )
        assert response.status_code == 200

        # Verify failures are cleared - should be able to login again
        response = client.post(
            "/api/v1/auth/login",
            json={"email": "test@example.com", "password": "ValidPass123"},
        )
        assert response.status_code == 200

    def test_logout_revokes_token(self, client):
        """Test that logout revokes the token."""
        # Register and login
        client.post(
            "/api/v1/auth/register",
            json={"email": "test@example.com", "password": "ValidPass123"},
        )
        login_response = client.post(
            "/api/v1/auth/login",
            json={"email": "test@example.com", "password": "ValidPass123"},
        )
        token = login_response.json()["access_token"]

        # Logout
        response = client.post(
            "/api/v1/auth/logout",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert response.status_code == 200

        # Try to use revoked token
        response = client.get(
            "/api/v1/auth/me",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert response.status_code == 401

    def test_refresh_token_requires_authentication(self, client):
        """Test that refresh endpoint requires authentication."""
        response = client.post("/api/v1/auth/refresh")
        # /refresh is not CSRF-exempt: an unauthenticated POST with no Bearer
        # token / API key / CSRF token is rejected by the CSRF middleware (403)
        # before reaching the route's own authentication check (401). Either
        # rejection satisfies the "refresh requires authentication" intent.
        assert response.status_code in (401, 403)

    def test_missing_email_or_password(self, client):
        """Test that email and password are required."""
        # Missing password — required field, pydantic rejects with 422
        response = client.post(
            "/api/v1/auth/register",
            json={"email": "test@example.com"},
        )
        assert response.status_code in [400, 422]

        # Missing email — required 