"""组织域写 API（``backend/app/api/organization.py``）单测。

为什么不与 ``/api/v1/agents`` 的测试重复
========================================
``/api/v1/agents`` 覆盖的是**运行期 Agent**（进程内 ``_AGENTS`` 字典，要求
``security:manage``）；本文件覆盖**组织域岗位智能体**（``OrganizationStore.AgentNode``，
要求 ``org:write``）。两个实体、两条写路径、两套 scope。

隔离策略
========
``OrganizationStore`` 是进程级单例（``core/org.py`` 末尾的 ``organization_store``），
所以：
- 每个用例新建自己的 org / department（uuid 后缀命名）；
- 断言一律限定在**自己创建的 org/department 内**，不做全表计数断言 ——
  否则会被同进程其它用例的写入污染。

模板 id 的来源
==============
``RoleTemplate.role_id`` 是 ``uuid4`` default_factory，**每次 build 都不同**。
所以用例里的模板 id 一律取自 ``organization_store.get_role_catalog()`` —— 也就是
端点实际校验的那份目录。另有一组用例专门锁死「三处目录必须同源」这条不变量。
"""
from __future__ import annotations

from types import SimpleNamespace
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient

from backend.app.api.workbench import get_workbench_principal
from backend.app.core.org import organization_store
from backend.app.core.security import ROLE_SCOPES, Principal
from backend.app.dependencies import get_current_principal
from backend.app.main import app
from backend.app.settings import get_settings

BASE = "/api/v1/organization"

# 端点响应的字段集合。前端（ConsoleShell.handleCreateAgent）目前只读 agent_id，
# 但契约本身写死在这里 —— 后端加/删字段时这里必须先红。
AGENT_CONTRACT_KEYS = {
    "agent_id",
    "org_id",
    "department_id",
    "role_template_id",
    "name",
    "title",
    "role",
    "manager_agent_id",
    "capabilities",
    "team_size_limit",
    "memory_scope",
    "status",
    "created_at",
    "warnings",
}

# 模板 level → 组织域 AgentRole。刻意在测试里**硬编码**，不 import 生产映射表 ——
# 否则映射表改错了测试会跟着一起错（断言空转）。
EXPECTED_ROLE_BY_LEVEL = {
    "executive": "director",
    "lead": "lead",
    "manager": "manager",
    "specialist": "specialist",
}


@pytest.fixture()
def client():
    # 不进上下文 → 不跑 lifespan；根 conftest 已在导入期注册好路由。
    yield TestClient(app)
    app.dependency_overrides.clear()


@pytest.fixture()
def admin_headers():
    return {"x-api-key": get_settings().bootstrap_api_key or "xagent-dev-key-2024"}


@pytest.fixture()
def csrf_exempt_headers():
    """只为跳过 cookie-CSRF 检查而带的 x-api-key。

    角色的 scope 由 ``_use_role`` 的 ``dependency_override`` 决定 —— override
    生效时这个头不参与鉴权。但没有它，POST 会先被 main.py 的 CSRF 中间件挡成
    ``403 {"detail": "CSRF token required"}``，根本走不到 ``enforce_scope``，
    于是「401/403 权限用例」会以假绿/假红收场。
    """
    return {"x-api-key": get_settings().bootstrap_api_key or "xagent-dev-key-2024"}


@pytest.fixture()
def bundle():
    """一个全新的组织 + 两个部门 + store 自己的模板目录。

    `tenant_id` 必须用 `"default"` —— 端点有租户边界（`_require_organization_in_tenant`），
    而 bootstrap key 解析出的 principal 其 tenant 就是 `"default"`。用别的租户建组织
    会让所有用例撞 404，测的就成了租户边界而不是被测逻辑。唯一性靠 uuid 名字保证。
    """
    suffix = uuid4().hex[:8]
    org = organization_store.create_organization(
        tenant_id="default", name=f"组织-{suffix}"
    )
    dept = organization_store.create_department(
        org_id=org.org_id, name=f"内容部-{suffix}"
    )
    other_dept = organization_store.create_department(
        org_id=org.org_id, name=f"运营部-{suffix}"
    )
    return SimpleNamespace(
        org=org,
        dept=dept,
        other_dept=other_dept,
        catalog=organization_store.get_role_catalog(),
        suffix=suffix,
    )


@pytest.fixture()
def foreign_bundle():
    """**另一个租户**的组织 + 部门，用于租户边界用例。"""
    suffix = uuid4().hex[:8]
    org = organization_store.create_organization(
        tenant_id=f"tenant-other-{suffix}", name=f"外部组织-{suffix}"
    )
    dept = organization_store.create_department(
        org_id=org.org_id, name=f"外部部门-{suffix}"
    )
    return SimpleNamespace(org=org, dept=dept, suffix=suffix)


def _payload(bundle, **overrides):
    payload = {
        "org_id": bundle.org.org_id,
        "department_id": bundle.dept.department_id,
        "name": f"岗位-{uuid4().hex[:6]}",
        "role_template_id": bundle.catalog.templates[0].role_id,
    }
    payload.update(overrides)
    return payload


def _create(client, headers, bundle, **overrides):
    r = client.post(f"{BASE}/agents", json=_payload(bundle, **overrides), headers=headers)
    assert r.status_code == 201, r.text
    return r.json()


def _use_role(role: str, *, authenticated: bool = True) -> None:
    app.dependency_overrides[get_current_principal] = lambda: Principal(
        tenant_id="default",
        user_id=f"{role}-user",
        role=role,
        scopes=list(ROLE_SCOPES.get(role, [])),
        authenticated=authenticated,
    )


def _principal_for(tenant_id: str) -> Principal:
    """该租户下的 admin principal —— 供两个依赖入口共用同一份身份。"""
    return Principal(
        tenant_id=tenant_id,
        user_id=f"{tenant_id}-admin",
        role="admin",
        scopes=list(ROLE_SCOPES.get("admin", [])),
        authenticated=True,
    )


def _org_agents(bundle, department_id=None):
    return organization_store.list_agents(
        org_id=bundle.org.org_id,
        department_id=department_id,
    )


# ═══════════════════════════════════════════════════════════════════════════════
# 契约形状
# ═══════════════════════════════════════════════════════════════════════════════


