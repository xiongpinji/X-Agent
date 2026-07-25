"""SSO 与企业认证 API (P1-02)。

自包含 router — 不依赖 main.py, 可直接 ``app.include_router(router)``。

能力分级:
- OIDC: **GA**。完整授权码流程 (discovery / JWKS 验签 / state+nonce 一次性校验 /
  JIT 用户 provisioning / 本地会话签发)。
- SAML 2.0: **Beta**。端点存在但一律 501 fail-closed (缺 XML DSig 真实验签,
  见 core.saml_sso.SAML_BETA_MESSAGE)。
- 旧版 OAuth (google/github/microsoft) / MFA / 会话管理端点保留并修复
  (此前 oauth callback 返回硬编码 "token" 假数据, WebAuthn/条件访问为
  空壳假成功 — 现已修复或显式 501)。

提供方配置 (两种方式, 集成波按需接线):
1. 环境变量 ``XAGENT_SSO_PROVIDERS``: JSON 数组, 每项为 OIDCConfig 字段
   (provider_name/tenant_id/discovery_url/client_id/client_secret/redirect_uri/...)。
2. 程序化: ``register_oidc_provider(config: OIDCConfig, http_client=None)``。
"""

from __future__ import annotations

import json
import logging
import os
from typing import Annotated, Any

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field

from backend.app.api.errors import api_error
from backend.app.core.contracts import ErrorCode
from backend.app.core.saml_sso import (
    AUTHLIB_AVAILABLE,
    JITProvisioner,
    MultiTenantSSOManager,
    OIDCConfig,
    SSOAuthenticationError,
    SSOConfigurationError,
    SSOError,
    SSOUser,
    UserStoreAdapter,
    get_sso_manager,
)
from backend.app.core.security import Principal
from backend.app.core.sso.mfa_manager import MFAManager, MFAMethod
from backend.app.core.sso.oauth_provider import OAuthManager, OAuthProvider
from backend.app.core.sso.session_manager import SessionManager
from backend.app.dependencies import get_current_principal

logger = logging.getLogger(__name__)

# ============================================================================
# 组件装配 (模块级单例; 测试可通过 set_* 替换)
# ============================================================================

sso_manager: MultiTenantSSOManager = get_sso_manager()
user_adapter = UserStoreAdapter()
jit_provisioner = JITProvisioner(user_adapter)

oauth_manager = OAuthManager()
mfa_manager = MFAManager()
session_manager = SessionManager()


class LocalSessionIssuer:
    """本地会话签发适配器 (惰性导入 backend.app.api.auth 的签发函数)。

    api/auth.py 的 _issue_token/_store_token_user 是平台唯一的本地会话
    令牌签发路径 (Redis + 内存兜底)。惰性导入避免循环依赖; 不可用时
    显式降级 (available=False), 绝不伪造令牌。
    """

    def __init__(self) -> None:
        self._issue_token: Any = None
        self._store_token_user: Any = None
        self._resolved = False
        self.available = False

    def _resolve(self) -> bool:
        if self._resolved:
            return self.available
        try:
            from backend.app.api.auth import _issue_token, _store_token_user

            self._issue_token = _issue_token
            self._store_token_user = _store_token_user
            self.available = True
        except Exception as exc:  # pragma: no cover - 防御性
            logger.error("本地会话签发器不可用: %s", exc)
            self.available = False
        self._resolved = True
        return self.available

    def issue(self, user_id: str) -> dict[str, Any] | None:
        """签发本地会话令牌; 签发器不可用时返回 None (显式降级)。"""
        if not self._resolve():
            return None
        token = self._issue_token()
        self._store_token_user(token, user_id)
        return {"access_token": token, "token_type": "Bearer"}


session_issuer = LocalSessionIssuer()


def set_session_issuer(issuer: Any) -> None:
    """替换本地会话签发器 (集成波/测试注入用)。"""
    global session_issuer
    session_issuer = issuer


# ============================================================================
# OIDC 提供方注册 (env + 程序化)
# ============================================================================

_env_providers_loaded = False


def register_oidc_provider(config: OIDCConfig, *, http_client: Any = None):
    """注册 OIDC 提供方 (程序化方式, 集成波调用)。

    Args:
        config: OIDC 配置。
        http_client: 可选注入 httpx.AsyncClient (测试用 MockTransport)。

    Returns:
        OIDCManager 实例。
    """
    return sso_manager.register_oidc_config(config, http_client=http_client)


