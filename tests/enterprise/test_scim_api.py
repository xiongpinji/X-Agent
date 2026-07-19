"""P1-02 SCIM 2.0 API 测试 — TestClient 直测 router (自建 FastAPI app, 不依赖 main.py)。

覆盖:
- Users CRUD: create/get/list/put/patch/delete
- Bearer 令牌鉴权 (缺失/非法/空注册表 fail-closed)
- 租户绑定与隔离 (跨租户 404 / 列表互不可见)
- 过滤 (userName eq / externalId eq / 非法过滤器)
- 分页 (startIndex/count)
- SCIM 错误格式 (schemas/status/scimType/detail)
- 存储适配层真实惰性接线 (monkeypatch user_store.get_user_store → postgres 模式)
"""

from __future__ import annotations

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from backend.app.api.scim import SCIMTokenRegistry, build_scim_router
from backend.app.core.saml_sso import InMemoryUserBackend, UserStoreAdapter

TOKEN_A = "scim-token-tenant-a-secret"
TOKEN_B = "scim-token-tenant-b-secret"

SCIM_USER = "urn:ietf:params:scim:schemas:core:2.0:User"
SCIM_ERROR = "urn:ietf:params:scim:api:messages:2.0:Error"
SCIM_PATCH = "urn:ietf:params:scim:api:messages:2.0:PatchOp"


@pytest.fixture()
def client() -> TestClient:
    registry = SCIMTokenRegistry()
    registry.register(TOKEN_A, "tenant-a", "tenant A provisioning")
    registry.register(TOKEN_B, "tenant-b", "tenant B provisioning")
    adapter = UserStoreAdapter(InMemoryUserBackend())
    app = FastAPI()
    app.include_router(build_scim_router(adapter=adapter, registry=registry))
    return TestClient(app)


