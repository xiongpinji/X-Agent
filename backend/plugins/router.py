"""插件系统 API 路由（可挂载，未挂载）

P1-12 交付物：集成波接线时仅需::

    from backend.plugins.router import router as plugin_runtime_router
    app.include_router(plugin_runtime_router)

路由基于 backend.plugins.runtime.PluginRuntime（MCP 插件框架接线），
scope 使用 RBAC 中真实存在的 tools:read / tools:*。
"""

from __future__ import annotations

import logging
from typing import Annotated, Any

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from backend.app.core.security import Principal
from backend.app.dependencies import get_current_principal, enforce_scope

from .runtime import get_plugin_runtime

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1/plugins", tags=["plugins"])

PrincipalDependency = Annotated[Principal, Depends(get_current_principal)]

SCOPE_PLUGIN_READ = "tools:read"
SCOPE_PLUGIN_MANAGE = "tools:*"


class InspectRequest(BaseModel):
    """进程内入口检查请求"""
    config: dict[str, Any] = Field(default_factory=dict)


@router.get("")
async def list_plugins(principal: PrincipalDependency) -> dict[str, Any]:
    """列出插件目录下所有插件及其显式状态"""
    enforce_scope(principal, SCOPE_PLUGIN_READ)
    runtime = get_plugin_runtime()
    infos = runtime.scan()
    return {
        "success": True,
        "plugins_dir": str(runtime.plugins_dir),
        "count": len(infos),
        "plugins": [i.to_dict() for i in infos],
    }


@router.post("/load-all")
async def load_all_plugins(principal: PrincipalDependency) -> dict[str, Any]:
    """加载所有可加载插件（逐项结果显式返回，失败不静默）"""
    enforce_scope(principal, SCOPE_PLUGIN_MANAGE)
    runtime = get_plugin_runtime()
    results = runtime.load_all()
    return {
        "success": True,
        "loaded": runtime.list_loaded(),
        "results": [r.to_dict() for r in results],
    }


@router.get("/{name}")
async def get_plugin(name: str, principal: PrincipalDependency) -> dict[str, Any]:
    """获取单个插件状态"""
    enforce_scope(principal, SCOPE_PLUGIN_READ)
    runtime = get_plugin_runtime()
    for info in runtime.scan():
        if info.name == name:
            return {"success": True, "plugin": info.to_dict()}
    raise HTTPException(status_code=404, detail=f"Plugin not found: {name}")


@router.post("/{name}/load")
async def load_plugin(name: str, principal: PrincipalDependency) -> dict[str, Any]:
    """加载插件（仅 mcp 格式且校验通过）"""
    enforce_scope(principal, SCOPE_PLUGIN_MANAGE)
    runtime = get_plugin_runtime()
    info = runtime.load(name)
    if info.status != "loaded":
        raise HTTPException(
            status_code=400,
            detail={"message": f"Plugin not loadable: {name}", "plugin": info.to_dict()},
        )
    return {"success": True, "plugin": info.to_dict()}


@router.post("/{name}/unload")
async def unload_plugin(name: str, principal: PrincipalDependency) -> dict[str, Any]:
    """卸载插件"""
    enforce_scope(principal, SCOPE_PLUGIN_MANAGE)
    runtime = get_plugin_runtime()
    if not runtime.unload(name):
        raise HTTPException(status_code=404, detail=f"Plugin not loaded: {name}")
    return {"success": True, "message": f"Plugin unloaded: {name}"}


@router.post("/{name}/inspect")
async def inspect_plugin(
    name: str,
    principal: PrincipalDependency,
    request: InspectRequest | None = None,
) -> dict[str, Any]:
    """进程内验证插件入口：导入模块 + 实例化入口类 + 比对声明工具"""
    enforce_scope(principal, SCOPE_PLUGIN_MANAGE)
    runtime = get_plugin_runtime()
    result = runtime.inspect_entrypoint(name, config=(request.config if request else None))
    if "manifest load failed" in (result.get("error") or ""):
        raise HTTPException(status_code=404, detail=result["error"])
    return {"success": result.get("ok", False), "inspection": result}


__all__ = ["router"]