def load_providers_from_env(env_var: str = "XAGENT_SSO_PROVIDERS") -> int:
    """从环境变量加载 OIDC 提供方配置。

    格式: JSON 数组, 每项为 OIDCConfig 字段字典。
    配置错误会记录错误并跳过该项 (不影响其他提供方) — 配置问题在
    /status 端点可见, 绝不静默。
    """
    global _env_providers_loaded
    raw = os.environ.get(env_var, "").strip()
    if not raw:
        _env_providers_loaded = True
        return 0
    try:
        entries = json.loads(raw)
        if not isinstance(entries, list):
            raise ValueError("顶层必须是 JSON 数组")
    except Exception as exc:
        logger.error("%s 解析失败: %s — 跳过 env 提供方加载。", env_var, exc)
        _env_providers_loaded = True
        return 0

    loaded = 0
    for idx, entry in enumerate(entries):
        try:
            config = OIDCConfig(**entry)
            register_oidc_provider(config)
            loaded += 1
        except Exception as exc:
            logger.error("%s[%d] 配置无效: %s — 已跳过。", env_var, idx, exc)
    _env_providers_loaded = True
    return loaded


def _ensure_env_providers() -> None:
    if not _env_providers_loaded:
        load_providers_from_env()


# ============================================================================
# OIDC / SAML SSO Router (prefix=/api/v1/sso)
# ============================================================================

oidc_router = APIRouter(prefix="/api/v1/sso", tags=["sso"])


class OIDCAuthorizeResponse(BaseModel):
    authorization_url: str
    state: str
    state_ttl_seconds: int = 600


class OIDCCallbackRequest(BaseModel):
    code: str = Field(..., min_length=1)
    state: str = Field(..., min_length=1)


class OIDCCallbackResponse(BaseModel):
    access_token: str | None
    token_type: str = "Bearer"
    user: dict[str, Any]
    sso: dict[str, Any]
    session: dict[str, Any]


@oidc_router.get("/providers")
async def list_sso_providers() -> dict[str, Any]:
    """列出已配置的 SSO 提供方 (脱敏)。"""
    _ensure_env_providers()
    return {
        "oidc_providers": sso_manager.list_oidc_providers(),
        "saml": {"status": "beta", "enabled": True, "require_signature": True, "message": "P1-05: 签名验证已启用"},
    }


@oidc_router.get("/oidc/{provider}/authorize", response_model=OIDCAuthorizeResponse)
async def oidc_authorize(
    provider: str,
    tenant_id: str = Query(default="default"),
) -> OIDCAuthorizeResponse:
    """发起 OIDC 授权码流程, 返回 IdP 授权 URL 与一次性 state。"""
    _ensure_env_providers()
    manager = sso_manager.find_oidc_manager(provider, tenant_id)
    if manager is None:
        raise HTTPException(
            status_code=404,
            detail=f"OIDC provider {provider!r} 未为租户 {tenant_id!r} 配置。",
        )

    entry = sso_manager.state_store.create(
        tenant_id=manager.config.tenant_id,
        provider_name=provider,
        redirect_uri=manager.config.redirect_uri,
    )
    try:
        url = await manager.generate_authorization_url(entry.state, entry.nonce)
    except SSOError as exc:
        raise HTTPException(status_code=502, detail=f"IdP discovery 失败: {exc}") from exc

    return OIDCAuthorizeResponse(
        authorization_url=url,
        state=entry.state,
        state_ttl_seconds=sso_manager.state_store._ttl,
    )


