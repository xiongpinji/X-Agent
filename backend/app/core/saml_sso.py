"""
SAML 2.0 / OpenID Connect 企业级单点登录核心模块 (P1-02)

能力分级:
- OIDC: **GA** — 完整授权码流程: discovery 文档拉取、JWKS 验签
  (authlib 优先, cryptography 兜底)、state/nonce 一次性校验、
  JIT (Just-In-Time) 用户 provisioning。
- SAML 2.0: **Beta** — 仅保留 AuthnRequest 生成能力; 响应验签需要
  python3-saml/signxml 级 XML DSig 验证, 当前 fail-closed 拒绝处理,
  绝不静默通过 (P0-05)。

HTTP 客户端: httpx (异步)。JWT 验签: authlib >= 1.7 (可选依赖,
缺失时降级为内置 cryptography 实现, 仅支持 RS256/HS256, 其余算法显式报错)。
"""

from __future__ import annotations

import base64
import hashlib
import hmac
import json
import logging
import secrets
import threading
import time
import uuid
import zlib
from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta
from enum import StrEnum
from typing import Any, Protocol
from urllib.parse import urlencode

from pydantic import BaseModel, Field

logger = logging.getLogger(__name__)

# ============================================================================
# 可选依赖: authlib (优先) / cryptography (兜底)
# ============================================================================

try:  # pragma: no cover - 导入分支由环境决定
    # authlib>=1.7 的 jose 模块是 joserfc 的兼容层; 优先直接用 joserfc (无弃用告警)
    from joserfc import jwt as _jose_jwt
    from joserfc.errors import JoseError
    from joserfc.jwk import KeySet as _JoseKeySet

    _JWT_BACKEND = "joserfc"
except ImportError:  # pragma: no cover
    try:
        import warnings

        with warnings.catch_warnings():
            warnings.simplefilter("ignore", DeprecationWarning)
            from authlib.jose import JsonWebKey, JsonWebToken
            from authlib.jose.errors import JoseError

        _JWT_BACKEND = "authlib"
    except ImportError:
        JoseError = Exception  # type: ignore[assignment]
        _JWT_BACKEND = "none"
        logger.warning(
            "joserfc/authlib 均未安装, OIDC id_token 验签降级为内置实现 (仅 RS256/HS256)。"
            "生产环境建议: pip install authlib"
        )

AUTHLIB_AVAILABLE = _JWT_BACKEND != "none"

_ASYMMETRIC_ALGS = (
    "RS256", "RS384", "RS512",
    "ES256", "ES384", "ES512",
    "PS256", "PS384", "PS512",
)
_SYMMETRIC_ALGS = ("HS256", "HS384", "HS512")
_SUPPORTED_ALGS = _ASYMMETRIC_ALGS + _SYMMETRIC_ALGS
# 内置兜底实现支持的算法 (无 authlib 时)
_FALLBACK_ALGS = ("RS256", "HS256")


# ============================================================================
# 异常体系
# ============================================================================

class SSOError(Exception):
    """SSO 基础异常。"""


class SSOConfigurationError(SSOError):
    """SSO 配置错误 (缺 discovery/JWKS/issuer 等)。"""


class SSOAuthenticationError(SSOError):
    """SSO 认证失败 (签名/state/nonce/iss/aud/exp 校验失败)。"""


class SSOStorageError(SSOError):
    """SSO 用户存储后端错误 (显式失败, 不静默降级)。"""


class SAMLSupportError(SSOError):
    """SAML 功能处于 Beta/未启用状态 (fail-closed)。"""


# ============================================================================
# 枚举与配置模型
# ============================================================================

class SSOProvider(StrEnum):
    """支持的 SSO 提供方类型。"""

    SAML = "saml"
    OAUTH2 = "oauth2"
    OIDC = "oidc"
    LDAP = "ldap"
    AZURE_AD = "azure_ad"
    OKTA = "okta"
    GOOGLE = "google"


class SAMLNameIDFormat(StrEnum):
    """SAML NameID 格式。"""

    PERSISTENT = "urn:oasis:names:tc:SAML:1.1:nameid-format:persistent"
    TRANSIENT = "urn:oasis:names:tc:SAML:1.1:nameid-format:transient"
    EMAIL = "urn:oasis:names:tc:SAML:1.1:nameid-format:emailAddress"
    UNSPECIFIED = "urn:oasis:names:tc:SAML:1.1:nameid-format:unspecified"


class SAMLBindingType(StrEnum):
    """SAML 绑定类型。"""

    HTTP_POST = "urn:oasis:names:tc:SAML:2.0:bindings:HTTP-POST"
    HTTP_REDIRECT = "urn:oasis:names:tc:SAML:2.0:bindings:HTTP-Redirect"
    HTTP_ARTIFACT = "urn:oasis:names:tc:SAML:2.0:bindings:HTTP-Artifact"


class OIDCScope(StrEnum):
    """OpenID Connect scopes。"""

    OPENID = "openid"
    PROFILE = "profile"
    EMAIL = "email"
    PHONE = "phone"
    ADDRESS = "address"


class SAMLConfig(BaseModel):
    """SAML 2.0 配置 (Beta — 见模块 docstring)。"""

    idp_entity_id: str = Field(..., description="IdP Entity ID")
    idp_sso_url: str = Field(..., description="IdP Single Sign-On URL")
    idp_slo_url: str | None = Field(None, description="IdP Single Logout URL")
    idp_certificate: str = Field(..., description="IdP X.509 certificate (PEM)")

    sp_entity_id: str = Field(..., description="SP Entity ID")
    sp_acs_url: str = Field(..., description="SP Assertion Consumer Service URL")
    sp_slo_url: str | None = Field(None, description="SP Single Logout URL")
    sp_certificate: str | None = Field(None, description="SP X.509 certificate (PEM)")
    sp_private_key: str | None = Field(None, description="SP private key (PEM)")

    name_id_format: SAMLNameIDFormat = SAMLNameIDFormat.PERSISTENT
    binding_type: SAMLBindingType = SAMLBindingType.HTTP_POST

    attribute_mappings: dict[str, str] = Field(
        default_factory=lambda: {
            "uid": "urn:oid:0.9.2342.19200300.100.1.3",
            "email": "urn:oid:0.9.2342.19200300.100.1.3",
            "name": "urn:oid:2.5.4.3",
            "groups": "urn:oid:1.3.6.1.4.1.5923.1.1.1.7",
        }
    )

    sign_requests: bool = True
    encrypt_assertions: bool = False
    force_authn: bool = False

    tenant_id: str = Field(..., description="关联租户 ID")
    enabled: bool = True


