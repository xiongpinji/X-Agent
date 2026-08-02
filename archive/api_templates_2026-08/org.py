from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field

from backend.app.api.errors import api_error
from backend.app.api.linked_summary import build_linked_summary
from backend.app.core.collaboration import collaboration_store
from backend.app.core.contracts import ErrorCode
from backend.app.core.memory import MemorySystem
from backend.app.core.org import AgentNode, AgentRole, Department, Organization, organization_store
from backend.app.core.security import Principal
from backend.app.dependencies import enforce_scope, get_current_principal, get_memory

router = APIRouter(prefix="/api/v1/org", tags=["org"])
PrincipalDependency = Annotated[Principal, Depends(get_current_principal)]
MemoryDependency = Annotated[MemorySystem, Depends(get_memory)]


class OrganizationCreateRequest(BaseModel):
    tenant_id: str = "default"
    name: str = Field(..., min_length=1, max_length=200)
    description: str = Field(default="", max_length=2000)
    owner_user_id: str = Field(default="anonymous", max_length=200)


class DepartmentCreateRequest(BaseModel):
    org_id: str
    name: str = Field(..., min_length=1, max_length=200)
    mission: str = Field(default="", max_length=2000)
    leader_agent_id: str | None = None
    parent_department_id: str | None = None


class AgentCreateRequest(BaseModel):
    org_id: str
    department_id: str
    name: str = Field(..., min_length=1, max_length=200)
    role: AgentRole = AgentRole.ASSISTANT
    role_template_id: str | None = None
    meeting_room_id: str | None = None
    title: str = Field(default="", max_length=200)
    manager_agent_id: str | None = None
    capabilities: list[str] = Field(default_factory=list)
    team_size_limit: int = Field(default=5, ge=0, le=100)
    memory_scope: dict[str, str] = Field(default_factory=dict)
    feishu_user_id: str | None = None
    feishu_open_id: str | None = None
    feishu_union_id: str | None = None
    feishu_email: str | None = None
    feishu_enabled: bool = False


class AgentUpdateRequest(BaseModel):
    name: str | None = None
    role: AgentRole | None = None
    title: str | None = None
    manager_agent_id: str | None = None
    capabilities: list[str] | None = None
    team_size_limit: int | None = Field(default=None, ge=0, le=100)
    feishu_user_id: str | None = None
    feishu_open_id: str | None = None
    feishu_union_id: str | None = None
    feishu_email: str | None = None
    feishu_enabled: bool | None = None


@router.post("/organizations", response_model=Organization)
async def create_organization(request: OrganizationCreateRequest, principal: PrincipalDependency) -> Organization:
    enforce_scope(principal, "security:manage")
    return organization_store.create_organization(
        tenant_id=principal.tenant_id,
        name=request.name,
        description=request.description,
        owner_user_id=principal.user_id,
    )


@router.get("/organizations", response_model=list[Organization])
async def list_organizations(principal: PrincipalDependency) -> list[Organization]:
    enforce_scope(principal, "security:manage")
    return organization_store.list_organizations(tenant_id=principal.tenant_id)


@router.get("/organizations/{org_id}", response_model=Organization)
async def get_organization(org_id: str, principal: PrincipalDependency) -> Organization:
    enforce_scope(principal, "security:manage")
    org = organization_store.get_organization(org_id)
    if org is None:
        raise api_error(404, ErrorCode.RESOURCE_NOT_FOUND, "Organization not found.", details={"resource_type": "organization", "resource_id": org_id})
    return org


