"""REST API with JWT authentication.

A self-contained FastAPI application that provides:
  * User registration
  * Login (issuing JWT access + refresh tokens)
  * Authenticated protected endpoints
  * Token refresh & logout
  * Password hashing (bcrypt)

This module is intentionally dependency-light and keeps all auth logic in
one place so it can be embedded into a larger backend or run standalone.
"""

from __future__ import annotations

import os
import secrets
from datetime import UTC, datetime, timedelta
from enum import Enum
from typing import Any

import bcrypt
import jwt
from fastapi import Depends, FastAPI, HTTPException, Security, status
from fastapi.security import (
    HTTPAuthorizationCredentials,
    HTTPBearer,
    OAuth2PasswordBearer,
    OAuth2PasswordRequestForm,
)
from pydantic import BaseModel, EmailStr, Field, field_validator

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------


class Settings:
    """Runtime configuration loaded from environment variables."""

    def __init__(self) -> None:
        self.secret_key: str = os.getenv(
            "AUTH_SECRET_KEY", secrets.token_hex(32)
        )
        self.algorithm: str = os.getenv("AUTH_ALGORITHM", "HS256")
        self.access_token_minutes: int = int(
            os.getenv("AUTH_ACCESS_TOKEN_MINUTES", "30")
        )
        self.refresh_token_days: int = int(
            os.getenv("AUTH_REFRESH_TOKEN_DAYS", "7")
        )


settings = Settings()

# ---------------------------------------------------------------------------
# Domain types
# ---------------------------------------------------------------------------


class Role(str, Enum):
    """Available user roles used for authorization."""

    USER = "user"
    ADMIN = "admin"


class User(BaseModel):
    """A registered user."""

    id: str
    email: EmailStr
    hashed_password: str
    role: Role = Role.USER
    is_active: bool = True
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))

    def verify_password(self, password: str) -> bool:
        """Verify a plaintext password against the stored hash."""
        try:
            return bcrypt.checkpw(
                password.encode("utf-8"), self.hashed_password.encode("utf-8")
            )
        except ValueError:
            return False


class UserCreate(BaseModel):
    """Payload for registering a new user."""

    email: EmailStr
    password: str = Field(min_length=8, max_length=128)
    role: Role = Role.USER

    @field_validator("password")
    @classmethod
    def _password_strength(cls, value: str) -> str:
        if not any(ch.isdigit() for ch in value):
            raise ValueError("password must contain at least one digit")
        if not any(ch.isalpha() for ch in value):
            raise ValueError("password must contain at least one letter")
        return value


class TokenPair(BaseModel):
    """Access + refresh token pair returned on login."""

    access_token: str
    refresh_token: str
    token_type: str = "bearer"
    expires_in: int


class UserOut(BaseModel):
    """Public representation of a user (no password)."""

    id: str
    email: EmailStr
    role: Role
    is_active: bool
    created_at: datetime


# ---------------------------------------------------------------------------
# In-memory storage (swap for a real DB in production)
# ---------------------------------------------------------------------------

_users: dict[str, User] = {}
_refresh_tokens: dict[str, str] = {}  # jti -> user_id


def _next_id() -> str:
    return secrets.token_hex(8)


def _hash_password(password: str) -> str:
    salt = bcrypt.gensalt()
    return bcrypt.hashpw(password.encode("utf-8"), salt).decode("utf-8")


def _create_access_token(user: User) -> tuple[str, int]:
    expires_in = settings.access_token_minutes * 60
    now = datetime.now(UTC)
    payload = {
        "sub": user.id,
        "email": user.email,
        "role": user.role.value,
        "type": "access",
        "iat": int(now.timestamp()),
        "exp": int((now + timedelta(seconds=expires_in)).timestamp()),
    }
    token = jwt.encode(payload, settings.secret_key, algorithm=settings.algorithm)
    return token, expires_in


def _create_refresh_token(user: User) -> str:
    jti = secrets.token_hex(16)
    now = datetime.now(UTC)
    payload = {
        "sub": user.id,
        "jti": jti,
        "type": "refresh",
        "iat": int(now.timestamp()),
        "exp": int(
            (now + timedelta(days=settings.refresh_token_days)).timestamp()
        ),
    }
    token = jwt.encode(payload, settings.secret_key, algorithm=settings.algorithm)
    _refresh_tokens[jti] = user.id
    return token


def _decode_token(token: str, expected_type: str) -> dict[str, Any]:
    """Decode and validate a JWT, raising HTTPException on failure."""
    try:
        payload = jwt.decode(
            token, settings.secret_key, algorithms=[settings.algorithm]
        )
    except jwt.ExpiredSignatureError as exc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token has expired",
            headers={"WWW-Authenticate": "Bearer"},
        ) from exc
    except jwt.InvalidTokenError as exc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid token",
            headers={"WWW-Authenticate": "Bearer"},
        ) from exc

    if payload.get("type") != expected_type:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Wrong token type",
            headers={"WWW-Authenticate": "Bearer"},
        )
    return payload