class OIDCConfig(BaseModel):
    """OpenID Connect 配置。"""

    provider_name: str = Field(..., description="提供方名称 (如 'okta', 'azure')")
    discovery_url: str = Field(..., description="OIDC Discovery 端点 URL")
    client_id: str = Field(..., description="OAuth 2.0 Client ID")
    client_secret: str = Field(..., description="OAuth 2.0 Client Secret")
    redirect_uri: str = Field(..., description="授权回调 URI")

    scopes: list[str] = Field(
        default_factory=lambda: ["openid", "profile", "email"],
        description="请求的 scope 列表",
    )

    claim_mappings: dict[str, str] = Field(
        default_factory=lambda: {
            "sub": "uid",
            "email": "email",
            "name": "name",
            "groups": "groups",
        },
        description="OIDC claim → 用户字段映射",
    )

    token_endpoint_auth_method: str = Field(
        default="client_secret_basic",
        description="token 端点客户端认证方式: client_secret_basic | client_secret_post",
    )
    require_https: bool = True
    validate_issuer: bool = True
    validate_audience: bool = True
    clock_skew_seconds: int = Field(default=60, description="exp/iat/nbf 容忍时钟偏差秒数")
    discovery_cache_ttl: int = Field(default=3600, description="discovery 文档缓存秒数")
    jwks_cache_ttl: int = Field(default=3600, description="JWKS 缓存秒数")
    http_timeout_seconds: float = Field(default=10.0, description="IdP HTTP 请求超时秒数")

    tenant_id: str = Field(default="default", description="关联租户 ID")
    enabled: bool = True


class SAMLAssertion(BaseModel):
    """SAML 断言模型。"""

    assertion_id: str
    issuer: str
    subject: str
    subject_format: SAMLNameIDFormat
    not_before: datetime
    not_on_or_after: datetime
    session_index: str
    attributes: dict[str, list[str]]
    signature_valid: bool
    encrypted: bool


class OIDCToken(BaseModel):
    """OIDC 令牌模型。"""

    access_token: str
    token_type: str = "Bearer"
    expires_in: int
    refresh_token: str | None = None
    id_token: str | None = None
    scope: str = ""


class SSOUser(BaseModel):
    """SSO 用户信息 (从 IdP claims 归一化)。"""

    uid: str = Field(..., description="IdP 侧唯一用户标识 (sub)")
    email: str = Field(..., description="用户邮箱")
    name: str = Field(default="", description="显示名")
    groups: list[str] = Field(default_factory=list)
    attributes: dict[str, Any] = Field(default_factory=dict)
    provider: SSOProvider = SSOProvider.OIDC
    provider_user_id: str = ""
    email_verified: bool = False
    last_login: datetime = Field(default_factory=lambda: datetime.now(UTC))
    jit_provisioned: bool = False


class SSOSession(BaseModel):
    """SSO 会话模型。"""

    session_id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    user_id: str
    tenant_id: str
    provider: SSOProvider
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    expires_at: datetime
    last_activity: datetime = Field(default_factory=lambda: datetime.now(UTC))
    ip_address: str = ""
    user_agent: str = ""
    active: bool = True

    def is_expired(self) -> bool:
        return datetime.now(UTC) > self.expires_at

    def is_idle_expired(self, idle_timeout_minutes: int = 30) -> bool:
        idle_threshold = datetime.now(UTC) - timedelta(minutes=idle_timeout_minutes)
        return self.last_activity < idle_threshold


# ============================================================================
# JWT 验签 (authlib 优先, cryptography 兜底) — 全部 fail-closed
# ============================================================================

def _b64url_decode(data: str) -> bytes:
    padding = "=" * (-len(data) % 4)
    return base64.urlsafe_b64decode(data + padding)


def _decode_jwt_parts(token: str) -> tuple[dict[str, Any], dict[str, Any], bytes, bytes]:
    """拆分 JWT, 返回 (header, payload, signature, signing_input)。"""
    try:
        header_b64, payload_b64, signature_b64 = token.split(".")
        header = json.loads(_b64url_decode(header_b64))
        payload = json.loads(_b64url_decode(payload_b64))
        signature = _b64url_decode(signature_b64)
        signing_input = f"{header_b64}.{payload_b64}".encode("ascii")
    except Exception as exc:
        raise SSOAuthenticationError(f"Malformed JWT: {exc}") from exc
    return header, payload, signature, signing_input


def _fallback_verify_signature(
    token: str,
    jwks: dict[str, Any] | None,
    client_secret: str | None,
) -> dict[str, Any]:
    """无 authlib 时的内置验签 (仅 RS256/HS256), 其余算法显式报错。

    Returns:
        验签通过后的 payload claims。

    Raises:
        SSOAuthenticationError: 验签失败或算法不受内置实现支持。
    """
    header, payload, signature, signing_input = _decode_jwt_parts(token)
    alg = str(header.get("alg") or "")

    if alg not in _FALLBACK_ALGS:
        raise SSOAuthenticationError(
            f"id_token alg='{alg}' 不受内置验签实现支持 "
            f"(内置支持: {', '.join(_FALLBACK_ALGS)}; 其余算法请安装 authlib)。"
            "拒绝认证 (fail-closed)。"
        )

    if alg.startswith("HS"):
        if not client_secret:
            raise SSOAuthenticationError(
                "HS* 算法验签需要 client_secret, 但未配置。拒绝认证 (fail-closed)。"
            )
        expected = hmac.new(client_secret.encode(), signing_input, hashlib.sha256).digest()
        if not hmac.compare_digest(expected, signature):
            raise SSOAuthenticationError("id_token 签名验证失败 (HS256)。")
        return payload

    # RS256: 从 JWKS 找 kid 匹配的 RSA 公钥
    kid = header.get("kid")
    keys = (jwks or {}).get("keys") or []
    jwk = None
    for candidate in keys:
        if (kid is None or candidate.get("kid") == kid) and candidate.get("kty") == "RSA":
            jwk = candidate
            break
    if jwk is None:
        raise SSOAuthenticationError(
            f"JWKS 中找不到匹配的 RSA 签名密钥 (kid={kid!r})。拒绝认证 (fail-closed)。"
        )

    try:
        from cryptography.hazmat.primitives.asymmetric import padding, rsa

        n = int.from_bytes(_b64url_decode(jwk["n"]), "big")
        e = int.from_bytes(_b64url_decode(jwk["e"]), "big")
        public_key = rsa.RSAPublicNumbers(e, n).public_key()
        public_key.verify(signature, signing_input, padding.PKCS1v15(), hashlib.sha256())
    except SSOAuthenticationError:
        raise
    except Exception as exc:
        raise SSOAuthenticationError(f"id_token 签名验证失败 (RS256): {exc}") from exc
    return payload


