"""Tests for OAuth2 authentication framework.

Tests cover:
- Provider registration and retrieval
- State token generation and validation
- User info normalization
- OAuth routes integration
"""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch
import httpx
from fastapi.testclient import TestClient

from backend.app.core.oauth2 import (
    OAuthProvider,
    OAuthUser,
    OAuthManager,
    get_oauth_manager,
    reset_oauth_manager,
)


class TestOAuthProvider:
    """Tests for OAuthProvider configuration."""

    def test_provider_initialization(self):
        """Test basic provider initialization."""
        provider = OAuthProvider(
            name="test",
            client_id="client123",
            client_secret="secret456",
            authorize_url="https://example.com/auth",
            token_url="https://example.com/token",
            userinfo_url="https://example.com/userinfo",
            scopes=["read", "write"],
        )

        assert provider.name == "test"
        assert provider.client_id == "client123"
        assert provider.client_secret == "secret456"
        assert provider.scopes == ["read", "write"]

    def test_get_authorize_url(self):
        """Test authorization URL generation."""
        provider = OAuthProvider(
            name="test",
            client_id="client123",
            client_secret="secret456",
            authorize_url="https://example.com/oauth/authorize",
            token_url="https://example.com/token",
            userinfo_url="https://example.com/userinfo",
            scopes=["read", "write"],
        )

        url = provider.get_authorize_url("state123", "http://localhost:8000/callback")

        assert "client_id=client123" in url
        assert "state=state123" in url
        assert "response_type=code" in url
        assert "scope=read+write" in url
        assert "redirect_uri=" in url


class TestOAuthUser:
    """Tests for normalized OAuth user information."""

    def test_oauth_user_initialization(self):
        """Test OAuthUser creation."""
        user = OAuthUser(
            provider="github",
            provider_user_id="12345",
            email="user@example.com",
            name="John Doe",
            avatar_url="https://avatars.example.com/john.jpg",
        )

        assert user.provider == "github"
        assert user.provider_user_id == "12345"
        assert user.email == "user@example.com"
        assert user.name == "John Doe"
        assert user.avatar_url == "https://avatars.example.com/john.jpg"

    def test_oauth_user_with_raw_data(self):
        """Test OAuthUser with raw provider data."""
        raw_data = {
            "id": "12345",
            "login": "johndoe",
            "name": "John Doe",
            "email": "user@example.com",
            "avatar_url": "https://avatars.example.com/john.jpg",
            "company": "Acme Inc",
        }

        user = OAuthUser(
            provider="github",
            provider_user_id="12345",
            email="user@example.com",
            name="John Doe",
            raw_data=raw_data,
        )

        assert user.raw_data == raw_data
        assert user.raw_data["company"] == "Acme Inc"