class TestContract:
    def test_create_returns_201_and_exact_key_set(self, client, admin_headers, bundle):
        body = _create(client, admin_headers, bundle)
        assert set(body.keys()) == AGENT_CONTRACT_KEYS

    def test_response_is_echoed_by_department_scoped_org_lookup(
        self, client, admin_headers, bundle
    ):
        """新增组织接口返回的 org_id / department_id 必须能在组织域里复核到。"""
        body = _create(client, admin_headers, bundle)
        assert organization_store.get_organization(body["org_id"]) is not None
        department = organization_store.get_department(body["department_id"])
        assert department is not None
        assert department.org_id == body["org_id"]

    def test_created_agent_is_readable_from_the_store(
        self, client, admin_headers, bundle
    ):
        """验收红线：落库必须能用 OrganizationStore.list_agents() 复核。

        断言基准刻意取**模板目录里的 role_template_id**，而不是响应体回显的值 ——
        后者与被测代码同源，一旦创建时写成空串，两边一起变空，断言就空转了
        （此前的版本正是这样，被 M8 变异判为 SURVIVED）。
        """
        template = bundle.catalog.templates[0]
        before = {a.agent_id for a in _org_agents(bundle, bundle.dept.department_id)}
        body = _create(client, admin_headers, bundle, role_template_id=template.role_id)
        after = _org_agents(bundle, bundle.dept.department_id)

        assert body["role_template_id"] == template.role_id
        assert body["agent_id"] not in before
        assert body["agent_id"] in {a.agent_id for a in after}

        stored = organization_store.get_agent(body["agent_id"])
        assert stored is not None
        assert stored.name == body["name"]
        assert stored.role_template_id == template.role_id
        assert stored.department_id == bundle.dept.department_id


# ═══════════════════════════════════════════════════════════════════════════════
# 模板继承（拍板 ①：只继承模板，不做逐字段覆盖）
# ═══════════════════════════════════════════════════════════════════════════════


class TestTemplateInheritance:
    def test_title_and_capabilities_come_from_template(
        self, client, admin_headers, bundle
    ):
        template = bundle.catalog.templates[1]  # 短剧导演
        body = _create(
            client, admin_headers, bundle, role_template_id=template.role_id
        )
        assert body["role_template_id"] == template.role_id
        assert body["title"] == template.title
        assert body["capabilities"] == list(template.core_skills)
        assert body["capabilities"], "模板 core_skills 不应为空，否则本断言空转"

    def test_explicit_title_overrides_template_title(
        self, client, admin_headers, bundle
    ):
        template = bundle.catalog.templates[1]
        body = _create(
            client,
            admin_headers,
            bundle,
            role_template_id=template.role_id,
            title="自定义标题",
        )
        assert body["title"] == "自定义标题"

    def test_blank_title_falls_back_to_template(self, client, admin_headers, bundle):
        template = bundle.catalog.templates[1]
        body = _create(
            client, admin_headers, bundle, role_template_id=template.role_id, title="   "
        )
        assert body["title"] == template.title

    @pytest.mark.parametrize("index", [0, 1, 2, 3, 4, 5])
    def test_role_is_derived_from_template_level(
        self, client, admin_headers, bundle, index
    ):
        template = bundle.catalog.templates[index]
        body = _create(
            client, admin_headers, bundle, role_template_id=template.role_id
        )
        assert body["role"] == EXPECTED_ROLE_BY_LEVEL[template.level]

    def test_all_six_seed_templates_have_an_expected_level(self, bundle):
        """种子的 level 必须都在 EXPECTED_ROLE_BY_LEVEL 里，防止新模板悄悄落到兜底分支。"""
        levels = {t.level for t in bundle.catalog.templates}
        assert levels <= set(EXPECTED_ROLE_BY_LEVEL), (
            f"有模板 level 未在测试映射表中：{levels - set(EXPECTED_ROLE_BY_LEVEL)}"
        )


# ═══════════════════════════════════════════════════════════════════════════════
# 重名口径（拍板 Q2：同部门唯一 → 409，跨部门允许）
# ═══════════════════════════════════════════════════════════════════════════════


class TestNameConflict:
    def test_duplicate_name_in_same_department_is_409(
        self, client, admin_headers, bundle
    ):
        name = f"重名-{uuid4().hex[:6]}"
        _create(client, admin_headers, bundle, name=name)

        r = client.post(
            f"{BASE}/agents", json=_payload(bundle, name=name), headers=admin_headers
        )
        assert r.status_code == 409, r.text
        assert r.json()["code"] == "resource_conflict"
        assert name in r.json()["message"]

    def test_duplicate_is_detected_after_stripping_whitespace(
        self, client, admin_headers, bundle
    ):
        name = f"空格-{uuid4().hex[:6]}"
        _create(client, admin_headers, bundle, name=name)

        r = client.post(
            f"{BASE}/agents",
            json=_payload(bundle, name=f"  {name}  "),
            headers=admin_headers,
        )
        assert r.status_code == 409, r.text

    def test_conflict_does_not_create_a_second_agent(
        self, client, admin_headers, bundle
    ):
        name = f"唯一-{uuid4().hex[:6]}"
        first = _create(client, admin_headers, bundle, name=name)
        client.post(
            f"{BASE}/agents", json=_payload(bundle, name=name), headers=admin_headers
        )

        same_name = [
            a for a in _org_agents(bundle, bundle.dept.department_id) if a.name == name
        ]
        assert [a.agent_id for a in same_name] == [first["agent_id"]]

    def test_same_name_in_another_department_is_allowed(
        self, client, admin_headers, bundle
    ):
        name = f"跨部门-{uuid4().hex[:6]}"
        first = _create(client, admin_headers, bundle, name=name)

        r = client.post(
            f"{BASE}/agents",
            json=_payload(
                bundle, name=name, department_id=bundle.other_dept.department_id
            ),
            headers=admin_headers,
        )
        assert r.status_code == 201, r.text
        assert r.json()["agent_id"] != first["agent_id"]


# ═══════════════════════════════════════════════════════════════════════════════
# 404 口径（不静默降级）
# ═══════════════════════════════════════════════════════════════════════════════


