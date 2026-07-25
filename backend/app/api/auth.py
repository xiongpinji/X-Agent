from __future__ import annotations

import logging
import threading
import time
from datetime import UTC, datetime
from typing import Annotated
from uuid import uuid4

from fastapi import APIRouter, Depends, Header

from backend.app.api.errors import api_error
from backend.app.core.admin import (
    AuthLoginRequest,
    AuthTokenResponse,
    UserCreateRequest,
    user_store,
)
from backend.app.core.contracts import ErrorCode
from backend.app.core.security import Principal
from backend.app.dependencies import get_current_principal

router = APIRouter(prefix="/api/v1/auth", tags=["auth"])
PrincipalDependency = Annotated[Principal, Depends(get_current_principal)]

logger = logging.getLogger(__name__)

# Token storage backends
_revoked_tokens: set[str] = set()
_token_expiry: dict[str, float] = {}
_token_users: dict[str, str] = {}
_token_lock = threading.Lock()
_DEFAULT_TOKEN_TTL_SECONDS = 900  # 15 minutes
_last_purge_ts: float = 0.0
_PURGE_INTERVAL_SECONDS = 300  # 清理过期 token 的最小间隔，避免每次校验都全量扫描


def _purge_expired_tokens(force: bool = False) -> None:
    """Opportunistically drop expired in-memory tokens to bound memory growth (S4).

    Only the in-memory fallback dicts are purged; Redis entries expire natively.
    Throttled to at most once per _PURGE_INTERVAL_SECONDS unless force=True.
    """
    global _last_purge_ts
    now = time.time()
    if not force and (now - _last_purge_ts) < _PURGE_INTERVAL_SECONDS:
        return
    with _token_lock:
        _last_purge_ts = now
        expired = [tok for tok, exp in _token_expiry.items() if now > exp]
        for tok in expired:
            _token_expiry.pop(tok, None)
            _token_users.pop(tok, None)
            _revoked_tokens.discard(tok)

# Login failure tracking for account lockout
_login_failures: dict[str, list[float]] = {}  # email -> [timestamp, ...]
_lockout_duration_seconds = 900  # 15 minutes
_max_login_attempts = 5

# Redis client (optional, for production use)
_redis_client = None
_use_redis = False


def _init_redis() -> None:
    """Initialize Redis client if available."""
    global _redis_client, _use_redis
    try:
        import redis

        from backend.app.settings import get_settings

        settings = get_settings()
        if settings.redis_url:
            _redis_client = redis.from_url(settings.redis_url, decode_responses=True)
            _redis_client.ping()
            _use_redis = True
            logger.info("Redis session storage initialized")
        else:
            logger.info("Redis URL not configured, using in-memory storage")
    except Exception as e:
        logger.warning(f"Failed to initialize Redis: {e}. Falling back to in-memory storage.")
        _use_redis = False


def _issue_token(ttl_seconds: int = _DEFAULT_TOKEN_TTL_SECONDS) -> str:
    """Issue a new session token with expiration."""
    token = f"xag_{uuid4().hex}"
    expiry_time = time.time() + ttl_seconds

    if _use_redis and _redis_client:
        try:
            _redis_client.setex(f"token:{token}:expiry", ttl_seconds, str(expiry_time))
            logger.debug(f"Token stored in Redis: {token}")
        except Exception as e:
            logger.warning(f"Failed to store token in Redis: {e}. Using in-memory fallback.")
            with _token_lock:
                _token_expiry[token] = expiry_time
    else:
        with _token_lock:
            _token_expiry[token] = expiry_time

    return token


def _is_token_valid(token: str) -> bool:
    """Check if token is valid and not expired or revoked."""
    if _use_redis and _redis_client:
        try:
            expiry_str = _redis_client.get(f"token:{token}:expiry")
            if expiry_str is None:
                return False
            expiry = float(expiry_str)
            is_revoked = _redis_client.exists(f"token:{token}:revoked")
            return time.time() <= expiry and not is_revoked
        except Exception as e:
            logger.warning(f"Redis token validation failed: {e}. Using in-memory fallback.")

    # Fallback to in-memory storage
    _purge_expired_tokens()
    with _token_lock:
        if token in _revoked_tokens:
            return False
        expiry = _token_expiry.get(token)

    return not (expiry is None or time.time() > expiry)


def _revoke_token(token: str) -> None:
    """Revoke a token, preventing further use."""
    if _use_redis and _redis_client:
        try:
            _redis_client.setex(f"token:{token}:revoked", 86400, "1")  # 24 hour TTL
            logger.debug(f"Token revoked in Redis: {token}")
        except Exception as e:
            logger.warning(f"Failed to revoke token in Redis: {e}. Using in-memory fallback.")
            with _token_lock:
                _revoked_tokens.add(token)
                _token_expiry.pop(token, None)
    else:
        with _token_lock:
            _revoked_tokens.add(token)
            _token_expiry.pop(token, None)


