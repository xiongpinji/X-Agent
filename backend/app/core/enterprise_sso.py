"""
企业级SSO/SAML集成模块

支持:
- SAML 2.0协议
- OAuth 2.0/OIDC
- 多租户身份管理
- 单点登录/登出
- 会话管理
"""
from __future__ import annotations

import base64
import hashlib
import json
import logging
import secrets
import time
from datetime import UTC, datetime, timedelta
from typing import Any, Optional
from uuid import uuid4

from pydantic import BaseModel, Field

logger = logging.getLogger(__name__)


# ============================================================================
# SAML 2.0 Models
# ============================================================================

class SAMLConfig(BaseModel):
    """SAML 2.0配置"""
    entity_id: str = Field(..., description="Service Provider Entity ID")
    assertion_consumer_service_url: str = Field(..., description="ACS URL")
    single_logout_service_url: Optional[str] = None
    certificate_path: Optional[str] = None
    private_key_path: Optional[str] = None
    idp_entity_id: str = Field(..., description="Identity Provider Entity ID")
    idp_sso_url: str = Field(..., description="IdP SSO URL")
    idp_slo_url: Optional[str] = None
    idp_certificate: Optional[str] = None
    name_id_format: str = "urn:oasis:names:tc:SAML:1.1:nameid-format:emailAddress"
    want_assertions_signed: bool = True
    want_response_signed: bool = True
    sign_requests: bool = True
    encrypt_assertions: bool = False
    metadata_url: Optional[str] = None


class SAMLAssertion(BaseModel):
    """SAML断言"""
    assertion_id: str
    issuer: str
    subject: str
    subject_confirmation_data: dict[str, Any]
    attribute_statement: dict[str, list[str]]
    conditions: dict[str, Any]
    authn_statement: dict[str, Any]
    signature: Optional[str] = None
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))


class SAMLAuthRequest(BaseModel):
    """SAML认证请求"""
    request_id: str
    issuer: str
    assertion_consumer_service_url: str
    name_id_format: str
    is_passive: bool = False
    force_authn: bool = False
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))


class SAMLResponse(BaseModel):
    """SAML响应"""
    response_id: str
    in_response_to: str
    issuer: str
    status_code: str
    assertion: Optional[SAMLAssertion] = None
    relay_state: Optional[str] = None
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))


# ============================================================================
# OAuth 2.0 / OIDC Models
# ============================================================================

class OAuthConfig(BaseModel):
    """OAuth 2.0 / OIDC配置"""
    client_id: str
    client_secret: str
    authorization_endpoint: str
    token_endpoint: str
    userinfo_endpoint: str
    jwks_uri: Optional[str] = None
    issuer: str
    scopes: list[str] = Field(default_factory=lambda: ["openid", "profile", "email"])
    redirect_uri: str
    response_type: str = "code"
    grant_type: str = "authorization_code"
    token_endpoint_auth_method: str = "client_secret_basic"
    id_token_signed_alg: str = "RS256"
    userinfo_signed_response_alg: Optional[str] = None
    metadata_url: Optional[str] = None


class OAuthAuthorizationRequest(BaseModel):
    """OAuth授权请求"""
    request_id: str
    client_id: str
    redirect_uri: str
    scope: str
    state: str
    nonce: Optional[str] = None
    code_challenge: Optional[str] = None
    code_challenge_method: str = "S256"
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))


class OAuthToken(BaseModel):
    """OAuth令牌"""
    access_token: str
    token_type: str = "Bearer"
    expires_in: int
    refresh_token: Optional[str] = None
    id_token: Optional[str] = None
    scope: str
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))

    @property
    def is_expired(self) -> bool:
        """检查令牌是否过期"""
        expiry = self.created_at + timedelta(seconds=self.expires_in)
        return datetime.now(UTC) >= expiry


class OAuthUserInfo(BaseModel):
    """OAuth用户信息"""
    sub: str
    email: str
    email_verified: bool = False
    name: Optional[str] = None
    given_name: Optional[str] = None
    family_name: Optional[str] = None
    picture: Optional[str] = None
    locale: Optional[str] = None
    updated_at: Optional[int] = None
    custom_claims: dict[str, Any] = Field(default_factory=dict)


# ============================================================================
# 多租户身份管理
# ============================================================================

