"""OAuth2 API routes.

Endpoints:
- GET /api/v1/auth/oauth/providers — list available providers
- GET /api/v1/auth/oauth/login/{provider} — redirect to provider login
- GET /api/v1/auth/oauth/callback/{provider} — handle OAuth callback
"""

from typing import Any

import logging
from fastapi import APIRouter, HTTPException, Query
from fastapi.responses import RedirectResponse, JSONResponse

from backend.app.core.oauth2 import get_oauth_manager, OAuthUser

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1/auth/oauth", tags=["oauth"])


@router.get("/providers")
async def list_providers() -> dict[str, Any]:
    """List available OAuth providers.

    Returns:
        JSON object with list of available provider names.

    Example:
        GET /api/v1/auth/oauth/providers
        Response: {"providers": ["github", "google"]}
    """
    mgr = get_oauth_manager()
    return {"providers": mgr.available_providers}


@router.get("/login/{provider}")
async def oauth_login(provider: str) -> RedirectResponse:
    """Redirect to OAuth provider login page.

    Initiates the OAuth2 authorization code flow by generating
    a state token and redirecting to the provider's authorization endpoint.

    Args:
        provider: OAuth provider name (e.g., 'github', 'google').

    Returns:
        HTTP 302 redirect to provider's authorization URL.

    Raises:
        HTTPException: 404 if provider is not configured.

    Example:
        GET /api/v1/auth/oauth/login/github
        Response: 302 redirect to GitHub OAuth authorize endpoint
    """
    mgr = get_oauth_manager()
    try:
        url, state = mgr.get_login_url(provider)
        logger.debug(f"Generated login URL for provider: {provider}, state: {state}")
    except ValueError as e:
        logger.warning(f"Login request for unknown provider: {provider}")
        raise HTTPException(status_code=404, detail=f"Provider '{provider}' not configured")
    return RedirectResponse(url=url)


@router.get("/callback/{provider}")
async def oauth_callback(
    provider: str, code: str = Query(...), state: str = Query(...)
) -> JSONResponse:
    """Handle OAuth callback after user authorization.

    Completes the OAuth2 authorization code flow by:
    1. Validating the state token (CSRF protection)
    2. Exchanging the authorization code for an access token
    3. Fetching user info from the provider
    4. Returning normalized user information

    Args:
        provider: OAuth provider name.
        code: Authorization code from provider callback.
        state: State token for CSRF validation.

    Returns:
        JSON response with authenticated user information.

    Raises:
        HTTPException: 400 if state token is invalid/expired.
        HTTPException: 502 if token exchange or user info fetch fails.

    Example:
        GET /api/v1/auth/oauth/callback/github?code=abc123&state=xyz789
        Response: {
            "status": "authenticated",
            "provider": "github",
            "provider_user_id": "12345",
            "email": "user@example.com",
            "name": "John Doe",
            "avatar_url": "https://avatars.githubusercontent.com/..."
        }
    """
    mgr = get_oauth_manager()

    # Validate state token
    if not mgr.validate_state(state):
        logger.warning(
            f"Invalid or expired state token for provider: {provider}, state: {state}"
        )
        raise HTTPException(status_code=400, detail="Invalid or expired state token")

    try:
        # Exchange code for access token
        token_data = await mgr.exchange_code(provider, code)
        access_token = token_data.get("access_token")

        if not access_token:
            logger.error(f"No access token in response from {provider}")
            raise HTTPException(
                status_code=502, detail="No access token received from provider"
            )

        # Fetch user info
        user_info = await mgr.get_user_info(provider, access_token)
        logger.info(
            f"Successfully authenticated user from {provider}: {user_info.provider_user_id}"
        )

        # Return user info
        # TODO: Create or lookup internal user, generate session token
        return JSONResponse(
            {
                "status": "authenticated",
                "provider": user_info.provider,
                "provider_user_id": user_info.provider_user_id,
                "email": user_info.email,
                "name": user_info.name,
                "avatar_url": user_info.avatar_url,
                "message": "User authenticated. Session creation pending full integration.",
            }
        )
    except ValueError as e:
        logger.error(f"Unknown provider in callback: {provider}")
        raise HTTPException(status_code=502, detail=f"OAuth flow failed: {str(e)}")
    except Exception as e:
        logger.error(f"OAuth flow failed for {provider}: {str(e)}", exc_info=True)
        raise HTTPException(status_code=502, detail=f"OAuth flow failed: {str(e)}")