@router.get("/organizations/{org_id}/summary")
async def get_organization_summary(org_id: str, principal: PrincipalDependency) -> dict[str, object]:
    enforce_scope(principal, "security:manage")
    org = organization_store.get_organization(org_id)
    if org is None:
        raise api_error(404, ErrorCode.RESOURCE_NOT_FOUND, "Organization not found.", details={"resource_type": "organization", "resource_id": org_id})
    departments = organization_store.list_departments(org_id=org_id)
    agents = organization_store.list_agents(org_id=org_id)
    trees = [organization_store.get_agent_tree(agent.agent_id) for agent in agents if agent.manager_agent_id is None]
    department_summaries = [organization_store.department_memory_summary(department.department_id) for department in departments]
    total_layer_counts: dict[int, int] = {}
    for summary in department_summaries:
        for layer, count in (summary.get("layer_totals") or {}).items():
            total_layer_counts[int(layer)] = total_layer_counts.get(int(layer), 0) + int(count)
    return {
        "organization": org.model_dump(mode="json"),
        "department_count": len(departments),
        "agent_count": len(agents),
        "departments": [department.model_dump(mode="json") for department in departments],
        "department_summaries": [summary for summary in department_summaries if summary],
        "org_layer_totals": dict(sorted(total_layer_counts.items())),
        "agents": [agent.model_dump(mode="json") for agent in agents],
        "trees": [tree for tree in trees if tree is not None],
    }


@router.get("/organizations/{org_id}/overview")
async def get_organization_overview(org_id: str, principal: PrincipalDependency) -> dict[str, object]:
    enforce_scope(principal, "security:manage")
    org = organization_store.get_organization(org_id)
    if org is None:
        raise api_error(404, ErrorCode.RESOURCE_NOT_FOUND, "Organization not found.", details={"resource_type": "organization", "resource_id": org_id})
    summary = await get_organization_summary(org_id, principal)
    leaders = [tree for tree in summary.get("trees", []) if tree]
    leader_memories = [organization_store.agent_memory_summary(tree["agent"]["agent_id"]) for tree in leaders if tree and isinstance(tree, dict) and tree.get("agent")]
    rooms = [room.model_dump(mode="json") for room in collaboration_store.list_rooms(tenant_id=org.tenant_id)]
    primary = {
        "organization": summary.get("organization", {}),
        "departments": summary.get("departments", []),
        "department_summaries": summary.get("department_summaries", []),
        "org_layer_totals": summary.get("org_layer_totals", {}),
        "leaders": leaders,
        "leader_memories": [item for item in leader_memories if item],
        "collaboration_rooms": rooms,
        "agent_count": summary.get("agent_count", 0),
        "department_count": summary.get("department_count", 0),
    }
    return build_linked_summary(
        resource_type="organization_overview",
        resource_id=org_id,
        primary=primary,
        workflow={"data": {"leaders": leaders, "collaboration_rooms": rooms}, "summary": {"agent_count": primary["agent_count"], "department_count": primary["department_count"]}},
        memory={"data": {"leader_memories": primary["leader_memories"], "department_summaries": primary["department_summaries"]}, "summary": {"leader_count": len(leaders), "department_count": primary["department_count"]}},
        audit={"data": {"org_layer_totals": primary["org_layer_totals"]}, "summary": {"agent_count": primary["agent_count"], "department_count": primary["department_count"]}},
        extra={"summary": {"organization_name": summary.get("organization", {}).get("name"), "agent_count": primary["agent_count"], "department_count": primary["department_count"]}},
    )


@router.post("/departments", response_model=Department)
async def create_department(request: DepartmentCreateRequest, principal: PrincipalDependency) -> Department:
    enforce_scope(principal, "security:manage")
    try:
        return organization_store.create_department(
            org_id=request.org_id,
            name=request.name,
            mission=request.mission,
            leader_agent_id=request.leader_agent_id,
            parent_department_id=request.parent_department_id,
        )
    except KeyError:
        raise api_error(404, ErrorCode.RESOURCE_NOT_FOUND, "Organization not found.", details={"resource_type": "organization", "resource_id": request.org_id})


@router.get("/departments", response_model=list[Department])
async def list_departments(principal: PrincipalDependency, org_id: str | None = None) -> list[Department]:
    enforce_scope(principal, "security:manage")
    return organization_store.list_departments(org_id=org_id)