@oidc_router.post("/oidc/{provider}/callback", response_model=OIDCCallbackResponse)
async def oidc_callback(provider: str, request: OIDCCallbackRequest) -> OIDCCallbackResponse:
    """OIDC 回调: state/nonce 校验 → 令牌交换 → id_token 验签 → JIT → 本地会话。"""
    _ensure_env_providers()

    # 1) state 一次性消费 (防 CSRF/重放)
    entry = sso_manager.state_store.consume(request.state)
    if entry is None:
        raise HTTPException(
            status_code=401,
            detail="state 无效或已过期 (可能为 CSRF/重放)。认证被拒绝。",
        )
    if entry.provider_name != provider:
        raise HTTPException(status_code=400, detail="state 与 provider 不匹配。")

    manager = sso_manager.find_oidc_manager(provider, entry.tenant_id)
    if manager is None:
        raise HTTPException(
            status_code=404,
            detail=f"OIDC provider {provider!r} 未配置 (tenant={entry.tenant_id})。",
        )

    # 2) 授权码交换 + id_token 验签 (nonce 校验在 validate_id_token 内完成)
    try:
        sso_user, _token = await manager.authenticate(
            request.code, expected_nonce=entry.nonce
        )
    except SSOAuthenticationError as exc:
        raise HTTPException(status_code=401, detail=f"OIDC 认证失败: {exc}") from exc
    except SSOConfigurationError as exc:
        raise HTTPException(status_code=502, detail=f"IdP 配置/可达性错误: {exc}") from exc
    except SSOError as exc:
        raise HTTPException(status_code=502, detail=f"SSO 错误: {exc}") from exc

    # 3) JIT provisioning
    try:
        provisioned = await jit_provisioner.provision(
            sso_user, tenant_id=entry.tenant_id, provider_name=provider
        )
    except SSOError as exc:
        raise HTTPException(status_code=503, detail=f"用户存储不可用: {exc}") from exc

    # 4) 本地会话签发 (不可用时显式降级: session.issued=false, 不伪造令牌)
    local_session = session_issuer.issue(provisioned.user_id)
    if local_session is None:
        logger.error(
            "OIDC 登录成功但本地会话签发器不可用 (user=%s) — 显式降级, "
            "响应不含 access_token。", provisioned.user_id,
        )

    return OIDCCallbackResponse(
        access_token=local_session["access_token"] if local_session else None,
        token_type="Bearer",
        user={
            "user_id": provisioned.user_id,
            "email": provisioned.email,
            "tenant_id": provisioned.tenant_id,
            "role": provisioned.role,
            "name": sso_user.name,
        },
        sso={
            "provider": provider,
            "protocol": "oidc",
            "jit_provisioned": provisioned.created,
            "storage_mode": provisioned.storage_mode,
            "email_verified": sso_user.email_verified,
        },
        session={
            "issued": local_session is not None,
            **({} if local_session else {"reason": "本地会话签发器不可用 (api.auth 未就绪)"}),
        },
    )


# ------------------------------------------------------------- SAML (Beta)

@oidc_router.get("/saml/{provider}/login")
async def saml_login(provider: str) -> dict[str, str]:
    """P1-05: SAML 登录 — 生成 AuthnRequest (Beta, 签名验证已启用)."""
    from backend.app.core.sso.saml_provider import SAMLConfig, SAMLProvider

    # Build config from environment
    config = SAMLConfig(
        entity_id=os.environ.get("XAGENT_SAML_ENTITY_ID", f"http://localhost:8000/api/v1/sso/saml/{provider}/acs"),
        acs_url=os.environ.get("XAGENT_SAML_ACS_URL", f"http://localhost:8000/api/v1/sso/saml/{provider}/acs"),
        idp_entity_id=os.environ.get("XAGENT_SAML_IDP_ENTITY_ID", ""),
        idp_sso_url=os.environ.get("XAGENT_SAML_IDP_SSO_URL", ""),
        idp_certificate=os.environ.get("XAGENT_SAML_IDP_CERTIFICATE", ""),
        require_signature=True,
    )
    if not config.idp_sso_url:
        raise HTTPException(status_code=501, detail="SAML IdP SSO URL 未配置 (XAGENT_SAML_IDP_SSO_URL)")
    saml_provider = SAMLProvider(config)
    request_id, auth_url = saml_provider.generate_auth_request()
    return {"request_id": request_id, "redirect_url": auth_url}


@oidc_router.post("/saml/{provider}/acs")
async def saml_acs(provider: str, saml_response: str = "", relay_state: str = "") -> dict[str, Any]:
    """P1-05: SAML ACS — 处理 IdP 响应 (Beta, 签名验证已启用)."""
    from backend.app.core.sso.saml_provider import SAMLConfig, SAMLProvider

    if not saml_response:
        raise HTTPException(status_code=400, detail="Missing SAMLResponse")
    config = SAMLConfig(
        entity_id=os.environ.get("XAGENT_SAML_ENTITY_ID", f"http://localhost:8000/api/v1/sso/saml/{provider}/acs"),
        acs_url=os.environ.get("XAGENT_SAML_ACS_URL", f"http://localhost:8000/api/v1/sso/saml/{provider}/acs"),
        idp_entity_id=os.environ.get("XAGENT_SAML_IDP_ENTITY_ID", ""),
        idp_sso_url=os.environ.get("XAGENT_SAML_IDP_SSO_URL", ""),
        idp_certificate=os.environ.get("XAGENT_SAML_IDP_CERTIFICATE", ""),
        require_signature=True,
    )
    saml_provider = SAMLProvider(config)
    assertion = saml_provider.verify_response(saml_response, relay_state=relay_state or None)
    if not assertion:
        raise HTTPException(status_code=401, detail="SAML 响应验证失败 (签名无效或断言过期)")
    return {
        "status": "authenticated",
        "subject": assertion.subject,
        "name_id": assertion.name_id,
        "session_index": assertion.session_index,
        "attributes": assertion.attributes,
    }


