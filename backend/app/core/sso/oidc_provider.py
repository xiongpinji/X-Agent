"""OpenID Connect (OIDC) Provider Implementation."""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from typing import Any
from uuid import uuid4

import httpx
from pydantic import BaseModel, Field

logger = logging.getLogger(__name__)


@dataclass
class OIDCConfig:
    """OpenID Connect configuration."""

    client_id: str
    client_secret: str
    redirect_uri: str
    discovery_url: str  # .well-known/openid-configuration endpoint
    scopes: list[str] = None
    response_type: str = "code"
    response_mode: str = "form_post"


class OIDCToken(BaseModel):
    """OIDC token response."""

    access_token: str
    token_type: str = "Bearer"
    expires_in: int | None = None
    refresh_token: str | None = None
    id_token: str | None = None
    scope: str | None = None


class OIDCUserInfo(BaseModel):
    """OIDC user information."""

    sub: str  # Subject (unique identifier)
    email: str | None = None
    email_verified: bool = False
    name: str | None = None
    given_name: str | None = None
    family_name: str | None = None
    picture: str | None = None
    locale: str | None = None
    phone_number: str | None = None
    phone_number_verified: bool = False
    updated_at: int | None = None


class OIDCDiscovery(BaseModel):
    """OIDC discovery document."""

    issuer: str
    authorization_endpoint: str
    token_endpoint: str
    userinfo_endpoint: str
    jwks_uri: str
    registration_endpoint: str | None = None
    scopes_supported: list[str] = []
    response_types_supported: list[str] = []
    response_modes_supported: list[str] = []
    grant_types_supported: list[str] = []
    subject_types_supported: list[str] = []
    id_token_signing_alg_values_supported: list[str] = []


class OIDCProvider:
    """OpenID Connect provider."""

    def __init__(self, config: OIDCConfig) -> None:
        """Initialize OIDC provider.

        Args:
            config: OIDC configuration
        """
        self.config = config
        if not config.scopes:
            self.config.scopes = ["openid", "profile", "email"]
        self._discovery: OIDCDiscovery | None = None
        self._sessions: dict[str, dict[str, Any]] = {}

    async def discover(self) -> bool:
        """Discover OIDC provider configuration.

        Returns:
            True if discovery successful
        """
        try:
            async with httpx.AsyncClient() as client:
                response = await client.get(self.config.discovery_url, timeout=10.0)
                response.raise_for_status()
                data = response.json()
                self._discovery = OIDCDiscovery(**data)
                logger.info(f"OIDC discovery successful: {self._discovery.issuer}")
                return True
        except Exception as e:
            logger.error(f"OIDC discovery failed: {e}")
            return False

    def get_authorization_url(self, state: str | None = None, nonce: str | None = None) -> str:
        """Get authorization URL.

        Args:
            state: State parameter for CSRF protection
            nonce: Nonce for ID token validation

        Returns:
            Authorization URL
        """
        if not self._discovery:
            raise ValueError("OIDC provider not discovered")

        state = state or uuid4().hex
        nonce = nonce or uuid4().hex

        # Store session state
        self._sessions[state] = {
            "nonce": nonce,
            "created_at": datetime.now(UTC),
        }

        params = {
            "client_id": self.config.client_id,
            "redirect_uri": self.config.redirect_uri,
            "response_type": self.config.response_type,
            "response_mode": self.config.response_mode,
            "scope": " ".join(self.config.scopes),
            "state": state,
            "nonce": nonce,
        }

        query_parts = [f"{k}={v}" for k, v in params.items()]
        return f"{self._discovery.authorization_endpoint}?{'&'.join(query_parts)}"

    async def exchange_code_for_token(self, code: str) -> OIDCToken:
        """Exchange authorization code for token.

        Args:
            code: Authorization code

        Returns:
            OIDC token

        Raises:
            ValueError: If token exchange fails
        """
        if not self._discovery:
            raise ValueError("OIDC provider not discovered")

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
                    self._discovery.token_endpoint,
                    data=payload,
                    headers={"Accept": "application/json"},
                    timeout=10.0,
                )
                response.raise_for_status()
                data = response.json()
                return OIDCToken(**data)
        except httpx.HTTPError as e:
            logger.error(f"Token exchange failed: {e}")
            raise ValueError(f"Failed to exchange code for token: {e}") from e

    async def get_user_info(self, token: OIDCToken) -> OIDCUserInfo:
        """Fetch user information.

        Args:
            token: OIDC access token

        Returns:
            User information

        Raises:
            ValueError: If user info fetch fails
        """
        if not self._discovery:
            raise ValueError("OIDC provider not discovered")

        headers = {"Authorization": f"Bearer {token.access_token}"}

        try:
            async with httpx.AsyncClient() as client:
                response = await client.get(
                    self._discovery.userinfo_endpoint,
                    headers=headers,
                    timeout=10.0,
                )
                response.raise_for_status()
                data = response.json()
                return OIDCUserInfo(**data)
        except httpx.HTTPError as e:
            logger.error(f"User info fetch failed: {e}")
            raise ValueError(f"Failed to fetch user info: {e}") from e

    async def refresh_token(self, refresh_token: str) -> OIDCToken:
        """Refresh access token.

        Args:
            refresh_token: Refresh token

        Returns:
            New OIDC token

        Raises:
            ValueError: If token refresh fails
        """
        if not self._discovery:
            raise ValueError("OIDC provider not discovered")

        payload = {
            "grant_type": "refresh_token",
            "refresh_token": refresh_token,
            "client_id": self.config.client_id,
            "client_secret": self.config.client_secret,
        }

        try:
            async with httpx.AsyncClient() as client:
                response = await client.post(
                    self._discovery.token_endpoint,
                    data=payload,
                    headers={"Accept": "application/json"},
                    timeout=10.0,
                )
                response.raise_for_status()
                data = response.json()
                return OIDCToken(**data)
        except httpx.HTTPError as e:
            logger.error(f"Token refresh failed: {e}")
            raise ValueError(f"Failed to refresh token: {e}") from e

    def validate_state(self, state: str) -> bool:
        """Validate state parameter.

        Args:
            state: State parameter

        Returns:
            True if state is valid
        """
        if state not in self._sessions:
            return False

        session = self._sessions[state]
        created_at = session.get("created_at")

        # Check if state is not older than 10 minutes
        if created_at and datetime.now(UTC) - created_at > timedelta(minutes=10):
            del self._sessions[state]
            return False

        return True

    def get_nonce(self, state: str) -> str | None:
        """Get nonce for state.

        Args:
            state: State parameter

        Returns:
            Nonce or None
        """
        if state not in self._sessions:
            return None

        return self._sessions[state].get("nonce")

    def cleanup_expired_sessions(self) -> int:
        """Clean up expired sessions.

        Returns:
            Number of sessions cleaned up
        """
        now = datetime.now(UTC)
        expired = [
            state
            for state, session in self._sessions.items()
            if now - session.get("created_at", now) > timedelta(minutes=10)
        ]

        for state in expired:
            del self._sessions[state]

        if expired:
            logger.debug(f"Cleaned up {len(expired)} expired OIDC sessions")

        return len(expired)