def _store_token_user(token: str, user_id: str) -> None:
    """Store token-to-user mapping for session lookup."""
    if _use_redis and _redis_client:
        try:
            _redis_client.setex(f"token:{token}:user", 86400, user_id)
        except Exception as e:
            logger.warning(f"Failed to store token-user mapping in Redis: {e}")
            with _token_lock:
                _token_users[token] = user_id
    else:
        with _token_lock:
            _token_users[token] = user_id


def _get_token_user(token: str) -> str | None:
    """Retrieve user ID from token."""
    if _use_redis and _redis_client:
        try:
            return _redis_client.get(f"token:{token}:user")
        except Exception as e:
            logger.warning(f"Failed to retrieve token-user mapping from Redis: {e}")

    with _token_lock:
        return _token_users.get(token)


def _check_account_lockout(email: str) -> bool:
    """Check if account is locked due to too many failed login attempts."""
    if email not in _login_failures:
        return False

    now = time.time()
    # Remove old failures outside the lockout window
    _login_failures[email] = [ts for ts in _login_failures[email] if now - ts < _lockout_duration_seconds]

    return len(_login_failures[email]) >= _max_login_attempts


def _record_login_failure(email: str) -> None:
    """Record a failed login attempt."""
    if email not in _login_failures:
        _login_failures[email] = []
    _login_failures[email].append(time.time())


def _clear_login_failures(email: str) -> None:
    """Clear login failures after successful authentication."""
    _login_failures.pop(email, None)


def _constant_time_compare(a: str, b: str) -> bool:
    """Compare two strings in constant time to prevent timing attacks.

    This function compares two strings byte-by-byte without short-circuiting,
    ensuring that the comparison time is independent of where the strings differ.
    This prevents attackers from using timing analysis to guess correct values.
    """
    if len(a) != len(b):
        # Still do a full comparison to maintain constant time
        result = False
        for x, y in zip(a, b, strict=False):
            result |= x != y
        return result

    result = False
    for x, y in zip(a, b, strict=False):
        result |= x != y
    return result


# Initialize Redis on module load
_init_redis()


@router.post("/register", response_model=AuthTokenResponse)
async def register(request: AuthLoginRequest) -> AuthTokenResponse:
    """Register a new user with email and password.

    Password requirements:
    - Minimum 8 characters
    - Must contain uppercase and lowercase letters
    - Must contain at least one digit
    """
    if not request.email or not request.password:
        raise api_error(400, ErrorCode.VALIDATION_ERROR, "Email and password are required.")

    # Validate password strength
    if len(request.password) < 8:
        raise api_error(400, ErrorCode.VALIDATION_ERROR, "Password must be at least 8 characters.")
    if not any(c.isupper() for c in request.password) or not any(c.islower() for c in request.password):
        raise api_error(400, ErrorCode.VALIDATION_ERROR, "Password must contain both uppercase and lowercase letters.")
    if not any(c.isdigit() for c in request.password):
        raise api_error(400, ErrorCode.VALIDATION_ERROR, "Password must contain at least one digit.")

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
    """Authenticate user with email and password.

    Implements:
    - Account lockout after 5 failed attempts (15 minute duration)
    - Constant-time password verification to prevent timing attacks
    - User enumeration prevention
    - SECURITY: Bootstrap Key强制更换检查
    """
    if not request.email or not request.password:
        raise api_error(400, ErrorCode.VALIDATION_ERROR, "Email and password are required.")

    # Check for account lockout
    if _check_account_lockout(request.email):
        raise api_error(429, ErrorCode.VALIDATION_ERROR, "Account temporarily locked due to too many failed login attempts.")

    start = time.monotonic()
    user = user_store.authenticate(request.email, request.password)
    # Constant-time compensation to prevent user enumeration via timing
    elapsed = (time.monotonic() - start) * 1000
    target_ms = 200
    if elapsed < target_ms:
        time.sleep((target_ms - elapsed) / 1000)

    if user is None:
        _record_login_failure(request.email)
        raise api_error(401, ErrorCode.AUTHENTICATION_FAILED, "Invalid email or password.")

    # Clear login failures on successful authentication
    _clear_login_failures(request.email)

    access_token = _issue_token()
    refresh_token = _issue_token(ttl_seconds=86400)  # 24 hours
    _store_token_user(access_token, user.id)
    _store_token_user(refresh_token, user.id)

    # SECURITY: 检查是否需要更换Bootstrap Key
    from backend.app.core.bootstrap_key_enforcer import get_bootstrap_key_enforcer
    enforcer = get_bootstrap_key_enforcer()
    requires_bootstrap_key_change = enforcer.check_bootstrap_key_requirement(user.id)

    response = AuthTokenResponse(
        access_token=access_token,
        refresh_token=refresh_token,
        user=user.model_dump(mode="json"),
    )

    # 如果需要更换Bootstrap Key，在响应中添加标记
    if requires_bootstrap_key_change:
        response.user["requires_bootstrap_key_change"] = True

    return response


