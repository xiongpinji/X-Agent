"""OAuth 2.0 Provider Implementation."""

from __future__ import annotations

import hashlib
import json
import logging
from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta
from enum import Enum
from typing import Any
from uuid import uuid4

import httpx
from pydantic import BaseModel, Field

logger = logging.getLogger(__name__)


class OAuthProvider(str, Enum):
    """Supported OAuth providers."""

    GOOGLE = "google"
    GITHUB = "github"
    MICROSOFT = "microsoft"


@dataclass
class OAuthConfig:
    """OAuth configuration."""

    provider: OAuthProvider
    client_id: str
    client_secret: str
    redirect_uri: str
    scopes: list[str] = field(default_factory=lambda: ["openid", "profile", "email"])
    authorization_endpoint: str = ""
    token_endpoint: str = ""
    userinfo_endpoint: str = ""
    revocation_endpoint: str | None = None


class OAuthToken(BaseModel):
    """OAuth token response."""

    access_token: str
    token_type: str = "Bearer"
    expires_in: int | None = None
    refresh_token: str | None = None
    scope: str | None = None
    id_token: str | None = None


class OAuthUserInfo(BaseModel):
    """OAuth user information."""

    sub: str  # Subject (unique identifier)
    email: str | None = None
    email_verified: bool = False
    name: str | None = None
    given_name: str | None = None
    family_name: str | None = None
    picture: str | None = None
    locale: str | None = None
    phone_number: str | None = None
    updated_at: int | None = None


class OAuthSession(BaseModel):
    """OAuth session state."""

    state: str = Field(default_factory=lambda: uuid4().hex)
    nonce: str = Field(default_factory=lambda: uuid4().hex)
    code_verifier: str = Field(default_factory=lambda: uuid4().hex)
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    expires_at: datetime = Field(default_factory=lambda: datetime.now(UTC) + timedelta(minutes=10))


class OAuthClient:
    """OAuth 2.0 client for handling authentication flows."""

    def __init__(self, config: OAuthConfig) -> None:
        """Initialize OAuth client.

        Args:
            config: OAuth configuration
        """
        self.config = config
        self._setup_endpoints()

    def _setup_endpoints(self) -> None:
        """Setup provider-specific endpoints."""
        if self.config.provider == OAuthProvider.GOOGLE:
            self.config.authorization_endpoint = "https://accounts.google.com/o/oauth2/v2/auth"
            self.config.token_endpoint = "https://oauth2.googleapis.com/token"
            self.config.userinfo_endpoint = "https://openidconnect.googleapis.com/v1/userinfo"
            self.config.revocation_endpoint = "https://oauth2.googleapis.com/revoke"

        elif self.config.provider == OAuthProvider.GITHUB:
            self.config.authorization_endpoint = "https://github.com/login/oauth/authorize"
            self.config.token_endpoint = "https://github.com/login/oauth/access_token"
            self.config.userinfo_endpoint = "https://api.github.com/user"
            self.config.revocation_endpoint = None

        elif self.config.provider == OAuthProvider.MICROSOFT:
            self.config.authorization_endpoint = "https://login.microsoftonline.com/common/oauth2/v2.0/authorize"
            self.config.token_endpoint = "https://login.microsoftonline.com/common/oauth2/v2.0/token"
            self.config.userinfo_endpoint = "https://graph.microsoft.com/v1.0/me"
            self.config.revocation_endpoint = "https://login.microsoftonline.com/common/oauth2/v2.0/logout"

    def get_authorization_url(self, session: OAuthSession) -> str:
        """Generate authorization URL for user redirect.

        Args:
            session: OAuth session with state and nonce

        Returns:
            Authorization URL
        """
        params = {
            "client_id": self.config.client_id,
            "redirect_uri": self.config.redirect_uri,
            "response_type": "code",
            "scope": " ".join(self.config.scopes),
            "state": session.state,
        }

        # Add provider-specific parameters
        if self.config.provider == OAuthProvider.GOOGLE:
            params["nonce"] = session.nonce
            params["access_type"] = "offline"
            params["prompt"] = "consent"

        elif self.config.provider == OAuthProvider.MICROSOFT:
            params["response_mode"] = "query"

        # Build query string
        query_parts = [f"{k}={v}" for k, v in params.items()]
        return f"{self.config.authorization_endpoint}?{'&'.join(query_parts)}"

    async def exchange_code_for_token(self, code: str) -> OAuthToken:
        """Exchange authorization code for access token.

        Args:
            code: Authorization code from provider

        Returns:
            OAuth token

        Raises:
            ValueError: If token exchange fails
        """
        payload = {
            "grant_type": "authorization_code",
            "code": code,
            "redirect_uri": self.config.redirect_uri,
            "client_id": self.config.client_id,
            "client_secret": self.config.client_secret,
        }

        try:
            async with httpx.AsyncClient() as client:
                response = await client.post(
                    self.config.token_endpoint,
                    data=payload,
                    headers={"Accept": "application/json"},
                    timeout=10.0,
                )
                response.raise_for_status()
                data = response.json()
                return OAuthToken(**data)
        except httpx.HTTPError as e:
            logger.error(f"Token exchange failed: {e}")
            raise ValueError(f"Failed to exchange code for token: {e}") from e

    async def get_user_info(self, token: OAuthToken) -> OAuthUserInfo:
        """Fetch user information from provider.

        Args:
            token: OAuth access token

        Returns:
            User information

        Raises:
            ValueError: If user info fetch fails
        """
        headers = {"Authorization": f"Bearer {token.access_token}"}

        # GitHub requires Accept header
        if self.config.provider == OAuthProvider.GITHUB:
            headers["Accept"] = "application/vnd.github.v3+json"

        try:
            async with httpx.AsyncClient() as client:
                response = await client.get(
                    self.config.userinfo_endpoint,
                    headers=headers,
                    timeout=10.0,
                )
                response.raise_for_status()
                data = response.json()

                # Normalize GitHub response
                if self.config.provider == OAuthProvider.GITHUB:
                    data = {
                        "sub": str(data.get("id")),
                        "email": data.get("email"),
                        "email_verified": True,
                        "name": data.get("name"),
                        "picture": data.get("avatar_url"),
                    }

                # Normalize Microsoft response
                elif self.config.provider == OAuthProvider.MICROSOFT:
                    data = {
                        "sub": data.get("id"),
                        "email": data.get("userPrincipalName"),
                        "email_verified": True,
                        "name": data.get("displayName"),
                    }

                return OAuthUserInfo(**data)
        except httpx.HTTPError as e:
            logger.error(f"User info fetch failed: {e}")
            raise ValueError(f"Failed to fetch user info: {e}") from e

    async def revoke_token(self, token: str) -> bool:
        """Revoke OAuth token.

        Args:
            token: Access token to revoke

        Returns:
            True if revocation successful
        """
        if not self.config.revocation_endpoint:
            logger.warning(f"Revocation not supported for {self.config.provider}")
            return False

        payload = {
            "token": token,
            "client_id": self.config.client_id,
            "client_secret": self.config.client_secret,
        }

        try:
            async with httpx.AsyncClient() as client:
                response = await client.post(
                    self.config.revocation_endpoint,
                    data=payload,
                    timeout=10.0,
                )
                return response.status_code == 200
        except httpx.HTTPError as e:
            logger.error(f"Token revocation failed: {e}")
            return False