def verify_jwt_signature(
    token: str,
    *,
    jwks: dict[str, Any] | None = None,
    client_secret: str | None = None,
) -> dict[str, Any]:
    """验证 JWT 签名并返回 payload (不校验 iss/aud/exp — 由调用方校验)。

    验签后端优先级: joserfc → authlib.jose → 内置 RS256/HS256 实现。
    任何失败一律抛 SSOAuthenticationError (fail-closed)。
    """
    header, _, _, _ = _decode_jwt_parts(token)
    alg = str(header.get("alg") or "")
    if alg not in _SUPPORTED_ALGS:
        raise SSOAuthenticationError(
            f"id_token alg='{alg}' 不在允许列表。拒绝认证 (fail-closed)。"
        )

    if alg.startswith("HS") and not client_secret:
        raise SSOAuthenticationError(
            "HS* 算法验签需要 client_secret, 但未配置。拒绝认证 (fail-closed)。"
        )
    if not alg.startswith("HS") and not jwks:
        raise SSOAuthenticationError(
            "非对称算法验签需要 JWKS, 但未获取到。拒绝认证 (fail-closed)。"
        )

    if _JWT_BACKEND == "joserfc":
        try:
            if alg.startswith("HS"):
                key = _JoseKeySet.import_key_set(
                    {"keys": [{"kty": "oct", "k": base64.urlsafe_b64encode(client_secret.encode()).decode().rstrip("=")}]}
                )
            else:
                key = _JoseKeySet.import_key_set(jwks)
            decoded = _jose_jwt.decode(token, key)
            return dict(decoded.claims)
        except JoseError as exc:
            raise SSOAuthenticationError(f"id_token 签名验证失败: {exc}") from exc
        except SSOAuthenticationError:
            raise
        except Exception as exc:
            raise SSOAuthenticationError(f"id_token 验证失败: {exc}") from exc

    if _JWT_BACKEND == "authlib":
        try:
            jwt = JsonWebToken(list(_SUPPORTED_ALGS))
            if alg.startswith("HS"):
                claims = jwt.decode(token, client_secret)
            else:
                key_set = JsonWebKey.import_key_set(jwks)
                claims = jwt.decode(token, key_set)
            return dict(claims)
        except JoseError as exc:
            raise SSOAuthenticationError(f"id_token 签名验证失败: {exc}") from exc
        except SSOAuthenticationError:
            raise
        except Exception as exc:
            raise SSOAuthenticationError(f"id_token 验证失败: {exc}") from exc

    return _fallback_verify_signature(token, jwks, client_secret)


def validate_claims(
    claims: dict[str, Any],
    *,
    issuer: str | None,
    audience: str | None,
    expected_nonce: str | None = None,
    validate_issuer: bool = True,
    validate_audience: bool = True,
    clock_skew: int = 60,
) -> dict[str, Any]:
    """校验 iss/aud/exp/nbf/nonce, 全部 fail-closed。"""
    now = int(time.time())

    if validate_issuer:
        if not issuer:
            raise SSOAuthenticationError(
                "启用了 issuer 校验但无可信 issuer (discovery 未加载)。拒绝认证 (fail-closed)。"
            )
        if claims.get("iss") != issuer:
            raise SSOAuthenticationError(
                f"id_token iss 不匹配: 期望 {issuer!r}, 实际 {claims.get('iss')!r}。"
            )

    if validate_audience:
        if not audience:
            raise SSOAuthenticationError(
                "启用了 audience 校验但无 client_id。拒绝认证 (fail-closed)。"
            )
        aud = claims.get("aud")
        aud_list = aud if isinstance(aud, list) else [aud]
        if audience not in aud_list:
            raise SSOAuthenticationError(
                f"id_token aud 不匹配: 期望包含 {audience!r}, 实际 {aud!r}。"
            )

    exp = claims.get("exp")
    if exp is None:
        raise SSOAuthenticationError("id_token 缺少 exp claim。拒绝认证 (fail-closed)。")
    if now > int(exp) + clock_skew:
        raise SSOAuthenticationError("id_token 已过期 (exp)。")

    nbf = claims.get("nbf")
    if nbf is not None and now + clock_skew < int(nbf):
        raise SSOAuthenticationError("id_token 尚未生效 (nbf)。")

    iat = claims.get("iat")
    if iat is not None and now + clock_skew < int(iat):
        raise SSOAuthenticationError("id_token iat 在未来, 拒绝认证。")

    if expected_nonce is not None:
        token_nonce = claims.get("nonce")
        if not token_nonce or not hmac.compare_digest(str(token_nonce), str(expected_nonce)):
            raise SSOAuthenticationError("id_token nonce 校验失败 (可能为重放攻击)。")

    if not claims.get("sub"):
        raise SSOAuthenticationError("id_token 缺少 sub claim。拒绝认证 (fail-closed)。")

    return claims


# ============================================================================
# OIDC state/nonce 一次性存储 (防 CSRF 与重放)
# ============================================================================

@dataclass
class OIDCStateEntry:
    state: str
    nonce: str
    tenant_id: str
    provider_name: str
    redirect_uri: str
    created_at: float = field(default_factory=time.time)
    extras: dict[str, Any] = field(default_factory=dict)


class OIDCStateStore:
    """一次性 state/nonce 存储 (进程内, 线程安全)。

    注意: 多实例部署需替换为共享存储 (如 Redis); 集成波可通过
    ``set_state_store`` 注入实现相同协议的分布式存储。
    """

    def __init__(self, ttl_seconds: int = 600, max_entries: int = 100_000):
        self._ttl = ttl_seconds
        self._max = max_entries
        self._entries: dict[str, OIDCStateEntry] = {}
        self._lock = threading.Lock()

    def create(
        self,
        *,
        tenant_id: str,
        provider_name: str,
        redirect_uri: str,
        extras: dict[str, Any] | None = None,
    ) -> OIDCStateEntry:
        entry = OIDCStateEntry(
            state=secrets.token_urlsafe(32),
            nonce=secrets.token_urlsafe(32),
            tenant_id=tenant_id,
            provider_name=provider_name,
            redirect_uri=redirect_uri,
            extras=extras or {},
        )
        with self._lock:
            self._purge_expired_locked()
            if len(self._entries) >= self._max:
                # 拒绝服务保护: 满了则淘汰最旧
                oldest = min(self._entries, key=lambda k: self._entries[k].created_at)
                self._entries.pop(oldest, None)
            self._entries[entry.state] = entry
        return entry

    def consume(self, state: str) -> OIDCStateEntry | None:
        """取出并销毁 state (一次性)。不存在/过期返回 None。"""
        with self._lock:
            entry = self._entries.pop(state, None)
        if entry is None:
            return None
        if time.time() - entry.created_at > self._ttl:
            return None
        return entry

    def peek(self, state: str) -> OIDCStateEntry | None:
        with self._lock:
            return self._entries.get(state)

    def _purge_expired_locked(self) -> None:
        now = time.time()
        expired = [k for k, v in self._entries.items() if now - v.created_at > self._ttl]
        for k in expired:
            self._entries.pop(k, None)

    def __len__(self) -> int:
        return len(self._entries)


# ============================================================================
# OIDC Manager — GA 真实实现
# ============================================================================