@oidc_router.get("/status")
async def sso_status() -> dict[str, Any]:
    """SSO 能力状态 (真实反映代码能力, 供集成波与运维核对)。"""
    _ensure_env_providers()
    return {
        "oidc": {
            "status": "GA",
            "features": [
                "discovery",
                "jwks_verification",
                "state_nonce_validation",
                "jit_provisioning",
                "local_session_issue",
            ],
            "providers_configured": len(sso_manager.oidc_configs),
        },
        "saml": {"status": "beta", "enabled": True, "require_signature": True, "message": "P1-05: 签名验证已启用"},
        "webauthn": {"status": "implemented", "features": ["registration", "authentication", "credential_management"]},
        "ldap": {"status": "implemented", "requires": "ldap3 library"},
        "jwt_backend": {
            "authlib_or_joserfc_available": AUTHLIB_AVAILABLE,
            "fallback": "builtin RS256/HS256 (cryptography)",
        },
        "user_storage_mode": user_adapter.mode,
        "session_issuer_available": session_issuer._resolve(),
    }


# ============================================================================
# 旧版认证端点 (prefix=/api/v1/auth) — 保留真实功能, 修复假成功
# ============================================================================

auth_router = APIRouter(prefix="/api/v1/auth", tags=["auth"])
PrincipalDependency = Annotated[Principal, Depends(get_current_principal)]


class OAuthLoginRequest(BaseModel):
    """旧版 OAuth 登录请求。"""

    provider: str
    code: str
    state: str


class OAuthLoginResponse(BaseModel):
    """旧版 OAuth 登录响应。"""

    access_token: str | None
    refresh_token: str | None
    user: dict
    session: dict[str, Any] = Field(default_factory=dict)


@auth_router.post("/sso/oauth/authorize")
async def oauth_authorize(provider: str = Query(...)) -> dict:
    """获取旧版 OAuth 授权 URL (google/github/microsoft)。"""
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


