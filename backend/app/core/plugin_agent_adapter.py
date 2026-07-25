"""插件 → AgentLoop 工具注册适配器（主循环消费接口）

P1-12 交付物：把 PluginRuntime 中已加载的 MCP 插件桥接为 AgentLoop 可消费的工具。

集成波接线方式（本模块不自作主张接线，仅供调用）::

    from backend.app.core.plugin_agent_adapter import register_plugins_into_tool_registry

    # 在构建 AgentLoop 的 ToolRegistry 之后、启动主循环之前：
    registered_names = register_plugins_into_tool_registry(tool_registry)
    # 此后 AgentLoop 即可通过 "plugin__<plugin-name>__<tool-name>" 工具名调用插件工具。

设计要点：
- 工具名统一加 ``plugin__<plugin>__`` 前缀，避免与内置工具/技能冲突；
- handler 签名为 ``async (**kwargs) -> dict``，与 ToolRegistry 的
  ``await tool.handler(**arguments)`` 调用约定一致；
- 进程内实例化插件入口类，直接调用方法（不走 MCP 子进程协议）；
- 执行失败返回 ``{"success": False, "error": ...}``，显式失败，不静默；
- 插件入口类实例化需要配置（如 allowed_paths），缺省配置从 manifest
  configuration 的 default 值构造；必填项无 default 时该插件跳过注册。
"""

from __future__ import annotations

import importlib.util
import logging
import sys
import time
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)

# 工具名前缀
PLUGIN_TOOL_PREFIX = "plugin__"

# 默认风险等级（插件工具默认 MEDIUM，因为插件可执行文件/网络操作）
DEFAULT_PLUGIN_RISK_LEVEL = "MEDIUM"
DEFAULT_PLUGIN_REQUIRED_SCOPE = "tools:execute"


def plugin_tool_name(plugin_name: str, tool_name: str) -> str:
    """构造注册进 ToolRegistry 的工具名"""
    safe_plugin = plugin_name.replace("-", "_")
    safe_tool = tool_name.replace("-", "_")
    return f"{PLUGIN_TOOL_PREFIX}{safe_plugin}__{safe_tool}"


def plugin_name_from_tool(tool_name: str) -> str | None:
    """从注册工具名反解插件名"""
    if not tool_name.startswith(PLUGIN_TOOL_PREFIX):
        return None
    rest = tool_name[len(PLUGIN_TOOL_PREFIX):]
    parts = rest.split("__", 1)
    return parts[0] if parts else None