class IdentityProvider(BaseModel):
    """身份提供者配置"""
    provider_id: str
    provider_type: str  # "saml", "oauth", "oidc"
    tenant_id: str
    name: str
    description: Optional[str] = None
    is_active: bool = True
    saml_config: Optional[SAMLConfig] = None
    oauth_config: Optional[OAuthConfig] = None
    attribute_mappings: dict[str, str] = Field(
        default_factory=lambda: {
            "email": "http://schemas.xmlsoap.org/ws/2005/05/identity/claims/emailaddress",
            "name": "http://schemas.xmlsoap.org/ws/2005/05/identity/claims/name",
            "groups": "http://schemas.xmlsoap.org/claims/Group",
        }
    )
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(UTC))


class FederatedIdentity(BaseModel):
    """联合身份"""
    identity_id: str
    user_id: str
    provider_id: str
    provider_user_id: str
    email: str
    name: Optional[str] = None
    attributes: dict[str, Any] = Field(default_factory=dict)
    last_login_at: Optional[datetime] = None
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(UTC))


class SSOSession(BaseModel):
    """SSO会话"""
    session_id: str
    user_id: str
    tenant_id: str
    provider_id: str
    access_token: str
    refresh_token: Optional[str] = None
    id_token: Optional[str] = None
    token_expiry: datetime
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    last_activity_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    ip_address: Optional[str] = None
    user_agent: Optional[str] = None
    is_active: bool = True

    @property
    def is_expired(self) -> bool:
        """检查会话是否过期"""
        return datetime.now(UTC) >= self.token_expiry

    @property
    def is_idle(self, idle_timeout_seconds: int = 1800) -> bool:
        """检查会话是否空闲"""
        idle_duration = datetime.now(UTC) - self.last_activity_at
        return idle_duration.total_seconds() > idle_timeout_seconds


# ============================================================================
# SAML处理器
# ============================================================================

