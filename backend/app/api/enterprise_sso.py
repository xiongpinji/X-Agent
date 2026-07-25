"""
企业级SSO/SAML API路由
"""
from __future__ import annotations

import logging
from typing import Any

from fastapi import APIRouter, HTTPException, status
from pydantic import BaseModel

from backend.app.core.enterprise_sso import (
    OAuthConfig,
    OAuthProcessor,
    SAMLConfig,
    SAMLProcessor,
    SSOSessionManager,
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1/enterprise/sso", tags=["enterprise-sso"])

# 初始化管理器
sso_session_manager = SSOSessionManager()


class SAMLConfigRequest(BaseModel):
    """SAML配置请求"""
    entity_id: str
    assertion_consumer_service_url: str
    idp_entity_id: str
    idp_sso_url: str


class OAuthConfigRequest(BaseModel):
    """OAuth配置请求"""
    client_id: str
    client_secret: str
    authorization_endpoint: str
    token_endpoint: str
    userinfo_endpoint: str
    issuer: str


class SAMLAuthResponse(BaseModel):
    """SAML认证响应"""
    request_id: str
    saml_request_b64: str
    redirect_url: str


class OAuthAuthResponse(BaseModel):
    """OAuth认证响应"""
    request_id: str
    authorization_url: str


@router.post("/saml/config", response_model=dict[str, Any])
async def configure_saml(request: SAMLConfigRequest) -> dict[str, Any]:
    """配置SAML 2.0"""
    try:
        config = SAMLConfig(
            entity_id=request.entity_id,
            assertion_consumer_service_url=request.assertion_consumer_service_url,
            idp_entity_id=request.idp_entity_id,
            idp_sso_url=request.idp_sso_url,
        )
        SAMLProcessor(config)

        return {
            "status": "success",
            "message": "SAML configured successfully",
            "entity_id": config.entity_id,
        }
    except Exception as e:
        logger.error(f"Failed to configure SAML: {e}")
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))


@router.post("/saml/auth", response_model=SAMLAuthResponse)
async def initiate_saml_auth() -> SAMLAuthResponse:
    """启动SAML认证"""
    try:
        config = SAMLConfig(
            entity_id="https://xagent.example.com",
            assertion_consumer_service_url="https://xagent.example.com/api/v1/enterprise/sso/saml/acs",
            idp_entity_id="https://idp.example.com",
            idp_sso_url="https://idp.example.com/sso",
        )
        processor = SAMLProcessor(config)
        request_id, saml_request_b64 = processor.generate_auth_request()

        return SAMLAuthResponse(
            request_id=request_id,
            saml_request_b64=saml_request_b64,
            redirect_url=f"{config.idp_sso_url}?SAMLRequest={saml_request_b64}",
        )
    except Exception as e:
        logger.error(f"Failed to initiate SAML auth: {e}")
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))


@router.post("/oauth/config", response_model=dict[str, Any])
async def configure_oauth(request: OAuthConfigRequest) -> dict[str, Any]:
    """配置OAuth 2.0/OIDC"""
    try:
        config = OAuthConfig(
            client_id=request.client_id,
            client_secret=request.client_secret,
            authorization_endpoint=request.authorization_endpoint,
            token_endpoint=request.token_endpoint,
            userinfo_endpoint=request.userinfo_endpoint,
            issuer=request.issuer,
        )
        OAuthProcessor(config)

        return {
            "status": "success",
            "message": "OAuth configured successfully",
            "client_id": config.client_id,
        }
    except Exception as e:
        logger.error(f"Failed to configure OAuth: {e}")
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))


@router.post("/oauth/auth", response_model=OAuthAuthResponse)
async def initiate_oauth_auth() -> OAuthAuthResponse:
    """启动OAuth认证"""
    try:
        config = OAuthConfig(
            client_id="xagent-client",
            client_secret="secret",
            authorization_endpoint="https://oauth.example.com/authorize",
            token_endpoint="https://oauth.example.com/token",
            userinfo_endpoint="https://oauth.example.com/userinfo",
            issuer="https://oauth.example.com",
            redirect_uri="https://xagent.example.com/api/v1/enterprise/sso/oauth/callback",
        )
        processor = OAuthProcessor(config)
        request_id, authorization_url = processor.generate_authorization_url()

        return OAuthAuthResponse(
            request_id=request_id,
            authorization_url=authorization_url,
        )
    except Exception as e:
        logger.error(f"Failed to initiate OAuth auth: {e}")
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))


@router.post("/logout", response_model=dict[str, Any])
async def sso_logout(session_id: str) -> dict[str, Any]:
    """SSO登出"""
    try:
        if sso_session_manager.invalidate_session(session_id):
            return {"status": "success", "message": "Logged out successfully"}
        else:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Session not found")
    except Exception as e:
        logger.error(f"Failed to logout: {e}")
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