def _auth(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


def _create_user(client: TestClient, token: str, user_name: str, **extra):
    payload = {
        "schemas": [SCIM_USER],
        "userName": user_name,
        "name": {"givenName": "Test", "familyName": "User", "formatted": "Test User"},
        **extra,
    }
    return client.post("/scim/v2/Users", json=payload, headers=_auth(token))


# ============================================================================
# 鉴权
# ============================================================================

def test_missing_auth_header(client: TestClient):
    resp = client.get("/scim/v2/Users")
    assert resp.status_code == 401
    body = resp.json()
    assert body["schemas"] == [SCIM_ERROR]
    assert body["status"] == "401"
    assert resp.headers.get("WWW-Authenticate", "").startswith("Bearer")


def test_invalid_token(client: TestClient):
    resp = client.get("/scim/v2/Users", headers=_auth("wrong-token"))
    assert resp.status_code == 401


def test_malformed_auth_header(client: TestClient):
    resp = client.get("/scim/v2/Users", headers={"Authorization": "Basic abc"})
    assert resp.status_code == 401


def test_empty_registry_fail_closed():
    app = FastAPI()
    app.include_router(
        build_scim_router(
            adapter=UserStoreAdapter(InMemoryUserBackend()),
            registry=SCIMTokenRegistry(),  # 空注册表
        )
    )
    empty_client = TestClient(app)
    resp = empty_client.get("/scim/v2/Users", headers=_auth(TOKEN_A))
    assert resp.status_code == 503
    assert resp.json()["schemas"] == [SCIM_ERROR]


# ============================================================================
# CRUD
# ============================================================================

def test_create_user(client: TestClient):
    resp = _create_user(client, TOKEN_A, "alice@a.com", externalId="ext-001")
    assert resp.status_code == 201, resp.text
    assert resp.headers["content-type"].startswith("application/scim+json")
    assert "Location" in resp.headers

    body = resp.json()
    assert body["schemas"] == [SCIM_USER]
    assert body["userName"] == "alice@a.com"
    assert body["externalId"] == "ext-001"
    assert body["active"] is True
    assert body["name"]["formatted"] == "Test User"
    assert body["emails"][0]["value"] == "alice@a.com"
    assert body["meta"]["resourceType"] == "User"
    assert body["id"]


def test_create_duplicate_user_conflict(client: TestClient):
    resp1 = _create_user(client, TOKEN_A, "dup@a.com")
    assert resp1.status_code == 201
    resp2 = _create_user(client, TOKEN_A, "dup@a.com")
    assert resp2.status_code == 409
    assert resp2.json()["scimType"] == "uniqueness"


def test_create_user_missing_username(client: TestClient):
    resp = client.post(
        "/scim/v2/Users",
        json={"schemas": [SCIM_USER], "name": {"formatted": "No Name"}},
        headers=_auth(TOKEN_A),
    )
    assert resp.status_code == 400
    assert resp.json()["scimType"] == "invalidValue"


def test_create_inactive_user(client: TestClient):
    resp = _create_user(client, TOKEN_A, "inactive@a.com", active=False)
    assert resp.status_code == 201
    assert resp.json()["active"] is False


def test_get_user(client: TestClient):
    created = _create_user(client, TOKEN_A, "get@a.com").json()
    resp = client.get(f"/scim/v2/Users/{created['id']}", headers=_auth(TOKEN_A))
    assert resp.status_code == 200
    assert resp.json()["userName"] == "get@a.com"


def test_get_user_not_found(client: TestClient):
    resp = client.get("/scim/v2/Users/nonexistent-id", headers=_auth(TOKEN_A))
    assert resp.status_code == 404
    assert resp.json()["schemas"] == [SCIM_ERROR]


def test_get_user_cross_tenant_is_404(client: TestClient):
    """租户隔离: B 租户令牌访问 A 租户用户 → 404 (不泄露存在性)。"""
    created = _create_user(client, TOKEN_A, "isolated@a.com").json()
    resp = client.get(f"/scim/v2/Users/{created['id']}", headers=_auth(TOKEN_B))
    assert resp.status_code == 404


def test_list_users_pagination(client: TestClient):
    for idx in range(3):
        assert _create_user(client, TOKEN_A, f"page{idx}@a.com").status_code == 201

    resp = client.get("/scim/v2/Users", params={"count": 2}, headers=_auth(TOKEN_A))
    assert resp.status_code == 200
    body = resp.json()
    assert body["totalResults"] == 3
    assert body["itemsPerPage"] == 2
    assert body["startIndex"] == 1

    resp2 = client.get(
        "/scim/v2/Users", params={"count": 2, "startIndex": 3}, headers=_auth(TOKEN_A)
    )
    body2 = resp2.json()
    assert body2["itemsPerPage"] == 1
    assert body2["totalResults"] == 3


def test_list_users_tenant_isolation(client: TestClient):
    _create_user(client, TOKEN_A, "only-a@a.com")
    resp = client.get("/scim/v2/Users", headers=_auth(TOKEN_B))
    assert resp.status_code == 200
    assert resp.json()["totalResults"] == 0
    assert resp.json()["Resources"] == []


def test_list_filter_username(client: TestClient):
    _create_user(client, TOKEN_A, "filter-me@a.com")
    _create_user(client, TOKEN_A, "other@a.com")
    resp = client.get(
        "/scim/v2/Users",
        params={"filter": 'userName eq "filter-me@a.com"'},
        headers=_auth(TOKEN_A),
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["totalResults"] == 1
    assert body["Resources"][0]["userName"] == "filter-me@a.com"


def test_list_filter_external_id(client: TestClient):
    _create_user(client, TOKEN_A, "ext@a.com", externalId="okta-123")
    resp = client.get(
        "/scim/v2/Users",
        params={"filter": 'externalId eq "okta-123"'},
        headers=_auth(TOKEN_A),
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["totalResults"] == 1
    assert body["Resources"][0]["externalId"] == "okta-123"


def test_list_invalid_filter(client: TestClient):
    resp = client.get(
        "/scim/v2/Users",
        params={"filter": "name co \"x\""},
        headers=_auth(TOKEN_A),
    )
    assert resp.status_code == 400
    assert resp.json()["scimType"] == "invalidFilter"


def test_replace_user_put(client: TestClient):
    created = _create_user(client, TOKEN_A, "put@a.com").json()
    resp = client.put(
        f"/scim/v2/Users/{created['id']}",
        json={
            "schemas": [SCIM_USER],
            "userName": "put@a.com",
            "name": {"formatted": "Replaced Name"},
            "active": False,
            "externalId": "ext-put",
        },
        headers=_auth(TOKEN_A),
    )
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["name"]["formatted"] == "Replaced Name"
    assert body["active"] is False
    assert body["externalId"] == "ext-put"


def test_put_username_change_rejected(client: TestClient):
    """存储层不支持 email 变更 → 显式 mutability 错误, 不静默忽略。"""
    created = _create_user(client, TOKEN_A, "orig@a.com").json()
    resp = client.put(
        f"/scim/v2/Users/{created['id']}",
        json={"schemas": [SCIM_USER], "userName": "changed@a.com", "active": True},
        headers=_auth(TOKEN_A),
    )
    assert resp.status_code == 400
    assert resp.json()["scimType"] == "mutability"


def test_patch_deactivate_and_reactivate(client: TestClient):
    created = _create_user(client, TOKEN_A, "patch@a.com").json()
    uid = created["id"]

    # 停用
    resp = client.patch(
        f"/scim/v2/Users/{uid}",
        json={
            "schemas": [SCIM_PATCH],
            "Operations": [{"op": "replace", "path": "active", "value": False}],
        },
        headers=_auth(TOKEN_A),
    )
    assert resp.status_code == 200
    assert resp.json()["active"] is False

    # 重新激活 (无 path 形式)
    resp2 = client.patch(
        f"/scim/v2/Users/{uid}",
        json={
            "schemas": [SCIM_PATCH],
            "Operations": [{"op": "replace", "value": {"active": True}}],
        },
        headers=_auth(TOKEN_A),
    )
    assert resp2.status_code == 200
    assert resp2.json()["active"] is True


def test_patch_name_and_external_id(client: TestClient):
    created = _create_user(client, TOKEN_A, "patch2@a.com").json()
    uid = created["id"]
    resp = client.patch(
        f"/scim/v2/Users/{uid}",
        json={
            "schemas": [SCIM_PATCH],
            "Operations": [
                {"op": "replace", "path": "name.formatted", "value": "Patched Name"},
                {"op": "add", "path": "externalId", "value": "ext-new"},
            ],
        },
        headers=_auth(TOKEN_A),
    )
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["name"]["formatted"] == "Patched Name"
    assert body["externalId"] == "ext-new"


def test_patch_remove_attribute(client: TestClient):
    created = _create_user(client, TOKEN_A, "patch3@a.com", externalId="ext-rm").json()
    uid = created["id"]
    resp = client.patch(
        f"/scim/v2/Users/{uid}",
        json={
            "schemas": [SCIM_PATCH],
            "Operations": [{"op": "remove", "path": "externalId"}],
        },
        headers=_auth(TOKEN_A),
    )
    assert resp.status_code == 200
    assert resp.json()["externalId"] is None


def test_patch_invalid_path(client: TestClient):
    created = _create_user(client, TOKEN_A, "patch4@a.com").json()
    resp = client.patch(
        f"/scim/v2/Users/{created['id']}",
        json={
            "schemas": [SCIM_PATCH],
            "Operations": [{"op": "replace", "path": "groups", "value": []}],
        },
        headers=_auth(TOKEN_A),
    )
    assert resp.status_code == 400
    assert resp.json()["scimType"] == "invalidPath"


def test_patch_wrong_schemas(client: TestClient):
    created = _create_user(client, TOKEN_A, "patch5@a.com").json()
    resp = client.patch(
        f"/scim/v2/Users/{created['id']}",
        json={
            "schemas": ["urn:wrong"],
            "Operations": [{"op": "replace", "path": "active", "value": False}],
        },
        headers=_auth(TOKEN_A),
    )
    assert resp.status_code == 400


def test_patch_not_found(client: TestClient):
    resp = client.patch(
        "/scim/v2/Users/nope",
        json={
            "schemas": [SCIM_PATCH],
            "Operations": [{"op": "replace", "path": "active", "value": False}],
        },
        headers=_auth(TOKEN_A),
    )
    assert resp.status_code == 404


def test_delete_user_deactivates(client: TestClient):
    created = _create_user(client, TOKEN_A, "delete@a.com").json()
    uid = created["id"]
    resp = client.delete(f"/scim/v2/Users/{uid}", headers=_auth(TOKEN_A))
    assert resp.status_code == 204

    # 记录保留 (软停用), active=False
    after = client.get(f"/scim/v2/Users/{uid}", headers=_auth(TOKEN_A))
    assert after.status_code == 200
    assert after.json()["active"] is False


def test_delete_not_found(client: TestClient):
    resp = client.delete("/scim/v2/Users/nope", headers=_auth(TOKEN_A))
    assert resp.status_code == 404


# ============================================================================
# 发现端点
# ============================================================================

def test_service_provider_config(client: TestClient):
    resp = client.get("/scim/v2/ServiceProviderConfig", headers=_auth(TOKEN_A))
    assert resp.status_code == 200
    body = resp.json()
    assert body["patch"]["supported"] is True
    assert body["filter"]["supported"] is True
    assert body["bulk"]["supported"] is False
    assert body["authenticationSchemes"][0]["type"] == "oauthbearertoken"


def test_resource_types(client: TestClient):
    resp = client.get("/scim/v2/ResourceTypes", headers=_auth(TOKEN_A))
    assert resp.status_code == 200
    resources = resp.json()["Resources"]
    assert any(r["id"] == "User" for r in resources)

    single = client.get("/scim/v2/ResourceTypes/User", headers=_auth(TOKEN_A))
    assert single.status_code == 200
    assert single.json()["endpoint"] == "/Users"


def test_schemas(client: TestClient):
    resp = client.get("/scim/v2/Schemas", headers=_auth(TOKEN_A))
    assert resp.status_code == 200
    schemas = resp.json()["Resources"]
    user_schema = next(s for s in schemas if s["id"] == SCIM_USER)
    attr_names = [a["name"] for a in user_schema["attributes"]]
    assert "userName" in attr_names and "active" in attr_names

    single = client.get(f"/scim/v2/Schemas/{SCIM_USER}", headers=_auth(TOKEN_A))
    assert single.status_code == 200

    missing = client.get("/scim/v2/Schemas/urn:unknown", headers=_auth(TOKEN_A))
    assert missing.status_code == 404


# ============================================================================
# 存储适配层: 真实惰性接线 (postgres 模式, 假 store)
# ============================================================================

@pytest.mark.asyncio
async def test_adapter_lazy_postgres_wiring(monkeypatch: pytest.MonkeyPatch):
    """UserStoreAdapter 惰性解析到 backend.app.models.user_store.get_user_store,
    并以 postgres 模式工作 (不触真实 DB — store 用假实现)。"""
    import backend.app.models.user_store as store_module

    calls: dict[str, int] = {"create": 0, "get_email": 0}

    class FakeStore:
        def __init__(self):
            self.users = {}

        async def create_user(self, user_id, email, password_hash, tenant_id="default",
                              full_name=None, role="user", metadata=None):
            import json as _json
            from types import SimpleNamespace

            calls["create"] += 1
            record = SimpleNamespace(
                user_id=user_id, email=email, tenant_id=tenant_id,
                full_name=full_name, role=role, is_active=True, is_verified=False,
                metadata_json=_json.dumps(metadata) if metadata else None,
                created_at=None, updated_at=None, last_login_at=None,
            )
            self.users[user_id] = record
            return record

        async def get_user_by_email(self, email, tenant_id="default"):
            calls["get_email"] += 1
            for u in self.users.values():
                if u.email == email and u.tenant_id == tenant_id:
                    return u
            return None

        async def get_user_by_id(self, user_id):
            return self.users.get(user_id)

        async def update_user(self, user_id, **kwargs):
            u = self.users.get(user_id)
            if not u:
                return None
            import json as _json

            for k, v in kwargs.items():
                if k == "metadata_json" and isinstance(v, dict):
                    v = _json.dumps(v)
                setattr(u, k, v)
            return u

        async def deactivate_user(self, user_id):
            u = self.users.get(user_id)
            if not u:
                return None
            u.is_active = False
            return u

        async def list_users(self, tenant_id="default", skip=0, limit=100):
            return [u for u in self.users.values() if u.tenant_id == tenant_id][skip:skip + limit]

        async def count_users(self, tenant_id="default"):
            return sum(1 for u in self.users.values() if u.tenant_id == tenant_id)

    monkeypatch.setattr(store_module, "get_user_store", lambda: FakeStore())

    adapter = UserStoreAdapter()
    created = await adapter.create_user(
        email="wired@example.com", tenant_id="tenant-x", full_name="Wired User"
    )
    assert adapter.mode == "postgres"
    assert calls["create"] == 1

    found = await adapter.get_user_by_email("wired@example.com", "tenant-x")
    assert found is not None and found.user_id == created.user_id
    assert calls["get_email"] == 1

    await adapter.deactivate_user(created.user_id)
    fresh = await adapter.get_user_by_id(created.user_id)
    assert fresh is not None and fresh.is_active is False


# ============================================================================
# env 令牌加载
# ============================================================================

def test_registry_load_from_env(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setenv(
        "XAGENT_SCIM_TOKENS",
        '{"env-token-1": {"tenant_id": "tenant-env", "description": "env loaded"}}',
    )
    registry = SCIMTokenRegistry()
    assert registry.load_from_env() == 1
    info = registry.authenticate("env-token-1")
    assert info is not None and info.tenant_id == "tenant-env"


def test_registry_load_from_env_bad_json(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setenv("XAGENT_SCIM_TOKENS", "{not json")
    registry = SCIMTokenRegistry()
    assert registry.load_from_env() == 0
    assert not registry.configured
