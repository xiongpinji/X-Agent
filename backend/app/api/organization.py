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

from collections import Counter
from typing import Annotated, Any

from fastapi import APIRouter, Depends
from pydantic import BaseModel, ConfigDict, Field

from backend.app.api.errors import api_error
from backend.app.core.contracts import ErrorCode
from backend.app.core.org import (
    AgentNameConflictError,
    AgentNode,
    Department,
    Organization,
    agent_role_for_template,
    organization_store,
)
from backend.app.core.security import Principal
from backend.app.dependencies import (
    enforce_scope,
    get_audit_store,
    get_current_principal,
)

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

    _record_org_audit(
        principal,
        action="organization_agent.create",
        resource_type="organization_agent",
        resource_id=agent.agent_id,
        details={
            "org_id": agent.org_id,
            "department_id": agent.department_id,
            "role_template_id": agent.role_template_id,
            "name": agent.name,
            "role": agent.role.value,
            "warnings": list(warnings),
        },
    )

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
# 治理读路径与审计落账
#
# 为什么写路径要显式落审计：``core.audit.AuditStore`` 此前只被 ``api/agents.py``
# （运行期 ``agent.run``）和审批域调用，**组织域一条都不写**。若只挂一个
# ``GET /organization/audit`` 而不补写，页面要么空、要么就得去编数字 —— 后者正是
# 本仓一直在拆的东西。
# ─────────────────────────────────────────────────────────────────────────────

#: 审计读取的扫描上界（内存存储，量级很小）。超过它时响应里会给 ``truncated: true``，
#: 而不是让 ``total`` 静默失真。
_AUDIT_SCAN_LIMIT = 2000


def _record_org_audit(
    principal: Principal,
    *,
    action: str,
    resource_type: str,
    resource_id: str,
    details: dict[str, Any] | None = None,
) -> None:
    """把一次组织域写操作落进审计存储。

    ``tenant_id`` 一律取 ``principal.tenant_id``，与 ``GET /organization/audit``
    的读取过滤口径**同源**；否则写进去的账在读取侧看不见。
    """
    get_audit_store().record(
        action=action,
        resource_type=resource_type,
        resource_id=resource_id,
        tenant_id=principal.tenant_id,
        actor_id=principal.user_id,
        outcome="success",
        details=details or {},
    )