class TestOAuthManager:
    """Tests for OAuth manager functionality."""

    def test_manager_initialization(self):
        """Test manager initialization."""
        manager = OAuthManager(redirect_base_url="https://api.example.com")

        assert manager.redirect_base_url == "https://api.example.com"
        assert manager.available_providers == []

    def test_register_github(self):
        """Test GitHub provider registration."""
        manager = OAuthManager()
        manager.register_github("client123", "secret456")

        assert "github" in manager.available_providers
        provider = manager.get_provider("github")
        assert provider is not None
        assert provider.name == "github"
        assert provider.client_id == "client123"
        assert provider.client_secret == "secret456"

    def test_register_google(self):
        """Test Google provider registration."""
        manager = OAuthManager()
        manager.register_google("client123", "secret456")

        assert "google" in manager.available_providers
        provider = manager.get_provider("google")
        assert provider is not None
        assert provider.name == "google"
        assert provider.client_id == "client123"

    def test_register_custom_provider(self):
        """Test custom provider registration."""
        manager = OAuthManager()
        custom = OAuthProvider(
            name="custom",
            client_id="id123",
            client_secret="secret123",
            authorize_url="https://custom.com/auth",
            token_url="https://custom.com/token",
            userinfo_url="https://custom.com/userinfo",
        )

        manager.register_provider(custom)
        assert "custom" in manager.available_providers

    def test_register_provider_empty_name_raises(self):
        """Test that registering provider with empty name raises error."""
        manager = OAuthManager()
        provider = OAuthProvider(
            name="",
            client_id="id123",
            client_secret="secret123",
            authorize_url="https://custom.com/auth",
            token_url="https://custom.com/token",
            userinfo_url="https://custom.com/userinfo",
        )

        with pytest.raises(ValueError, match="Provider name cannot be empty"):
            manager.register_provider(provider)

    def test_get_login_url_generates_state(self):
        """Test login URL generation with state token."""
        manager = OAuthManager(redirect_base_url="http://localhost:8000")
        manager.register_github("client123", "secret456")

        url, state = manager.get_login_url("github")

        assert "state=" in url
        assert "client_id=client123" in url
        assert len(state) > 0
        assert state in manager._pending_states

    def test_get_login_url_unknown_provider_raises(self):
        """Test that unknown provider raises ValueError."""
        manager = OAuthManager()

        with pytest.raises(ValueError, match="Unknown provider"):
            manager.get_login_url("unknown")

    def test_validate_state_succeeds(self):
        """Test valid state validation."""
        manager = OAuthManager()
        manager.register_github("client123", "secret456")

        url, state = manager.get_login_url("github")

        # State should be valid
        assert manager.validate_state(state) is True
        # State should be consumed, not valid again
        assert manager.validate_state(state) is False

    def test_validate_state_rejects_unknown(self):
        """Test that unknown state is rejected."""
        manager = OAuthManager()

        assert manager.validate_state("unknown_state") is False

    def test_validate_state_rejects_expired(self):
        """Test that expired state is rejected."""
        manager = OAuthManager()
        manager.register_github("client123", "secret456")

        url, state = manager.get_login_url("github")

        # Manually expire the state
        import time

        manager._pending_states[state] = time.time() - 700  # 11+ minutes old

        assert manager.validate_state(state) is False

    def test_available_providers(self):
        """Test available providers listing."""
        manager = OAuthManager()
        manager.register_github("id1", "secret1")
        manager.register_google("id2", "secret2")

        providers = manager.available_providers
        assert "github" in providers
        assert "google" in providers
        assert len(providers) == 2

    def test_clear_pending_states(self):
        """Test clearing pending states."""
        manager = OAuthManager()
        manager.register_github("client123", "secret456")

        url, state = manager.get_login_url("github")
        assert len(manager._pending_states) > 0

        manager.clear_pending_states()
        assert len(manager._pending_states) == 0

    def test_get_provider(self):
        """Test retrieving provider configuration."""
        manager = OAuthManager()
        manager.register_github("client123", "secret456")

        provider = manager.get_provider("github")
        assert provider is not None
        assert provider.name == "github"

        assert manager.get_provider("unknown") is None

    @pytest.mark.asyncio
    async def test_exchange_code_github(self):
        """Test GitHub code exchange."""
        manager = OAuthManager(redirect_base_url="http://localhost:8000")
        manager.register_github("client123", "secret456")

        token_response = {
            "access_token": "token123",
            "token_type": "bearer",
            "expires_in": 3600,
        }

        with patch("httpx.AsyncClient.post", new_callable=AsyncMock) as mock_post:
            mock_response = AsyncMock()
            mock_response.json.return_value = token_response
            mock_post.return_value.__aenter__.return_value = mock_response

            result = await manager.exchange_code("github", "code123")

            assert result["access_token"] == "token123"
            assert result["token_type"] == "bearer"

    @pytest.mark.asyncio
    async def test_exchange_code_unknown_provider(self):
        """Test code exchange with unknown provider."""
        manager = OAuthManager()

        with pytest.raises(ValueError, match="Unknown provider"):
            await manager.exchange_code("unknown", "code123")

    @pytest.mark.asyncio
    async def test_get_user_info_github(self):
        """Test GitHub user info retrieval and normalization."""
        manager = OAuthManager()
        manager.register_github("client123", "secret456")

        github_data = {
            "id": 12345,
            "login": "johndoe",
            "name": "John Doe",
            "email": "john@example.com",
            "avatar_url": "https://avatars.githubusercontent.com/u/12345",
            "bio": "Developer",
        }

        with patch("httpx.AsyncClient.get", new_callable=AsyncMock) as mock_get:
            mock_response = AsyncMock()
            mock_response.json.return_value = github_data
            mock_get.return_value.__aenter__.return_value = mock_response

            user = await manager.get_user_info("github", "token123")

            assert user.provider == "github"
            assert user.provider_user_id == "12345"
            assert user.email == "john@example.com"
            assert user.name == "John Doe"
            assert user.avatar_url == "https://avatars.githubusercontent.com/u/12345"
            assert user.raw_data["bio"] == "Developer"

    @pytest.mark.asyncio
    async def test_get_user_info_google(self):
        """Test Google user info retrieval and normalization."""
        manager = OAuthManager()
        manager.register_google("client123", "secret456")

        google_data = {
            "sub": "google_user_12345",
            "email": "john@gmail.com",
            "name": "John Doe",
            "picture": "https://lh3.googleusercontent.com/...",
            "email_verified": True,
        }

        with patch("httpx.AsyncClient.get", new_callable=AsyncMock) as mock_get:
            mock_response = AsyncMock()
            mock_response.json.return_value = google_data
            mock_get.return_value.__aenter__.return_value = mock_response

            user = await manager.get_user_info("google", "token123")

            assert user.provider == "google"
            assert user.provider_user_id == "google_user_12345"
            assert user.email == "john@gmail.com"
            assert user.name == "John Doe"
            assert user.avatar_url == "https://lh3.googleusercontent.com/..."

    @pytest.mark.asyncio
    async def test_get_user_info_generic_oidc(self):
        """Test generic OIDC provider user info."""
        manager = OAuthManager()
        manager.register_provider(
            OAuthProvider(
                name="oidc",
                client_id="id123",
                client_secret="secret123",
                authorize_url="https://oidc.example.com/auth",
                token_url="https://oidc.example.com/token",
                userinfo_url="https://oidc.example.com/userinfo",
            )
        )

        oidc_data = {
            "sub": "user123",
            "email": "user@example.com",
            "name": "User Name",
            "picture": "https://example.com/avatar.jpg",
        }

        with patch("httpx.AsyncClient.get", new_callable=AsyncMock) as mock_get:
            mock_response = AsyncMock()
            mock_response.json.return_value = oidc_data
            mock_get.return_value.__aenter__.return_value = mock_response

            user = await manager.get_user_info("oidc", "token123")

            assert user.provider == "oidc"
            assert user.provider_user_id == "user123"
            assert user.email == "user@example.com"


