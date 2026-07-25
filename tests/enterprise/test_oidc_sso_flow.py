"""P1-02 OIDC SSO 流程测试 — Mock IdP (httpx MockTransport)。

覆盖:
- discovery 拉取 + 缓存
- 授权 URL 构建 (state/nonce/client_id/redirect_uri)
- 完整授权码回调流程 (TestClient + 自建 FastAPI app, 不依赖 main.py)
- state 一次性/重放拒绝、nonce 校验、签名篡改拒绝、audience 拒绝
- JIT provisioning (创建 + 幂等关联)
- userinfo 兜底
- HS256 对称验签路径
- SAML Beta fail-closed (501)
"""

from __future__ import annotations

import json
import time
from typing import Any, Optional

import httpx
import pytest

# Skip entire module if joserfc is not installed
pytest.importorskip("joserfc", reason="joserfc not installed")

from cryptography.hazmat.primitives.asymmetric import rsa
from fastapi import FastAPI
from fastapi.testclient import TestClient
from joserfc import jwt as jose_jwt

import backend.app.api.sso as sso_module
from backend.app.core.saml_sso import (
    InMemoryUserBackend,
    JITProvisioner,
    OIDCConfig,
    OIDCManager,
    OIDCStateStore,
    UserStoreAdapter,
)

IDP_BASE = "https://idp.example.com"
KID = "test-kid-1"


# ============================================================================
# Mock IdP 装备
# ============================================================================