@router.get("/departments/{department_id}", response_model=Department)
async def get_department(department_id: str, principal: PrincipalDependency) -> Department:
    enforce_scope(principal, "security:manage")
    department = organization_store.get_department(department_id)
    if department is None:
        raise api_error(404, ErrorCode.RESOURCE_NOT_FOUND, "Department not found.", details={"resource_type": "department", "resource_id": department_id})
    return department


@router.get("/departments/{department_id}/memory")
async def get_department_memory(department_id: str, principal: PrincipalDependency) -> dict[str, object]:
    enforce_scope(principal, "memory:read")
    summary = organization_store.department_memory_summary(department_id)
    if not summary:
        raise api_error(404, ErrorCode.RESOURCE_NOT_FOUND, "Department not found.", details={"resource_type": "department", "resource_id": department_id})
    return summary


@router.post("/agents", response_model=AgentNode)
async def create_agent(request: AgentCreateRequest, principal: PrincipalDependency) -> AgentNode:
    enforce_scope(principal, "security:manage")
    try:
        role_catalog = organization_store.get_role_catalog() if hasattr(organization_store, "get_role_catalog") else None
        template = None
        if request.role_template_id and role_catalog is not None:
            template = next((item for item in role_catalog.templates if item.role_id == request.role_template_id), None)
        inherited_capabilities = list(request.capabilities)
        inherited_title = request.title
        inherited_memory_scope = {
            **request.memory_scope,
            "feishu_user_id": request.feishu_user_id or "",
            "feishu_open_id": request.feishu_open_id or "",
            "feishu_union_id": request.feishu_union_id or "",
            "feishu_email": request.feishu_email or "",
            "feishu_enabled": str(request.feishu_enabled),
        }
        if template is not None:
            inherited_capabilities = list(dict.fromkeys([*template.core_skills, *inherited_capabilities]))
            inherited_title = inherited_title or template.title
            inherited_memory_scope["role_template_id"] = template.role_id
            inherited_memory_scope["role_name"] = template.role_name
            inherited_memory_scope["role_category"] = str(template.category)
            inherited_memory_scope["persona"] = template.persona
        agent = organization_store.create_agent(
            org_id=request.org_id,
            department_id=request.department_id,
            name=request.name,
            role=request.role,
            title=inherited_title,
            manager_agent_id=request.manager_agent_id,
            capabilities=inherited_capabilities,
            team_size_limit=request.team_size_limit,
            memory_scope=inherited_memory_scope,
        )
        if hasattr(agent, "meeting_room_id") and request.meeting_room_id is not None:
            agent.meeting_room_id = request.meeting_room_id
        if template is not None:
            agent.memory_scope["workflow_name"] = template.role_name
        return agent
        return agent
    except KeyError as exc:
        missing_id = str(exc)
        raise api_error(404, ErrorCode.RESOURCE_NOT_FOUND, "Organization or department not found.", details={"resource_id": missing_id})


@router.get("/agents", response_model=list[AgentNode])
async def list_agents(principal: PrincipalDependency, org_id: str | None = None, department_id: str | None = None, manager_agent_id: str | None = None) -> list[AgentNode]:
    enforce_scope(principal, "security:manage")
    return organization_store.list_agents(org_id=org_id, department_id=department_id, manager_agent_id=manager_agent_id)


@router.get("/agents/{agent_id}", response_model=AgentNode)
async def get_agent(agent_id: str, principal: PrincipalDependency) -> AgentNode:
    enforce_scope(principal, "security:manage")
    agent = organization_store.get_agent(agent_id)
    if agent is None:
        raise api_error(404, ErrorCode.RESOURCE_NOT_FOUND, "Agent not found.", details={"resource_type": "agent", "resource_id": agent_id})
    return agent