class OIDCManager:
    """OpenID Connect 认证管理器 (完整授权码流程)。

    - discovery 文档拉取 + TTL 缓存
    - JWKS 拉取 + TTL 缓存 (未知 kid 时自动刷新一次, 应对密钥轮换)
    - 授权码交换 (client_secret_basic / client_secret_post)
    - id_token 验签 + iss/aud/exp/nonce 校验
    - userinfo 兜底获取
    """

    def __init__(self, config: OIDCConfig, *, http_client: Any = None):
        self.config = config
        self.logger = logging.getLogger(f"{__name__}.OIDCManager")
        self._http_client = http_client  # 可注入 httpx.AsyncClient (测试用 MockTransport)
        self._discovery_cache: dict[str, Any] | None = None
        self._discovery_fetched_at: float = 0.0
        self._jwks_cache: dict[str, Any] | None = None
        self._jwks_fetched_at: float = 0.0

    # ------------------------------------------------------------------ HTTP

    async def _request(self, method: str, url: str, **kwargs: Any) -> dict[str, Any]:
        import httpx

        timeout = kwargs.pop("timeout", self.config.http_timeout_seconds)
        if self._http_client is not None:
            resp = await self._http_client.request(method, url, timeout=timeout, **kwargs)
        else:
            async with httpx.AsyncClient() as client:
                resp = await client.request(method, url, timeout=timeout, **kwargs)
        if resp.status_code != 200:
            raise SSOConfigurationError(
                f"IdP 请求失败: {method} {url} → HTTP {resp.status_code}"
            )
        try:
            return resp.json()
        except Exception as exc:
            raise SSOConfigurationError(f"IdP 响应非 JSON: {method} {url}: {exc}") from exc

    # ------------------------------------------------------------- discovery

    async def get_discovery_document(self, *, force_refresh: bool = False) -> dict[str, Any]:
        """拉取 OIDC discovery 文档 (带 TTL 缓存)。"""
        now = time.time()
        if (
            not force_refresh
            and self._discovery_cache is not None
            and now - self._discovery_fetched_at < self.config.discovery_cache_ttl
        ):
            return self._discovery_cache

        if self.config.require_https and not self.config.discovery_url.startswith("https://"):
            # 测试环境可用 http (require_https=False); 默认强制 https
            raise SSOConfigurationError(
                f"discovery_url 必须为 https: {self.config.discovery_url!r} "
                "(测试可用 require_https=False 显式放宽)。"
            )

        doc = await self._request("GET", self.config.discovery_url)
        if not doc.get("issuer"):
            raise SSOConfigurationError("discovery 文档缺少 issuer 字段。")
        self._discovery_cache = doc
        self._discovery_fetched_at = now
        self.logger.debug("Fetched OIDC discovery document for %s", self.config.provider_name)
        return doc

    # ------------------------------------------------------------------ JWKS

    async def get_jwks(self, *, force_refresh: bool = False) -> dict[str, Any]:
        """拉取 JWKS (带 TTL 缓存)。"""
        now = time.time()
        if (
            not force_refresh
            and self._jwks_cache is not None
            and now - self._jwks_fetched_at < self.config.jwks_cache_ttl
        ):
            return self._jwks_cache

        discovery = await self.get_discovery_document()
        jwks_uri = discovery.get("jwks_uri")
        if not jwks_uri:
            raise SSOConfigurationError("discovery 文档缺少 jwks_uri。")

        self._jwks_cache = await self._request("GET", jwks_uri)
        self._jwks_fetched_at = now
        return self._jwks_cache

    # -------------------------------------------------------- authorize URL

    async def generate_authorization_url(
        self,
        state: str,
        nonce: str,
        *,
        extra_params: dict[str, str] | None = None,
    ) -> str:
        """生成 OIDC 授权 URL (authorization_endpoint 取自 discovery)。"""
        discovery = await self.get_discovery_document()
        auth_endpoint = discovery.get("authorization_endpoint")
        if not auth_endpoint:
            raise SSOConfigurationError("discovery 文档缺少 authorization_endpoint。")

        params: dict[str, str] = {
            "client_id": self.config.client_id,
            "response_type": "code",
            "scope": " ".join(self.config.scopes),
            "redirect_uri": self.config.redirect_uri,
            "state": state,
            "nonce": nonce,
        }
        if extra_params:
            params.update(extra_params)
        return f"{auth_endpoint}?{urlencode(params)}"

    # --------------------------------------------------------- token exchange

    async def exchange_code_for_token(self, code: str) -> OIDCToken:
        """授权码交换令牌 (真实 HTTP 调用)。"""
        discovery = await self.get_discovery_document()
        token_endpoint = discovery.get("token_endpoint")
        if not token_endpoint:
            raise SSOConfigurationError("discovery 文档缺少 token_endpoint。")

        data: dict[str, str] = {
            "grant_type": "authorization_code",
            "code": code,
            "redirect_uri": self.config.redirect_uri,
        }
        kwargs: dict[str, Any] = {}
        if self.config.token_endpoint_auth_method == "client_secret_post":
            data["client_id"] = self.config.client_id
            data["client_secret"] = self.config.client_secret
        else:  # client_secret_basic (默认)
            kwargs["auth"] = (self.config.client_id, self.config.client_secret)

        import httpx

        try:
            if self._http_client is not None:
                resp = await self._http_client.post(
                    token_endpoint, data=data, timeout=self.config.http_timeout_seconds, **kwargs
                )
            else:
                async with httpx.AsyncClient() as client:
                    resp = await client.post(
                        token_endpoint, data=data, timeout=self.config.http_timeout_seconds, **kwargs
                    )
        except httpx.HTTPError as exc:
            raise SSOAuthenticationError(f"token 交换网络错误: {exc}") from exc

        if resp.status_code != 200:
            raise SSOAuthenticationError(
                f"token 交换失败: HTTP {resp.status_code}: {resp.text[:200]}"
            )

        token_data = resp.json()
        if "access_token" not in token_data:
            raise SSOAuthenticationError("token 响应缺少 access_token。")

        return OIDCToken(
            access_token=token_data["access_token"],
            token_type=token_data.get("token_type", "Bearer"),
            expires_in=int(token_data.get("expires_in", 3600)),
            refresh_token=token_data.get("refresh_token"),
            id_token=token_data.get("id_token"),
            scope=token_data.get("scope", ""),
        )

    # -------------------------------------------------------- id_token 校验

    async def validate_id_token(
        self,
        id_token: str,
        *,
        expected_nonce: str | None = None,
    ) -> dict[str, Any]:
        """验签 + 校验 id_token, 返回 claims。全程 fail-closed。"""
        discovery = await self.get_discovery_document()
        issuer = discovery.get("issuer")

        # 先看 alg 决定密钥材料
        header, _, _, _ = _decode_jwt_parts(id_token)
        alg = str(header.get("alg") or "")

        jwks: dict[str, Any] | None = None
        secret: str | None = None
        if alg.startswith("HS"):
            secret = self.config.client_secret
        else:
            jwks = await self.get_jwks()

        try:
            claims = verify_jwt_signature(id_token, jwks=jwks, client_secret=secret)
        except SSOAuthenticationError:
            # 未知 kid 可能因密钥轮换: 刷新 JWKS 重试一次
            if jwks is not None:
                jwks = await self.get_jwks(force_refresh=True)
                claims = verify_jwt_signature(id_token, jwks=jwks, client_secret=secret)
            else:
                raise

        return validate_claims(
            claims,
            issuer=issuer,
            audience=self.config.client_id,
            expected_nonce=expected_nonce,
            validate_issuer=self.config.validate_issuer,
            validate_audience=self.config.validate_audience,
            clock_skew=self.config.clock_skew_seconds,
        )

    # --------------------------------------------------------------- userinfo

    async def get_userinfo(self, access_token: str) -> dict[str, Any]:
        """调用 userinfo 端点 (真实 HTTP)。"""
        discovery = await self.get_discovery_document()
        userinfo_endpoint = discovery.get("userinfo_endpoint")
        if not userinfo_endpoint:
            raise SSOConfigurationError("discovery 文档缺少 userinfo_endpoint。")

        import httpx

        headers = {"Authorization": f"Bearer {access_token}"}
        try:
            if self._http_client is not None:
                resp = await self._http_client.get(
                    userinfo_endpoint, headers=headers, timeout=self.config.http_timeout_seconds
                )
            else:
                async with httpx.AsyncClient() as client:
                    resp = await client.get(
                        userinfo_endpoint, headers=headers, timeout=self.config.http_timeout_seconds
                    )
        except httpx.HTTPError as exc:
            raise SSOAuthenticationError(f"userinfo 请求网络错误: {exc}") from exc
        if resp.status_code != 200:
            raise SSOAuthenticationError(f"userinfo 请求失败: HTTP {resp.status_code}")
        return resp.json()

    # ------------------------------------------------------------ 组合流程

    async def authenticate(
        self,
        code: str,
        *,
        expected_nonce: str | None = None,
    ) -> tuple[SSOUser, OIDCToken]:
        """完整认证: code → token → id_token 校验 → (userinfo 兜底) → SSOUser。"""
        token = await self.exchange_code_for_token(code)

        claims: dict[str, Any] = {}
        if token.id_token:
            claims = await self.validate_id_token(token.id_token, expected_nonce=expected_nonce)

        if not claims.get("email"):
            # userinfo 兜底补全 email/profile claims
            try:
                userinfo = await self.get_userinfo(token.access_token)
                merged = dict(userinfo)
                merged.update({k: v for k, v in claims.items() if v is not None})
                claims = merged
            except SSOError:
                if not claims:
                    raise

        return self._to_sso_user(claims), token

    def _to_sso_user(self, claims: dict[str, Any]) -> SSOUser:
        mapping = self.config.claim_mappings

        def _get(field: str, default: Any = "") -> Any:
            claim_name = next((c for c, f in mapping.items() if f == field), field)
            return claims.get(claim_name, default)

        uid = str(_get("uid") or claims.get("sub") or "")
        groups_raw = _get("groups", [])
        if isinstance(groups_raw, str):
            groups_raw = [groups_raw]

        return SSOUser(
            uid=uid,
            email=str(_get("email") or ""),
            name=str(_get("name") or ""),
            groups=list(groups_raw or []),
            attributes={k: v for k, v in claims.items() if k not in mapping},
            provider=SSOProvider.OIDC,
            provider_user_id=uid,
            email_verified=bool(claims.get("email_verified", False)),
        )


