"""组织域写入 API（组织 / 部门 / 岗位智能体）。

为什么新建本模块，而不是复用 organization_control
================================================
``organization_control.py`` 是一个**纯 fixture 模块**：4 个 GET 全部返回硬编码
字面量（``"total_departments": 8`` / ``"root_name": "统一控制台"`` / …），且不在
``main.py`` 的 ``_KEPT_ROUTER_MODULES`` 白名单里。把它挂进白名单 = 把当前「诚实的
404」换成「200 + 编造数字」，那是把缺陷升级成欺骗。因此组织域的真实端点落在本模块，
fixture 模块维持未挂载。

与 ``/api/v1/agents`` 的区别
============================
``api/agents.py`` 写的是**运行期 Agent**（进程内 ``_AGENTS`` 字典、``persona`` 是
dict、要求 ``security:manage``）。本模块写的是**组织域岗位智能体**
（``core/org.py`` 的 ``AgentNode``）。两者实体不同（一个是"能不能跑"，一个是
"在组织里挂在哪个部门、向谁汇报"），刻意不复用同一条写路径。

只继承模板（拍板 ①）
====================
岗位画像不做逐字段覆盖：``role`` / ``title`` / ``capabilities`` 全部由所选
``RoleTemplate`` 派生，payload 只承载「组织定位」——org / department / name /
manager / role_template_id。这样就不会再出现「表单里根本没这个输入框、前端却恒发
空数组」的半实现字段（旧 ``AgentCreatePayload`` 的 capabilities/plugins/apps 即如此）。

持久化（拍板 ③）
================
``OrganizationStore`` 目前是**纯内存、无种子**，因此本端点的产物「重启即失」。
本次刻意不引入持久化：验收只认「契约正确 + ``list_agents()`` 可复核」，不认
「重启后还在」。
"""
from __future__ import annotations

from typing import Annotated, Any

from fastapi import APIRouter, Depends
from pydantic import BaseModel, ConfigDict, Field

from backend.app.api.errors import api_error
from backend.app.core.contracts import ErrorCode
from backend.app.core.org import (
    AgentNameConflictError,
    Department,
    Organization,
    agent_role_for_template,
    organization_store,
)
from backend.app.core.security import Principal
from backend.app.dependencies import enforce_scope, get_current_principal

router = APIRouter(prefix="/api/v1/organization", tags=["organization"])

PrincipalDependency = Annotated[Principal, Depends(get_current_principal)]


def _require_organization_in_tenant(org_id: str, principal: Principal) -> Organization:
    """取组织，且必须属于当前租户；否则 404。

    「不存在」与「属于别的租户」返回**同一个 404**：403 会泄漏「该 org_id 真实存在」，
    让攻击者能枚举别人的组织 id。

    注：OrganizationStore 目前是进程内单例、没有租户级隔离层，所以这层校验是
    唯一的边界 —— 组织域任何按 id 取对象的入口都必须先过它。
    """
    organization = organization_store.get_organization(org_id)
    if organization is None or organization.tenant_id != principal.tenant_id:
        raise api_error(
            404, ErrorCode.RESOURCE_NOT_FOUND, f"组织不存在：{org_id}"
        )
    return organization


def _organization_payload(organization: Organization) -> dict[str, Any]:
    return {
        "org_id": organization.org_id,
        "tenant_id": organization.tenant_id,
        "name": organization.name,
        "description": organization.description,
        "owner_user_id": organization.owner_user_id,
        "status": organization.status.value,
        "created_at": organization.created_at,
        "updated_at": organization.updated_at,
    }


def _department_payload(department: Department) -> dict[str, Any]:
    return {
        "department_id": department.department_id,
        "org_id": department.org_id,
        "name": department.name,
        "mission": department.mission,
        "leader_agent_id": department.leader_agent_id,
        "parent_department_id": department.parent_department_id,
        "created_at": department.created_at,
        "updated_at": department.updated_at,
    }


class OrganizationAgentCreateRequest(BaseModel):
    """创建组织岗位智能体的请求体。

    ``role_template_id`` 是岗位画像的唯一来源；本模型**刻意**不含
    capabilities / plugins / apps / persona / tone / decision_style /
    communication_style / risk_appetite / room_id —— 它们要么由模板派生，
    要么当前没有落点（见模块 docstring）。

    ``extra="forbid"``：旧版 ``AgentCreatePayload`` 会带上 capabilities / persona
    等字段。静默忽略它们 = 又一次「前端以为设置了、后端根本没读」；这里直接 422，
    把口径差当场暴露出来。
    """

    model_config = ConfigDict(extra="forbid")

    org_id: str = Field(min_length=1)
    department_id: str = Field(min_length=1)
    name: str = Field(min_length=1)
    role_template_id: str = Field(min_length=1)
    # 不传则由模板的 title 兜底（见 handler 注释）。
    title: str = ""
    manager_agent_id: str | None = None
    team_size_limit: int = Field(default=5, ge=0, le=100)
    memory_scope: dict[str, str] = Field(default_factory=dict)