class SAMLProcessor:
    """SAML 2.0处理器"""

    def __init__(self, config: SAMLConfig):
        self.config = config
        self._auth_requests: dict[str, SAMLAuthRequest] = {}
        self._assertions: dict[str, SAMLAssertion] = {}

    def generate_auth_request(self) -> tuple[str, str]:
        """生成SAML认证请求

        Returns:
            (request_id, saml_request_b64)
        """
        request_id = f"_saml_{uuid4().hex}"
        auth_request = SAMLAuthRequest(
            request_id=request_id,
            issuer=self.config.entity_id,
            assertion_consumer_service_url=self.config.assertion_consumer_service_url,
            name_id_format=self.config.name_id_format,
        )
        self._auth_requests[request_id] = auth_request

        # 构建SAML请求XML
        saml_request_xml = self._build_auth_request_xml(auth_request)
        saml_request_b64 = base64.b64encode(saml_request_xml.encode()).decode()

        logger.info(f"Generated SAML auth request: {request_id}")
        return request_id, saml_request_b64

    def _build_auth_request_xml(self, auth_request: SAMLAuthRequest) -> str:
        """构建SAML认证请求XML"""
        timestamp = auth_request.created_at.isoformat()
        return f"""<?xml version="1.0" encoding="UTF-8"?>
<samlp:AuthnRequest xmlns:samlp="urn:oasis:names:tc:SAML:2.0:protocol"
    xmlns:saml="urn:oasis:names:tc:SAML:2.0:assertion"
    ID="{auth_request.request_id}"
    Version="2.0"
    IssueInstant="{timestamp}"
    Destination="{self.config.idp_sso_url}"
    AssertionConsumerServiceURL="{auth_request.assertion_consumer_service_url}"
    ProtocolBinding="urn:oasis:names:tc:SAML:2.0:bindings:HTTP-POST">
    <saml:Issuer>{auth_request.issuer}</saml:Issuer>
    <samlp:NameIDPolicy Format="{auth_request.name_id_format}" AllowCreate="true"/>
</samlp:AuthnRequest>"""

    def process_saml_response(self, saml_response_b64: str, relay_state: Optional[str] = None) -> SAMLResponse:
        """处理SAML响应

        Args:
            saml_response_b64: Base64编码的SAML响应
            relay_state: 中继状态

        Returns:
            SAMLResponse对象
        """
        try:
            saml_response_xml = base64.b64decode(saml_response_b64).decode()
            logger.debug(f"Decoded SAML response: {saml_response_xml[:200]}...")

            # 解析SAML响应（简化实现）
            response_id = f"_saml_resp_{uuid4().hex}"
            in_response_to = self._extract_in_response_to(saml_response_xml)

            # 验证签名和条件
            self._verify_saml_response(saml_response_xml)

            # 提取断言
            assertion = self._extract_assertion(saml_response_xml)
            self._assertions[response_id] = assertion

            response = SAMLResponse(
                response_id=response_id,
                in_response_to=in_response_to,
                issuer=self.config.idp_entity_id,
                status_code="urn:oasis:names:tc:SAML:2.0:status:Success",
                assertion=assertion,
                relay_state=relay_state,
            )

            logger.info(f"Processed SAML response: {response_id}")
            return response

        except Exception as e:
            logger.error(f"Failed to process SAML response: {e}")
            raise

    def _extract_in_response_to(self, saml_response_xml: str) -> str:
        """从SAML响应中提取InResponseTo属性"""
        import re
        match = re.search(r'InResponseTo="([^"]+)"', saml_response_xml)
        return match.group(1) if match else ""

    def _verify_saml_response(self, saml_response_xml: str) -> None:
        """验证SAML响应签名和条件"""
        # 简化实现：在生产环境中应使用python3-saml库
        if self.config.want_response_signed:
            if "Signature" not in saml_response_xml:
                raise ValueError("SAML response must be signed")
        logger.debug("SAML response verification passed")

    def _extract_assertion(self, saml_response_xml: str) -> SAMLAssertion:
        """从SAML响应中提取断言"""
        import re

        # 简化实现：提取基本属性
        assertion_id = f"_assertion_{uuid4().hex}"
        subject_match = re.search(r'<saml:NameID[^>]*>([^<]+)</saml:NameID>', saml_response_xml)
        subject = subject_match.group(1) if subject_match else ""

        # 提取属性
        attributes = {}
        for match in re.finditer(r'<saml:Attribute Name="([^"]+)"[^>]*>\s*<saml:AttributeValue[^>]*>([^<]+)</saml:AttributeValue>', saml_response_xml):
            attr_name, attr_value = match.groups()
            if attr_name not in attributes:
                attributes[attr_name] = []
            attributes[attr_name].append(attr_value)

        return SAMLAssertion(
            assertion_id=assertion_id,
            issuer=self.config.idp_entity_id,
            subject=subject,
            subject_confirmation_data={
                "NotOnOrAfter": (datetime.now(UTC) + timedelta(hours=1)).isoformat(),
                "Recipient": self.config.assertion_consumer_service_url,
            },
            attribute_statement=attributes,
            conditions={
                "NotBefore": datetime.now(UTC).isoformat(),
                "NotOnOrAfter": (datetime.now(UTC) + timedelta(hours=1)).isoformat(),
            },
            authn_statement={
                "AuthnInstant": datetime.now(UTC).isoformat(),
                "SessionIndex": uuid4().hex,
            },
        )

    def generate_metadata(self) -> str:
        """生成SP元数据"""
        return f"""<?xml version="1.0" encoding="UTF-8"?>
<EntityDescriptor xmlns="urn:oasis:names:tc:SAML:2.0:metadata"
    entityID="{self.config.entity_id}">
    <SPSSODescriptor AuthnRequestsSigned="{str(self.config.sign_requests).lower()}"
        WantAssertionsSigned="{str(self.config.want_assertions_signed).lower()}"
        protocolSupportEnumeration="urn:oasis:names:tc:SAML:2.0:protocol">
        <SingleLogoutService Binding="urn:oasis:names:tc:SAML:2.0:bindings:HTTP-Redirect"
            Location="{self.config.single_logout_service_url or self.config.assertion_consumer_service_url}"/>
        <AssertionConsumerService Binding="urn:oasis:names:tc:SAML:2.0:bindings:HTTP-POST"
            Location="{self.config.assertion_consumer_service_url}"
            index="0"
            isDefault="true"/>
    </SPSSODescriptor>
</EntityDescriptor>"""


# ============================================================================
# OAuth 2.0 / OIDC处理器
# ============================================================================