class TestNotFound:
    def test_unknown_org_is_404(self, client, admin_headers, bundle):
        r = client.post(
            f"{BASE}/agents",
            json=_payload(bundle, org_id=f"missing-{uuid4().hex[:6]}"),
            headers=admin_headers,
        )
        assert r.status_code == 404, r.text
        assert r.json()["code"] == "resource_not_found"

    def test_unknown_department_is_404(self, client, admin_headers, bundle):
        r = client.post(
            f"{BASE}/agents",
            json=_payload(bundle, department_id=f"missing-{uuid4().hex[:6]}"),
            headers=admin_headers,
        )
        assert r.status_code == 404, r.text

    def test_department_from_another_organization_is_404(
        self, client, admin_headers, bundle
    ):
        """部门存在 but 不属于该组织 → 拒绝，而不是建出跨组织的错挂载。"""
        other_org = organization_store.create_organization(
            tenant_id=f"tenant-x-{uuid4().hex[:6]}", name="别的组织"
        )
        foreign_dept = organization_store.create_department(
            org_id=other_org.org_id, name="外来部门"
        )

        r = client.post(
            f"{BASE}/agents",
            json=_payload(bundle, department_id=foreign_dept.department_id),
            headers=admin_headers,
        )
        assert r.status_code == 404, r.text
        assert "不属于" in r.json()["message"]

    def test_unknown_role_template_is_404(self, client, admin_headers, bundle):
        r = client.post(
            f"{BASE}/agents",
            json=_payload(bundle, role_template_id=f"missing-{uuid4().hex[:6]}"),
            headers=admin_headers,
        )
        assert r.status_code == 404, r.text
        assert "岗位模板" in r.json()["message"]

    def test_unknown_manager_is_404(self, client, admin_headers, bundle):
        r = client.post(
            f"{BASE}/agents",
            json=_payload(bundle, manager_agent_id=f"missing-{uuid4().hex[:6]}"),
            headers=admin_headers,
        )
        assert r.status_code == 404, r.text
        assert "上级智能体" in r.json()["message"]

    def test_manager_from_another_organization_is_404(
        self, client, admin_headers, bundle
    ):
        other_org = organization_store.create_organization(
            tenant_id=f"tenant-y-{uuid4().hex[:6]}", name="另一个组织"
        )
        other_dept = organization_store.create_department(
            org_id=other_org.org_id, name="外部部门"
        )
        outsider = organization_store.create_agent(
            org_id=other_org.org_id,
            department_id=other_dept.department_id,
            name=f"外部-{uuid4().hex[:6]}",
        )

        r = client.post(
            f"{BASE}/agents",
            json=_payload(bundle, manager_agent_id=outsider.agent_id),
            headers=admin_headers,
        )
        assert r.status_code == 404, r.text
        assert "不属于" in r.json()["message"]

    @pytest.mark.parametrize("field", ["org_id", "department_id", "role_template_id"])
    def test_empty_required_field_is_422(self, client, admin_headers, bundle, field):
        r = client.post(
            f"{BASE}/agents", json=_payload(bundle, **{field: ""}), headers=admin_headers
        )
        assert r.status_code == 422, r.text

    def test_blank_only_name_is_422(self, client, admin_headers, bundle):
        """name 全为空白字符：strip 后为空 → 422，而不是建出一个空名岗位。"""
        r = client.post(
            f"{BASE}/agents", json=_payload(bundle, name="   "), headers=admin_headers
        )
        assert r.status_code == 422, r.text

    def test_profile_overlay_fields_are_rejected(self, client, admin_headers, bundle):
        """拍板 ①：画像字段不做覆盖 —— 旧客户端带上它们时必须 422，不能静默忽略。"""
        for field, value in (
            ("capabilities", ["x"]),
            ("plugins", ["x"]),
            ("apps", ["x"]),
            ("persona", "professional"),
            ("tone", "clear"),
            ("decision_style", "balanced"),
            ("communication_style", "direct"),
            ("risk_appetite", "medium"),
            ("room_id", "room-1"),
        ):
            r = client.post(
                f"{BASE}/agents",
                json=_payload(bundle, **{field: value}),
                headers=admin_headers,
            )
            assert r.status_code == 422, f"{field} 应被拒绝，实际 {r.status_code}"

    def test_team_size_limit_out_of_range_is_422(self, client, admin_headers, bundle):
        r = client.post(
            f"{BASE}/agents",
            json=_payload(bundle, team_size_limit=101),
            headers=admin_headers,
        )
        assert r.status_code == 422, r.text


# ═══════════════════════════════════════════════════════════════════════════════
# 鉴权（拍板 Q8：admin + developer）
# ═══════════════════════════════════════════════════════════════════════════════


class TestAuthorization:
    def test_admin_can_create(self, client, admin_headers, bundle):
        body = _create(client, admin_headers, bundle)
        assert body["agent_id"]

    def test_developer_can_create(self, client, bundle, csrf_exempt_headers):
        _use_role("developer")
        r = client.post(
            f"{BASE}/agents", json=_payload(bundle), headers=csrf_exempt_headers
        )
        assert r.status_code == 201, r.text

    def test_user_role_is_403(self, client, bundle, csrf_exempt_headers):
        _use_role("user")
        r = client.post(
            f"{BASE}/agents", json=_payload(bundle), headers=csrf_exempt_headers
        )
        assert r.status_code == 403, r.text
        assert "org:write" in r.json()["message"]

    def test_viewer_role_is_403(self, client, bundle, csrf_exempt_headers):
        _use_role("viewer")
        r = client.post(
            f"{BASE}/agents", json=_payload(bundle), headers=csrf_exempt_headers
        )
        assert r.status_code == 403, r.text

    def test_unauthenticated_principal_is_401(self, client, bundle, csrf_exempt_headers):
        """未认证 ≠ 403：enforce_scope 先验 authenticated，再验 scope。

        注意 ``authenticated=True`` + 空 scope 是 403（上面的 anonymous 用例），
        真正的「没登录」是 ``authenticated=False``。两者混起来会让 401/403
        的回归测试互相掩护。
        """
        _use_role("anonymous", authenticated=False)
        r = client.post(
            f"{BASE}/agents", json=_payload(bundle), headers=csrf_exempt_headers
        )
        assert r.status_code == 401, r.text
        assert r.json()["code"] == "authentication_failed"

    def test_role_with_no_scope_at_all_is_403(self, client, bundle, csrf_exempt_headers):
        """已认证但完全没 scope（近似 anonymous 角色）→ 403。"""
        _use_role("anonymous")
        r = client.post(
            f"{BASE}/agents", json=_payload(bundle), headers=csrf_exempt_headers
        )
        assert r.status_code == 403, r.text
        assert r.json()["code"] == "authorization_failed"

    def test_forbidden_request_creates_nothing(self, client, bundle, csrf_exempt_headers):
        before = {a.agent_id for a in _org_agents(bundle, bundle.dept.department_id)}
        _use_role("user")
        client.post(f"{BASE}/agents", json=_payload(bundle), headers=csrf_exempt_headers)
        after = {a.agent_id for a in _org_agents(bundle, bundle.dept.department_id)}
        assert after == before


# ═══════════════════════════════════════════════════════════════════════════════
# 汇报关系：部分成功必须显式（warnings）
# ═══════════════════════════════════════════════════════════════════════════════


