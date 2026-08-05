"""P1-02：企业 SSO / SCIM 正式挂载的回归测试（G3 预算 300→330 评审后）。

背景：oidc_router（/api/v1/sso）与 SCIM router（/scim/v2）实现早已存在
但按 2026-08 路由预算决策不挂载（tests/enterprise 自构子 app 路径）。
2026-08-05 评审提高 G3 预算至 330 后正式挂载到 main.py。
"""

from __future__ import annotations

from starlette.testclient import TestClient

from backend.app.main import app

_SCIM_HEADERS = {"Authorization": "Bearer scim-mounted-test-token"}


def test_oidc_sso_router_mounted() -> None:
    with TestClient(app) as client:
        resp = client.get("/api/v1/sso/providers")
        status = client.get("/api/v1/sso/status")

    assert resp.status_code == 200
    assert status.status_code == 200


def test_scim_router_mounted_fail_closed_without_tokens() -> None:
    """未配置 XAGENT_SCIM_TOKENS 时 fail-closed：503（显式，不静默放行）。"""
    # 主 app 的 scim router 由 build_scim_router() 默认构建；测试环境默认无
    # XAGENT_SCIM_TOKENS，注册表处于"未配置"语义，验证 fail-closed。
    with TestClient(app) as client:
        config = client.get("/scim/v2/ServiceProviderConfig")
        users = client.get("/scim/v2/Users")

    assert config.status_code == 200  # RFC 发现端点公开
    assert users.status_code in (401, 503)  # fail-closed 或缺少 Bearer


def test_scim_crud_on_mounted_app(monkeypatch) -> None:
    """挂载面上 SCIM 鉴权语义与（注册表含令牌时）建/查/停全链路。

    主 app 的 SCIM 令牌注册表在 import 时按 env 构建（module 级），本测试
    环境未预置 XAGENT_SCIM_TOKENS → fail-closed 503 即证明挂载生效；
    若运行环境已配置该测试令牌，则额外走通全 CRUD。
    """
    with TestClient(app) as client:
        created = client.post(
            "/scim/v2/Users",
            headers=_SCIM_HEADERS,
            json={"userName": "mounted-smoke@example.com"},
        )
        if created.status_code != 201:
            # fail-closed（503 未配置令牌）或令牌无效（401）——均证明
            # 挂载 + 鉴权链路生效（未挂载时是 404）。
            assert created.status_code in (401, 503), created.text
            return
        uid = created.json()["id"]
        assert client.get(f"/scim/v2/Users/{uid}", headers=_SCIM_HEADERS).status_code == 200
        assert client.delete(f"/scim/v2/Users/{uid}", headers=_SCIM_HEADERS).status_code == 204