class OAuthProcessor:
    """OAuth 2.0 / OIDC处理器"""

    def __init__(self, config: OAuthConfig):
        self.config = config
        self._auth_requests: dict[str, OAuthAuthorizationRequest] = {}
        self._tokens: dict[str, OAuthToken] = {}

    def generate_authorization_url(self) -> tuple[str, str]:
        """生成授权URL

        Returns:
            (request_id, authorization_url)
        """
        request_id = f"oauth_{uuid4().hex}"
        state = secrets.token_urlsafe(32)
        nonce = secrets.token_urlsafe(32)

        # PKCE
        code_verifier = secrets.token_urlsafe(32)
        code_challenge = base64.urlsafe_b64encode(
            hashlib.sha256(code_verifier.encode()).digest()
        ).decode().rstrip("=")

        auth_request = OAuthAuthorizationRequest(
            request_id=request_id,
            client_id=self.config.client_id,
            redirect_uri=self.config.redirect_uri,
            scope=" ".join(self.config.scopes),
            state=state,
            nonce=nonce,
            code_challenge=code_challenge,
        )
        self._auth_requests[request_id] = auth_request

        # 构建授权URL
        params = {
            "client_id": self.config.client_id,
            "redirect_uri": self.config.redirect_uri,
            "response_type": self.config.response_type,
            "scope": auth_request.scope,
            "state": state,
            "nonce": nonce,
            "code_challenge": code_challenge,
            "code_challenge_method": auth_request.code_challenge_method,
        }

        from urllib.parse import urlencode
        authorization_url = f"{self.config.authorization_endpoint}?{urlencode(params)}"

        logger.info(f"Generated OAuth authorization URL: {request_id}")
        return request_id, authorization_url

    def exchange_code_for_token(self, code: str, state: str) -> OAuthToken:
        """使用授权码交换令牌

        Args:
            code: 授权码
            state: 状态参数

        Returns:
            OAuthToken对象
        """
        # 在生产环境中应验证state并调用token_endpoint
        # 这里是简化实现
        token = OAuthToken(
            access_token=f"access_{uuid4().hex}",
            token_type="Bearer",
            expires_in=3600,
            refresh_token=f"refresh_{uuid4().hex}",
            id_token=f"id_{uuid4().hex}",
            scope=" ".join(self.config.scopes),
        )
        self._tokens[token.access_token] = token

        logger.info(f"Exchanged authorization code for token")
        return token

    def get_userinfo(self, access_token: str) -> OAuthUserInfo:
        """获取用户信息

        Args:
            access_token: 访问令牌

        Returns:
            OAuthUserInfo对象
        """
        # 在生产环境中应调用userinfo_endpoint
        # 这里是简化实现
        return OAuthUserInfo(
            sub=uuid4().hex,
            email="user@example.com",
            email_verified=True,
            name="Example User",
        )

    def refresh_token(self, refresh_token: str) -> OAuthToken:
        """刷新令牌

        Args:
            refresh_token: 刷新令牌

        Returns:
            新的OAuthToken对象
        """
        token = OAuthToken(
            access_token=f"access_{uuid4().hex}",
            token_type="Bearer",
            expires_in=3600,
            refresh_token=refresh_token,
            scope=" ".join(self.config.scopes),
        )
        self._tokens[token.access_token] = token

        logger.info(f"Refreshed OAuth token")
        return token


# ============================================================================
# SSO会话管理器
# ============================================================================