class OAuthManager:
    """Manages OAuth authentication flows."""

    def __init__(self) -> None:
        """Initialize OAuth manager."""
        self._clients: dict[OAuthProvider, OAuthClient] = {}
        self._sessions: dict[str, OAuthSession] = {}

    def register_provider(self, config: OAuthConfig) -> None:
        """Register OAuth provider.

        Args:
            config: OAuth configuration
        """
        client = OAuthClient(config)
        self._clients[config.provider] = client
        logger.info(f"Registered OAuth provider: {config.provider}")

    def create_session(self, provider: OAuthProvider) -> OAuthSession:
        """Create OAuth session.

        Args:
            provider: OAuth provider

        Returns:
            OAuth session with state and nonce
        """
        session = OAuthSession()
        self._sessions[session.state] = session
        logger.debug(f"Created OAuth session for {provider}: {session.state}")
        return session

    def get_authorization_url(self, provider: OAuthProvider, session: OAuthSession) -> str:
        """Get authorization URL.

        Args:
            provider: OAuth provider
            session: OAuth session

        Returns:
            Authorization URL

        Raises:
            ValueError: If provider not registered
        """
        if provider not in self._clients:
            raise ValueError(f"OAuth provider not registered: {provider}")

        return self._clients[provider].get_authorization_url(session)

    async def authenticate(
        self,
        provider: OAuthProvider,
        code: str,
        state: str,
    ) -> tuple[OAuthUserInfo, OAuthToken]:
        """Authenticate user with OAuth.

        Args:
            provider: OAuth provider
            code: Authorization code
            state: State parameter for CSRF validation

        Returns:
            Tuple of user info and token

        Raises:
            ValueError: If authentication fails
        """
        if provider not in self._clients:
            raise ValueError(f"OAuth provider not registered: {provider}")

        # Validate state
        if state not in self._sessions:
            raise ValueError("Invalid state parameter")

        session = self._sessions.pop(state)
        if datetime.now(UTC) > session.expires_at:
            raise ValueError("OAuth session expired")

        # Exchange code for token
        client = self._clients[provider]
        token = await client.exchange_code_for_token(code)

        # Fetch user info
        user_info = await client.get_user_info(token)

        logger.info(f"OAuth authentication successful for {provider}: {user_info.email}")
        return user_info, token

    async def revoke_token(self, provider: OAuthProvider, token: str) -> bool:
        """Revoke OAuth token.

        Args:
            provider: OAuth provider
            token: Access token

        Returns:
            True if revocation successful
        """
        if provider not in self._clients:
            return False

        return await self._clients[provider].revoke_token(token)

    def cleanup_expired_sessions(self) -> int:
        """Clean up expired OAuth sessions.

        Returns:
            Number of sessions cleaned up
        """
        now = datetime.now(UTC)
        expired = [state for state, session in self._sessions.items() if now > session.expires_at]

        for state in expired:
            del self._sessions[state]

        if expired:
            logger.debug(f"Cleaned up {len(expired)} expired OAuth sessions")

        return len(expired)