# ============================================================================
# 用户存储适配层 (惰性导入 + 显式降级)
# ============================================================================

@dataclass
class UserRecord:
    """归一化用户记录 (与存储后端解耦)。"""

    user_id: str
    email: str
    tenant_id: str
    full_name: str | None = None
    role: str = "user"
    is_active: bool = True
    is_verified: bool = False
    metadata: dict[str, Any] = field(default_factory=dict)
    created_at: str | None = None
    updated_at: str | None = None
    last_login_at: str | None = None


class UserBackend(Protocol):
    """用户存储后端协议 (Postgres 桥 / 内存实现均满足)。"""

    async def get_user_by_email(self, email: str, tenant_id: str) -> UserRecord | None: ...
    async def get_user_by_id(self, user_id: str) -> UserRecord | None: ...
    async def create_user(self, *, email: str, tenant_id: str, full_name: str | None,
                          role: str, metadata: dict[str, Any], password_hash: str) -> UserRecord: ...
    async def update_user(self, user_id: str, **fields: Any) -> UserRecord | None: ...
    async def deactivate_user(self, user_id: str) -> bool: ...
    async def list_users(self, tenant_id: str, skip: int, limit: int) -> list[UserRecord]: ...
    async def count_users(self, tenant_id: str) -> int: ...


# SSO/JIT 与 SCIM 创建的用户没有本地口令 — 使用显式不可用占位哈希,
# 任何口令校验路径都不可能匹配该值 (非任何哈希格式)。
UNUSABLE_PASSWORD_HASH_PREFIX = "!external-managed:"


class InMemoryUserBackend:
    """内存用户后端 (显式降级用 / 测试用)。

    注意: 数据不持久, 仅在 Postgres 存储不可用或单元测试时启用,
    日志会明确警告。
    """

    def __init__(self) -> None:
        self._users: dict[str, UserRecord] = {}
        self._lock = threading.Lock()

    async def get_user_by_email(self, email: str, tenant_id: str) -> UserRecord | None:
        with self._lock:
            for user in self._users.values():
                # email 全局唯一 (对齐 UserStoreModel.email unique 约束)
                if user.email == email and user.tenant_id == tenant_id:
                    return user
        return None

    async def get_user_by_id(self, user_id: str) -> UserRecord | None:
        with self._lock:
            return self._users.get(user_id)

    async def create_user(self, *, email: str, tenant_id: str, full_name: str | None,
                          role: str, metadata: dict[str, Any], password_hash: str) -> UserRecord:
        with self._lock:
            for user in self._users.values():
                if user.email == email:
                    raise SSOStorageError(f"email 已存在 (全局唯一约束): {email}")
            now = datetime.now(UTC).isoformat()
            record = UserRecord(
                user_id=str(uuid.uuid4()),
                email=email,
                tenant_id=tenant_id,
                full_name=full_name,
                role=role,
                is_active=True,
                is_verified=False,
                metadata=dict(metadata),
                created_at=now,
                updated_at=now,
            )
            self._users[record.user_id] = record
            return record

    async def update_user(self, user_id: str, **fields: Any) -> UserRecord | None:
        allowed = {"full_name", "role", "is_active", "is_verified", "last_login_at", "metadata"}
        with self._lock:
            user = self._users.get(user_id)
            if user is None:
                return None
            for key, value in fields.items():
                if key in allowed:
                    setattr(user, key, value)
            user.updated_at = datetime.now(UTC).isoformat()
            return user

    async def deactivate_user(self, user_id: str) -> bool:
        user = await self.update_user(user_id, is_active=False)
        return user is not None

    async def list_users(self, tenant_id: str, skip: int, limit: int) -> list[UserRecord]:
        with self._lock:
            users = [u for u in self._users.values() if u.tenant_id == tenant_id]
        return users[skip: skip + limit]

    async def count_users(self, tenant_id: str) -> int:
        with self._lock:
            return sum(1 for u in self._users.values() if u.tenant_id == tenant_id)