class OrganizationCreateRequest(BaseModel):
    """创建组织的请求体。

    刻意**不含 `tenant_id`** —— 归属一律取 `principal.tenant_id`。
    允许客户端指定就等于开了一个跨租户写入口，而目前没有任何真实需求需要它。
    """

    model_config = ConfigDict(extra="forbid")

    name: str = Field(min_length=1)
    description: str = ""


class DepartmentCreateRequest(BaseModel):
    """创建部门的请求体。`parent_department_id` 支持多级组织结构。"""

    model_config = ConfigDict(extra="forbid")

    org_id: str = Field(min_length=1)
    name: str = Field(min_length=1)
    mission: str = ""
    leader_agent_id: str | None = None
    parent_department_id: str | None = None


@router.post("/agents", status_code=201)
async def create_organization_agent(
    payload: OrganizationAgentCreateRequest,
    principal: PrincipalDependency = None,
) -> dict[str, Any]:
    """在指定部门下创建一个岗位智能体。

    鉴权：``org:write``（拍板 Q8 —— admin + developer）。

    继承规则（本端点独有的策略层，领域层只负责落库）：
    - ``role``       ← ``agent_role_for_template(template)``（模板 level 映射）
    - ``title``      ← 请求留空时取 ``template.title``
    - ``capabilities`` ← ``template.core_skills``

    错误口径：
    - 组织 / 部门 / 模板 / 上级 不存在 → 404（不做静默降级：把打错的 id 静默建成
      一个没有汇报关系的孤儿岗位，比报错更难排查）
    - 同部门重名 → 409 RESOURCE_CONFLICT（拍板 Q2）

    响应里的 ``warnings`` 承载「部分成功」：目前唯一来源是上级编制已满
    （智能体建成了，但没挂上汇报关系）。
    """
    enforce_scope(principal, "org:write")

    # 租户边界：不能往别的租户的组织里塞智能体。
    _require_organization_in_tenant(payload.org_id, principal)

    department = organization_store.get_department(payload.department_id)
    if department is None:
        raise api_error(
            404, ErrorCode.RESOURCE_NOT_FOUND, f"部门不存在：{payload.department_id}"
        )
    if department.org_id != payload.org_id:
        raise api_error(
            404,
            ErrorCode.RESOURCE_NOT_FOUND,
            f"部门 {payload.department_id} 不属于组织 {payload.org_id}",
        )

    template = next(
        (
            item
            for item in organization_store.get_role_catalog().templates
            if item.role_id == payload.role_template_id
        ),
        None,
    )
    if template is None:
        raise api_error(
            404,
            ErrorCode.RESOURCE_NOT_FOUND,
            f"岗位模板不存在：{payload.role_template_id}",
        )

    if payload.manager_agent_id:
        manager = organization_store.get_agent(payload.manager_agent_id)
        if manager is None:
            raise api_error(
                404,
                ErrorCode.RESOURCE_NOT_FOUND,
                f"上级智能体不存在：{payload.manager_agent_id}",
            )
        if manager.org_id != payload.org_id:
            raise api_error(
                404,
                ErrorCode.RESOURCE_NOT_FOUND,
                f"上级智能体 {payload.manager_agent_id} 不属于组织 {payload.org_id}",
            )

    name = payload.name.strip()
    if not name:
        raise api_error(
            422, ErrorCode.VALIDATION_ERROR, "智能体名称不能为空（或全为空白字符）"
        )

    warnings: list[str] = []
    try:
        agent = organization_store.create_agent(
            org_id=payload.org_id,
            department_id=payload.department_id,
            name=name,
            role=agent_role_for_template(template),
            title=payload.title.strip() or template.title,
            role_template_id=template.role_id,
            manager_agent_id=payload.manager_agent_id,
            capabilities=list(template.core_skills),
            team_size_limit=payload.team_size_limit,
            memory_scope=dict(payload.memory_scope),
            warnings=warnings,
        )
    except AgentNameConflictError as exc:
        raise api_error(
            409,
            ErrorCode.RESOURCE_CONFLICT,
            f"部门内已存在同名智能体「{exc.name}」",
        ) from exc
    except KeyError as exc:  # 上面已逐个校验过；这里是并发窗口的兜底
        raise api_error(
            404, ErrorCode.RESOURCE_NOT_FOUND, f"组织域对象已不存在：{exc.args[0] if exc.args else 'unknown'}"
        ) from exc

    return {
        "agent_id": agent.agent_id,
        "org_id": agent.org_id,
        "department_id": agent.department_id,
        "role_template_id": agent.role_template_id,
        "name": agent.name,
        "title": agent.title,
        "role": agent.role.value,
        "manager_agent_id": agent.manager_agent_id,
        "capabilities": agent.capabilities,
        "team_size_limit": agent.team_size_limit,
        "memory_scope": agent.memory_scope,
        "status": agent.status.value,
        "created_at": agent.created_at,
        "warnings": warnings,
    }


