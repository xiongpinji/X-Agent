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
    """一个全新的组织 + 两个部门 + store 自己的模板目录。"""
    suffix = uuid4().hex[:8]
    org = organization_store.create_organization(
        tenant_id=f"tenant-{suffix}", name=f"组织-{suffix}"
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