class TestGlobalOAuthManager:
    """Tests for global OAuth manager instance."""

    def setup_method(self):
        """Reset global manager before each test."""
        reset_oauth_manager()

    def teardown_method(self):
        """Clean up after tests."""
        reset_oauth_manager()

    def test_get_oauth_manager_creates_instance(self):
        """Test that get_oauth_manager creates singleton instance."""
        mgr1 = get_oauth_manager()
        mgr2 = get_oauth_manager()

        assert mgr1 is mgr2  # Same instance

    def test_get_oauth_manager_with_env_vars(self):
        """Test that get_oauth_manager registers providers from env."""
        import os

        os.environ["XAGENT_OAUTH_GITHUB_CLIENT_ID"] = "github_id"
        os.environ["XAGENT_OAUTH_GITHUB_CLIENT_SECRET"] = "github_secret"
        os.environ["XAGENT_OAUTH_GOOGLE_CLIENT_ID"] = "google_id"
        os.environ["XAGENT_OAUTH_GOOGLE_CLIENT_SECRET"] = "google_secret"
        os.environ["XAGENT_OAUTH_REDIRECT_BASE_URL"] = "https://api.example.com"

        try:
            reset_oauth_manager()
            mgr = get_oauth_manager()

            assert "github" in mgr.available_providers
            assert "google" in mgr.available_providers
            assert mgr.redirect_base_url == "https://api.example.com"
        finally:
            # Cleanup
            os.environ.pop("XAGENT_OAUTH_GITHUB_CLIENT_ID", None)
            os.environ.pop("XAGENT_OAUTH_GITHUB_CLIENT_SECRET", None)
            os.environ.pop("XAGENT_OAUTH_GOOGLE_CLIENT_ID", None)
            os.environ.pop("XAGENT_OAUTH_GOOGLE_CLIENT_SECRET", None)
            os.environ.pop("XAGENT_OAUTH_REDIRECT_BASE_URL", None)
            reset_oauth_manager()

    def test_get_oauth_manager_default_redirect_url(self):
        """Test default redirect base URL."""
        mgr = get_oauth_manager()

        assert mgr.redirect_base_url == "http://localhost:8000"


