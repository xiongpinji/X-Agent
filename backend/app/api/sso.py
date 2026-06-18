"""SSO and Enterprise Authentication API Endpoints."""

from __future__ import annotations

import logging
from typing import Annotated

from fastapi import APIRouter, Depends, Header, Query

from backend.app.api.errors import api_error
from backend.app.core.contracts import ErrorCode
from backend.app.core.security import Principal
from backend.app.core.sso.mfa_manager import MFAManager, MFAMethod
from backend.app.core.sso.oauth_provider import OAuthManager, OAuthProvider
from backend.app.core.sso.session_manager import SessionManager
from backend.app.core.sso.webauthn_provider import WebAuthnProvider
from backend.app.dependencies import get_current_principal
from pydantic import BaseModel, Field

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1/auth", tags=["auth"])
PrincipalDependency = Annotated[Principal, Depends(get_current_principal)]

# Initialize managers (in production, these would be singletons)
oauth_manager = OAuthManager()
mfa_manager = MFAManager()
session_manager = SessionManager()


# ============================================================================
# OAuth 2.0 Endpoints
# ============================================================================


class OAuthLoginRequest(BaseModel):
    """OAuth login request."""

    provider: str
    code: str
    state: str


class OAuthLoginResponse(BaseModel):
    """OAuth login response."""

    access_token: str
    refresh_token: str
    user: dict


@router.post("/sso/oauth/authorize")
async def oauth_authorize(provider: str = Query(...)) -> dict:
    """Get OAuth authorization URL.

    Args:
        provider: OAuth provider (google, github, microsoft)

    Returns:
        Authorization URL and state
    """
    try:
        oauth_provider = OAuthProvider(provider)
    except ValueError:
        raise api_error(
            400,
            ErrorCode.VALIDATION_ERROR,
            f"Unsupported OAuth provider: {provider}",
        )

    session = oauth_manager.create_session(oauth_provider)
    auth_url = oauth_manager.get_authorization_url(oauth_provider, session)

    return {
        "authorization_url": auth_url,
        "state": session.state,
    }


@router.post("/sso/oauth/callback")
async def oauth_callback(request: OAuthLoginRequest) -> OAuthLoginResponse:
    """Handle OAuth callback.

    Args:
        request: OAuth callback request

    Returns:
        Authentication response
    """
    try:
        oauth_provider = OAuthProvider(request.provider)
    except ValueError:
        raise api_error(
            400,
            ErrorCode.VALIDATION_ERROR,
            f"Unsupported OAuth provider: {request.provider}",
        )

    try:
        user_info, token = await oauth_manager.authenticate(
            oauth_provider,
            request.code,
            request.state,
        )
    except ValueError as e:
        raise api_error(401, ErrorCode.AUTHENTICATION_FAILED, str(e))

    # TODO: Create or update user in database
    # TODO: Create session
    # TODO: Issue tokens

    return OAuthLoginResponse(
        access_token="token",
        refresh_token="refresh_token",
        user={
            "email": user_info.email,
            "name": user_info.name,
        },
    )


# ============================================================================
# MFA Endpoints
# ============================================================================


class MFASetupRequest(BaseModel):
    """MFA setup request."""

    method: str


class MFASetupResponse(BaseModel):
    """MFA setup response."""

    secret: str | None = None
    provisioning_uri: str | None = None
    backup_codes: list[str] | None = None
    challenge_id: str | None = None


@router.post("/mfa/setup")
async def setup_mfa(
    request: MFASetupRequest,
    principal: PrincipalDependency,
) -> MFASetupResponse:
    """Setup MFA for user.

    Args:
        request: MFA setup request
        principal: Current principal

    Returns:
        MFA setup response
    """
    if not principal.authenticated:
        raise api_error(401, ErrorCode.AUTHENTICATION_FAILED, "Authentication required.")

    try:
        method = MFAMethod(request.method)
    except ValueError:
        raise api_error(
            400,
            ErrorCode.VALIDATION_ERROR,
            f"Unsupported MFA method: {request.method}",
        )

    if method == MFAMethod.TOTP:
        secret, provisioning_uri = mfa_manager.setup_totp(principal.user_id)
        return MFASetupResponse(
            secret=secret,
            provisioning_uri=provisioning_uri,
        )

    elif method == MFAMethod.SMS or method == MFAMethod.EMAIL:
        challenge = await mfa_manager.create_challenge(
            principal.user_id,
            method,
            metadata={"email": principal.user_id},
        )
        return MFASetupResponse(challenge_id=challenge.challenge_id)

    raise api_error(501, ErrorCode.VALIDATION_ERROR, f"MFA method not implemented: {method}")