@router.get("/agents/{agent_id}/memory")
async def get_agent_memory(agent_id: str, principal: PrincipalDependency, memory: MemoryDependency) -> dict[str, object]:
    enforce_scope(principal, "memory:read")
    agent = organization_store.get_agent(agent_id)
    if agent is None:
        raise api_error(404, ErrorCode.RESOURCE_NOT_FOUND, "Agent not found.", details={"resource_type": "agent", "resource_id": agent_id})
    summary = memory.agent_summary(agent_id) if hasattr(memory, "agent_summary") else None
    if summary is None:
        return {"agent_id": agent_id, "summary": None, "items": [], "layers": []}
    items = memory.agent_items(agent_id) if hasattr(memory, "agent_items") else []
    layers = memory.agent_memory_layers(agent_id) if hasattr(memory, "agent_memory_layers") else []
    return {"agent_id": agent_id, "summary": summary, "items": [item.model_dump(mode="json") if hasattr(item, "model_dump") else item for item in items], "layers": layers}


@router.put("/agents/{agent_id}", response_model=AgentNode)
async def update_agent(agent_id: str, request: AgentUpdateRequest, principal: PrincipalDependency) -> AgentNode:
    enforce_scope(principal, "security:manage")
    agent = organization_store.get_agent(agent_id)
    if agent is None:
        raise api_error(404, ErrorCode.RESOURCE_NOT_FOUND, "Agent not found.", details={"resource_type": "agent", "resource_id": agent_id})
    if request.name is not None:
        agent.name = request.name
    if request.role is not None:
        agent.role = request.role
    if request.title is not None:
        agent.title = request.title
    if request.manager_agent_id is not None:
        agent.manager_agent_id = request.manager_agent_id
    if request.capabilities is not None:
        agent.capabilities = request.capabilities
    if request.team_size_limit is not None:
        agent.team_size_limit = request.team_size_limit
    if request.feishu_user_id is not None:
        agent.memory_scope["feishu_user_id"] = request.feishu_user_id
    if request.feishu_open_id is not None:
        agent.memory_scope["feishu_open_id"] = request.feishu_open_id
    if request.feishu_union_id is not None:
        agent.memory_scope["feishu_union_id"] = request.feishu_union_id
    if request.feishu_email is not None:
        agent.memory_scope["feishu_email"] = request.feishu_email
    if request.feishu_enabled is not None:
        agent.memory_scope["feishu_enabled"] = str(request.feishu_enabled)
    return agent


@router.post("/agents/{agent_id}/children/{child_agent_id}", response_model=AgentNode)
async def attach_child_agent(agent_id: str, child_agent_id: str, principal: PrincipalDependency) -> AgentNode:
    enforce_scope(principal, "security:manage")
    agent = organization_store.get_agent(agent_id)
    child = organization_store.get_agent(child_agent_id)
    if agent is None:
        raise api_error(404, ErrorCode.RESOURCE_NOT_FOUND, "Agent not found.", details={"resource_type": "agent", "resource_id": agent_id})
    if child is None:
        raise api_error(404, ErrorCode.RESOURCE_NOT_FOUND, "Child agent not found.", details={"resource_type": "agent", "resource_id": child_agent_id})
    child.manager_agent_id = agent_id
    if child_agent_id not in agent.child_agent_ids and len(agent.child_agent_ids) < agent.team_size_limit:
        agent.child_agent_ids.append(child_agent_id)
    return agent


@router.delete("/agents/{agent_id}")
async def delete_agent(agent_id: str, principal: PrincipalDependency) -> dict[str, bool]:
    enforce_scope(principal, "security:manage")
    agent = organization_store.get_agent(agent_id)
    if agent is None:
        raise api_error(404, ErrorCode.RESOURCE_NOT_FOUND, "Agent not found.", details={"resource_type": "agent", "resource_id": agent_id})
    agent.status = "inactive"
    return {"deleted": True}