# ---------------------------------------------------------------------------
# Security dependencies
# ---------------------------------------------------------------------------

_bearer = HTTPBearer(auto_error=False)
_oauth2 = OAuth2PasswordBearer(tokenUrl="/auth/login")


def get_current_user(
    credentials: HTTPAuthorizationCredentials | None = Depends(_bearer),
) -> User:
    """Resolve the authenticated user from the Authorization header."""
    if credentials is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Not authenticated",
            headers={"WWW-Authenticate": "Bearer"},
        )
    payload = _decode_token(credentials.credentials, expected_type="access")
    user = _users.get(payload.get("sub", ""))
    if user is None or not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User not found or inactive",
        )
    return user


def require_admin(user: User = Depends(get_current_user)) -> User:
    """Dependency that only admits admin users."""
    if user.role != Role.ADMIN:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Admin privileges required",
        )
    return user


# ---------------------------------------------------------------------------
# Application
# ---------------------------------------------------------------------------

app = FastAPI(
    title="Authenticated REST API",
    version="1.0.0",
    description="A REST API with JWT-based authentication.",
)


@app.get("/health")
def health() -> dict[str, str]:
    """Liveness probe."""
    return {"status": "ok"}


@app.post(
    "/auth/register",
    response_model=UserOut,
    status_code=status.HTTP_201_CREATED,
)
def register(payload: UserCreate) -> UserOut:
    """Register a new user."""
    email = payload.email.lower()
    if any(u.email == email for u in _users.values()):
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Email already registered",
        )
    user = User(
        id=_next_id(),
        email=EmailStr(email),
        hashed_password=_hash_password(payload.password),
        role=payload.role,
    )
    _users[user.id] = user
    return UserOut(
        id=user.id,
        email=user.email,
        role=user.role,
        is_active=user.is_active,
        created_at=user.created_at,
    )


@app.post("/auth/login", response_model=TokenPair)
def login(form: OAuth2PasswordRequestForm = Depends()) -> TokenPair:
    """Exchange credentials for a token pair (OAuth2 form body)."""
    user = next(
        (u for u in _users.values() if u.email == form.username.lower()), None
    )
    if user is None or not user.verify_password(form.password):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect email or password",
            headers={"WWW-Authenticate": "Bearer"},
        )
    if not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="User account is disabled",
        )
    access_token, expires_in = _create_access_token(user)
    refresh_token = _create_refresh_token(user)
    return TokenPair(
        access_token=access_token,
        refresh_token=refresh_token,
        expires_in=expires_in,
    )


@app.post("/auth/refresh", response_model=TokenPair)
def refresh(
    credentials: HTTPAuthorizationCredentials = Security(_bearer),
) -> TokenPair:
    """Issue a fresh token pair from a valid refresh token."""
    payload = _decode_token(credentials.credentials, expected_type="refresh")
    jti = payload.get("jti")
    user_id = _refresh_tokens.get(jti)
    if user_id is None or user_id != payload.get("sub"):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Refresh token revoked or invalid",
        )
    user = _users.get(user_id)
    if user is None or not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User not found or inactive",
        )
    # Rotate: revoke old refresh token, issue new pair.
    _refresh_tokens.pop(jti, None)
    access_token, expires_in = _create_access_token(user)
    refresh_token = _create_refresh_token(user)
    return TokenPair(
        access_token=access_token,
        refresh_token=refresh_token,
        expires_in=expires_in,
    )


@app.post("/auth/logout", status_code=status.HTTP_204_NO_CONTENT)
def logout(
    credentials: HTTPAuthorizationCredentials = Security(_bearer),
) -> None:
    """Revoke the presented refresh token."""
    payload = _decode_token(credentials.credentials, expected_type="refresh")
    _refresh_tokens.pop(payload.get("jti"), None)


@app.get("/users/me", response_model=UserOut)
def me(user: User = Depends(get_current_user)) -> UserOut:
    """Return the currently authenticated user's profile."""
    return UserOut(
        id=user.id,
        email=user.email,
        role=user.role,
        is_active=user.is_active,
        created_at=user.created_at,
    )


@app.get("/users", response_model=list[UserOut])
def list_users(user: User = Depends(require_admin)) -> list[UserOut]:
    """Admin-only: list all registered users."""
    return [
        UserOut(
            id=u.id,
            email=u.email,
            role=u.role,
            is_active=u.is_active,
            created_at=u.created_at,
        )
        for u in _users.values()
    ]
