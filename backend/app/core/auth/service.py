"""High-level authentication service facade.

Wires together password hashing, token management and session storage into a
single dependency-injectable ``AuthService``.
"""

from __future__ import annotations

import secrets
from collections.abc import Callable
from dataclasses import dataclass
from typing import Protocol

from .security import PasswordHasher
from .sessions import SessionStore
from .tokens import TokenManager, TokenPair, TokenPayload


class AuthenticationError(Exception):
    """Raised when authentication fails."""


class UserLookup(Protocol):
    """Protocol for credential validation callbacks."""

    def __call__(self, username: str, password: str) -> str | None:
        """Return the user id if credentials are valid, else ``None``."""
        ...


@dataclass(frozen=True)
class AuthConfig:
    """Configuration for :class:`AuthService`."""

    token_secret: str
    access_ttl: int = 900
    refresh_ttl: int = 86_400
    session_ttl: int = 86_400


class AuthService:
    """Facade combining hashing, tokens and sessions.

    Parameters
    ----------
    config:
        Service configuration.
    validate_credentials:
        Callable returning a user id for valid credentials (or ``None``).
    """

    def __init__(
        self,
        config: AuthConfig,
        validate_credentials: Callable[[str, str], str | None],
    ) -> None:
        self.config = config
        self._hasher = PasswordHasher()
        self._token_manager = TokenManager(
            config.token_secret,
            access_ttl=config.access_ttl,
            refresh_ttl=config.refresh_ttl,
        )
        self._sessions = SessionStore()
        self._validate_credentials = validate_credentials

    # -- password helpers -------------------------------------------------

    def hash_password(self, password: str) -> str:
        """Hash a plaintext password for storage."""
        return self._hasher.hash(password)

    def verify_password(self, password: str, stored_hash: str) -> bool:
        """Verify a plaintext password against a stored hash."""
        return self._hasher.verify(password, stored_hash)

    # -- authentication ---------------------------------------------------

    def authenticate(self, username: str, password: str) -> TokenPair:
        """Authenticate a user and issue a new token pair.

        Raises
        ------
        AuthenticationError
            If the credentials are invalid.
        """
        user_id = self._validate_credentials(username, password)
        if user_id is None:
            raise AuthenticationError("Invalid username or password")

        pair = self._token_manager.create_pair(user_id)
        self._sessions.create(
            secrets.token_hex(16),
            user_id,
            ttl=self.config.session_ttl,
            username=username,
        )
        return pair

    def validate_access_token(self, token: str) -> TokenPayload:
        """Validate an access token, returning its payload."""
        return self._token_manager.decode(token, expected_type="access")

    def refresh(self, refresh_token: str) -> TokenPair:
        """Exchange a valid refresh token for a fresh token pair.

        Raises
        ------
        AuthenticationError
            If the refresh token is invalid or expired.
        """
        try:
            payload = self._token_manager.decode(
                refresh_token, expected_type="refresh"
            )
        except Exception as exc:
            raise AuthenticationError("Invalid refresh token") from exc
        return self._token_manager.create_pair(payload.sub)

    def close(self) -> None:
        """Release resources (no-op for the in-memory store)."""
        self._sessions.cleanup_expired()