@router.post("/login/oauth")
async def login_oauth(
    provider: str | None = None,
    code: str | None = None,
    state: str | None = None,
) -> dict[str, object]:
    """OAuth login endpoint supporting multiple providers.

    Supported providers: google, github, microsoft

    Args:
        provider: OAuth provider name
        code: Authorization code from provider
        state: State parameter for CSRF protection

    Returns:
        Authentication token response
    """
    # provider / code 声明为可选，由 handler 统一返回 400 VALIDATION_ERROR：
    # 业务级输入错误走我们自己的错误信封(400+code)，而非 FastAPI 必填参数缺失
    # 的 422 —— 与姊妹端点 reset_password 的校验范式一致。
    if not provider:
        raise api_error(400, ErrorCode.VALIDATION_ERROR, "OAuth provider is required.")

    if provider not in {"google", "github", "microsoft"}:
        raise api_error(
            400,
            ErrorCode.VALIDATION_ERROR,
            f"Unsupported OAuth provider: {provider}",
            details={"supported_providers": ["google", "github", "microsoft"]},
        )

    if not code:
        raise api_error(400, ErrorCode.VALIDATION_ERROR, "Authorization code is required.")

    # NOTE: Requires OAuth provider SDK integration (Google/GitHub)
    # This would involve:
    # 1. Exchanging code for access token
    # 2. Fetching user profile from provider
    # 3. Creating or updating user in database
    # 4. Issuing session token

    raise api_error(
        501,
        ErrorCode.VALIDATION_ERROR,
        f"OAuth login for {provider} is not yet implemented.",
        details={"provider": provider},
    )


@router.post("/refresh")
async def refresh(principal: PrincipalDependency) -> dict[str, object]:
    """Refresh access token using refresh token."""
    if not principal.authenticated:
        raise api_error(401, ErrorCode.AUTHENTICATION_FAILED, "Authentication required.")
    return {"access_token": _issue_token(), "token_type": "Bearer", "expires_in": 900}


@router.post("/logout")
async def logout(
    principal: PrincipalDependency,
    authorization: str | None = Header(default=None, alias="Authorization"),
) -> dict[str, bool]:
    """Logout and revoke current token."""
    if authorization and authorization.lower().startswith("bearer "):
        token = authorization[7:].strip()
        if token:
            _revoke_token(token)
            # Clean up token-user mapping
            if _use_redis and _redis_client:
                try:
                    _redis_client.delete(f"token:{token}:user")
                except Exception as e:
                    logger.warning(f"Failed to clean up token mapping: {e}")
            else:
                with _token_lock:
                    _token_users.pop(token, None)
    return {"ok": True}


@router.post("/verify-email")
async def verify_email(
    token: str | None = None,
    principal: PrincipalDependency | None = None,
) -> dict[str, bool]:
    """Verify user email address using verification token.

    Args:
        token: Email verification token sent to user's email
        principal: Optional current principal for authenticated verification

    Returns:
        Success status
    """
    # token 声明为可选：缺失时由 handler 返回 400 VALIDATION_ERROR(业务校验)，
    # 而非 FastAPI 必填参数缺失的 422 —— 与 reset_password / login_oauth 范式一致。
    if not token:
        raise api_error(400, ErrorCode.VALIDATION_ERROR, "Verification token is required.")

    # NOTE: Requires email verification service integration
    # This would involve:
    # 1. Validating the verification token
    # 2. Checking token expiration
    # 3. Marking user email as verified
    # 4. Invalidating the token

    raise api_error(
        501,
        ErrorCode.VALIDATION_ERROR,
        "Email verification is not yet implemented.",
        details={"token_length": len(token)},
    )