class TestManagerWiring:
    def test_manager_gets_child_when_capacity_allows(
        self, client, admin_headers, bundle
    ):
        manager = _create(
            client, admin_headers, bundle, name=f"组长-{uuid4().hex[:6]}"
        )
        child = _create(
            client,
            admin_headers,
            bundle,
            name=f"组员-{uuid4().hex[:6]}",
            manager_agent_id=manager["agent_id"],
        )

        assert child["warnings"] == []
        stored_manager = organization_store.get_agent(manager["agent_id"])
        assert stored_manager is not None
        assert stored_manager.child_agent_ids == [child["agent_id"]]

    def test_manager_capacity_full_reports_a_warning_and_skips_wiring(
        self, client, admin_headers, bundle
    ):
        manager = _create(
            client,
            admin_headers,
            bundle,
            name=f"满员组长-{uuid4().hex[:6]}",
            team_size_limit=1,
        )
        first = _create(
            client,
            admin_headers,
            bundle,
            name=f"组员A-{uuid4().hex[:6]}",
            manager_agent_id=manager["agent_id"],
        )
        assert first["warnings"] == []

        second = _create(
            client,
            admin_headers,
            bundle,
            name=f"组员B-{uuid4().hex[:6]}",
            manager_agent_id=manager["agent_id"],
        )
        # 智能体仍然建成了（201），但汇报关系没挂上 —— 这件事必须说出来
        assert second["warnings"], "满员却没有任何告警"
        assert any("编制上限" in w for w in second["warnings"])

        stored_manager = organization_store.get_agent(manager["agent_id"])
        assert stored_manager is not None
        assert stored_manager.child_agent_ids == [first["agent_id"]]

    def test_zero_capacity_manager_reports_a_warning(
        self, client, admin_headers, bundle
    ):
        manager = _create(
            client,
            admin_headers,
            bundle,
            name=f"零编制-{uuid4().hex[:6]}",
            team_size_limit=0,
        )
        child = _create(
            client,
            admin_headers,
            bundle,
            name=f"组员C-{uuid4().hex[:6]}",
            manager_agent_id=manager["agent_id"],
        )
        assert child["warnings"], "team_size_limit=0 却没有任何告警"


# ═══════════════════════════════════════════════════════════════════════════════
# 组织图：role_template_id 直取（拍板 ②：停用 role_index 反查）
# ═══════════════════════════════════════════════════════════════════════════════


class TestOrganizationGraph:
    def test_graph_instance_carries_the_real_template_id(
        self, client, admin_headers, bundle
    ):
        template = bundle.catalog.templates[1]
        body = _create(
            client, admin_headers, bundle, role_template_id=template.role_id
        )

        graph = organization_store.build_organization_graph(bundle.org.org_id)
        assert graph is not None
        instance = next(
            i for i in graph.agent_instances if i.agent_id == body["agent_id"]
        )
        assert instance.role_template_id == template.role_id

    def test_graph_template_nodes_use_the_same_catalog_as_the_store(self, bundle):
        """不变量：图里的 role_template node_id 必须与 store 目录同源。

        ``RoleTemplate.role_id`` 是 uuid4 default_factory ⇒ 每次
        ``build_default_role_catalog()`` 都产出新 id。图里若独立 build 一份，
        前端就没法把 ``agent_instances[].role_template_id`` join 回
        ``role_templates[].role_id``。
        """
        graph = organization_store.build_organization_graph(bundle.org.org_id)
        assert graph is not None
        assert {t.role_id for t in graph.role_templates} == {
            t.role_id for t in bundle.catalog.templates
        }

    def test_workbench_role_catalog_is_the_same_catalog_as_the_store(
        self, client, admin_headers
    ):
        """不变量：控制台 bootstrap 收到的模板 id 必须能在 store 里查到。

        否则 CreateAgentPage 选中模板后提交，端点必然 404 —— 页面「看得见、
        点不动」。
        """
        r = client.get("/api/v1/workbench", headers=admin_headers)
        assert r.status_code == 200, r.text
        payload = r.json()
        console_catalog = payload.get("role_catalog") or {}
        console_ids = {t["role_id"] for t in console_catalog.get("templates", [])}
        assert console_ids, "bootstrap 未返回模板，断言会空转"
        assert console_ids == {
            t.role_id for t in organization_store.get_role_catalog().templates
        }

    def test_agent_role_derivation_matches_graph_metadata(
        self, client, admin_headers, bundle
    ):
        template = bundle.catalog.templates[0]  # 总经理 / executive
        body = _create(
            client, admin_headers, bundle, role_template_id=template.role_id
        )
        graph = organization_store.build_organization_graph(bundle.org.org_id)
        assert graph is not None
        node = next(n for n in graph.nodes if n.node_id == body["agent_id"])
        assert node.metadata["role"] == body["role"] == "director"


# ═══════════════════════════════════════════════════════════════════════════════
# 组织 / 部门端点 —— 闭环：组织域可以「从零真实地建起来」
#
# 这批端点的存在理由：OrganizationStore 无种子且 create_organization /
# create_department 在 backend/app/** 里零调用者 ⇒ 不先建出组织与部门，
# POST /agents 根本没有合法的 org_id / department_id 可用。
# ═══════════════════════════════════════════════════════════════════════════════

ORGANIZATION_CONTRACT_KEYS = {
    "org_id",
    "tenant_id",
    "name",
    "description",
    "owner_user_id",
    "status",
    "created_at",
    "updated_at",
}

DEPARTMENT_CONTRACT_KEYS = {
    "department_id",
    "org_id",
    "name",
    "mission",
    "leader_agent_id",
    "parent_department_id",
    "created_at",
    "updated_at",
}