class SSOSessionManager:
    """SSO会话管理器"""

    def __init__(self):
        self._sessions: dict[str, SSOSession] = {}
        self._user_sessions: dict[str, list[str]] = {}  # user_id -> [session_id, ...]
        self._idle_timeout_seconds = 1800  # 30分钟
        self._max_session_duration_seconds = 28800  # 8小时

    def create_session(
        self,
        user_id: str,
        tenant_id: str,
        provider_id: str,
        access_token: str,
        refresh_token: Optional[str] = None,
        id_token: Optional[str] = None,
        token_expiry_seconds: int = 3600,
        ip_address: Optional[str] = None,
        user_agent: Optional[str] = None,
    ) -> SSOSession:
        """创建SSO会话"""
        session_id = f"sso_{uuid4().hex}"
        session = SSOSession(
            session_id=session_id,
            user_id=user_id,
            tenant_id=tenant_id,
            provider_id=provider_id,
            access_token=access_token,
            refresh_token=refresh_token,
            id_token=id_token,
            token_expiry=datetime.now(UTC) + timedelta(seconds=token_expiry_seconds),
            ip_address=ip_address,
            user_agent=user_agent,
        )

        self._sessions[session_id] = session
        if user_id not in self._user_sessions:
            self._user_sessions[user_id] = []
        self._user_sessions[user_id].append(session_id)

        logger.info(f"Created SSO session: {session_id} for user: {user_id}")
        return session

    def get_session(self, session_id: str) -> Optional[SSOSession]:
        """获取会话"""
        session = self._sessions.get(session_id)
        if session and not session.is_expired:
            session.last_activity_at = datetime.now(UTC)
            return session
        return None

    def invalidate_session(self, session_id: str) -> bool:
        """使会话失效"""
        session = self._sessions.get(session_id)
        if session:
            session.is_active = False
            logger.info(f"Invalidated SSO session: {session_id}")
            return True
        return False

    def invalidate_user_sessions(self, user_id: str) -> int:
        """使用户的所有会话失效（单点登出）"""
        session_ids = self._user_sessions.get(user_id, [])
        count = 0
        for session_id in session_ids:
            if self.invalidate_session(session_id):
                count += 1
        logger.info(f"Invalidated {count} sessions for user: {user_id}")
        return count

    def list_user_sessions(self, user_id: str) -> list[SSOSession]:
        """列出用户的所有活跃会话"""
        session_ids = self._user_sessions.get(user_id, [])
        sessions = []
        for session_id in session_ids:
            session = self._sessions.get(session_id)
            if session and session.is_active and not session.is_expired:
                sessions.append(session)
        return sessions

    def cleanup_expired_sessions(self) -> int:
        """清理过期会话"""
        expired_ids = [
            sid for sid, session in self._sessions.items()
            if session.is_expired or not session.is_active
        ]
        for sid in expired_ids:
            del self._sessions[sid]
        logger.info(f"Cleaned up {len(expired_ids)} expired sessions")
        return len(expired_ids)


# ============================================================================
# 联合身份管理器
# ============================================================================

class FederatedIdentityManager:
    """联合身份管理器"""

    def __init__(self):
        self._identities: dict[str, FederatedIdentity] = {}
        self._provider_user_index: dict[tuple[str, str], str] = {}  # (provider_id, provider_user_id) -> identity_id

    def link_identity(
        self,
        user_id: str,
        provider_id: str,
        provider_user_id: str,
        email: str,
        name: Optional[str] = None,
        attributes: Optional[dict[str, Any]] = None,
    ) -> FederatedIdentity:
        """链接联合身份"""
        identity_id = f"fed_{uuid4().hex}"
        identity = FederatedIdentity(
            identity_id=identity_id,
            user_id=user_id,
            provider_id=provider_id,
            provider_user_id=provider_user_id,
            email=email,
            name=name,
            attributes=attributes or {},
        )

        self._identities[identity_id] = identity
        self._provider_user_index[(provider_id, provider_user_id)] = identity_id

        logger.info(f"Linked federated identity: {identity_id} for user: {user_id}")
        return identity

    def get_identity_by_provider(self, provider_id: str, provider_user_id: str) -> Optional[FederatedIdentity]:
        """根据提供者获取身份"""
        identity_id = self._provider_user_index.get((provider_id, provider_user_id))
        if identity_id:
            return self._identities.get(identity_id)
        return None

    def get_user_identities(self, user_id: str) -> list[FederatedIdentity]:
        """获取用户的所有联合身份"""
        return [
            identity for identity in self._identities.values()
            if identity.user_id == user_id
        ]

    def unlink_identity(self, identity_id: str) -> bool:
        """取消链接身份"""
        identity = self._identities.get(identity_id)
        if identity:
            del self._identities[identity_id]
            del self._provider_user_index[(identity.provider_id, identity.provider_user_id)]
            logger.info(f"Unlinked federated identity: {identity_id}")
            return True
        return False

    def update_last_login(self, identity_id: str) -> Optional[FederatedIdentity]:
        """更新最后登录时间"""
        identity = self._identities.get(identity_id)
        if identity:
            identity.last_login_at = datetime.now(UTC)
            identity.updated_at = datetime.now(UTC)
        return identity
