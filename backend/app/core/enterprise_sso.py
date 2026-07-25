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
import logging
import secrets
from datetime import UTC, datetime, timedelta
from typing import Any
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
    single_logout_service_url: str | None = None
    certificate_path: str | None = None
    private_key_path: str | None = None
    idp_entity_id: str = Field(..., description="Identity Provider Entity ID")
    idp_sso_url: str = Field(..., description="IdP SSO URL")
    idp_slo_url: str | None = None
    idp_certificate: str | None = None
    name_id_format: str = "urn:oasis:names:tc:SAML:1.1:nameid-format:emailAddress"
    want_assertions_signed: bool = True
    want_response_signed: bool = True
    sign_requests: bool = True
    encrypt_assertions: bool = False
    metadata_url: str | None = None


class SAMLAssertion(BaseModel):
    """SAML断言"""
    assertion_id: str
    issuer: str
    subject: str
    subject_confirmation_data: dict[str, Any]
    attribute_statement: dict[str, list[str]]
    conditions: dict[str, Any]
    authn_statement: dict[str, Any]
    signature: str | None = None
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
    assertion: SAMLAssertion | None = None
    relay_state: str | None = None
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
    jwks_uri: str | None = None
    issuer: str
    scopes: list[str] = Field(default_factory=lambda: ["openid", "profile", "email"])
    # P1-02: 放宽为可选 — api/enterprise_sso.py 的配置端点不传该字段;
    # 但 exchange_code_for_token 时若仍缺失会显式报错 (fail-closed)
    redirect_uri: str | None = None
    response_type: str = "code"
    grant_type: str = "authorization_code"
    token_endpoint_auth_method: str = "client_secret_basic"
    id_token_signed_alg: str = "RS256"
    userinfo_signed_response_alg: str | None = None
    metadata_url: str | None = None
    http_timeout_seconds: float = 10.0


class OAuthAuthorizationRequest(BaseModel):
    """OAuth授权请求"""
    request_id: str
    client_id: str
    redirect_uri: str | None = None
    scope: str
    state: str
    nonce: str | None = None
    code_challenge: str | None = None
    code_challenge_method: str = "S256"
    # P1-02: 保存 PKCE verifier 供 token 交换时使用 (此前丢失导致 PKCE 流程无法闭环)
    code_verifier: str | None = None
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))


class OAuthToken(BaseModel):
    """OAuth令牌"""
    access_token: str
    token_type: str = "Bearer"
    expires_in: int
    refresh_token: str | None = None
    id_token: str | None = None
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
    name: str | None = None
    given_name: str | None = None
    family_name: str | None = None
    picture: str | None = None
    locale: str | None = None
    updated_at: int | None = None
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
    description: str | None = None
    is_active: bool = True
    saml_config: SAMLConfig | None = None
    oauth_config: OAuthConfig | None = None
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
    name: str | None = None
    attributes: dict[str, Any] = Field(default_factory=dict)
    last_login_at: datetime | None = None
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(UTC))


