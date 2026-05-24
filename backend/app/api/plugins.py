from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field

from backend.app.api.errors import api_error
from backend.app.core.plugins import plugin_store
from backend.app.core.security import Principal
from backend.app.dependencies import enforce_scope, get_current_principal

router = APIRouter(prefix="/api/v1/plugins", tags=["plugins"])
PrincipalDependency = Annotated[Principal, Depends(get_current_principal)]


class PluginRecord(BaseModel):
    id: str
    name: str
    version: str = "v1"
    description: str = ""
    status: str = "inactive"
    capabilities: list[str] = Field(default_factory=list)
    manifest: dict[str, object] = Field(default_factory=dict)
    sandbox: str = "isolated"
    allowed_actions: list[str] = Field(default_factory=lambda: ["read", "execute"])
    requires_approval: bool = False
    installed: bool = False
    install_path: str | None = None


class PluginCreateRequest(BaseModel):
    name: str = Field(..., min_length=1, max_length=200)
    version: str = Field(default="v1", max_length=80)
    description: str = Field(default="", max_length=2000)
    capabilities: list[str] = Field(default_factory=list)
    manifest: dict[str, object] = Field(default_factory=dict)
    sandbox: str = Field(default="isolated", max_length=80)
    allowed_actions: list[str] = Field(default_factory=lambda: ["read", "execute"])
    requires_approval: bool = False
    installed: bool = False
    install_path: str | None = None


class PluginUpdateRequest(BaseModel):
    name: str | None = None
    version: str | None = None
    description: str | None = None
    capabilities: list[str] | None = None
    manifest: dict[str, object] | None = None
    status: str | None = None
    sandbox: str | None = None
    allowed_actions: list[str] | None = None
    requires_approval: bool | None = None
    installed: bool | None = None
    install_path: str | None = None


@router.get("", response_model=list[PluginRecord])
async def list_plugins(principal: PrincipalDependency) -> list[PluginRecord]:
    enforce_scope(principal, "tools:read")
    return [PluginRecord.model_validate(item.model_dump(mode="json")) for item in plugin_store.list()]


@router.post("", response_model=PluginRecord)
async def create_plugin(request: PluginCreateRequest, principal: PrincipalDependency) -> PluginRecord:
    enforce_scope(principal, "tools:read")
    record = plugin_store.register(
        name=request.name,
        version=request.version,
        description=request.description,
        capabilities=request.capabilities,
        manifest=request.manifest,
        sandbox=request.sandbox,
        allowed_actions=request.allowed_actions,
        requires_approval=request.requires_approval,
        installed=request.installed,
        install_path=request.install_path,
    )
    return PluginRecord.model_validate(record.model_dump(mode="json"))


@router.get("/{plugin_id}", response_model=PluginRecord)
async def get_plugin(plugin_id: str, principal: PrincipalDependency) -> PluginRecord:
    enforce_scope(principal, "tools:read")
    record = plugin_store.get(plugin_id)
    if record is None:
        raise api_error(404, "RESOURCE_NOT_FOUND", "Plugin not found.")
    return PluginRecord.model_validate(record.model_dump(mode="json"))


@router.put("/{plugin_id}", response_model=PluginRecord)
async def update_plugin(plugin_id: str, request: PluginUpdateRequest, principal: PrincipalDependency) -> PluginRecord:
    enforce_scope(principal, "tools:read")
    record = plugin_store.update(
        plugin_id,
        name=request.name,
        version=request.version,
        description=request.description,
        capabilities=request.capabilities,
        manifest=request.manifest,
        status=request.status,
        sandbox=request.sandbox,
        allowed_actions=request.allowed_actions,
        requires_approval=request.requires_approval,
        installed=request.installed,
        install_path=request.install_path,
    )
    if record is None:
        raise api_error(404, "RESOURCE_NOT_FOUND", "Plugin not found.")
    return PluginRecord.model_validate(record.model_dump(mode="json"))


