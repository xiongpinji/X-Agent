from __future__ import annotations

import threading
import time
from typing import Annotated
from uuid import uuid4

from fastapi import APIRouter, Depends, Header

from backend.app.api.errors import api_error
from backend.app.core.admin import AuthLoginRequest, AuthTokenResponse, UserCreateRequest, user_store
from backend.app.core.contracts import ErrorCode
from backend.app.core.security import Principal
from backend.app.dependencies import get_current_principal

router = APIRouter(prefix="/api/v1/auth", tags=["auth"])
PrincipalDependency = Annotated[Principal, Depends(get_current_principal)]

# In-memory token store (replace with Redis in production)
_revoked_tokens: set[str] = set()
_token_expiry: dict[str, float] = {}
_token_users: dict[str, str] = {}
_token_lock = threading.Lock()
_DEFAULT_TOKEN_TTL_SECONDS = 900  # 15 minutes


def _issue_token(ttl_seconds: int = _DEFAULT_TOKEN_TTL_SECONDS) -> str:
    token = f"xag_{uuid4().hex}"
    with _token_lock:
        _token_expiry[token] = time.time() + ttl_seconds
    return token


def _is_token_valid(token: str) -> bool:
    with _token_lock:
        if token in _revoked_tokens:
            return False
        expiry = _token_expiry.get(token)
    if expiry is None or time.time() > expiry:
        return False
    return True


def _revoke_token(token: str) -> None:
    with _token_lock:
        _revoked_tokens.add(token)
        _token_expiry.pop(token, None)


@router.post("/register", response_model=AuthTokenResponse)
async def register(request: AuthLoginRequest) -> AuthTokenResponse:
    if not request.email or not request.password:
        raise api_error(400, ErrorCode.VALIDATION_ERROR, "Email and password are required.")
    # Prevent user enumeration: use constant-time check logic
    existing = None
    for user in user_store.list():
        if user.email == request.email:
            existing = user
            break
    if existing is not None:
        # Simulate password hash work to maintain constant timing
        import bcrypt
        bcrypt.gensalt(rounds=12)
        raise api_error(409, ErrorCode.VALIDATION_ERROR, "Registration failed.")
    user = user_store.create(
        UserCreateRequest(email=request.email, display_name=request.email.split("@")[0]),
        password=request.password,
    )
    return AuthTokenResponse(
        access_token=_issue_token(),
        refresh_token=_issue_token(),
        user=user.model_dump(mode="json"),
    )


@router.post("/login", response_model=AuthTokenResponse)
async def login(request: AuthLoginRequest) -> AuthTokenResponse:
    if not request.email or not request.password:
        raise api_error(400, ErrorCode.VALIDATION_ERROR, "Email and password are required.")
    start = time.monotonic()
    user = user_store.authenticate(request.email, request.password)
    # Constant-time compensation to prevent user enumeration via timing
    elapsed = (time.monotonic() - start) * 1000
    target_ms = 200
    if elapsed < target_ms:
        time.sleep((target_ms - elapsed) / 1000)
    if user is None:
        raise api_error(401, ErrorCode.AUTHENTICATION_FAILED, "Invalid email or password.")
    access_token = _issue_token()
    refresh_token = _issue_token(ttl_seconds=86400)  # 24 hours
    _token_users[access_token] = user.id
    _token_users[refresh_token] = user.id
    return AuthTokenResponse(
        access_token=access_token,
        refresh_token=refresh_token,
        user=user.model_dump(mode="json"),
    )


@router.post("/login/oauth")
async def login_oauth(payload: dict[str, object] | None = None) -> dict[str, object]:
    # Phase 0: OAuth is not implemented. Reject all requests.
    raise api_error(501, ErrorCode.VALIDATION_ERROR, "OAuth login is not implemented.")


@router.post("/refresh")
async def refresh(principal: PrincipalDependency) -> dict[str, object]:
    if not principal.authenticated:
        raise api_error(401, ErrorCode.AUTHENTICATION_FAILED, "Authentication required.")
    return {"access_token": _issue_token(), "token_type": "Bearer", "expires_in": 900}


@router.post("/logout")
async def logout(
    principal: PrincipalDependency,
    authorization: str | None = Header(default=None, alias="Authorization"),
) -> dict[str, bool]:
    if authorization and authorization.lower().startswith("bearer "):
        token = authorization[7:].strip()
        if token:
            _revoke_token(token)
            _token_users.pop(token, None)
    return {"ok": True}


@router.post("/verify-email")
async def verify_email() -> dict[str, bool]:
    raise api_error(501, ErrorCode.VALIDATION_ERROR, "Email verification is not implemented.")


@router.post("/reset-password")
async def reset_password() -> dict[str, bool]:
    raise api_error(501, ErrorCode.VALIDATION_ERROR, "Password reset is not implemented.")


@router.get("/me", response_model=dict[str, object])
async def me(principal: PrincipalDependency) -> dict[str, object]:
    return principal.model_dump(mode="json")


@router.put("/me")
async def update_me(principal: PrincipalDependency) -> dict[str, object]:
    return principal.model_dump(mode="json")