class MFAVerifyRequest(BaseModel):
    """MFA verification request."""

    challenge_id: str
    code: str


@router.post("/mfa/verify")
async def verify_mfa(
    request: MFAVerifyRequest,
    principal: PrincipalDependency,
) -> dict:
    """Verify MFA code.

    Args:
        request: MFA verification request
        principal: Current principal

    Returns:
        Verification result
    """
    if not principal.authenticated:
        raise api_error(401, ErrorCode.AUTHENTICATION_FAILED, "Authentication required.")

    if not mfa_manager.verify_challenge(request.challenge_id, request.code):
        raise api_error(401, ErrorCode.AUTHENTICATION_FAILED, "Invalid MFA code.")

    # TODO: Mark session as MFA verified
    # session_manager.verify_mfa(session_id, method)

    return {"verified": True}


# ============================================================================
# Session Management Endpoints
# ============================================================================


class SessionListResponse(BaseModel):
    """Session list response."""

    sessions: list[dict]


@router.get("/sessions")
async def list_sessions(principal: PrincipalDependency) -> SessionListResponse:
    """Get all active sessions for user.

    Args:
        principal: Current principal

    Returns:
        List of sessions
    """
    if not principal.authenticated:
        raise api_error(401, ErrorCode.AUTHENTICATION_FAILED, "Authentication required.")

    sessions = session_manager.get_user_sessions(principal.user_id)
    return SessionListResponse(
        sessions=[
            {
                "session_id": s.session_id,
                "created_at": s.created_at.isoformat(),
                "last_activity": s.last_activity.isoformat(),
                "ip_address": s.ip_address,
                "device_name": s.device_name,
                "mfa_verified": s.mfa_verified,
                "trusted_device": s.trusted_device,
            }
            for s in sessions
        ]
    )


@router.delete("/sessions/{session_id}")
async def revoke_session(
    session_id: str,
    principal: PrincipalDependency,
) -> dict:
    """Revoke a session.

    Args:
        session_id: Session ID to revoke
        principal: Current principal

    Returns:
        Revocation result
    """
    if not principal.authenticated:
        raise api_error(401, ErrorCode.AUTHENTICATION_FAILED, "Authentication required.")

    session = session_manager.get_session(session_id)
    if not session or session.user_id != principal.user_id:
        raise api_error(404, ErrorCode.VALIDATION_ERROR, "Session not found.")

    session_manager.revoke_session(session_id)
    return {"revoked": True}


@router.post("/sessions/revoke-all")
async def revoke_all_sessions(
    principal: PrincipalDependency,
    exclude_current: bool = Query(True),
) -> dict:
    """Revoke all sessions for user.

    Args:
        principal: Current principal
        exclude_current: Whether to exclude current session

    Returns:
        Revocation result
    """
    if not principal.authenticated:
        raise api_error(401, ErrorCode.AUTHENTICATION_FAILED, "Authentication required.")

    exclude_session_id = None
    if exclude_current and principal.api_key_id:
        # TODO: Get current session ID from principal
        pass

    count = session_manager.revoke_user_sessions(principal.user_id, exclude_session_id)
    return {"revoked_count": count}


# ============================================================================
# WebAuthn Endpoints
# ============================================================================


class WebAuthnRegistrationStartRequest(BaseModel):
    """WebAuthn registration start request."""

    username: str


class WebAuthnRegistrationStartResponse(BaseModel):
    """WebAuthn registration start response."""

    challenge_id: str
    options: dict


