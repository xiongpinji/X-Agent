"""P1-10 "1+1" 最后接线的回归测试：运行时工具注册表单一实例。

背景（2026-08-04 修复）：此前 main.py startup 与 dependencies.get_agent()
各建一套 ToolRegistry —— 技能注册和 MCP 桥接写进 app.state 那套，
而 agent 实际使用另一套，技能/MCP 工具永远进不了主循环。
修复后统一为 dependencies.get_runtime_tool_registry() 单例。
"""

from backend.app.dependencies import get_agent, get_runtime_tool_registry, get_tool_catalog


def test_agent_uses_shared_runtime_registry() -> None:
    """AgentLoop 的工具注册表必须是 dependencies 持有的唯一实例。"""
    assert get_agent().tools is get_runtime_tool_registry()


def test_runtime_registry_is_singleton() -> None:
    """get_runtime_tool_registry 多次调用返回同一实例（lru_cache 单例）。"""
    assert get_runtime_tool_registry() is get_runtime_tool_registry()


def test_tool_catalog_is_singleton() -> None:
    """get_tool_catalog 多次调用返回同一实例（P1-10 实例级单例化）。"""
    assert get_tool_catalog() is get_tool_catalog()


def test_container_shares_tool_catalog_singleton() -> None:
    """container 的 tool_registry 必须是 dependencies 持有的唯一目录实例。"""
    from backend.app.container import get_container

    assert get_container().tool_registry is get_tool_catalog()


def test_legacy_management_surfaces_share_tool_catalog() -> None:
    """旧管理面（ToolExecutor / ToolManager）默认共享目录单例。"""
    from backend.app.core.tool_executor import ToolExecutor
    from backend.app.core.tool_manager import ToolManager

    assert ToolExecutor().registry is get_tool_catalog()
    assert ToolManager().registry is get_tool_catalog()
    # 显式 storage_path 仍允许隔离实例（测试/离线工具场景）
    import tempfile
    from pathlib import Path

    with tempfile.TemporaryDirectory() as tmp:
        isolated = ToolManager(Path(tmp))
        assert isolated.registry is not get_tool_catalog()
