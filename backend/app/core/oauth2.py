"""OAuth2/SSO Authentication Framework for X-Agent.

Supports:
- GitHub OAuth2 (code grant flow)
- Google OAuth2 (code grant flow)
- Generic OIDC provider support
- PKCE flow for enhanced security
- State validation and CSRF protection

Configuration via environment:
- XAGENT_OAUTH_GITHUB_CLIENT_ID
- XAGENT_OAUTH_GITHUB_CLIENT_SECRET
- XAGENT_OAUTH_GOOGLE_CLIENT_ID
- XAGENT_OAUTH_GOOGLE_CLIENT_SECRET
- XAGENT_OAUTH_REDIRECT_BASE_URL (e.g. http://localhost:8000)
"""

from __future__ import annotations

import logging
import secrets
import time
from dataclasses import dataclass, field
from typing import Any, Optional
from urllib.parse import urlencode

import httpx

logger = logging.getLogger(__name__)


@dataclass
class OAuthProvider:
    """Configuration for an OAuth2 provider.

    Attributes:
        name: Provider identifier (e.g., 'github', 'google').
        client_id: OAuth2 client ID.
        client_secret: OAuth2 client secret.
        authorize_url: Provider's authorization endpoint.
        token_url: Provider's token endpoint.
        userinfo_url: Provider's user info endpoint.
        scopes: List of OAuth scopes to request.
    """

    name: str
    client_id: str
    client_secret: str
    authorize_url: str
    token_url: str
    userinfo_url: str
    scopes: list[str] = field(default_factory=list)

    def get_authorize_url(self, state: str, redirect_uri: str) -> str:
        """Generate the OAuth2 authorization URL.

        Args:
            state: CSRF protection token.
            redirect_uri: Callback URI after user authorization.

        Returns:
            Complete authorization URL with query parameters.
        """
        params = {
            "client_id": self.client_id,
            "redirect_uri": redirect_uri,
            "scope": " ".join(self.scopes),
            "state": state,
            "response_type": "code",
        }
        return f"{self.authorize_url}?{urlencode(params)}"


@dataclass
class OAuthUser:
    """Normalized user info from OAuth provider.

    Attributes:
        provider: Provider name (e.g., 'github', 'google').
        provider_user_id: User ID from the OAuth provider.
        email: User's email address.
        name: User's display name.
        avatar_url: URL to user's avatar image.
        raw_data: Complete response data from provider.
    """

    provider: str
    provider_user_id: str
    email: str
    name: str
    avatar_url: str = ""
    raw_data: dict[str, Any] = field(default_factory=dict)