@router.post("/webauthn/register/start")
async def webauthn_register_start(
    request: WebAuthnRegistrationStartRequest,
    principal: PrincipalDependency,
) -> WebAuthnRegistrationStartResponse:
    """Start WebAuthn registration.

    Args:
        request: Registration start request
        principal: Current principal

    Returns:
        Registration challenge
    """
    if not principal.authenticated:
        raise api_error(401, ErrorCode.AUTHENTICATION_FAILED, "Authentication required.")

    raise api_error(
        501,
        ErrorCode.VALIDATION_ERROR,
        "WebAuthn registration is disabled until standards-compliant attestation verification is configured.",
    )


class WebAuthnRegistrationCompleteRequest(BaseModel):
    """WebAuthn registration complete request."""

    challenge_id: str
    credential_id: str
    public_key: str
    device_name: str | None = None


@router.post("/webauthn/register/complete")
async def webauthn_register_complete(
    request: WebAuthnRegistrationCompleteRequest,
    principal: PrincipalDependency,
) -> dict:
    """Complete WebAuthn registration.

    Args:
        request: Registration complete request
        principal: Current principal

    Returns:
        Registration result
    """
    if not principal.authenticated:
        raise api_error(401, ErrorCode.AUTHENTICATION_FAILED, "Authentication required.")

    raise api_error(
        501,
        ErrorCode.VALIDATION_ERROR,
        "WebAuthn registration is disabled until standards-compliant attestation verification is configured.",
    )


class WebAuthnAuthenticationStartResponse(BaseModel):
    """WebAuthn authentication start response."""

    challenge_id: str
    options: dict


@router.post("/webauthn/authenticate/start")
async def webauthn_authenticate_start() -> WebAuthnAuthenticationStartResponse:
    """Start WebAuthn authentication.

    Returns:
        Authentication challenge
    """
    raise api_error(
        501,
        ErrorCode.VALIDATION_ERROR,
        "WebAuthn authentication is disabled until standards-compliant assertion verification is configured.",
    )


class WebAuthnAuthenticationCompleteRequest(BaseModel):
    """WebAuthn authentication complete request."""

    challenge_id: str
    credential_id: str
    signature: str
    client_data: str


@router.post("/webauthn/authenticate/complete")
async def webauthn_authenticate_complete(
    request: WebAuthnAuthenticationCompleteRequest,
) -> dict:
    """Complete WebAuthn authentication.

    Args:
        request: Authentication complete request

    Returns:
        Authentication result
    """
    raise api_error(
        501,
        ErrorCode.VALIDATION_ERROR,
        "WebAuthn authentication is disabled until standards-compliant assertion verification is configured.",
    )


# ============================================================================
# Conditional Access Endpoints
# ============================================================================


class ConditionalAccessPolicyRequest(BaseModel):
    """Conditional access policy request."""

    name: str
    conditions: dict
    grant_controls: dict
    session_controls: dict


@router.post("/conditional-access/policies")
async def create_conditional_access_policy(
    request: ConditionalAccessPolicyRequest,
    principal: PrincipalDependency,
) -> dict:
    """Create conditional access policy.

    Args:
        request: Policy request
        principal: Current principal

    Returns:
        Created policy
    """
    if not principal.authenticated or principal.role != "admin":
        raise api_error(403, ErrorCode.VALIDATION_ERROR, "Admin access required.")

    # TODO: Create and store policy
    # policy = ConditionalAccessPolicy(
    #     name=request.name,
    #     conditions=request.conditions,
    #     grant_controls=request.grant_controls,
    #     session_controls=request.session_controls,
    # )
    # session_manager.add_conditional_policy(policy)

    return {"policy_id": "policy_id"}


@router.get("/conditional-access/policies")
async def list_conditional_access_policies(
    principal: PrincipalDependency,
) -> dict:
    """List conditional access policies.

    Args:
        principal: Current principal

    Returns:
        List of policies
    """
    if not principal.authenticated or principal.role != "admin":
        raise api_error(403, ErrorCode.VALIDATION_ERROR, "Admin access required.")

    # TODO: Retrieve policies
    return {"policies": []}