def _b64u_int(value: int) -> str:
    import base64

    raw = value.to_bytes((value.bit_length() + 7) // 8, "big")
    return base64.urlsafe_b64encode(raw).decode().rstrip("=")


class MockIdP:
    """可编程的 Mock OIDC IdP。"""

    def __init__(self) -> None:
        self.private_key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
        numbers = self.private_key.public_key().public_numbers()
        self.jwks = {
            "keys": [
                {
                    "kty": "RSA",
                    "kid": KID,
                    "use": "sig",
                    "alg": "RS256",
                    "n": _b64u_int(numbers.n),
                    "e": _b64u_int(numbers.e),
                }
            ]
        }
        self.discovery = {
            "issuer": IDP_BASE,
            "authorization_endpoint": f"{IDP_BASE}/authorize",
            "token_endpoint": f"{IDP_BASE}/token",
            "userinfo_endpoint": f"{IDP_BASE}/userinfo",
            "jwks_uri": f"{IDP_BASE}/jwks",
        }
        # 测试可编程行为
        self.expected_nonce: Optional[str] = None
        self.nonce_override: Optional[str] = None
        self.audience: str = "test-client-id"
        self.signing_key: Any = self.private_key
        self.signing_alg: str = "RS256"
        self.signing_kid: Optional[str] = KID
        self.include_id_token: bool = True
        self.include_email: bool = True
        self.userinfo = {
            "sub": "idp-user-42",
            "email": "alice@example.com",
            "email_verified": True,
            "name": "Alice Liddell",
        }
        self.token_requests: list[dict[str, Any]] = []

    # ------------------------------------------------------------------ JWT

    def make_id_token(self, **claim_overrides: Any) -> str:
        now = int(time.time())
        claims: dict[str, Any] = {
            "iss": IDP_BASE,
            "aud": self.audience,
            "sub": "idp-user-42",
            "exp": now + 600,
            "iat": now,
            "nonce": self.nonce_override or self.expected_nonce,
            "name": "Alice Liddell",
        }
        if self.include_email:
            claims["email"] = "alice@example.com"
            claims["email_verified"] = True
        claims.update(claim_overrides)

        header: dict[str, Any] = {"alg": self.signing_alg, "typ": "JWT"}
        if self.signing_kid:
            header["kid"] = self.signing_kid
        if self.signing_alg.startswith("RS"):
            from cryptography.hazmat.primitives.serialization import (
                Encoding,
                NoEncryption,
                PrivateFormat,
            )
            from joserfc.jwk import RSAKey

            pem = self.signing_key.private_bytes(
                Encoding.PEM, PrivateFormat.PKCS8, NoEncryption()
            )
            key: Any = RSAKey.import_key(pem)
        elif self.signing_alg.startswith("HS"):
            from joserfc.jwk import OctKey

            key = OctKey.import_key(self.signing_key)
        else:
            raise AssertionError(f"测试未支持的签名算法: {self.signing_alg}")
        return jose_jwt.encode(header, claims, key)

    # ------------------------------------------------------------------ HTTP

    def handler(self, request: httpx.Request) -> httpx.Response:
        path = request.url.path
        if path == "/.well-known/openid-configuration":
            return httpx.Response(200, json=self.discovery)
        if path == "/jwks":
            return httpx.Response(200, json=self.jwks)
        if path == "/token":
            body = request.content.decode()
            params = dict(x.split("=", 1) for x in body.split("&") if "=" in x)
            self.token_requests.append(params)
            if params.get("grant_type") != "authorization_code":
                return httpx.Response(400, json={"error": "unsupported_grant_type"})
            if params.get("code") != "valid-code":
                return httpx.Response(400, json={"error": "invalid_grant"})
            payload: dict[str, Any] = {
                "access_token": "idp-access-token-1",
                "token_type": "Bearer",
                "expires_in": 3600,
                "scope": "openid profile email",
            }
            if self.include_id_token:
                payload["id_token"] = self.make_id_token()
            return httpx.Response(200, json=payload)
        if path == "/userinfo":
            auth = request.headers.get("Authorization", "")
            if auth != "Bearer idp-access-token-1":
                return httpx.Response(401, json={"error": "invalid_token"})
            return httpx.Response(200, json=self.userinfo)
        if path == "/authorize":
            return httpx.Response(200, text="authorize page")
        return httpx.Response(404, json={"error": "not_found"})

    def make_http_client(self) -> httpx.AsyncClient:
        return httpx.AsyncClient(transport=httpx.MockTransport(self.handler))


# ============================================================================
# Fixtures
# ============================================================================

PROVIDER = "mockidp"
TENANT = "tenant-oidc-test"
CLIENT_ID = "test-client-id"


def _config() -> OIDCConfig:
    return OIDCConfig(
        provider_name=PROVIDER,
        discovery_url=f"{IDP_BASE}/.well-known/openid-configuration",
        client_id=CLIENT_ID,
        client_secret="test-client-secret",
        redirect_uri="https://app.example.com/sso/callback",
        tenant_id=TENANT,
    )


@pytest.fixture()
def idp() -> MockIdP:
    return MockIdP()


@pytest.fixture()
def manager(idp: MockIdP) -> OIDCManager:
    return OIDCManager(_config(), http_client=idp.make_http_client())


@pytest.fixture()
def sso_app(idp: MockIdP, monkeypatch: pytest.MonkeyPatch):
    """自建 FastAPI app (不依赖 main.py), 注入 Mock IdP 与内存用户存储。"""
    # 内存用户存储 + 独立 provisioner
    adapter = UserStoreAdapter(InMemoryUserBackend())
    monkeypatch.setattr(sso_module, "user_adapter", adapter)
    monkeypatch.setattr(sso_module, "jit_provisioner", JITProvisioner(adapter))

    # 真实 LocalSessionIssuer (惰性走 api.auth, 内存令牌) — 可用;
    # 但为确定性, 注入假签发器
    class FakeIssuer:
        def issue(self, user_id: str):
            return {"access_token": f"local-session-for-{user_id}", "token_type": "Bearer"}

        def _resolve(self):
            return True

    monkeypatch.setattr(sso_module, "session_issuer", FakeIssuer())

    sso_module.register_oidc_provider(_config(), http_client=idp.make_http_client())

    app = FastAPI()
    app.include_router(sso_module.oidc_router)
    client = TestClient(app)
    return client, idp, adapter


def _do_authorize(client: TestClient, idp: MockIdP) -> str:
    resp = client.get(f"/api/v1/sso/oidc/{PROVIDER}/authorize", params={"tenant_id": TENANT})
    assert resp.status_code == 200, resp.text
    data = resp.json()
    url = data["authorization_url"]
    assert url.startswith(f"{IDP_BASE}/authorize?")
    assert f"client_id={CLIENT_ID}" in url
    assert "nonce=" in url
    assert f"state={data['state']}" in url
    # 把服务端 nonce 同步给 Mock IdP (真实流程中 IdP 经 authorize 请求拿到)
    entry = sso_module.sso_manager.state_store.peek(data["state"])
    assert entry is not None
    idp.expected_nonce = entry.nonce
    return data["state"]


# ============================================================================
# 单元级: manager / state store
# ============================================================================

@pytest.mark.asyncio
async def test_discovery_and_authorization_url(manager: OIDCManager, idp: MockIdP):
    doc = await manager.get_discovery_document()
    assert doc["issuer"] == IDP_BASE
    # 缓存: 第二次命中缓存 (对象同一)
    assert await manager.get_discovery_document() is doc

    url = await manager.generate_authorization_url("state-1", "nonce-1")
    assert url.startswith(f"{IDP_BASE}/authorize?")
    assert "state=state-1" in url and "nonce=nonce-1" in url
    assert "scope=openid+profile+email" in url or "scope=openid%20profile%20email" in url


@pytest.mark.asyncio
async def test_jwks_fetch_and_cache(manager: OIDCManager):
    jwks = await manager.get_jwks()
    assert jwks["keys"][0]["kid"] == KID
    assert await manager.get_jwks() is jwks


def test_state_store_one_time():
    store = OIDCStateStore(ttl_seconds=60)
    entry = store.create(tenant_id="t", provider_name="p", redirect_uri="https://x/cb")
    assert store.consume(entry.state) is not None
    # 重放 → None
    assert store.consume(entry.state) is None
    assert store.consume("nonexistent") is None


def test_state_store_expiry():
    store = OIDCStateStore(ttl_seconds=0)
    entry = store.create(tenant_id="t", provider_name="p", redirect_uri="https://x/cb")
    entry.created_at -= 10  # 强制过期
    assert store.consume(entry.state) is None


# ============================================================================
# 路由级: 完整 OIDC 流程
# ============================================================================

def test_full_oidc_login_flow(sso_app):
    client, idp, adapter = sso_app

    state = _do_authorize(client, idp)
    resp = client.post(
        f"/api/v1/sso/oidc/{PROVIDER}/callback",
        json={"code": "valid-code", "state": state},
    )
    assert resp.status_code == 200, resp.text
    data = resp.json()

    assert data["access_token"], "本地会话令牌缺失"
    assert data["session"]["issued"] is True
    assert data["user"]["email"] == "alice@example.com"
    assert data["user"]["tenant_id"] == TENANT
    assert data["sso"]["jit_provisioned"] is True
    assert data["sso"]["storage_mode"] in {"memory", "custom"}

    # token 端点确实被调用且带授权码
    assert idp.token_requests and idp.token_requests[0].get("code") == "valid-code"

    # 第二次登录: JIT 幂等关联, 不再创建
    state2 = _do_authorize(client, idp)
    resp2 = client.post(
        f"/api/v1/sso/oidc/{PROVIDER}/callback",
        json={"code": "valid-code", "state": state2},
    )
    assert resp2.status_code == 200, resp2.text
    assert resp2.json()["sso"]["jit_provisioned"] is False
    # 同一用户 id
    assert resp2.json()["user"]["user_id"] == data["user"]["user_id"]


def test_callback_rejects_unknown_state(sso_app):
    client, _idp, _adapter = sso_app
    resp = client.post(
        f"/api/v1/sso/oidc/{PROVIDER}/callback",
        json={"code": "valid-code", "state": "forged-state"},
    )
    assert resp.status_code == 401


def test_callback_rejects_replayed_state(sso_app):
    client, idp, _adapter = sso_app
    state = _do_authorize(client, idp)
    resp1 = client.post(
        f"/api/v1/sso/oidc/{PROVIDER}/callback",
        json={"code": "valid-code", "state": state},
    )
    assert resp1.status_code == 200
    # 同一 state 重放
    resp2 = client.post(
        f"/api/v1/sso/oidc/{PROVIDER}/callback",
        json={"code": "valid-code", "state": state},
    )
    assert resp2.status_code == 401


def test_callback_rejects_bad_nonce(sso_app):
    client, idp, _adapter = sso_app
    state = _do_authorize(client, idp)
    idp.nonce_override = "attacker-nonce"
    resp = client.post(
        f"/api/v1/sso/oidc/{PROVIDER}/callback",
        json={"code": "valid-code", "state": state},
    )
    assert resp.status_code == 401
    assert "nonce" in resp.json()["detail"].lower()


def test_callback_rejects_tampered_signature(sso_app):
    client, idp, _adapter = sso_app
    state = _do_authorize(client, idp)
    # 用另一把私钥签名
    idp.signing_key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    resp = client.post(
        f"/api/v1/sso/oidc/{PROVIDER}/callback",
        json={"code": "valid-code", "state": state},
    )
    assert resp.status_code == 401


def test_callback_rejects_wrong_audience(sso_app):
    client, idp, _adapter = sso_app
    state = _do_authorize(client, idp)
    idp.audience = "some-other-client"
    resp = client.post(
        f"/api/v1/sso/oidc/{PROVIDER}/callback",
        json={"code": "valid-code", "state": state},
    )
    assert resp.status_code == 401


def test_callback_rejects_expired_token(sso_app):
    client, idp, _adapter = sso_app
    state = _do_authorize(client, idp)

    original = idp.make_id_token

    def expired_token(**kw):
        return original(exp=int(time.time()) - 3600, iat=int(time.time()) - 7200, **kw)

    idp.make_id_token = expired_token  # type: ignore[assignment]
    resp = client.post(
        f"/api/v1/sso/oidc/{PROVIDER}/callback",
        json={"code": "valid-code", "state": state},
    )
    assert resp.status_code == 401


def test_callback_rejects_invalid_grant(sso_app):
    client, idp, _adapter = sso_app
    state = _do_authorize(client, idp)
    resp = client.post(
        f"/api/v1/sso/oidc/{PROVIDER}/callback",
        json={"code": "wrong-code", "state": state},
    )
    assert resp.status_code == 401


def test_userinfo_fallback_when_email_missing(sso_app):
    client, idp, _adapter = sso_app
    state = _do_authorize(client, idp)
    idp.include_email = False  # id_token 无 email → userinfo 兜底
    resp = client.post(
        f"/api/v1/sso/oidc/{PROVIDER}/callback",
        json={"code": "valid-code", "state": state},
    )
    assert resp.status_code == 200, resp.text
    assert resp.json()["user"]["email"] == "alice@example.com"


def test_authorize_unknown_provider(sso_app):
    client, _idp, _adapter = sso_app
    resp = client.get("/api/v1/sso/oidc/nope/authorize", params={"tenant_id": TENANT})
    assert resp.status_code == 404


# ============================================================================
# HS256 对称验签路径
# ============================================================================

@pytest.mark.asyncio
async def test_hs256_id_token(idp: MockIdP):
    secret = "hs-client-secret"
    idp.signing_alg = "HS256"
    idp.signing_key = secret
    idp.signing_kid = None

    config = OIDCConfig(
        provider_name="hs-provider",
        discovery_url=f"{IDP_BASE}/.well-known/openid-configuration",
        client_id=CLIENT_ID,
        client_secret=secret,
        redirect_uri="https://app.example.com/cb",
        tenant_id="tenant-hs",
    )
    manager = OIDCManager(config, http_client=idp.make_http_client())
    idp.audience = CLIENT_ID
    idp.expected_nonce = "n-1"
    token = idp.make_id_token()
    claims = await manager.validate_id_token(token, expected_nonce="n-1")
    assert claims["sub"] == "idp-user-42"


# ============================================================================
# SAML Beta (P1-05: 签名验证已启用, 未配置 IdP 时仍 501)
# ============================================================================

def test_saml_endpoints_fail_closed(sso_app):
    client, _idp, _adapter = sso_app
    # P1-05: SAML login 在未配置 IdP SSO URL 时返回 501
    resp_login = client.get(f"/api/v1/sso/saml/{PROVIDER}/login")
    assert resp_login.status_code == 501
    assert "SSO URL" in resp_login.json()["detail"] or "未配置" in resp_login.json()["detail"]

    # P1-05: SAML ACS 缺少 SAMLResponse 时返回 400
    resp_acs = client.post(f"/api/v1/sso/saml/{PROVIDER}/acs")
    assert resp_acs.status_code in (400, 422, 501)


# ============================================================================
# status / providers
# ============================================================================

def test_status_and_providers(sso_app):
    client, _idp, _adapter = sso_app
    status = client.get("/api/v1/sso/status")
    assert status.status_code == 200
    body = status.json()
    assert body["oidc"]["status"] == "GA"
    assert body["saml"]["status"] == "beta"
    assert body["saml"]["enabled"] is True  # P1-05: 签名验证已启用
    assert body["jwt_backend"]["authlib_or_joserfc_available"] is True
    assert body["oidc"]["providers_configured"] >= 1

    providers = client.get("/api/v1/sso/providers")
    assert providers.status_code == 200
    names = [p["provider_name"] for p in providers.json()["oidc_providers"]]
    assert PROVIDER in names