def _tenant_agent_nodes(principal: Principal, org_id: str | None = None) -> list[AgentNode]:
    """当前租户下的岗位智能体（给出 ``org_id`` 时收窄到该组织）。

    ``OrganizationStore`` 是**进程级单例、跨租户共用**，而 ``list_agents()`` 不认识
    租户 ⇒ 必须先按「本租户的组织 id 集合」收窄，否则会把别的租户的编制算进在用数。
    """
    if org_id is not None:
        _require_organization_in_tenant(org_id, principal)
        return organization_store.list_agents(org_id=org_id)

    tenant_org_ids = {
        organization.org_id
        for organization in organization_store.list_organizations(
            tenant_id=principal.tenant_id
        )
    }
    return [
        agent
        for agent in organization_store.list_agents()
        if agent.org_id in tenant_org_ids
    ]


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
    _record_org_audit(
        principal,
        action="organization.create",
        resource_type="organization",
        resource_id=organization.org_id,
        details={"name": organization.name, "tenant_id": organization.tenant_id},
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
    _record_org_audit(
        principal,
        action="department.create",
        resource_type="department",
        resource_id=department.department_id,
        details={
            "org_id": department.org_id,
            "name": department.name,
            "parent_department_id": department.parent_department_id,
            "leader_agent_id": department.leader_agent_id,
        },
    )
    return _department_payload(department)


# ─────────────────────────────────────────────────────────────────────────────
# 治理读路径（岗位模板目录 / 审计流水）
#
# 控制台的「角色权限」与「组织审核」两页此前是硬编码占位（24 个角色 / 13 条事件），
# 数据源 /api/v1/organization-control/* 未挂载。这里给出**两条真实读路径**，
# 让那两页可以接线到真数据 —— 而不是把 fixture 模块挂上白名单。
# ─────────────────────────────────────────────────────────────────────────────


@router.get("/roles")
async def list_organization_roles(
    principal: PrincipalDependency = None,
    org_id: str | None = None,
) -> dict[str, Any]:
    """岗位模板目录 + **真实**的在用数量。

    角色目录必须取 ``organization_store.get_role_catalog()``：``RoleTemplate.role_id``
    是 ``uuid4`` factory，各处自行 ``build_default_role_catalog()`` 会得到**不同的 id**
    ⇒ 前端拿着模板 id 去创建智能体必然 404（与写路径同源是硬要求）。

    ``in_use`` 是该模板在当前租户（给出 ``org_id`` 时收窄到该组织）下**真实在用**的
    智能体数量 —— 由 ``list_agents()`` 数出来，不是估计值、更不是常量。
    """
    enforce_scope(principal, "org:read")

    catalog = organization_store.get_role_catalog()
    usage: Counter[str] = Counter(
        agent.role_template_id for agent in _tenant_agent_nodes(principal, org_id)
    )

    return {
        "resource_type": "organization_roles",
        "org_id": org_id,
        "total_templates": len(catalog.templates),
        "in_use_total": sum(usage.values()),
        "templates": [
            {
                "role_id": template.role_id,
                "role_name": template.role_name,
                "category": template.category,
                "level": template.level,
                "title": template.title,
                "description": template.description,
                "core_skills": list(template.core_skills),
                "in_use": usage.get(template.role_id, 0),
            }
            for template in catalog.templates
        ],
        "role_groups": catalog.role_groups,
    }


@router.get("/audit")
async def list_organization_audit(
    principal: PrincipalDependency = None,
    limit: int = 50,
    offset: int = 0,
    resource_type: str | None = None,
    outcome: str | None = None,
) -> dict[str, Any]:
    """组织域审计流水（真实数据，读 ``core.audit.AuditStore``）。

    与 ``POST /organizations`` / ``/departments`` / ``/agents`` 写的是**同一份**存储，
    按 ``principal.tenant_id`` 隔离。**刻意不挂载 organization_control.py**：
    它的 ``GET /audit`` 返回硬编码的 13 条事件，挂上去等于把编造数字包装成功能。

    读数口径：先把该租户的匹配记录整段取出（内存存储，量级很小），再切片 ——
    ``total`` / ``summary`` 与列表出自**同一份**数据，不会出现「汇总说 13 条、
    列表只有 3 条」的错位。超过 ``_AUDIT_SCAN_LIMIT`` 时置 ``truncated: true``，
    让截断可见而不是让 ``total`` 静默失真。
    """
    enforce_scope(principal, "org:read")

    if limit < 1 or limit > 200:
        raise api_error(422, ErrorCode.VALIDATION_ERROR, "limit 必须在 1..200 之间")
    if offset < 0:
        raise api_error(422, ErrorCode.VALIDATION_ERROR, "offset 不能为负数")

    matched = get_audit_store().list(
        tenant_id=principal.tenant_id,
        resource_type=resource_type,
        outcome=outcome,
        limit=_AUDIT_SCAN_LIMIT,
    )
    page = matched[offset : offset + limit]
    outcomes = Counter(record.outcome for record in matched)

    return {
        "resource_type": "organization_audit",
        "tenant_id": principal.tenant_id,
        "total": len(matched),
        "limit": limit,
        "offset": offset,
        "scan_limit": _AUDIT_SCAN_LIMIT,
        "truncated": len(matched) >= _AUDIT_SCAN_LIMIT,
        "filters": {"resource_type": resource_type, "outcome": outcome},
        "summary": {
            "success": outcomes.get("success", 0),
            "failure": outcomes.get("failure", 0) + outcomes.get("failed", 0),
            "latest_outcome": matched[0].outcome if matched else None,
        },
        "records": [
            {
                "id": record.id,
                "actor_id": record.actor_id,
                "action": record.action,
                "resource_type": record.resource_type,
                "resource_id": record.resource_id,
                "outcome": record.outcome,
                "created_at": record.created_at,
                "details": record.details,
            }
            for record in page
        ],
    }