class _PostgresUserBackend:
    """Postgres 用户存储桥 (包装 backend.app.models.user_store)。

    调用失败时抛 SSOStorageError (显式失败, 绝不静默切换到内存,
    避免产生分叉用户数据)。
    """

    def __init__(self, store: Any):
        self._store = store

    @staticmethod
    def _to_record(model: Any) -> UserRecord:
        metadata: dict[str, Any] = {}
        raw = getattr(model, "metadata_json", None)
        if raw:
            try:
                metadata = json.loads(raw)
            except (TypeError, ValueError):
                metadata = {}
        created = getattr(model, "created_at", None)
        updated = getattr(model, "updated_at", None)
        last_login = getattr(model, "last_login_at", None)
        return UserRecord(
            user_id=model.user_id,
            email=model.email,
            tenant_id=model.tenant_id,
            full_name=getattr(model, "full_name", None),
            role=getattr(model, "role", "user"),
            is_active=bool(getattr(model, "is_active", True)),
            is_verified=bool(getattr(model, "is_verified", False)),
            metadata=metadata,
            created_at=created.isoformat() if hasattr(created, "isoformat") else None,
            updated_at=updated.isoformat() if hasattr(updated, "isoformat") else None,
            last_login_at=last_login.isoformat() if hasattr(last_login, "isoformat") else None,
        )

    async def get_user_by_email(self, email: str, tenant_id: str) -> UserRecord | None:
        try:
            model = await self._store.get_user_by_email(email, tenant_id)
        except SSOError:
            raise
        except Exception as exc:
            raise SSOStorageError(f"查询用户失败 (email={email}): {exc}") from exc
        return self._to_record(model) if model is not None else None

    async def get_user_by_id(self, user_id: str) -> UserRecord | None:
        try:
            model = await self._store.get_user_by_id(user_id)
        except Exception as exc:
            raise SSOStorageError(f"查询用户失败 (id={user_id}): {exc}") from exc
        return self._to_record(model) if model is not None else None

    async def create_user(self, *, email: str, tenant_id: str, full_name: str | None,
                          role: str, metadata: dict[str, Any], password_hash: str) -> UserRecord:
        try:
            model = await self._store.create_user(
                user_id=str(uuid.uuid4()),
                email=email,
                password_hash=password_hash,
                tenant_id=tenant_id,
                full_name=full_name,
                role=role,
                metadata=metadata,
            )
        except Exception as exc:
            raise SSOStorageError(f"创建用户失败 (email={email}): {exc}") from exc
        return self._to_record(model)

    async def update_user(self, user_id: str, **fields: Any) -> UserRecord | None:
        kwargs: dict[str, Any] = {}
        for key, value in fields.items():
            if key == "metadata":
                kwargs["metadata_json"] = value
            elif key in {"full_name", "role", "is_active", "is_verified", "last_login_at"}:
                kwargs[key] = value
        try:
            model = await self._store.update_user(user_id, **kwargs)
        except Exception as exc:
            raise SSOStorageError(f"更新用户失败 (id={user_id}): {exc}") from exc
        return self._to_record(model) if model is not None else None

    async def deactivate_user(self, user_id: str) -> bool:
        try:
            model = await self._store.deactivate_user(user_id)
        except Exception as exc:
            raise SSOStorageError(f"停用用户失败 (id={user_id}): {exc}") from exc
        return model is not None

    async def list_users(self, tenant_id: str, skip: int, limit: int) -> list[UserRecord]:
        try:
            models = await self._store.list_users(tenant_id=tenant_id, skip=skip, limit=limit)
        except Exception as exc:
            raise SSOStorageError(f"列出用户失败 (tenant={tenant_id}): {exc}") from exc
        return [self._to_record(m) for m in models]

    async def count_users(self, tenant_id: str) -> int:
        try:
            return await self._store.count_users(tenant_id=tenant_id)
        except Exception as exc:
            raise SSOStorageError(f"统计用户失败 (tenant={tenant_id}): {exc}") from exc


class UserStoreAdapter:
    """用户存储适配器: 优先 Postgres (惰性导入), 不可用时显式降级为内存。

    - 惰性导入 ``backend.app.models.user_store.get_user_store``, 不修改对方文件;
      存储层被另一代理 Postgres 化期间接口变动时, 仅本适配层需要跟进。
    - 降级为内存后端时 ``mode == "memory"`` 并输出 WARNING 日志 (显式降级,
      绝不静默)。
    - Postgres 后端运行期错误一律抛 SSOStorageError (显式失败)。
    """

    def __init__(self, backend: UserBackend | None = None):
        self._backend: UserBackend | None = backend
        self._mode: str | None = None
        self._resolve_lock = threading.Lock()

    # ------------------------------------------------------------------ 解析

    def _resolve_backend(self) -> UserBackend:
        if self._backend is not None:
            return self._backend
        with self._resolve_lock:
            if self._backend is not None:
                return self._backend
            try:
                from backend.app.models.user_store import get_user_store

                self._backend = _PostgresUserBackend(get_user_store())
                self._mode = "postgres"
                logger.info("UserStoreAdapter: 使用 Postgres 用户存储。")
            except Exception as exc:
                self._backend = InMemoryUserBackend()
                self._mode = "memory"
                logger.warning(
                    "UserStoreAdapter: Postgres 用户存储不可用 (%s), "
                    "显式降级为内存后端 — 数据不持久, 仅适用于开发/测试。",
                    exc,
                )
        return self._backend

    @property
    def mode(self) -> str:
        """当前后端模式: "postgres" | "memory" | "unresolved"。"""
        if self._backend is None:
            return "unresolved"
        return self._mode or "custom"

    def reset(self) -> None:
        """重置解析结果 (测试用)。"""
        with self._resolve_lock:
            self._backend = None
            self._mode = None

    # ------------------------------------------------------------------ 委托

    async def get_user_by_email(self, email: str, tenant_id: str = "default") -> UserRecord | None:
        return await self._resolve_backend().get_user_by_email(email, tenant_id)

    async def get_user_by_id(self, user_id: str) -> UserRecord | None:
        return await self._resolve_backend().get_user_by_id(user_id)

    async def create_user(self, *, email: str, tenant_id: str, full_name: str | None = None,
                          role: str = "user", metadata: dict[str, Any] | None = None,
                          password_hash: str | None = None) -> UserRecord:
        return await self._resolve_backend().create_user(
            email=email,
            tenant_id=tenant_id,
            full_name=full_name,
            role=role,
            metadata=metadata or {},
            password_hash=password_hash or f"{UNUSABLE_PASSWORD_HASH_PREFIX}{uuid.uuid4().hex}",
        )

    async def update_user(self, user_id: str, **fields: Any) -> UserRecord | None:
        return await self._resolve_backend().update_user(user_id, **fields)

    async def deactivate_user(self, user_id: str) -> bool:
        return await self._resolve_backend().deactivate_user(user_id)

    async def activate_user(self, user_id: str) -> bool:
        user = await self._resolve_backend().update_user(user_id, is_active=True)
        return user is not None

    async def list_users(self, tenant_id: str = "default", skip: int = 0,
                         limit: int = 100) -> list[UserRecord]:
        return await self._resolve_backend().list_users(tenant_id, skip, limit)

    async def count_users(self, tenant_id: str = "default") -> int:
        return await self._resolve_backend().count_users(tenant_id)