class TestOrganizationsApi:
    def test_create_returns_201_and_exact_key_set(self, client, admin_headers):
        r = client.post(
            f"{BASE}/organizations",
            json={"name": f"新组织-{uuid4().hex[:6]}"},
            headers=admin_headers,
        )
        assert r.status_code == 201, r.text
        assert set(r.json().keys()) == ORGANIZATION_CONTRACT_KEYS

    def test_created_organization_is_readable_from_the_store(
        self, client, admin_headers
    ):
        name = f"落库组织-{uuid4().hex[:6]}"
        created = client.post(
            f"{BASE}/organizations", json={"name": name}, headers=admin_headers
        ).json()

        stored = organization_store.get_organization(created["org_id"])
        assert stored is not None
        assert stored.name == name
        assert created["org_id"] in {
            org.org_id
            for org in organization_store.list_organizations(tenant_id="default")
        }

    def test_tenant_and_owner_come_from_the_principal_not_the_body(
        self, client, admin_headers
    ):
        """请求体里塞 tenant_id 必须 422 —— 归属只能来自 principal。"""
        created = client.post(
            f"{BASE}/organizations",
            json={"name": f"归属-{uuid4().hex[:6]}"},
            headers=admin_headers,
        ).json()
        assert created["tenant_id"] == "default"
        assert created["owner_user_id"] == "bootstrap-admin"

        r = client.post(
            f"{BASE}/organizations",
            json={"name": "越权归属", "tenant_id": "someone-else"},
            headers=admin_headers,
        )
        assert r.status_code == 422, r.text

    def test_list_only_returns_own_tenant(self, client, admin_headers, foreign_bundle):
        own = client.post(
            f"{BASE}/organizations",
            json={"name": f"本租户-{uuid4().hex[:6]}"},
            headers=admin_headers,
        ).json()

        listed = client.get(f"{BASE}/organizations", headers=admin_headers).json()
        ids = {item["org_id"] for item in listed}
        assert own["org_id"] in ids
        assert foreign_bundle.org.org_id not in ids
        assert all(item["tenant_id"] == "default" for item in listed)

    def test_blank_name_is_422(self, client, admin_headers):
        r = client.post(
            f"{BASE}/organizations", json={"name": "   "}, headers=admin_headers
        )
        assert r.status_code == 422, r.text

    def test_user_role_cannot_create_or_list(self, client, csrf_exempt_headers):
        _use_role("user")
        assert (
            client.post(
                f"{BASE}/organizations",
                json={"name": "x"},
                headers=csrf_exempt_headers,
            ).status_code
            == 403
        )
        r = client.get(f"{BASE}/organizations", headers=csrf_exempt_headers)
        assert r.status_code == 403, r.text
        assert "org:read" in r.json()["message"]

    def test_developer_can_create(self, client, csrf_exempt_headers):
        _use_role("developer")
        r = client.post(
            f"{BASE}/organizations",
            json={"name": f"开发者建的-{uuid4().hex[:6]}"},
            headers=csrf_exempt_headers,
        )
        assert r.status_code == 201, r.text


class TestDepartmentsApi:
    def test_create_returns_201_and_exact_key_set(self, client, admin_headers, bundle):
        r = client.post(
            f"{BASE}/departments",
            json={"org_id": bundle.org.org_id, "name": f"新部门-{uuid4().hex[:6]}"},
            headers=admin_headers,
        )
        assert r.status_code == 201, r.text
        assert set(r.json().keys()) == DEPARTMENT_CONTRACT_KEYS

    def test_created_department_is_listed_and_stored(self, client, admin_headers, bundle):
        name = f"落库部门-{uuid4().hex[:6]}"
        created = client.post(
            f"{BASE}/departments",
            json={"org_id": bundle.org.org_id, "name": name, "mission": "跑内容"},
            headers=admin_headers,
        ).json()

        listed = client.get(
            f"{BASE}/departments",
            params={"org_id": bundle.org.org_id},
            headers=admin_headers,
        ).json()
        assert created["department_id"] in {d["department_id"] for d in listed}
        assert any(d["name"] == name and d["mission"] == "跑内容" for d in listed)

        stored = organization_store.get_department(created["department_id"])
        assert stored is not None and stored.name == name

    def test_list_is_scoped_to_the_requested_org(
        self, client, admin_headers, bundle, foreign_bundle
    ):
        """★ 别组织的部门绝不能出现在本组织的列表里。

        ``foreign_bundle`` 同样是**必需**的：单跑本类时 store 里只有 bundle 自己
        造的部门 ⇒ 即便 ``list_departments(org_id=...)`` 的过滤被摘掉，「自己的部门
        在列表里」也照样成立（变异实测 SURVIVED）。垫上 foreign_bundle 才能把
        「org 维度不串」这条不变量钉住。
        """
        listed = client.get(
            f"{BASE}/departments",
            params={"org_id": bundle.org.org_id},
            headers=admin_headers,
        ).json()
        ids = {d["department_id"] for d in listed}
        assert bundle.dept.department_id in ids
        assert foreign_bundle.dept.department_id not in ids
        assert all(d["org_id"] == bundle.org.org_id for d in listed)

    def test_unknown_org_is_404(self, client, admin_headers):
        r = client.post(
            f"{BASE}/departments",
            json={"org_id": f"missing-{uuid4().hex[:6]}", "name": "孤儿部门"},
            headers=admin_headers,
        )
        assert r.status_code == 404, r.text

    def test_foreign_tenant_org_is_404(self, client, admin_headers, foreign_bundle):
        """跨租户读写必须 404（与「不存在」同码同文案，不泄漏 id 是否存在）。"""
        assert (
            client.post(
                f"{BASE}/departments",
                json={"org_id": foreign_bundle.org.org_id, "name": "越界部门"},
                headers=admin_headers,
            ).status_code
            == 404
        )
        assert (
            client.get(
                f"{BASE}/departments",
                params={"org_id": foreign_bundle.org.org_id},
                headers=admin_headers,
            ).status_code
            == 404
        )

    def test_blank_name_is_422(self, client, admin_headers, bundle):
        r = client.post(
            f"{BASE}/departments",
            json={"org_id": bundle.org.org_id, "name": "  "},
            headers=admin_headers,
        )
        assert r.status_code == 422, r.text

    def test_leader_must_exist_and_belong_to_the_org(
        self, client, admin_headers, bundle, foreign_bundle
    ):
        outsider = organization_store.create_agent(
            org_id=foreign_bundle.org.org_id,
            department_id=foreign_bundle.dept.department_id,
            name=f"外部负责人-{uuid4().hex[:6]}",
        )
        for bad_leader in (f"missing-{uuid4().hex[:6]}", outsider.agent_id):
            r = client.post(
                f"{BASE}/departments",
                json={
                    "org_id": bundle.org.org_id,
                    "name": f"部门-{uuid4().hex[:6]}",
                    "leader_agent_id": bad_leader,
                },
                headers=admin_headers,
            )
            assert r.status_code == 404, f"{bad_leader} 应被拒绝，实际 {r.status_code}"

    def test_parent_must_exist_and_belong_to_the_org(
        self, client, admin_headers, bundle, foreign_bundle
    ):
        for bad_parent in (
            f"missing-{uuid4().hex[:6]}",
            foreign_bundle.dept.department_id,
        ):
            r = client.post(
                f"{BASE}/departments",
                json={
                    "org_id": bundle.org.org_id,
                    "name": f"子部门-{uuid4().hex[:6]}",
                    "parent_department_id": bad_parent,
                },
                headers=admin_headers,
            )
            assert r.status_code == 404, f"{bad_parent} 应被拒绝，实际 {r.status_code}"

    def test_valid_leader_and_parent_are_accepted(
        self, client, admin_headers, bundle
    ):
        leader = _create(client, admin_headers, bundle, name=f"负责人-{uuid4().hex[:6]}")
        child = client.post(
            f"{BASE}/departments",
            json={
                "org_id": bundle.org.org_id,
                "name": f"子部门-{uuid4().hex[:6]}",
                "leader_agent_id": leader["agent_id"],
                "parent_department_id": bundle.dept.department_id,
            },
            headers=admin_headers,
        )
        assert child.status_code == 201, child.text
        assert child.json()["leader_agent_id"] == leader["agent_id"]
        assert child.json()["parent_department_id"] == bundle.dept.department_id