class TestOAuthRoutes:
    """Tests for OAuth FastAPI routes."""

    @pytest.fixture
    def app(self):
        """Create test FastAPI app with OAuth routes."""
        from fastapi import FastAPI

        app = FastAPI()

        # Register routes
        from backend.app.api.oauth_routes import router as oauth_router

        app.include_router(oauth_router)

        return app

    @pytest.fixture
    def client(self, app):
        """Create test client."""
        return TestClient(app)

    def setup_method(self):
        """Reset global manager before each test."""
        reset_oauth_manager()

    def teardown_method(self):
        """Clean up after tests."""
        reset_oauth_manager()

    def test_list_providers_endpoint(self, client):
        """Test GET /api/v1/auth/oauth/providers endpoint."""
        mgr = get_oauth_manager()
        mgr.register_github("id1", "secret1")
        mgr.register_google("id2", "secret2")

        response = client.get("/api/v1/auth/oauth/providers")

        assert response.status_code == 200
        data = response.json()
        assert "providers" in data
        assert "github" in data["providers"]
        assert "google" in data["providers"]

    def test_oauth_login_redirect(self, client):
        """Test GET /api/v1/auth/oauth/login/{provider} redirect."""
        mgr = get_oauth_manager()
        mgr.register_github("client123", "secret456")

        response = client.get(
            "/api/v1/auth/oauth/login/github", follow_redirects=False
        )

        assert response.status_code == 307  # Redirect
        location = response.headers["location"]
        assert "github.com/login/oauth/authorize" in location
        assert "client_id=client123" in location
        assert "state=" in location

    def test_oauth_login_unknown_provider(self, client):
        """Test login with unknown provider returns 404."""
        response = client.get("/api/v1/auth/oauth/login/unknown")

        assert response.status_code == 404
        data = response.json()
        assert "not configured" in data["detail"]

    @pytest.mark.asyncio
    async def test_oauth_callback_success(self, client):
        """Test successful OAuth callback."""
        mgr = get_oauth_manager()
        mgr.register_github("client123", "secret456")

        # Generate a login state
        url, state = mgr.get_login_url("github")

        # Mock the token exchange and user info
        token_response = {"access_token": "token123", "token_type": "bearer"}
        user_response = {
            "id": 12345,
            "login": "johndoe",
            "name": "John Doe",
            "email": "john@example.com",
            "avatar_url": "https://avatars.githubusercontent.com/u/12345",
        }

        with patch("httpx.AsyncClient.post", new_callable=AsyncMock) as mock_post:
            with patch("httpx.AsyncClient.get", new_callable=AsyncMock) as mock_get:
                # Setup post mock for token exchange
                post_response = AsyncMock()
                post_response.json.return_value = token_response
                mock_post.return_value.__aenter__.return_value = post_response

                # Setup get mock for user info
                get_response = AsyncMock()
                get_response.json.return_value = user_response
                mock_get.return_value.__aenter__.return_value = get_response

                # Call callback
                response = client.get(
                    f"/api/v1/auth/oauth/callback/github?code=code123&state={state}"
                )

                assert response.status_code == 200
                data = response.json()
                assert data["status"] == "authenticated"
                assert data["provider"] == "github"
                assert data["provider_user_id"] == "12345"
                assert data["email"] == "john@example.com"

    def test_oauth_callback_invalid_state(self, client):
        """Test callback with invalid state token."""
        mgr = get_oauth_manager()
        mgr.register_github("client123", "secret456")

        response = client.get(
            "/api/v1/auth/oauth/callback/github?code=code123&state=invalid_state"
        )

        assert response.status_code == 400
        data = response.json()
        assert "state token" in data["detail"]

    @pytest.mark.asyncio
    async def test_oauth_callback_exchange_failure(self, client):
        """Test callback when token exchange fails."""
        mgr = get_oauth_manager()
        mgr.register_github("client123", "secret456")

        # Generate a login state
        url, state = mgr.get_login_url("github")

        # Mock the token exchange to fail
        with patch("httpx.AsyncClient.post", new_callable=AsyncMock) as mock_post:
            mock_post.side_effect = httpx.HTTPError("Token exchange failed")

            response = client.get(
                f"/api/v1/auth/oauth/callback/github?code=code123&state={state}"
            )

            assert response.status_code == 502
            data = response.json()
            assert "OAuth flow failed" in data["detail"]