# ============================================================================
# JIT (Just-In-Time) 用户 provisioning
# ============================================================================

@dataclass
class JITProvisionResult:
    user_id: str
    email: str
    tenant_id: str
    created: bool
    storage_mode: str
    role: str = "user"


class JITProvisioner:
    """JIT 用户 provisioning: 按 (email, tenant) 查找, 不存在则创建。"""

    def __init__(self, adapter: UserStoreAdapter | None = None):
        self.adapter = adapter or UserStoreAdapter()

    async def provision(
        self,
        sso_user: SSOUser,
        *,
        tenant_id: str,
        provider_name: str,
    ) -> JITProvisionResult:
        if not sso_user.email:
            raise SSOAuthenticationError(
                "IdP 未返回 email claim, 无法进行 JIT provisioning "
                "(请检查 claim_mappings 或 IdP scope 配置)。"
            )

        existing = await self.adapter.get_user_by_email(sso_user.email, tenant_id)
        if existing is not None:
            metadata = dict(existing.metadata or {})
            sso_links = metadata.setdefault("sso_identities", {})
            sso_links[provider_name] = {
                "provider_user_id": sso_user.uid,
                "last_login": datetime.now(UTC).isoformat(),
            }
            updates: dict[str, Any] = {
                "last_login_at": datetime.now(UTC),
                "metadata": metadata,
            }
            if sso_user.name and not existing.full_name:
                updates["full_name"] = sso_user.name
            await self.adapter.update_user(existing.user_id, **updates)
            logger.info("JIT: 关联已存在用户 %s (provider=%s)", existing.user_id, provider_name)
            return JITProvisionResult(
                user_id=existing.user_id,
                email=existing.email,
                tenant_id=tenant_id,
                created=False,
                storage_mode=self.adapter.mode,
                role=existing.role,
            )

        record = await self.adapter.create_user(
            email=sso_user.email,
            tenant_id=tenant_id,
            full_name=sso_user.name or None,
            role="user",
            metadata={
                "sso_identities": {
                    provider_name: {
                        "provider_user_id": sso_user.uid,
                        "last_login": datetime.now(UTC).isoformat(),
                    }
                },
                "jit_provisioned": True,
                "jit_provider": provider_name,
                "groups": sso_user.groups,
            },
        )
        if sso_user.email_verified:
            await self.adapter.update_user(record.user_id, is_verified=True)
        logger.info(
            "JIT: 创建用户 %s (email=%s, tenant=%s, provider=%s)",
            record.user_id, record.email, tenant_id, provider_name,
        )
        return JITProvisionResult(
            user_id=record.user_id,
            email=record.email,
            tenant_id=tenant_id,
            created=True,
            storage_mode=self.adapter.mode,
            role="user",
        )


# ============================================================================
# SAML Manager — Beta (fail-closed)
# ============================================================================

SAML_BETA_MESSAGE = (
    "SAML 2.0 当前处于 Beta: 缺少 XML DSig 真实验签 (需 python3-saml/signxml), "
    "响应处理一律 fail-closed 拒绝。OIDC 已 GA, 生产 SSO 请使用 OIDC。"
)


class SAMLManager:
    """SAML 2.0 认证管理器 (Beta — AuthnRequest 可生成, 响应验签 fail-closed)。"""

    def __init__(self, config: SAMLConfig):
        self.config = config
        self.logger = logging.getLogger(f"{__name__}.SAMLManager")

    def generate_auth_request(self) -> str:
        """生成 SAML AuthnRequest (base64, HTTP-Redirect binding)。"""
        request_id = f"_{uuid.uuid4().hex}"
        issue_instant = datetime.now(UTC).isoformat()

        authn_request = f"""<?xml version="1.0" encoding="UTF-8"?>
<samlp:AuthnRequest xmlns:samlp="urn:oasis:names:tc:SAML:2.0:protocol"
    xmlns:saml="urn:oasis:names:tc:SAML:2.0:assertion"
    ID="{request_id}"
    Version="2.0"
    IssueInstant="{issue_instant}"
    Destination="{self.config.idp_sso_url}"
    AssertionConsumerServiceURL="{self.config.sp_acs_url}"
    ProtocolBinding="{self.config.binding_type.value}">
    <saml:Issuer>{self.config.sp_entity_id}</saml:Issuer>
    <samlp:NameIDPolicy Format="{self.config.name_id_format.value}" AllowCreate="true"/>
    <samlp:RequestedAuthnContext Comparison="exact">
        <saml:AuthnContextClassRef>urn:oasis:names:tc:SAML:2.0:ac:classes:Password</saml:AuthnContextClassRef>
    </samlp:RequestedAuthnContext>
</samlp:AuthnRequest>"""

        compressed = zlib.compress(authn_request.encode("utf-8"))
        encoded = base64.b64encode(compressed).decode("utf-8")
        self.logger.debug("Generated SAML AuthnRequest: %s", request_id)
        return encoded

    def parse_response(self, saml_response: str) -> SAMLAssertion:
        """解析并验证 SAML Response — Beta 阶段 fail-closed。"""
        raise SAMLSupportError(SAML_BETA_MESSAGE)

    def _verify_signature(self, saml_response: bytes) -> bool:
        """SAML 签名校验 — Beta 阶段 fail-closed (P0-05)。"""
        raise SAMLSupportError(SAML_BETA_MESSAGE)

    def generate_logout_request(self, session_index: str) -> str:
        """生成 SAML LogoutRequest (base64)。"""
        request_id = f"_{uuid.uuid4().hex}"
        issue_instant = datetime.now(UTC).isoformat()

        logout_request = f"""<?xml version="1.0" encoding="UTF-8"?>
<samlp:LogoutRequest xmlns:samlp="urn:oasis:names:tc:SAML:2.0:protocol"
    xmlns:saml="urn:oasis:names:tc:SAML:2.0:assertion"
    ID="{request_id}"
    Version="2.0"
    IssueInstant="{issue_instant}"
    Destination="{self.config.idp_slo_url}">
    <saml:Issuer>{self.config.sp_entity_id}</saml:Issuer>
    <saml:NameID Format="{self.config.name_id_format.value}">user@example.com</saml:NameID>
    <samlp:SessionIndex>{session_index}</samlp:SessionIndex>
</samlp:LogoutRequest>"""

        compressed = zlib.compress(logout_request.encode("utf-8"))
        return base64.b64encode(compressed).decode("utf-8")

    def generate_metadata(self) -> str:
        """生成 SP 元数据 XML。"""
        return f"""<?xml version="1.0" encoding="UTF-8"?>
<EntityDescriptor xmlns="urn:oasis:names:tc:SAML:2.0:metadata"
    entityID="{self.config.sp_entity_id}">
    <SPSSODescriptor AuthnRequestsSigned="{str(self.config.sign_requests).lower()}"
        WantAssertionsSigned="true"
        protocolSupportEnumeration="urn:oasis:names:tc:SAML:2.0:protocol">
        <AssertionConsumerService Binding="urn:oasis:names:tc:SAML:2.0:bindings:HTTP-POST"
            Location="{self.config.sp_acs_url}"
            index="0"
            isDefault="true"/>
    </SPSSODescriptor>
</EntityDescriptor>"""