@router.post("/{plugin_id}/install", response_model=PluginRecord)
async def install_plugin(plugin_id: str, request: dict[str, object] | None = None, principal: PrincipalDependency = None) -> PluginRecord:
    enforce_scope(principal, "tools:read")
    request = request or {}
    install_path = request.get("install_path") if isinstance(request.get("install_path"), str) else None
    record = plugin_store.install(plugin_id, install_path=install_path)
    if record is None:
        raise api_error(404, "RESOURCE_NOT_FOUND", "Plugin not found.")
    return PluginRecord.model_validate(record.model_dump(mode="json"))


@router.post("/{plugin_id}/enable", response_model=PluginRecord)
async def enable_plugin(plugin_id: str, principal: PrincipalDependency) -> PluginRecord:
    enforce_scope(principal, "tools:read")
    record = plugin_store.enable(plugin_id)
    if record is None:
        raise api_error(404, "RESOURCE_NOT_FOUND", "Plugin not found.")
    return PluginRecord.model_validate(record.model_dump(mode="json"))


@router.post("/{plugin_id}/disable", response_model=PluginRecord)
async def disable_plugin(plugin_id: str, principal: PrincipalDependency) -> PluginRecord:
    enforce_scope(principal, "tools:read")
    record = plugin_store.disable(plugin_id)
    if record is None:
        raise api_error(404, "RESOURCE_NOT_FOUND", "Plugin not found.")
    return PluginRecord.model_validate(record.model_dump(mode="json"))


@router.post("/{plugin_id}/uninstall", response_model=PluginRecord)
async def uninstall_plugin(plugin_id: str, principal: PrincipalDependency) -> PluginRecord:
    enforce_scope(principal, "tools:read")
    record = plugin_store.uninstall(plugin_id)
    if record is None:
        raise api_error(404, "RESOURCE_NOT_FOUND", "Plugin not found.")
    return PluginRecord.model_validate(record.model_dump(mode="json"))


@router.get("/{plugin_id}/executions")
async def list_plugin_executions(plugin_id: str, principal: PrincipalDependency) -> list[dict[str, object]]:
    enforce_scope(principal, "tools:read")
    if plugin_store.get(plugin_id) is None:
        raise api_error(404, "RESOURCE_NOT_FOUND", "Plugin not found.")
    return [item.model_dump(mode="json") for item in plugin_store.list_executions(plugin_id)]


@router.post("/{plugin_id}/executions")
async def record_plugin_execution(
    plugin_id: str,
    request: dict[str, object] | None = None,
    principal: PrincipalDependency = None,
) -> dict[str, object]:
    enforce_scope(principal, "tools:read")
    if plugin_store.get(plugin_id) is None:
        raise api_error(404, "RESOURCE_NOT_FOUND", "Plugin not found.")
    request = request or {}
    action = str(request.get("action", "plugin.execute"))
    if not plugin_store.can_execute(plugin_id, action):
        raise api_error(403, "AUTHORIZATION_FAILED", "Plugin action is not allowed.")
    if plugin_store.needs_approval(plugin_id) and not bool(request.get("approved", False)):
        raise api_error(403, "AUTHORIZATION_FAILED", "Plugin execution requires approval.")
    execution = plugin_store.record_execution(
        plugin_id,
        action=action,
        success=bool(request.get("success", True)),
        output=dict(request.get("output", {}) or {}),
        error=request.get("error") if isinstance(request.get("error"), str) else None,
    )
    return execution.model_dump(mode="json")


@router.delete("/{plugin_id}")
async def delete_plugin(plugin_id: str, principal: PrincipalDependency) -> dict[str, bool]:
    enforce_scope(principal, "tools:read")
    if not plugin_store.delete(plugin_id):
        raise api_error(404, "RESOURCE_NOT_FOUND", "Plugin not found.")
    return {"deleted": True}