# ─────────────────────────────────────────────────────────────────────────────
# 组织 / 部门
#
# 这两个端点的存在理由：OrganizationStore 纯内存无种子，而 create_organization /
# create_department 在 backend/app/** 里**零调用者** ⇒ 运行时组织域永远为空 ⇒
# POST /agents 拿不到合法的 org_id / department_id（控制台表单也因此恒空、
# 校验阶段就被拦下）。有了它们，组织域第一次能「从零真实地建起来」，
# 不需要预置任何假数据。
# ─────────────────────────────────────────────────────────────────────────────


@router.get("/organizations")
async def list_organizations(
    principal: PrincipalDependency = None,
) -> list[dict[str, Any]]:
    """列出**当前租户**的组织（`list_organizations` 已按 updated_at 倒序）。"""
    enforce_scope(principal, "org:read")
    return [
        _organization_payload(organization)
        for organization in organization_store.list_organizations(
            tenant_id=principal.tenant_id
        )
    ]


@router.post("/organizations", status_code=201)
async def create_organization(
    payload: OrganizationCreateRequest,
    principal: PrincipalDependency = None,
) -> dict[str, Any]:
    """创建一个组织（归属 = 当前租户，创建者记为 owner）。"""
    enforce_scope(principal, "org:write")

    name = payload.name.strip()
    if not name:
        raise api_error(
            422, ErrorCode.VALIDATION_ERROR, "组织名称不能为空（或全为空白字符）"
        )

    organization = organization_store.create_organization(
        tenant_id=principal.tenant_id,
        name=name,
        description=payload.description.strip(),
        owner_user_id=principal.user_id,
    )
    return _organization_payload(organization)


@router.get("/departments")
async def list_departments(
    org_id: str,
    principal: PrincipalDependency = None,
) -> list[dict[str, Any]]:
    """列出某组织下的部门。"""
    enforce_scope(principal, "org:read")
    _require_organization_in_tenant(org_id, principal)
    return [
        _department_payload(department)
        for department in organization_store.list_departments(org_id=org_id)
    ]


@router.post("/departments", status_code=201)
async def create_department(
    payload: DepartmentCreateRequest,
    principal: PrincipalDependency = None,
) -> dict[str, Any]:
    """在指定组织下创建一个部门。

    `leader_agent_id` / `parent_department_id` 若给出，必须存在**且同属该组织** ——
    放行一个打错的 id 会静默挂出一棵错的汇报树，比直接报错难查得多。
    """
    enforce_scope(principal, "org:write")
    _require_organization_in_tenant(payload.org_id, principal)

    name = payload.name.strip()
    if not name:
        raise api_error(
            422, ErrorCode.VALIDATION_ERROR, "部门名称不能为空（或全为空白字符）"
        )

    if payload.leader_agent_id:
        leader = organization_store.get_agent(payload.leader_agent_id)
        if leader is None or leader.org_id != payload.org_id:
            raise api_error(
                404,
                ErrorCode.RESOURCE_NOT_FOUND,
                f"负责人不存在或不属于该组织：{payload.leader_agent_id}",
            )

    if payload.parent_department_id:
        parent = organization_store.get_department(payload.parent_department_id)
        if parent is None or parent.org_id != payload.org_id:
            raise api_error(
                404,
                ErrorCode.RESOURCE_NOT_FOUND,
                f"上级部门不存在或不属于该组织：{payload.parent_department_id}",
            )

    department = organization_store.create_department(
        org_id=payload.org_id,
        name=name,
        mission=payload.mission.strip(),
        leader_agent_id=payload.leader_agent_id,
        parent_department_id=payload.parent_department_id,
    )
    return _department_payload(department)
