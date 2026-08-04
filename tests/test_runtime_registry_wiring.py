"""P1-10 "1+1" 最后接线的回归测试：运行时工具注册表单一实例。

背景（2026-08-04 修复）：此前 main.py startup 与 dependencies.get_agent()
各建一套 ToolRegistry —— 技能注册和 MCP 桥接写进 app.state 那套，
而 agent 实际使用另一套，技能/MCP 工具永远进不了主循环。
修复后统一为 dependencies.get_runtime_tool_registry() 单例。
"""

from backend.app.dependencies import get_agent, get_runtime_tool_registry


def test_agent_uses_shared_runtime_registry() -> None:
    """AgentLoop 的工具注册表必须是 dependencies 持有的唯一实例。"""
    assert get_agent().tools is get_runtime_tool_registry()


def test_runtime_registry_is_singleton() -> None:
    """get_runtime_tool_registry 多次调用返回同一实例（lru_cache 单例）。"""
    assert get_runtime_tool_registry() is get_runtime_tool_registry()