def _instantiate_plugin_entry(
    plugin_dir: Path,
    module_name_str: str,
    class_name: str,
    config: dict[str, Any],
) -> Any:
    """进程内导入并实例化插件入口类"""
    module_file = plugin_dir / f"{module_name_str.replace('.', '/')}.py"
    if not module_file.exists():
        raise FileNotFoundError(f"Entry module not found: {module_file}")

    mod_name = f"xagent_plugin_bridge.{plugin_dir.name.replace('-', '_')}"
    spec = importlib.util.spec_from_file_location(mod_name, module_file)
    if spec is None or spec.loader is None:
        raise ImportError(f"Cannot create module spec for {module_file}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[mod_name] = module
    try:
        spec.loader.exec_module(module)
    finally:
        sys.modules.pop(mod_name, None)

    cls = getattr(module, class_name, None)
    if cls is None:
        raise AttributeError(f"Entry class '{class_name}' not found in {module_file.name}")

    return cls(config)


def _default_config_from_manifest(manifest: Any) -> dict[str, Any]:
    """从 manifest configuration 构造默认配置（仅取有 default 的项）"""
    config: dict[str, Any] = {}
    for key, spec in manifest.configuration.items():
        if isinstance(spec, dict) and "default" in spec:
            config[key] = spec["default"]
    return config


def _has_required_config_without_default(manifest: Any) -> list[str]:
    """返回必填但无 default 的配置项列表"""
    missing = []
    for key, spec in manifest.configuration.items():
        if isinstance(spec, dict) and spec.get("required") and "default" not in spec:
            missing.append(key)
    return missing


def build_plugin_tool_handler(
    instance: Any,
    tool_name: str,
    plugin_name: str,
) -> Any:
    """构造单个插件工具的 async handler"""

    async def _handler(**kwargs: Any) -> dict[str, Any]:
        started = time.perf_counter()
        method = getattr(instance, tool_name, None)
        if method is None or not callable(method):
            return {
                "success": False,
                "error": f"Plugin '{plugin_name}' has no callable method '{tool_name}'",
            }
        try:
            import asyncio
            if asyncio.iscoroutinefunction(method):
                result = await method(**kwargs)
            else:
                result = method(**kwargs)
            return {
                "success": True,
                "data": result,
                "execution_time": time.perf_counter() - started,
            }
        except Exception as e:
            logger.error(f"Plugin tool '{plugin_name}/{tool_name}' raised: {e}", exc_info=True)
            return {
                "success": False,
                "error": f"Plugin tool execution error: {e}",
                "execution_time": time.perf_counter() - started,
            }

    _handler.__name__ = f"plugin_handler_{plugin_name.replace('-', '_')}_{tool_name.replace('-', '_')}"
    return _handler


def register_plugins_into_tool_registry(
    tool_registry: Any,
    runtime: Any | None = None,
    plugin_configs: dict[str, dict[str, Any]] | None = None,
) -> list[str]:
    """把所有已加载插件的工具注册进 AgentLoop 的 ToolRegistry（集成波入口）。

    Args:
        tool_registry: backend.app.core.tools.ToolRegistry 实例
        runtime: PluginRuntime 实例（缺省使用全局 get_plugin_runtime()）
        plugin_configs: 每个插件的额外配置覆盖 {plugin_name: {key: value}}

    Returns:
        注册成功的工具名列表（"plugin__<plugin>__<tool>"）。
        配置不满足的插件跳过注册（显式日志，不静默）。
    """
    from backend.app.core.tools import RiskLevel
    from backend.plugins.runtime import get_plugin_runtime

    runtime = runtime or get_plugin_runtime()
    plugin_configs = plugin_configs or {}

    # 确保插件已加载
    if not runtime.list_loaded():
        runtime.load_all()

    registered: list[str] = []

    for dir_name in runtime.list_loaded():
        plugin = runtime.get_loaded(dir_name)
        if plugin is None or plugin.manifest is None:
            continue

        manifest = plugin.manifest

        # 检查必填配置
        missing = _has_required_config_without_default(manifest)
        config = _default_config_from_manifest(manifest)
        # 合并用户提供的配置
        if dir_name in plugin_configs:
            config.update(plugin_configs[dir_name])

        if missing and not all(k in config for k in missing):
            still_missing = [k for k in missing if k not in config]
            logger.warning(
                "P1-12: Plugin '%s' skipped — required config missing: %s",
                dir_name, still_missing,
            )
            continue

        # 实例化插件入口类
        entry = manifest.entry_point
        if entry.type != "python":
            logger.info("P1-12: Plugin '%s' skipped — entry type '%s' not supported for in-process bridge", dir_name, entry.type)
            continue

        try:
            instance = _instantiate_plugin_entry(
                Path(plugin.plugin_path),
                entry.module,
                entry.class_name,
                config,
            )
        except Exception as e:
            logger.warning("P1-12: Plugin '%s' instantiation failed: %s", dir_name, e)
            continue

        # 注册每个声明的工具
        for tool_def in manifest.tools:
            tool_name = tool_def.get("name")
            if not tool_name:
                continue
            if not callable(getattr(instance, tool_name, None)):
                logger.warning(
                    "P1-12: Plugin '%s' tool '%s' — method not found on instance, skipping",
                    dir_name, tool_name,
                )
                continue

            reg_name = plugin_tool_name(dir_name, tool_name)
            handler = build_plugin_tool_handler(instance, tool_name, dir_name)
            description = tool_def.get("description_zh") or tool_def.get("description") or f"Plugin {dir_name}: {tool_name}"
            parameters_schema = tool_def.get("input_schema")

            tool_registry.register(
                reg_name,
                description=description,
                handler=handler,
                risk_level=RiskLevel[DEFAULT_PLUGIN_RISK_LEVEL],
                required_scope=DEFAULT_PLUGIN_REQUIRED_SCOPE,
                parameters_schema=parameters_schema,
            )
            registered.append(reg_name)
            logger.info("P1-12: Registered plugin tool: %s", reg_name)

    return registered


def unregister_plugin_tools(tool_registry: Any, plugin_name: str) -> list[str]:
    """从 ToolRegistry 中移除指定插件的所有工具（用于 disable）。

    Returns:
        被移除的工具名列表。
    """
    prefix = f"{PLUGIN_TOOL_PREFIX}{plugin_name.replace('-', '_')}__"
    removed = []
    # ToolRegistry._tools 是内部 dict
    tools_dict = getattr(tool_registry, "_tools", None)
    if tools_dict is None:
        return removed
    to_remove = [name for name in tools_dict if name.startswith(prefix)]
    for name in to_remove:
        del tools_dict[name]
        removed.append(name)
    return removed


__all__ = [
    "DEFAULT_PLUGIN_REQUIRED_SCOPE",
    "DEFAULT_PLUGIN_RISK_LEVEL",
    "PLUGIN_TOOL_PREFIX",
    "build_plugin_tool_handler",
    "plugin_name_from_tool",
    "plugin_tool_name",
    "register_plugins_into_tool_registry",
    "unregister_plugin_tools",
]