# ═══════════════════════════════════════════════════════════════════════════════
# 租户边界（新增：此前 POST /agents 只验组织存在，不验归属）
# ═══════════════════════════════════════════════════════════════════════════════


class TestTenantBoundary:
    def test_agents_endpoint_rejects_foreign_tenant_org(
        self, client, admin_headers, foreign_bundle
    ):
        before = {a.agent_id for a in organization_store.list_agents()}
        r = client.post(
            f"{BASE}/agents",
            json={
                "org_id": foreign_bundle.org.org_id,
                "department_id": foreign_bundle.dept.department_id,
                "name": f"越界岗位-{uuid4().hex[:6]}",
                "role_template_id": organization_store.get_role_catalog()
                .templates[0]
                .role_id,
            },
            headers=admin_headers,
        )
        assert r.status_code == 404, r.text
        assert {a.agent_id for a in organization_store.list_agents()} == before

    def test_missing_and_foreign_org_share_the_same_error_shape(
        self, client, admin_headers, foreign_bundle
    ):
        """同码同文案 —— 否则可以用错误文案当「组织存在性探针」。"""
        missing = client.get(
            f"{BASE}/departments",
            params={"org_id": f"missing-{uuid4().hex[:6]}"},
            headers=admin_headers,
        )
        foreign = client.get(
            f"{BASE}/departments",
            params={"org_id": foreign_bundle.org.org_id},
            headers=admin_headers,
        )
        assert missing.status_code == foreign.status_code == 404
        assert missing.json()["code"] == foreign.json()["code"]
        assert (
            missing.json()["message"].split("：")[0]
            == foreign.json()["message"].split("：")[0]
        )


# ═══════════════════════════════════════════════════════════════════════════════
# 控制台 bootstrap 与组织域的接线（闭环不变量）
# ═══════════════════════════════════════════════════════════════════════════════