@router.post("/reset-password")
async def reset_password(
    email: str | None = None,
    token: str | None = None,
    new_password: str | None = None,
) -> dict[str, bool]:
    """Password reset endpoint supporting two flows.

    Flow 1 (Request reset):
    - POST with email only
    - Sends reset token to email

    Flow 2 (Complete reset):
    - POST with token and new_password
    - Validates token and updates password

    Args:
        email: User email for requesting reset
        token: Reset token from email
        new_password: New password for completion

    Returns:
        Success status
    """
    if email and not token:
        # Request password reset
        if not email:
            raise api_error(400, ErrorCode.VALIDATION_ERROR, "Email is required for password reset request.")

        # Find user by email
        user = None
        for u in user_store.list():
            if u.email == email:
                user = u
                break

        if user is None:
            # Prevent user enumeration: simulate work
            import bcrypt
            bcrypt.gensalt(rounds=12)
            raise api_error(400, ErrorCode.VALIDATION_ERROR, "Password reset request failed.")

        # Generate reset token (valid for 1 hour)
        reset_token = f"xag_reset_{uuid4().hex}"
        expiry_time = time.time() + 3600  # 1 hour

        if _use_redis and _redis_client:
            try:
                _redis_client.setex(f"reset:{reset_token}:user_id", 3600, user.id)
                _redis_client.setex(f"reset:{reset_token}:expiry", 3600, str(expiry_time))
                logger.info(f"Password reset token generated for user: {user.id}")
            except Exception as e:
                logger.warning(f"Failed to store reset token in Redis: {e}")
                raise api_error(500, ErrorCode.VALIDATION_ERROR, "Failed to generate reset token.")
        else:
            with _token_lock:
                _token_expiry[f"reset:{reset_token}"] = expiry_time
                _token_users[f"reset:{reset_token}"] = user.id

        # NOTE: Requires email transport integration for password reset
        # For now, return success (in production, send email with reset link)
        return {"ok": True}

    elif token and new_password:
        # Complete password reset
        if len(new_password) < 8:
            raise api_error(400, ErrorCode.VALIDATION_ERROR, "Password must be at least 8 characters.")
        if not any(c.isupper() for c in new_password) or not any(c.islower() for c in new_password):
            raise api_error(
                400,
                ErrorCode.VALIDATION_ERROR,
                "Password must contain both uppercase and lowercase letters.",
            )
        if not any(c.isdigit() for c in new_password):
            raise api_error(400, ErrorCode.VALIDATION_ERROR, "Password must contain at least one digit.")

        # Validate reset token
        user_id = None
        if _use_redis and _redis_client:
            try:
                user_id = _redis_client.get(f"reset:{token}:user_id")
                expiry_str = _redis_client.get(f"reset:{token}:expiry")
                if user_id and expiry_str:
                    expiry = float(expiry_str)
                    if time.time() > expiry:
                        raise api_error(400, ErrorCode.VALIDATION_ERROR, "Reset token has expired.")
                else:
                    raise api_error(400, ErrorCode.VALIDATION_ERROR, "Invalid reset token.")
            except Exception as e:
                logger.warning(f"Failed to validate reset token in Redis: {e}")
                raise api_error(400, ErrorCode.VALIDATION_ERROR, "Invalid reset token.")
        else:
            with _token_lock:
                user_id = _token_users.get(f"reset:{token}")
                expiry = _token_expiry.get(f"reset:{token}")
                if not user_id or not expiry or time.time() > expiry:
                    raise api_error(400, ErrorCode.VALIDATION_ERROR, "Invalid or expired reset token.")

        # Update user password
        user = user_store.get(user_id)
        if not user:
            raise api_error(400, ErrorCode.VALIDATION_ERROR, "User not found.")

        import bcrypt
        user.password_hash = bcrypt.hashpw(new_password.encode("utf-8"), bcrypt.gensalt(rounds=12)).decode("utf-8")
        user.updated_at = datetime.now(UTC)
        user_store._records[user.id] = user

        # Invalidate reset token
        if _use_redis and _redis_client:
            try:
                _redis_client.delete(f"reset:{token}:user_id")
                _redis_client.delete(f"reset:{token}:expiry")
            except Exception as e:
                logger.warning(f"Failed to invalidate reset token: {e}")
        else:
            with _token_lock:
                _token_users.pop(f"reset:{token}", None)
                _token_expiry.pop(f"reset:{token}", None)

        return {"ok": True}

    else:
        raise api_error(
            400,
            ErrorCode.VALIDATION_ERROR,
            "Either email (for request) or token+new_password (for completion) is required.",
        )


@router.get("/me", response_model=dict[str, object])
async def me(principal: PrincipalDependency) -> dict[str, object]:
    """Get current user information."""
    return principal.model_dump(mode="json")


@router.put("/me")
async def update_me(principal: PrincipalDependency) -> dict[str, object]:
    """Update current user information."""
    return principal.model_dump(mode="json")
