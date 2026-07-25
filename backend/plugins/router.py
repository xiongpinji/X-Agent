"""插件系统 API 路由（已挂载至主 app）

P1-12 交付物：插件运行时全接线。
路由基于 backend.plugins.runtime.PluginRuntime（MCP 插件框架接线），
scope 使用 RBAC 中真实存在的 tools:read / tools:*。

生命周期端点：
- GET  /api/v1/plugins                — 列出所有插件
- POST /api/v1/plugins/{name}/enable  — 激活插件（加载 + 注册工具）
- POST /api/v1/plugins/{name}/disable — 停用插件（卸载 + 移除工具）
- GET  /api/v1/plugins/{name}/config  — 获取插件配置 schema
"""

from __future__ import annotations

import logging
from typing import Annotated, Any

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from backend.app.core.security import Principal
from backend.app.dependencies import enforce_scope, get_current_principal

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


@router.get("/health")
async def plugin_health_check(principal: PrincipalDependency) -> dict[str, Any]:
    """插件系统健康检查。

    P1-12: 返回插件运行时状态、已加载插件数、可加载插件数、
    ToolRegistry 桥接状态等信息。
    """
    enforce_scope(principal, SCOPE_PLUGIN_READ)
    runtime = get_plugin_runtime()

    # 扫描插件目录
    all_plugins = runtime.scan(refresh=True)
    loaded = runtime.list_loaded()
    loadable = [p for p in all_plugins if p.status == "loadable"]
    invalid = [p for p in all_plugins if p.status == "invalid"]

    # 检查 ToolRegistry 桥接状态
    registry = _get_runtime_tool_registry()
    registry_available = registry is not None
    registered_plugin_tools: list[str] = []
    if registry_available:
        try:
            from backend.app.core.plugin_agent_adapter import PLUGIN_TOOL_PREFIX

            tools_dict = getattr(registry, "_tools", {})
            registered_plugin_tools = [
                name for name in tools_dict if name.startswith(PLUGIN_TOOL_PREFIX)
            ]
        except Exception:
            pass

    # 总体健康状态
    overall_status = "healthy"
    if not runtime.plugins_dir.is_dir():
        overall_status = "unhealthy"
    elif invalid:
        overall_status = "degraded"

    return {
        "status": overall_status,
        "plugins_dir": str(runtime.plugins_dir),
        "plugins_dir_exists": runtime.plugins_dir.is_dir(),
        "total_plugins": len(all_plugins),
        "loaded_count": len(loaded),
        "loadable_count": len(loadable),
        "invalid_count": len(invalid),
        "loaded_plugins": loaded,
        "invalid_plugins": [p.name for p in invalid],
        "tool_registry_available": registry_available,
        "registered_plugin_tools_count": len(registered_plugin_tools),
        "registered_plugin_tools": registered_plugin_tools,
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


@router.post("/{name}/enable")
async def enable_plugin(name: str, principal: PrincipalDependency) -> dict[str, Any]:
    """激活插件：加载 + 将工具注册进 AgentLoop ToolRegistry"""
    enforce_scope(principal, SCOPE_PLUGIN_MANAGE)
    runtime = get_plugin_runtime()

    # 加载插件
    info = runtime.load(name)
    if info.status != "loaded":
        raise HTTPException(
            status_code=400,
            detail={"message": f"Plugin cannot be enabled: {name}", "plugin": info.to_dict()},
        )

    # 注册工具进 ToolRegistry
    registered_tools: list[str] = []
    try:
        from backend.app.core.plugin_agent_adapter import register_plugins_into_tool_registry

        registry = _get_runtime_tool_registry()
        if registry is not None:
            all_registered = register_plugins_into_tool_registry(registry, runtime=runtime)
            # 只保留属于本插件的工具名
            prefix = f"plugin__{name.replace('-', '_')}__"
            registered_tools = [t for t in all_registered if t.startswith(prefix)]
    except Exception as e:
        logger.warning(f"P1-12: Plugin '{name}' loaded but tool registration failed: {e}")

    return {
        "success": True,
        "plugin": info.to_dict(),
        "registered_tools": registered_tools,
    }


@router.post("/{name}/disable")
async def disable_plugin(name: str, principal: PrincipalDependency) -> dict[str, Any]:
    """停用插件：从 ToolRegistry 移除工具 + 卸载插件"""
    enforce_scope(principal, SCOPE_PLUGIN_MANAGE)
    runtime = get_plugin_runtime()

    # 从 ToolRegistry 移除工具
    removed_tools: list[str] = []
    try:
        from backend.app.core.plugin_agent_adapter import unregister_plugin_tools

        registry = _get_runtime_tool_registry()
        if registry is not None:
            removed_tools = unregister_plugin_tools(registry, name)
    except Exception as e:
        logger.warning(f"P1-12: Failed to remove tools for plugin '{name}': {e}")

    # 卸载插件
    if not runtime.unload(name):
        raise HTTPException(status_code=404, detail=f"Plugin not loaded: {name}")

    return {
        "success": True,
        "message": f"Plugin disabled: {name}",
        "removed_tools": removed_tools,
    }


@router.get("/{name}/config")
async def get_plugin_config(name: str, principal: PrincipalDependency) -> dict[str, Any]:
    """获取插件配置 schema（来自 manifest.configuration）"""
    enforce_scope(principal, SCOPE_PLUGIN_READ)
    runtime = get_plugin_runtime()

    # 先尝试从已加载插件获取
    plugin = runtime.get_loaded(name)
    if plugin and plugin.manifest:
        return {
            "success": True,
            "plugin": name,
            "configuration": plugin.manifest.configuration,
            "current_config": plugin.config,
        }

    # 未加载时从 manifest 文件读取
    from backend.app.core.mcp_plugin_adapter import MCPPluginAdapter

    adapter = MCPPluginAdapter(runtime.plugins_dir)
    plugin_path = runtime.plugins_dir / name
    try:
        manifest = adapter.load_manifest(plugin_path)
    except Exception:
        raise HTTPException(status_code=404, detail=f"Plugin not found or no manifest: {name}")

    return {
        "success": True,
        "plugin": name,
        "configuration": manifest.configuration,
        "current_config": {},
    }


def _get_runtime_tool_registry() -> Any | None:
    """获取全局运行时 ToolRegistry（通过 agent 单例）"""
    try:
        from backend.app.dependencies import get_agent
        agent = get_agent()
        return agent.tools
    except Exception:
        return None


__all__ = ["router"]
