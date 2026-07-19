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
from typing import Annotated, Any, Optional

from fastapi import APIRouter, Depends, Header, HTTPException, Query, Request
from pydantic import BaseModel, Field

from backend.app.api.errors import api_error
from backend.app.core.contracts import ErrorCode
from backend.app.core.saml_sso import (
    AUTHLIB_AVAILABLE,
    SAML_BETA_MESSAGE,
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

    def issue(self, user_id: str) -> Optional[dict[str, Any]]:
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
    access_token: Optional[str]
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
        "saml": {"status": "beta", "enabled": False, "message": SAML_BETA_MESSAGE},
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
async def saml_login(provider: str) -> None:
    """SAML 登录 — Beta, fail-closed (501)。"""
    raise HTTPException(status_code=501, detail=SAML_BETA_MESSAGE)


@oidc_router.post("/saml/{provider}/acs")
async def saml_acs(provider: str) -> None:
    """SAML ACS — Beta, fail-closed (501)。"""
    raise HTTPException(status_code=501, detail=SAML_BETA_MESSAGE)


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
        "saml": {"status": "beta", "enabled": False, "message": SAML_BETA_MESSAGE},
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

    access_token: Optional[str]
    refresh_token: Optional[str]
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
# WebAuthn / 条件访问 — 未实现, 显式 501 fail-closed (P1-02 修复假成功)
# ============================================================================

_WEBAUTHN_NOT_IMPLEMENTED = (
    "WebAuthn 注册/认证端点尚未实现真实验证逻辑 (此前为空壳假成功, P1-02 已移除), "
    "请等待后续迭代或贡献 core.sso.webauthn_provider 的验签实现。"
)
_CONDITIONAL_ACCESS_NOT_IMPLEMENTED = (
    "条件访问策略端点尚未实现真实策略引擎 (此前为空壳假成功, P1-02 已移除)。"
)


@auth_router.post("/webauthn/register/start")
async def webauthn_register_start() -> None:
    """WebAuthn 注册 — 未实现 (501 fail-closed)。"""
    raise api_error(501, ErrorCode.VALIDATION_ERROR, _WEBAUTHN_NOT_IMPLEMENTED)


@auth_router.post("/webauthn/register/complete")
async def webauthn_register_complete() -> None:
    """WebAuthn 注册完成 — 未实现 (501 fail-closed)。"""
    raise api_error(501, ErrorCode.VALIDATION_ERROR, _WEBAUTHN_NOT_IMPLEMENTED)


@auth_router.post("/webauthn/authenticate/start")
async def webauthn_authenticate_start() -> None:
    """WebAuthn 认证 — 未实现 (501 fail-closed)。"""
    raise api_error(501, ErrorCode.VALIDATION_ERROR, _WEBAUTHN_NOT_IMPLEMENTED)


@auth_router.post("/webauthn/authenticate/complete")
async def webauthn_authenticate_complete() -> None:
    """WebAuthn 认证完成 — 未实现 (501 fail-closed)。"""
    raise api_error(501, ErrorCode.VALIDATION_ERROR, _WEBAUTHN_NOT_IMPLEMENTED)


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