class TestWorkbenchGraphWiring:
    def test_bootstrap_graph_reflects_the_real_organization(
        self, client, admin_headers, bundle
    ):
        """★ 闭环不变量：刚建的组织/部门必须出现在 bootstrap 的组织图里。

        隔离此用例的是一个**真实存在的后端 bug**：workbench 曾把
        principal.tenant_id 当 org_id 传给 build_organization_graph ⇒
        恒返回 None ⇒ 控制台组织图恒空 ⇒ CreateAgentPage 的「所属组织/部门」
        下拉恒空、表单在校验阶段就被拦下（页面看得见、点不动）。
        """
        r = client.get("/api/v1/workbench", headers=admin_headers)
        assert r.status_code == 200, r.text
        graph = r.json().get("organization_graph") or {}
        assert graph, "bootstrap 组织图为空 —— 组织域与工作台断了"
        assert graph["organization"]["org_id"] == bundle.org.org_id
        assert {d["department_id"] for d in graph["departments"]} >= {
            bundle.dept.department_id,
            bundle.other_dept.department_id,
        }

    @staticmethod
    def _as_workbench_tenant(tenant_id: str) -> None:
        """把 workbench 的租户换成指定租户。

        ★ 必须覆盖 ``get_workbench_principal`` 而不是 ``get_current_principal``：
        workbench 端点的依赖是前者，它在内部**以普通函数调用**方式执行
        ``get_current_principal(request)``（见 ``api/workbench.py``），不经过 FastAPI 的
        Depends 解析 ⇒ 覆盖后者对本端点**完全无效**：用例会拿到 bootstrap 的 default
        租户、看见别的用例建的组织，于是断言结构性恒假。
        """
        app.dependency_overrides[get_workbench_principal] = lambda: _principal_for(
            tenant_id
        )

    @staticmethod
    def _as_tenant(tenant_id: str) -> None:
        """**读、写两个入口都指向同一租户**。

        真实请求里 workbench 与 /organization/* 解析出的是**同一个** principal；
        测试里必须照做，否则会出现「图建在 A 租户、写端点用 B 租户」的错配
        （读端点被覆盖、写端点没被覆盖 ⇒ 404）。
        """
        principal = _principal_for(tenant_id)
        app.dependency_overrides[get_workbench_principal] = lambda: principal
        app.dependency_overrides[get_current_principal] = lambda: principal

    def test_first_visit_seeds_a_usable_default_organization(
        self, client, csrf_exempt_headers, foreign_bundle
    ):
        """★ (b) 方案 A：空租户首次打开控制台 ⇒ 立刻可用。

        钉住的是「控制台没有建组织/部门的入口」这一事实：``CreateAgentPage`` 的
        「所属组织」**不可切换**（取自 ``organization_graph.organization.org_id``）、
        「所属部门」取 ``departments[0]`` ⇒ 图空则两个值皆空 ⇒ 表单在校验阶段就被拦下。
        所以「首访即有一个组织 + 一个部门」是控制台可用的**前提**，不是锦上添花。

        ``foreign_bundle`` 用于排除「拿别人的组织充数」这条假绿路径。
        """
        tenant = f"fresh-tenant-{uuid4().hex[:8]}"
        self._as_workbench_tenant(tenant)

        r = client.get("/api/v1/workbench", headers=csrf_exempt_headers)
        assert r.status_code == 200, r.text
        graph = r.json().get("organization_graph") or {}
        assert graph, "空租户首访必须拿到可用组织图，否则控制台走不动"
        assert graph["organization"]["name"] == "我的组织"
        assert graph["organization"]["tenant_id"] == tenant
        assert [d["name"] for d in graph["departments"]] == ["综合部"]
        assert graph["organization"]["owner_user_id"] == "system"
        assert graph["organization"]["org_id"] != foreign_bundle.org.org_id

    def test_seeded_graph_is_directly_usable_by_the_create_agent_form(
        self, client, csrf_exempt_headers
    ):
        """★★ 闭环：种出来的图，**原样**喂给创建表单的默认取值即可建出第一个岗位。

        这是「(b) 让首屏可用」最直接的证明。前端 ``CreateAgentPage`` 的三个初值就是
        ``graph.organization.org_id``（**不可切换**）、``graph.departments[0].department_id``、
        ``roleCatalog.templates[0].role_id`` —— 全部从**同一次** workbench 响应里取，
        中间不掺任何夹具造的数据。

        顺带钉住「图的模板 id 与创建端点校验用的是同一份目录」：图的 ``role_templates``
        由 ``build_organization_graph`` 从 ``store._role_catalog`` 取，创建端点也查
        ``store.get_role_catalog()`` ⇒ 两边必须是**同一个对象**，否则提交必然 404。
        ⚠️ 口径别混：本条覆盖的是**图**这条路径（突变点在 ``build_organization_graph``）；
        workbench 自己那份局部 ``role_catalog``（只喂 ConsoleBootstrapResponse，与图无关）
        由 ``test_workbench_role_catalog_is_the_same_catalog_as_the_store`` 守。
        """
        tenant = f"e2e-tenant-{uuid4().hex[:8]}"
        self._as_tenant(tenant)

        boot = client.get("/api/v1/workbench", headers=csrf_exempt_headers)
        assert boot.status_code == 200, boot.text
        graph = boot.json().get("organization_graph") or {}
        assert graph and graph["departments"] and graph["role_templates"], (
            "首屏图必须自带组织 + 部门 + 模板目录"
        )

        # 前端真实的默认取值顺序
        created = client.post(
            f"{BASE}/agents",
            json={
                "org_id": graph["organization"]["org_id"],
                "department_id": graph["departments"][0]["department_id"],
                "name": f"首位岗位-{uuid4().hex[:6]}",
                "role_template_id": graph["role_templates"][0]["role_id"],
            },
            headers=csrf_exempt_headers,
        )
        assert created.status_code == 201, created.text
        body = created.json()
        assert body["department_id"] == graph["departments"][0]["department_id"]
        assert body["role_template_id"] == graph["role_templates"][0]["role_id"]

    def test_seeding_is_idempotent_across_repeat_visits(
        self, client, csrf_exempt_headers
    ):
        """刷新多少次都只有一个组织 —— 否则每次轮询都往 store 里塞一条。"""
        tenant = f"repeat-tenant-{uuid4().hex[:8]}"
        self._as_workbench_tenant(tenant)

        first = client.get("/api/v1/workbench", headers=csrf_exempt_headers).json()
        org_id = first["organization_graph"]["organization"]["org_id"]
        for _ in range(3):
            again = client.get("/api/v1/workbench", headers=csrf_exempt_headers).json()
            assert again["organization_graph"]["organization"]["org_id"] == org_id

        assert [
            o.org_id for o in organization_store.list_organizations(tenant_id=tenant)
        ] == [org_id]
        assert len(organization_store.list_departments(org_id=org_id)) == 1

    def test_seeding_leaves_a_tenant_with_organizations_alone(
        self, client, csrf_exempt_headers, bundle
    ):
        """已有组织 ⇒ 种子绝不介入（用户自建的组织不会被覆盖、也不会被再建一个）。"""
        self._as_workbench_tenant("default")  # bundle 建在 default 租户下
        before = {
            o.org_id for o in organization_store.list_organizations(tenant_id="default")
        }

        r = client.get("/api/v1/workbench", headers=csrf_exempt_headers)
        assert r.status_code == 200, r.text
        graph = r.json().get("organization_graph") or {}
        assert graph["organization"]["org_id"] == bundle.org.org_id
        assert {
            o.org_id for o in organization_store.list_organizations(tenant_id="default")
        } == before

    def test_seeding_off_keeps_the_graph_honestly_empty(
        self, client, csrf_exempt_headers, foreign_bundle, monkeypatch
    ):
        """开关关闭 ⇒ 空租户维持空图，且**不会**退化成「看见别人的组织」。

        ★ 语义变更：本条取代原先的
        ``test_bootstrap_graph_is_empty_for_a_tenant_without_organizations``。
        原先「空租户 ⇒ 空图」是无条件的；引入惰性种子后，默认（非 production）下
        首访即会种出一个组织，只有**关闭开关**时才维持空图。两种行为都钉住，
        才不会把「有意的种子」误判成「租户过滤失效」。
        """
        monkeypatch.setattr(get_settings(), "seed_default_organization", False)
        # 前置：别人的组织**确实**在 store 里 —— 否则空图只是因为 store 本来就空。
        assert organization_store.get_organization(foreign_bundle.org.org_id) is not None
        assert organization_store.list_organizations(), "store 里必须已有组织，否则断言空转"

        tenant = f"empty-tenant-{uuid4().hex[:8]}"
        self._as_workbench_tenant(tenant)
        r = client.get("/api/v1/workbench", headers=csrf_exempt_headers)
        assert r.status_code == 200, r.text
        assert (r.json().get("organization_graph") or {}) == {}
        assert organization_store.list_organizations(tenant_id=tenant) == []

    def test_console_can_complete_the_full_flow_without_seed_data(
        self, client, admin_headers, csrf_exempt_headers
    ):
        """端到端闭环：建组织 → 建部门 → 建岗位，全程只用公开端点、零预置数据。

        这条把「组织域无种子」这个阻塞的**解法**钉住：不依赖任何 fixture 造数据，
        控制台该走的每一步都在这里走通了。
        """
        template_id = organization_store.get_role_catalog().templates[1].role_id

        org = client.post(
            f"{BASE}/organizations",
            json={"name": f"闭环组织-{uuid4().hex[:6]}"},
            headers=admin_headers,
        ).json()
        dept = client.post(
            f"{BASE}/departments",
            json={"org_id": org["org_id"], "name": f"闭环部门-{uuid4().hex[:6]}"},
            headers=admin_headers,
        ).json()
        agent = client.post(
            f"{BASE}/agents",
            json={
                "org_id": org["org_id"],
                "department_id": dept["department_id"],
                "name": f"闭环岗位-{uuid4().hex[:6]}",
                "role_template_id": template_id,
            },
            headers=admin_headers,
        )
        assert agent.status_code == 201, agent.text

        # 1) 落库可复核（验收红线）
        assert agent.json()["agent_id"] in {
            a.agent_id
            for a in organization_store.list_agents(department_id=dept["department_id"])
        }
        # 2) 组织图（控制台的数据来源）里看得见
        graph = organization_store.build_organization_graph(org["org_id"])
        assert graph is not None
        assert agent.json()["agent_id"] in {i.agent_id for i in graph.agent_instances}
        # 3) 该组织是当前租户最近更新的 ⇒ 它就是要展示到控制台的那一个
        assert organization_store.list_organizations(tenant_id="default")[
            0
        ].org_id == org["org_id"]