# ============================================================================
# SSO Session Manager
# ============================================================================

class SSOSessionManager:
    """SSO 会话管理器 (进程内)。"""

    def __init__(self, session_timeout_minutes: int = 480, idle_timeout_minutes: int = 30):
        self.session_timeout_minutes = session_timeout_minutes
        self.idle_timeout_minutes = idle_timeout_minutes
        self.sessions: dict[str, SSOSession] = {}
        self.logger = logging.getLogger(f"{__name__}.SSOSessionManager")

    def create_session(
        self,
        user_id: str,
        tenant_id: str,
        provider: SSOProvider,
        ip_address: str = "",
        user_agent: str = "",
    ) -> SSOSession:
        session = SSOSession(
            user_id=user_id,
            tenant_id=tenant_id,
            provider=provider,
            expires_at=datetime.now(UTC) + timedelta(minutes=self.session_timeout_minutes),
            ip_address=ip_address,
            user_agent=user_agent,
        )
        self.sessions[session.session_id] = session
        self.logger.info("Created SSO session %s for user %s", session.session_id, user_id)
        return session

    def get_session(self, session_id: str) -> SSOSession | None:
        session = self.sessions.get(session_id)
        if session is None:
            return None
        if session.is_expired() or session.is_idle_expired(self.idle_timeout_minutes):
            self.invalidate_session(session_id)
            return None
        session.last_activity = datetime.now(UTC)
        return session

    def invalidate_session(self, session_id: str) -> None:
        if session_id in self.sessions:
            self.sessions[session_id].active = False
            self.logger.info("Invalidated SSO session %s", session_id)

    def cleanup_expired_sessions(self) -> int:
        expired = [
            sid for sid, session in self.sessions.items()
            if session.is_expired() or session.is_idle_expired(self.idle_timeout_minutes)
        ]
        for sid in expired:
            del self.sessions[sid]
        if expired:
            self.logger.info("Cleaned up %d expired SSO sessions", len(expired))
        return len(expired)


# ============================================================================
# Multi-tenant SSO Manager
# ============================================================================

class MultiTenantSSOManager:
    """多租户 SSO 管理器。"""

    def __init__(self):
        self.saml_configs: dict[str, SAMLConfig] = {}
        self.oidc_configs: dict[str, OIDCConfig] = {}
        self.saml_managers: dict[str, SAMLManager] = {}
        self.oidc_managers: dict[str, OIDCManager] = {}
        self.session_manager = SSOSessionManager()
        self.state_store = OIDCStateStore()
        self.logger = logging.getLogger(f"{__name__}.MultiTenantSSOManager")

    def register_saml_config(self, config: SAMLConfig) -> None:
        if not config.enabled:
            self.logger.warning("SAML config for tenant %s is disabled", config.tenant_id)
            return
        self.saml_configs[config.tenant_id] = config
        self.saml_managers[config.tenant_id] = SAMLManager(config)
        self.logger.info("Registered SAML config (Beta) for tenant %s", config.tenant_id)

    def register_oidc_config(
        self,
        config: OIDCConfig,
        *,
        http_client: Any = None,
    ) -> OIDCManager:
        """注册租户 OIDC 配置, 返回管理器实例。

        Args:
            config: OIDC 配置。
            http_client: 可选注入的 httpx.AsyncClient (测试用 MockTransport)。
        """
        if not config.enabled:
            self.logger.warning("OIDC config for tenant %s is disabled", config.tenant_id)
            raise SSOConfigurationError(f"OIDC provider {config.provider_name} is disabled")
        self.oidc_configs[config.tenant_id] = config
        manager = OIDCManager(config, http_client=http_client)
        self.oidc_managers[config.tenant_id] = manager
        self.logger.info(
            "Registered OIDC config for tenant %s (provider=%s)",
            config.tenant_id, config.provider_name,
        )
        return manager

    def get_saml_manager(self, tenant_id: str) -> SAMLManager | None:
        return self.saml_managers.get(tenant_id)

    def get_oidc_manager(self, tenant_id: str) -> OIDCManager | None:
        return self.oidc_managers.get(tenant_id)

    def find_oidc_manager(self, provider_name: str, tenant_id: str) -> OIDCManager | None:
        """按 provider 名 + 租户查找 OIDC 管理器。"""
        manager = self.oidc_managers.get(tenant_id)
        if manager is not None and manager.config.provider_name == provider_name:
            return manager
        for candidate in self.oidc_managers.values():
            if candidate.config.provider_name == provider_name and (
                tenant_id == "*" or candidate.config.tenant_id in (tenant_id, "default")
            ):
                return candidate
        return None

    def get_enabled_providers(self, tenant_id: str) -> list[SSOProvider]:
        providers: list[SSOProvider] = []
        if tenant_id in self.saml_configs:
            providers.append(SSOProvider.SAML)
        if tenant_id in self.oidc_configs:
            providers.append(SSOProvider.OIDC)
        return providers

    def list_oidc_providers(self) -> list[dict[str, str]]:
        """列出已注册 OIDC 提供方 (脱敏: 不含 secret)。"""
        return [
            {
                "provider_name": config.provider_name,
                "tenant_id": config.tenant_id,
                "client_id": config.client_id,
                "discovery_url": config.discovery_url,
            }
            for config in self.oidc_configs.values()
        ]


# 全局实例
_sso_manager = MultiTenantSSOManager()


def get_sso_manager() -> MultiTenantSSOManager:
    """获取全局 SSO 管理器实例。"""
    return _sso_manager


def set_state_store(store: OIDCStateStore) -> None:
    """替换全局 state 存储 (集成波可注入 Redis 等分布式实现)。"""
    _sso_manager.state_store = store