class SSOSession(BaseModel):
    """SSO会话"""
    session_id: str
    user_id: str
    tenant_id: str
    provider_id: str
    access_token: str
    refresh_token: str | None = None
    id_token: str | None = None
    token_expiry: datetime
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    last_activity_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    ip_address: str | None = None
    user_agent: str | None = None
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

    def process_saml_response(self, saml_response_b64: str, relay_state: str | None = None) -> SAMLResponse:
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
        """验证SAML响应签名和条件（fail-closed）。

        ⚠️⚠️ SECURITY (P0-05): 原实现仅检查 XML 中是否存在 "Signature" 字符串，
        完全未做 XML DSig 签名验证，等同于没有验证，攻击者可任意伪造断言完成登录。
        当前代码库未集成 python3-saml/signxml，无法执行真实验证，
        因此此处 fail-closed：一律抛出异常拒绝处理 SAML 响应，绝不静默通过。
        ➡️ 真 SSO 实现见 P1-02。

        Raises:
            ValueError: 始终抛出（fail-closed），直到 P1-02 落地真实签名验证。
        """
        raise ValueError(
            "SAML response signature verification is not implemented; "
            "refusing to process SAML response (fail-closed, P0-05). "
            "SAML 当前为 Beta 状态 (P1-02): 需接入 python3-saml/signxml 做真实 "
            "XML 签名验证后方可启用; OIDC 已 GA, 请优先使用 OIDC。"
        )

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
    """OAuth 2.0 / OIDC处理器 (P1-02: 真实 HTTP 实现, 无任何伪造数据)"""

    def __init__(self, config: OAuthConfig, *, http_client: Any = None):
        self.config = config
        self._auth_requests: dict[str, OAuthAuthorizationRequest] = {}
        self._state_index: dict[str, str] = {}  # state -> request_id
        self._tokens: dict[str, OAuthToken] = {}
        # 可注入 httpx.Client (同步); None 时按需创建
        self._http_client = http_client

    def _post(self, url: str, **kwargs: Any) -> httpx.Response:  # noqa: F821
        import httpx

        timeout = kwargs.pop("timeout", self.config.http_timeout_seconds)
        if self._http_client is not None:
            return self._http_client.post(url, timeout=timeout, **kwargs)
        with httpx.Client() as client:
            return client.post(url, timeout=timeout, **kwargs)

    def _get(self, url: str, **kwargs: Any) -> httpx.Response:  # noqa: F821
        import httpx

        timeout = kwargs.pop("timeout", self.config.http_timeout_seconds)
        if self._http_client is not None:
            return self._http_client.get(url, timeout=timeout, **kwargs)
        with httpx.Client() as client:
            return client.get(url, timeout=timeout, **kwargs)

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
            code_verifier=code_verifier,
        )
        self._auth_requests[request_id] = auth_request
        self._state_index[state] = request_id

        # 构建授权URL
        params = {
            "client_id": self.config.client_id,
            "redirect_uri": self.config.redirect_uri or "",
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
        """使用授权码交换令牌 (P1-02: 真实 token 端点调用 + state 校验)

        Args:
            code: 授权码
            state: 状态参数 (必须与 generate_authorization_url 签发的匹配, 一次性)

        Returns:
            OAuthToken对象

        Raises:
            ValueError: state 未知/已使用、token 端点报错、或 id_token 验签失败
        """
        # 1) state 一次性校验 (防 CSRF)
        request_id = self._state_index.pop(state, None)
        auth_request = self._auth_requests.pop(request_id, None) if request_id else None
        if auth_request is None:
            logger.warning("OAuth token exchange rejected: unknown or reused state")
            raise ValueError("Invalid or expired OAuth state (possible CSRF). Authentication rejected.")

        # 2) 真实调用 token 端点
        if not self.config.redirect_uri:
            raise ValueError(
                "OAuthConfig.redirect_uri 未配置, 无法完成授权码交换 (fail-closed)。"
            )

        data: dict[str, str] = {
            "grant_type": "authorization_code",
            "code": code,
            "redirect_uri": self.config.redirect_uri,
        }
        if auth_request.code_verifier:
            data["code_verifier"] = auth_request.code_verifier

        kwargs: dict[str, Any] = {}
        if self.config.token_endpoint_auth_method == "client_secret_post":
            data["client_id"] = self.config.client_id
            data["client_secret"] = self.config.client_secret
        else:  # client_secret_basic (默认)
            kwargs["auth"] = (self.config.client_id, self.config.client_secret)

        try:
            resp = self._post(self.config.token_endpoint, data=data, **kwargs)
        except Exception as e:
            logger.error(f"Token endpoint request failed: {e}")
            raise ValueError(f"Token exchange request failed: {e}") from e

        if resp.status_code != 200:
            logger.error(f"Token exchange failed: HTTP {resp.status_code}")
            raise ValueError(f"Token exchange failed: HTTP {resp.status_code}")

        token_data = resp.json()
        if "access_token" not in token_data:
            raise ValueError("Token endpoint response missing access_token")

        # 3) 若返回 id_token 则必须验签 (fail-closed)
        id_token = token_data.get("id_token")
        if id_token:
            self._verify_id_token(id_token, expected_nonce=auth_request.nonce)

        token = OAuthToken(
            access_token=token_data["access_token"],
            token_type=token_data.get("token_type", "Bearer"),
            expires_in=int(token_data.get("expires_in", 3600)),
            refresh_token=token_data.get("refresh_token"),
            id_token=id_token,
            scope=token_data.get("scope", " ".join(self.config.scopes)),
        )
        self._tokens[token.access_token] = token

        logger.info("Exchanged authorization code for token (state validated)")
        return token

    def _verify_id_token(self, id_token: str, *, expected_nonce: str | None = None) -> dict[str, Any]:
        """验证 id_token 签名与 claims (复用 saml_sso 的验签器, fail-closed)。"""
        from backend.app.core.saml_sso import (
            SSOAuthenticationError,
            validate_claims,
            verify_jwt_signature,
        )

        jwks: dict[str, Any] | None = None
        secret: str | None = None

        import base64 as _b64
        import json as _json

        try:
            header = _json.loads(_b64.urlsafe_b64decode(id_token.split(".")[0] + "=="))
        except Exception as e:
            raise ValueError(f"Malformed id_token header: {e}") from e

        alg = str(header.get("alg") or "")
        if alg.startswith("HS"):
            secret = self.config.client_secret
        else:
            jwks_uri = self.config.jwks_uri
            if not jwks_uri:
                # 尝试 OIDC discovery
                discovery_base = (self.config.metadata_url or "").strip()
                if not discovery_base and self.config.issuer:
                    discovery_base = self.config.issuer.rstrip("/") + "/.well-known/openid-configuration"
                if discovery_base:
                    try:
                        doc = self._get(discovery_base).json()
                        jwks_uri = doc.get("jwks_uri")
                    except Exception as e:
                        raise ValueError(f"OIDC discovery failed, cannot verify id_token: {e}") from e
            if not jwks_uri:
                raise ValueError(
                    "无法确定 JWKS 端点 (jwks_uri/metadata_url/issuer 均未配置), "
                    "id_token 无法验签, 拒绝认证 (fail-closed)。"
                )
            try:
                jwks = self._get(jwks_uri).json()
            except Exception as e:
                raise ValueError(f"JWKS fetch failed, cannot verify id_token: {e}") from e

        try:
            claims = verify_jwt_signature(id_token, jwks=jwks, client_secret=secret)
            validate_claims(
                claims,
                issuer=self.config.issuer or None,
                audience=self.config.client_id,
                expected_nonce=expected_nonce,
                validate_issuer=bool(self.config.issuer),
                validate_audience=True,
            )
        except SSOAuthenticationError as e:
            raise ValueError(f"id_token validation failed: {e}") from e
        return claims

    def get_userinfo(self, access_token: str) -> OAuthUserInfo:
        """获取用户信息 (P1-02: 真实 userinfo 端点调用)

        Args:
            access_token: 访问令牌

        Returns:
            OAuthUserInfo对象

        Raises:
            ValueError: 令牌无效或端点报错
        """
        try:
            resp = self._get(
                self.config.userinfo_endpoint,
                headers={"Authorization": f"Bearer {access_token}"},
            )
        except Exception as e:
            logger.error(f"Userinfo request failed: {e}")
            raise ValueError(f"Userinfo request failed: {e}") from e

        if resp.status_code == 401:
            raise ValueError("Userinfo rejected the access token (401)")
        if resp.status_code != 200:
            raise ValueError(f"Userinfo request failed: HTTP {resp.status_code}")

        data = resp.json()
        known = {
            "sub", "email", "email_verified", "name", "given_name",
            "family_name", "picture", "locale", "updated_at",
        }
        return OAuthUserInfo(
            sub=str(data.get("sub", "")),
            email=str(data.get("email", "")),
            email_verified=bool(data.get("email_verified", False)),
            name=data.get("name"),
            given_name=data.get("given_name"),
            family_name=data.get("family_name"),
            picture=data.get("picture"),
            locale=data.get("locale"),
            updated_at=data.get("updated_at"),
            custom_claims={k: v for k, v in data.items() if k not in known},
        )

    def refresh_token(self, refresh_token: str) -> OAuthToken:
        """刷新令牌 (P1-02: 真实 token 端点调用)

        Args:
            refresh_token: 刷新令牌

        Returns:
            新的OAuthToken对象
        """
        data: dict[str, str] = {
            "grant_type": "refresh_token",
            "refresh_token": refresh_token,
        }
        kwargs: dict[str, Any] = {}
        if self.config.token_endpoint_auth_method == "client_secret_post":
            data["client_id"] = self.config.client_id
            data["client_secret"] = self.config.client_secret
        else:
            kwargs["auth"] = (self.config.client_id, self.config.client_secret)

        try:
            resp = self._post(self.config.token_endpoint, data=data, **kwargs)
        except Exception as e:
            logger.error(f"Token refresh request failed: {e}")
            raise ValueError(f"Token refresh request failed: {e}") from e

        if resp.status_code != 200:
            raise ValueError(f"Token refresh failed: HTTP {resp.status_code}")

        token_data = resp.json()
        token = OAuthToken(
            access_token=token_data["access_token"],
            token_type=token_data.get("token_type", "Bearer"),
            expires_in=int(token_data.get("expires_in", 3600)),
            refresh_token=token_data.get("refresh_token", refresh_token),
            id_token=token_data.get("id_token"),
            scope=token_data.get("scope", " ".join(self.config.scopes)),
        )
        self._tokens[token.access_token] = token

        logger.info("Refreshed OAuth token via token endpoint")
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
        refresh_token: str | None = None,
        id_token: str | None = None,
        token_expiry_seconds: int = 3600,
        ip_address: str | None = None,
        user_agent: str | None = None,
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

    def get_session(self, session_id: str) -> SSOSession | None:
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
        name: str | None = None,
        attributes: dict[str, Any] | None = None,
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

    def get_identity_by_provider(self, provider_id: str, provider_user_id: str) -> FederatedIdentity | None:
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

    def update_last_login(self, identity_id: str) -> FederatedIdentity | None:
        """更新最后登录时间"""
        identity = self._identities.get(identity_id)
        if identity:
            identity.last_login_at = datetime.now(UTC)
            identity.updated_at = datetime.now(UTC)
        return identity