class TestWorkbenchOrganizationSelection:
    """(c) 组织切换：``GET /api/v1/workbench?org_id=...``。

    ★ 为什么每个用例都要建**两个**组织，且让被选中的那个**不是** ``[0]``
    =====================================================================
    ``OrganizationStore`` 是进程级单例，而缺省行为恰好就是
    ``list_organizations(...)[0]``。若用例只建一个组织再断言「选中的是它」，
    那么把实现原样退回「永远取 [0]」也能通过 —— 断言恒真、测试空转
    （本仓已反复出现的第四种空转归因：对照组缺失）。所以这里必须让
    「正确实现」与「退化成 [0]」在结果上**可区分**。
    """

    def test_explicit_org_id_selects_that_organization_not_the_most_recent(
        self, client, admin_headers
    ):
        suffix = uuid4().hex[:8]
        older = organization_store.create_organization(
            tenant_id="default", name=f"较早组织-{suffix}"
        )
        older_dept = organization_store.create_department(
            org_id=older.org_id, name=f"较早部门-{suffix}"
        )
        # 后建 ⇒ updated_at 更晚（create_department 会 touch 其组织的 updated_at）
        # ⇒ list_organizations(...)[0] 是 newer。目标组织刻意选 older。
        newer = organization_store.create_organization(
            tenant_id="default", name=f"较新组织-{suffix}"
        )
        newer_dept = organization_store.create_department(
            org_id=newer.org_id, name=f"较新部门-{suffix}"
        )
        # 前置断言：先证明「[0] ≠ 目标组织」这个前提真的成立。
        # 少了它，本用例会在前提不成立时静默退化成「取 [0] 也对」。
        assert (
            organization_store.list_organizations(tenant_id="default")[0].org_id
            == newer.org_id
        )

        r = client.get(
            f"/api/v1/workbench?org_id={older.org_id}", headers=admin_headers
        )
        assert r.status_code == 200, r.text
        graph = r.json()["organization_graph"]
        assert graph["organization"]["org_id"] == older.org_id
        assert graph["organization"]["name"] == f"较早组织-{suffix}"
        assert [d["department_id"] for d in graph["departments"]] == [
            older_dept.department_id
        ]
        # 反向：最近更新的那个组织的内容不得混进来
        assert newer_dept.department_id not in {
            d["department_id"] for d in graph["departments"]
        }

    def test_omitting_org_id_keeps_the_most_recent_organization(
        self, client, admin_headers
    ):
        """省略参数 ⇒ 维持旧行为（首屏 / 未登录 bootstrap 依赖它）。"""
        suffix = uuid4().hex[:8]
        org = organization_store.create_organization(
            tenant_id="default", name=f"缺省组织-{suffix}"
        )
        organization_store.create_department(
            org_id=org.org_id, name=f"缺省部门-{suffix}"
        )

        r = client.get("/api/v1/workbench", headers=admin_headers)
        assert r.status_code == 200, r.text
        assert r.json()["organization_graph"]["organization"]["org_id"] == org.org_id

    def test_unknown_org_id_is_404(self, client, admin_headers):
        missing_id = str(uuid4())
        r = client.get(
            f"/api/v1/workbench?org_id={missing_id}", headers=admin_headers
        )
        assert r.status_code == 404, r.text
        body = r.json()
        assert body["code"] == "resource_not_found"
        assert body["message"] == f"组织不存在：{missing_id}"

    def test_foreign_tenant_org_id_is_404(self, client, admin_headers, foreign_bundle):
        """别的租户的组织 ⇒ 404（不是静默回退到自己的 [0]）。

        静默回退会让「切换没生效」看起来像「切换成功了」，用户在一个
        不该看的组织上继续操作，比直接报错危险得多。
        """
        r = client.get(
            f"/api/v1/workbench?org_id={foreign_bundle.org.org_id}",
            headers=admin_headers,
        )
        assert r.status_code == 404, r.text
        assert r.json()["code"] == "resource_not_found"

    def test_missing_and_foreign_org_share_the_same_error_shape(
        self, client, admin_headers, foreign_bundle
    ):
        """「不存在」与「属于别人」必须同码同文案，否则可枚举他人 org_id。"""
        missing_id = str(uuid4())
        missing = client.get(
            f"/api/v1/workbench?org_id={missing_id}", headers=admin_headers
        )
        foreign = client.get(
            f"/api/v1/workbench?org_id={foreign_bundle.org.org_id}",
            headers=admin_headers,
        )

        assert missing.status_code == foreign.status_code == 404
        assert missing.json()["code"] == foreign.json()["code"]
        assert missing.json()["message"] == f"组织不存在：{missing_id}"
        assert (
            foreign.json()["message"]
            == f"组织不存在：{foreign_bundle.org.org_id}"
        )

    def test_console_org_id_reports_the_selected_organization(
        self, client, admin_headers
    ):
        """``console.org_id`` 必须是被选中的组织，而不是 ``principal.tenant_id``。

        此前它恒等于 tenant_id（``"default"``），与 organization_graph 里的真实
        org_id 不是一回事 —— 前端拿它拼 SSE 的 org_id 过滤参数，等于永远过滤错。
        """
        suffix = uuid4().hex[:8]
        org = organization_store.create_organization(
            tenant_id="default", name=f"标识组织-{suffix}"
        )

        r = client.get(f"/api/v1/workbench?org_id={org.org_id}", headers=admin_headers)
        assert r.status_code == 200, r.text
        body = r.json()
        assert body["console"]["org_id"] == org.org_id
        assert body["console"]["org_id"] != body["console"]["tenant_id"]
        assert body["organization_graph"]["organization"]["org_id"] == org.org_id

    def test_switching_twice_returns_each_organizations_own_agents(
        self, client, admin_headers
    ):
        """★ 切换语义：同一客户端连续切两次，两份图各自只含自己的智能体。"""
        suffix = uuid4().hex[:8]
        left = organization_store.create_organization(
            tenant_id="default", name=f"左组织-{suffix}"
        )
        left_dept = organization_store.create_department(
            org_id=left.org_id, name=f"左部门-{suffix}"
        )
        right = organization_store.create_organization(
            tenant_id="default", name=f"右组织-{suffix}"
        )
        right_dept = organization_store.create_department(
            org_id=right.org_id, name=f"右部门-{suffix}"
        )
        template_id = organization_store.get_role_catalog().templates[0].role_id
        left_agent = organization_store.create_agent(
            org_id=left.org_id,
            department_id=left_dept.department_id,
            name=f"左岗位-{suffix}",
            role_template_id=template_id,
        )
        right_agent = organization_store.create_agent(
            org_id=right.org_id,
            department_id=right_dept.department_id,
            name=f"右岗位-{suffix}",
            role_template_id=template_id,
        )

        left_graph = client.get(
            f"/api/v1/workbench?org_id={left.org_id}", headers=admin_headers
        ).json()["organization_graph"]
        right_graph = client.get(
            f"/api/v1/workbench?org_id={right.org_id}", headers=admin_headers
        ).json()["organization_graph"]

        assert {a["agent_id"] for a in left_graph["agent_instances"]} == {
            left_agent.agent_id
        }
        assert {a["agent_id"] for a in right_graph["agent_instances"]} == {
            right_agent.agent_id
        }