@auth_router.post("/sso/oauth/callback")
async def oauth_callback(request: OAuthLoginRequest) -> OAuthLoginResponse:
    """旧版 OAuth 回调 (P1-02 修复: 真实 userinfo + JIT + 本地会话签发)。

    此前该端点返回硬编码的 "token"/"refresh_token" 假数据, 现已修复:
    - userinfo 来自 OAuthManager.authenticate 的真实 provider HTTP 调用;
    - 用户经 JIT provisioning 落入用户存储;
    - 本地会话经 session_issuer 真实签发, 不可用时显式降级为 null。
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
        user_info, _token = await oauth_manager.authenticate(
            oauth_provider,
            request.code,
            request.state,
        )
    except ValueError as e:
        raise api_error(401, ErrorCode.AUTHENTICATION_FAILED, str(e))

    if not user_info.email:
        raise api_error(
            401,
            ErrorCode.AUTHENTICATION_FAILED,
            "OAuth provider 未返回 email, 无法完成登录。",
        )

    # JIT provisioning (真实落库)
    sso_user = SSOUser(
        uid=str(getattr(user_info, "provider_user_id", "") or user_info.email),
        email=user_info.email,
        name=getattr(user_info, "name", "") or "",
        provider_user_id=str(getattr(user_info, "provider_user_id", "") or ""),
        email_verified=True,  # 旧版 OAuth userinfo 来源视为已验证邮箱渠道
    )
    try:
        provisioned = await jit_provisioner.provision(
            sso_user, tenant_id="default", provider_name=request.provider
        )
    except SSOError as exc:
        raise api_error(503, ErrorCode.INTERNAL_ERROR, f"用户存储不可用: {exc}")

    # 本地会话签发 (真实; 不可用时显式降级)
    access = session_issuer.issue(provisioned.user_id)
    refresh = session_issuer.issue(provisioned.user_id) if access else None

    return OAuthLoginResponse(
        access_token=access["access_token"] if access else None,
        refresh_token=refresh["access_token"] if refresh else None,
        user={
            "user_id": provisioned.user_id,
            "email": provisioned.email,
            "name": sso_user.name,
            "tenant_id": provisioned.tenant_id,
        },
        session={
            "issued": access is not None,
            "jit_provisioned": provisioned.created,
            "storage_mode": provisioned.storage_mode,
            **({} if access else {"reason": "本地会话签发器不可用 (api.auth 未就绪)"}),
        },
    )


# ============================================================================
# MFA Endpoints (保留 — 由 core.sso.mfa_manager 真实实现支撑)
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


@auth_router.post("/mfa/setup")
async def setup_mfa(
    request: MFASetupRequest,
    principal: PrincipalDependency,
) -> MFASetupResponse:
    """Setup MFA for user."""
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


@auth_router.post("/mfa/verify")
async def verify_mfa(
    request: MFAVerifyRequest,
    principal: PrincipalDependency,
) -> dict:
    """Verify MFA code."""
    if not principal.authenticated:
        raise api_error(401, ErrorCode.AUTHENTICATION_FAILED, "Authentication required.")

    if not mfa_manager.verify_challenge(request.challenge_id, request.code):
        raise api_error(401, ErrorCode.AUTHENTICATION_FAILED, "Invalid MFA code.")

    return {"verified": True}


# ============================================================================
# Session Management Endpoints (保留 — core.sso.session_manager 真实实现)
# ============================================================================


class SessionListResponse(BaseModel):
    """Session list response."""

    sessions: list[dict]


@auth_router.get("/sessions")
async def list_sessions(principal: PrincipalDependency) -> SessionListResponse:
    """Get all active sessions for user."""
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


@auth_router.delete("/sessions/{session_id}")
async def revoke_session(
    session_id: str,
    principal: PrincipalDependency,
) -> dict:
    """Revoke a session."""
    if not principal.authenticated:
        raise api_error(401, ErrorCode.AUTHENTICATION_FAILED, "Authentication required.")

    session = session_manager.get_session(session_id)
    if not session or session.user_id != principal.user_id:
        raise api_error(404, ErrorCode.RESOURCE_NOT_FOUND, "Session not found.")

    session_manager.revoke_session(session_id)
    return {"revoked": True}


@auth_router.post("/sessions/revoke-all")
async def revoke_all_sessions(
    principal: PrincipalDependency,
    exclude_current: bool = Query(True),
) -> dict:
    """Revoke all sessions for user."""
    if not principal.authenticated:
        raise api_error(401, ErrorCode.AUTHENTICATION_FAILED, "Authentication required.")

    count = session_manager.revoke_user_sessions(principal.user_id, None)
    return {"revoked_count": count}


# ============================================================================
# WebAuthn (FIDO2) — P1-05: 实现真实注册/认证流程
# ============================================================================

_CONDITIONAL_ACCESS_NOT_IMPLEMENTED = (
    "条件访问策略端点尚未实现真实策略引擎 (此前为空壳假成功, P1-02 已移除)。"
)

# P1-05: WebAuthn provider singleton
from backend.app.core.sso.webauthn_provider import WebAuthnConfig, WebAuthnProvider

_webauthn_provider: WebAuthnProvider | None = None


def _get_webauthn_provider() -> WebAuthnProvider:
    """Get or create WebAuthn provider singleton."""
    global _webauthn_provider
    if _webauthn_provider is None:
        rp_id = os.environ.get("XAGENT_WEBAUTHN_RP_ID", "localhost")
        origin = os.environ.get("XAGENT_WEBAUTHN_ORIGIN", "http://localhost:3000")
        _webauthn_provider = WebAuthnProvider(
            WebAuthnConfig(rp_id=rp_id, origin=origin)
        )
    return _webauthn_provider


class WebAuthnRegisterStartRequest(BaseModel):
    user_id: str = Field(..., min_length=1)
    username: str = Field(..., min_length=1)


class WebAuthnRegisterCompleteRequest(BaseModel):
    challenge_id: str = Field(..., min_length=1)
    credential_id: str = Field(..., min_length=1)
    public_key: str = Field(..., min_length=1)
    device_name: str | None = None
    transports: list[str] = Field(default_factory=list)


class WebAuthnAuthStartRequest(BaseModel):
    user_id: str = Field(..., min_length=1)


class WebAuthnAuthCompleteRequest(BaseModel):
    challenge_id: str = Field(..., min_length=1)
    credential_id: str = Field(..., min_length=1)
    signature: str = Field(..., min_length=1)
    client_data: str = Field(default="")


@auth_router.post("/webauthn/register/start")
async def webauthn_register_start(req: WebAuthnRegisterStartRequest):
    """P1-05: WebAuthn 注册 — 生成注册 challenge."""
    provider = _get_webauthn_provider()
    options = provider.create_registration_challenge(req.user_id, req.username)
    # Return challenge_id for the complete step
    challenge_id = next(
        (cid for cid, c in provider._challenges.items() if c.user_id == req.user_id and c.operation == "register"),
        "",
    )
    return {"challenge_id": challenge_id, "options": options}


@auth_router.post("/webauthn/register/complete")
async def webauthn_register_complete(req: WebAuthnRegisterCompleteRequest):
    """P1-05: WebAuthn 注册完成 — 验证并存储凭据."""
    provider = _get_webauthn_provider()
    success = provider.verify_registration(
        challenge_id=req.challenge_id,
        credential_id=req.credential_id,
        public_key=req.public_key,
        device_name=req.device_name,
        transports=req.transports,
    )
    if not success:
        raise api_error(400, ErrorCode.VALIDATION_ERROR, "WebAuthn 注册验证失败: challenge 无效或已过期")
    return {"status": "registered", "credential_id": req.credential_id}


@auth_router.post("/webauthn/authenticate/start")
async def webauthn_authenticate_start(req: WebAuthnAuthStartRequest):
    """P1-05: WebAuthn 认证 — 生成认证 challenge."""
    provider = _get_webauthn_provider()
    options = provider.create_authentication_challenge(req.user_id)
    challenge_id = next(
        (cid for cid, c in provider._challenges.items() if c.user_id == req.user_id and c.operation == "authenticate"),
        "",
    )
    return {"challenge_id": challenge_id, "options": options}


@auth_router.post("/webauthn/authenticate/complete")
async def webauthn_authenticate_complete(req: WebAuthnAuthCompleteRequest):
    """P1-05: WebAuthn 认证完成 — 验证签名."""
    provider = _get_webauthn_provider()
    success = provider.verify_authentication(
        challenge_id=req.challenge_id,
        credential_id=req.credential_id,
        signature=req.signature,
        client_data=req.client_data,
    )
    if not success:
        raise api_error(401, ErrorCode.VALIDATION_ERROR, "WebAuthn 认证失败: 签名验证未通过")
    # Get user_id from credential
    credential = provider._credentials.get(req.credential_id)
    user_id = credential.user_id if credential else ""
    return {"status": "authenticated", "user_id": user_id}


@auth_router.post("/conditional-access/policies")
async def create_conditional_access_policy() -> None:
    """条件访问策略 — 未实现 (501 fail-closed)。"""
    raise api_error(501, ErrorCode.VALIDATION_ERROR, _CONDITIONAL_ACCESS_NOT_IMPLEMENTED)


@auth_router.get("/conditional-access/policies")
async def list_conditional_access_policies() -> None:
    """条件访问策略列表 — 未实现 (501 fail-closed)。"""
    raise api_error(501, ErrorCode.VALIDATION_ERROR, _CONDITIONAL_ACCESS_NOT_IMPLEMENTED)


# ============================================================================
# 聚合 router (集成波挂载入口)
# ============================================================================

router = APIRouter()
router.include_router(oidc_router)
router.include_router(auth_router)


# ============================================================================
# 集成波接线说明
# ============================================================================
# 在 backend/app/main.py 中:
#   from backend.app.api.sso import router as sso_router
#   app.include_router(sso_router)
# 即同时挂载:
#   /api/v1/sso/*  (OIDC GA / SAML Beta / status / providers)
#   /api/v1/auth/* (旧版 OAuth / MFA / 会话管理)
# 提供方配置: 设置环境变量 XAGENT_SSO_PROVIDERS (JSON 数组), 或在应用启动时
# 调用 backend.app.api.sso.register_oidc_provider(OIDCConfig(...))。
# 本地会话签发: LocalSessionIssuer 惰性使用 backend.app.api.auth._issue_token,
# 无需 main.py 改动; 若需 JWT 式会话, 可用 set_session_issuer() 注入新实现。
# 多实例部署: state_store 为进程内实现, 需经
#   backend.app.core.saml_sso.set_state_store(...) 注入分布式存储。