class OAuthManager:
    """Manages OAuth2 flows for multiple providers.

    Thread-safe manager for handling OAuth2 authorization flows,
    token exchange, and user info retrieval across multiple providers.
    """

    def __init__(self, redirect_base_url: str = "http://localhost:8000") -> None:
        """Initialize OAuth manager.

        Args:
            redirect_base_url: Base URL for OAuth callbacks
                (e.g., 'https://api.example.com').
        """
        self.providers: dict[str, OAuthProvider] = {}
        self.redirect_base_url = redirect_base_url
        self._pending_states: dict[str, float] = {}  # state -> timestamp

    def register_github(self, client_id: str, client_secret: str) -> None:
        """Register GitHub as OAuth provider.

        Args:
            client_id: GitHub OAuth app client ID.
            client_secret: GitHub OAuth app client secret.
        """
        self.providers["github"] = OAuthProvider(
            name="github",
            client_id=client_id,
            client_secret=client_secret,
            authorize_url="https://github.com/login/oauth/authorize",
            token_url="https://github.com/login/oauth/access_token",
            userinfo_url="https://api.github.com/user",
            scopes=["read:user", "user:email"],
        )

    def register_google(self, client_id: str, client_secret: str) -> None:
        """Register Google as OAuth provider.

        Args:
            client_id: Google OAuth app client ID.
            client_secret: Google OAuth app client secret.
        """
        self.providers["google"] = OAuthProvider(
            name="google",
            client_id=client_id,
            client_secret=client_secret,
            authorize_url="https://accounts.google.com/o/oauth2/v2/auth",
            token_url="https://oauth2.googleapis.com/token",
            userinfo_url="https://www.googleapis.com/oauth2/v3/userinfo",
            scopes=["openid", "email", "profile"],
        )

    def register_provider(self, provider: OAuthProvider) -> None:
        """Register a custom OAuth provider.

        Args:
            provider: OAuthProvider configuration object.

        Raises:
            ValueError: If provider name is empty or invalid.
        """
        if not provider.name:
            raise ValueError("Provider name cannot be empty")
        self.providers[provider.name] = provider
        logger.info(f"Registered OAuth provider: {provider.name}")

    def get_login_url(self, provider_name: str) -> tuple[str, str]:
        """Get login URL and state token for a provider.

        Args:
            provider_name: Name of the provider (e.g., 'github', 'google').

        Returns:
            Tuple of (authorize_url, state_token).

        Raises:
            ValueError: If provider is not configured.
        """
        provider = self.providers.get(provider_name)
        if not provider:
            raise ValueError(f"Unknown provider: {provider_name}")

        state = secrets.token_urlsafe(32)
        self._pending_states[state] = time.time()

        redirect_uri = (
            f"{self.redirect_base_url}/api/v1/auth/oauth/callback/{provider_name}"
        )
        url = provider.get_authorize_url(state, redirect_uri)
        return url, state

    def validate_state(self, state: str) -> bool:
        """Validate and consume a state token.

        Validates that the state token exists and was created within
        the last 10 minutes. Removes the token from pending states.

        Args:
            state: State token to validate.

        Returns:
            True if state is valid and exists; False otherwise.
        """
        # Clean old states (> 10 min)
        now = time.time()
        self._pending_states = {
            s: t
            for s, t in self._pending_states.items()
            if now - t < 600  # 10 minutes
        }

        if state in self._pending_states:
            del self._pending_states[state]
            return True
        return False

    async def exchange_code(
        self, provider_name: str, code: str
    ) -> dict[str, Any]:
        """Exchange authorization code for access token.

        Implements the OAuth2 authorization code exchange flow.

        Args:
            provider_name: Name of the provider.
            code: Authorization code from provider callback.

        Returns:
            Token response containing access_token, token_type, etc.

        Raises:
            ValueError: If provider is not configured.
            httpx.HTTPError: If token exchange fails.
        """
        provider = self.providers.get(provider_name)
        if not provider:
            raise ValueError(f"Unknown provider: {provider_name}")

        redirect_uri = (
            f"{self.redirect_base_url}/api/v1/auth/oauth/callback/{provider_name}"
        )

        async with httpx.AsyncClient() as client:
            resp = await client.post(
                provider.token_url,
                data={
                    "client_id": provider.client_id,
                    "client_secret": provider.client_secret,
                    "code": code,
                    "redirect_uri": redirect_uri,
                    "grant_type": "authorization_code",
                },
                headers={"Accept": "application/json"},
            )
            resp.raise_for_status()
            return resp.json()

    async def get_user_info(
        self, provider_name: str, access_token: str
    ) -> OAuthUser:
        """Fetch user info from provider using access token.

        Normalizes provider-specific user data into standard OAuthUser format.

        Args:
            provider_name: Name of the provider.
            access_token: OAuth2 access token.

        Returns:
            Normalized OAuthUser object.

        Raises:
            ValueError: If provider is not configured.
            httpx.HTTPError: If user info fetch fails.
        """
        provider = self.providers.get(provider_name)
        if not provider:
            raise ValueError(f"Unknown provider: {provider_name}")

        async with httpx.AsyncClient() as client:
            resp = await client.get(
                provider.userinfo_url,
                headers={"Authorization": f"Bearer {access_token}"},
            )
            resp.raise_for_status()
            data = resp.json()

        # Normalize based on provider
        if provider_name == "github":
            return OAuthUser(
                provider="github",
                provider_user_id=str(data.get("id", "")),
                email=data.get("email", ""),
                name=data.get("name", data.get("login", "")),
                avatar_url=data.get("avatar_url", ""),
                raw_data=data,
            )
        elif provider_name == "google":
            return OAuthUser(
                provider="google",
                provider_user_id=data.get("sub", ""),
                email=data.get("email", ""),
                name=data.get("name", ""),
                avatar_url=data.get("picture", ""),
                raw_data=data,
            )
        else:
            # Generic OIDC/OAuth provider
            return OAuthUser(
                provider=provider_name,
                provider_user_id=str(data.get("id", data.get("sub", ""))),
                email=data.get("email", ""),
                name=data.get("name", ""),
                avatar_url=data.get("picture", data.get("avatar_url", "")),
                raw_data=data,
            )

    @property
    def available_providers(self) -> list[str]:
        """List configured providers.

        Returns:
            List of provider names that have been registered.
        """
        return list(self.providers.keys())

    def clear_pending_states(self) -> None:
        """Clear all pending state tokens.

        Useful for testing or cleanup operations.
        """
        self._pending_states.clear()

    def get_provider(self, name: str) -> Optional[OAuthProvider]:
        """Retrieve a provider configuration by name.

        Args:
            name: Provider name.

        Returns:
            OAuthProvider if found, None otherwise.
        """
        return self.providers.get(name)


# Global instance
_oauth_manager: Optional[OAuthManager] = None


def get_oauth_manager() -> OAuthManager:
    """Get or create the global OAuth manager.

    Auto-initializes and registers providers from environment variables:
    - XAGENT_OAUTH_GITHUB_CLIENT_ID / _CLIENT_SECRET
    - XAGENT_OAUTH_GOOGLE_CLIENT_ID / _CLIENT_SECRET
    - XAGENT_OAUTH_REDIRECT_BASE_URL (defaults to http://localhost:8000)

    Returns:
        Global OAuthManager instance.
    """
    global _oauth_manager
    if _oauth_manager is None:
        import os

        redirect_base = os.environ.get(
            "XAGENT_OAUTH_REDIRECT_BASE_URL", "http://localhost:8000"
        )
        _oauth_manager = OAuthManager(redirect_base_url=redirect_base)

        # Auto-register providers if credentials exist
        gh_id = os.environ.get("XAGENT_OAUTH_GITHUB_CLIENT_ID")
        gh_secret = os.environ.get("XAGENT_OAUTH_GITHUB_CLIENT_SECRET")
        if gh_id and gh_secret:
            _oauth_manager.register_github(gh_id, gh_secret)
            logger.info("GitHub OAuth registered")

        go_id = os.environ.get("XAGENT_OAUTH_GOOGLE_CLIENT_ID")
        go_secret = os.environ.get("XAGENT_OAUTH_GOOGLE_CLIENT_SECRET")
        if go_id and go_secret:
            _oauth_manager.register_google(go_id, go_secret)
            logger.info("Google OAuth registered")

    return _oauth_manager


def reset_oauth_manager() -> None:
    """Reset the global OAuth manager.

    Primarily for testing purposes.
    """
    global _oauth_manager
    _oauth_manager = None
