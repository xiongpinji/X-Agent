"""X-Agent 插件运行时（backend.plugins）

P1-12 交付物：基于现存资产接线的插件系统
- 框架：backend.app.core.mcp_plugin_adapter（存活代码，未归档）
- 插件目录：项目根 plugins/（3 个 MCP 插件可直接加载；
  3 个旧格式插件显式标记 legacy_unsupported，不静默、不假装可用）

对外导出 PluginRuntime 与 router（router 达到可挂载状态，未挂载，
由集成波决定挂载时机）。
"""

from .runtime import PluginRuntime, PluginInfo, get_plugin_runtime

__all__ = ["PluginRuntime", "PluginInfo", "get_plugin_runtime"]
