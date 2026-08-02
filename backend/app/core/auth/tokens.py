"""Access and refresh token management.

Tokens are signed HMAC-SHA256 JSON payloads using only the standard library.
Each token carries a subject (user id), a type, an issued-at timestamp and an
expiry timestamp.
"""

from __future__ import annotations

import base64
import hashlib
import hmac
import json
import secrets
import time
from dataclasses import dataclass, field
from typing import Any, Final

#: Token types.
ACCESS_TOKEN: Final[str] = "access"
REFRESH_TOKEN: Final[str] = "refresh"


class TokenError(Exception):
    """Base exception for token-related failures."""


class TokenExpiredError(TokenError):
    """Raised when a token has passed its expiry time."""


class InvalidTokenError(TokenError):
    """Raised when a token is malformed or its signature is invalid."""


def _b64url_encode(data: bytes) -> str:
    return base64.urlsafe_b64encode(data).rstrip(b"=").decode("ascii")


def _b64url_decode(data: str) -> bytes:
    padding = "=" * (-len(data) % 4)
    return base64.urlsafe_b64decode(data + padding)


@dataclass(frozen=True)
class TokenPayload:
    """Decoded payload of a token."""

    sub: str
    typ: str
    iat: int
    exp: int
    claims: dict[str, Any] = field(default_factory=dict)

    @property
    def is_expired(self) -> bool:
        """Whether the token has already expired."""
        return self.exp <= int(time.time())


@dataclass(frozen=True)
class TokenPair:
    """A matched access/refresh token pair."""

    access_token: str
    refresh_token: str
    access_expires_in: int
    refresh_expires_in: int


class TokenManager:
    """Signs and verifies HMAC-SHA256 JSON tokens.

    Parameters
    ----------
    secret:
        Shared signing secret (must be kept private).
    access_ttl:
        Access token lifetime in seconds.
    refresh_ttl:
        Refresh token lifetime in seconds.
    """

    def __init__(
        self,
        secret: str,
        *,
        access_ttl: int = 900,
        refresh_ttl: int = 86_400,
    ) -> None:
        if not secret:
            raise ValueError("secret must not be empty")
        if access_ttl <= 0 or refresh_ttl <= 0:
            raise ValueError("TTLs must be positive")
        self._secret = secret.encode("utf-8")
        self.access_ttl = access_ttl
        self.refresh_ttl = refresh_ttl

    def _sign(self, payload: dict[str, Any]) -> str:
        body = _b64url_encode(json.dumps(payload, sort_keys=True).encode("utf-8"))
        signature = hmac.new(self._secret, body.encode("ascii"), hashlib.sha256).digest()
        return f"{body}.{_b64url_encode(signature)}"

    def _verify(self, token: str) -> dict[str, Any]:
        try:
            body, signature = token.split(".", 1)
        except ValueError as exc:
            raise InvalidTokenError("Malformed token") from exc

        expected = hmac.new(self._secret, body.encode("ascii"), hashlib.sha256).digest()
        provided = _b64url_decode(signature)
        if not hmac.compare_digest(expected, provided):
            raise InvalidTokenError("Invalid token signature")

        try:
            payload = json.loads(_b64url_decode(body))
        except (ValueError, json.JSONDecodeError) as exc:
            raise InvalidTokenError("Malformed token payload") from exc
        return payload

    def create_access_token(
        self, subject: str, *, ttl: int | None = None, **claims: Any
    ) -> str:
        """Create a signed access token for ``subject``."""
        return self._issue(subject, ACCESS_TOKEN, ttl or self.access_ttl, claims)

    def create_refresh_token(
        self, subject: str, *, ttl: int | None = None, **claims: Any
    ) -> str:
        """Create a signed refresh token for ``subject``."""
        return self._issue(subject, REFRESH_TOKEN, ttl or self.refresh_ttl, claims)

    def create_pair(self, subject: str, **claims: Any) -> TokenPair:
        """Create a matched access/refresh token pair."""
        now = int(time.time())
        access = self._issue(subject, ACCESS_TOKEN, self.access_ttl, claims, now=now)
        refresh = self._issue(subject, REFRESH_TOKEN, self.refresh_ttl, claims, now=now)
        return TokenPair(
            access_token=access,
            refresh_token=refresh,
            access_expires_in=self.access_ttl,
            refresh_expires_in=self.refresh_ttl,
        )

    def _issue(
        self,
        subject: str,
        typ: str,
        ttl: int,
        claims: dict[str, Any],
        *,
        now: int | None = None,
    ) -> str:
        now = now if now is not None else int(time.time())
        payload: dict[str, Any] = {
            "sub": subject,
            "typ": typ,
            "iat": now,
            "exp": now + ttl,
            "jti": secrets.token_hex(8),
        }
        payload.update(claims)
        return self._sign(payload)

    def decode(self, token: str, *, expected_type: str | None = None) -> TokenPayload:
        """Verify and decode a token into a :class:`TokenPayload`.

        Raises
        ------
        TokenExpiredError
            If the token has expired.
        InvalidTokenError
            If the token is malformed or signature is invalid.
        """
        payload = self._verify(token)
        if expected_type is not None and payload.get("typ") != expected_type:
            raise InvalidTokenError(
                f"Expected token type {expected_type!r}, got {payload.get('typ')!r}"
            )
        result = TokenPayload(
            sub=str(payload["sub"]),
            typ=str(payload.get("typ", "")),
            iat=int(payload.get("iat", 0)),
            exp=int(payload.get("exp", 0)),
            claims={k: v for k, v in payload.items() if k not in {"sub", "typ", "iat", "exp", "jti"}},
        )
        if result.is_expired:
            raise TokenExpiredError("Token has expired")
        return result
