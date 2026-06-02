"""
main.py MCP 集成的单元测试

验证 FastAPI 应用的 startup/shutdown 生命周期中 MCP 管理器的初始化和清理行为。
重点测试边界条件：无配置、配置错误、部分成功、完整成功。
"""

from __future__ import annotations

import os
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
import pytest_asyncio

from backend.app.core.tool_registry import ToolRegistry
from backend.app.core.mcp.manager import (
    initialize_mcp_manager,
    shutdown_mcp_manager,
    get_mcp_manager,
)


@pytest_asyncio.fixture(autouse=True)
async def reset_mcp_manager():
    """每个测试前后重置全局 MCP 管理器"""
    # 测试前清理
    await shutdown_mcp_manager()
    yield
    # 测试后清理
    await shutdown_mcp_manager()


@pytest_asyncio.fixture
def tool_registry():
    """工具注册表 fixture"""
    return ToolRegistry()


class TestMCPStartupLifecycle:
    """测试 main.py startup_event 中的 MCP 初始化路径"""

    @pytest.mark.asyncio
    async def test_no_config_graceful_skip(self, tool_registry):
        """无配置时优雅跳过（fail-open），返回 None 且不抛异常"""
        # 指定一个不存在的配置路径
        manager = await initialize_mcp_manager(
            tool_registry=tool_registry,
            config_path="nonexistent_path.yaml"
        )

        # 断言：返回 None（初始化被跳过）
        assert manager is None
        # 断言：全局管理器未设置
        assert get_mcp_manager() is None

    @pytest.mark.asyncio
    async def test_empty_config_graceful_skip(self, tool_registry, tmp_path):
        """配置文件存在但无 mcp_servers 时优雅跳过"""
        # 创建空配置文件
        empty_config = tmp_path / "empty_mcp.yaml"
        empty_config.write_text("# 空配置\nglobal:\n  log_level: info\n")

        manager = await initialize_mcp_manager(
            tool_registry=tool_registry,
            config_path=str(empty_config)
        )

        assert manager is None
        assert get_mcp_manager() is None

    @pytest.mark.asyncio
    async def test_all_servers_fail_returns_none(self, tool_registry, tmp_path):
        """所有服务器连接失败时返回 None（不阻塞启动）"""
        # 创建配置：一个会失败的服务器（无效 URL）
        fail_config = tmp_path / "fail_mcp.yaml"
        fail_config.write_text("""
mcp_servers:
  - name: invalid_server
    url: http://nonexistent-host-12345.invalid:9999/mcp
    enabled: true
    timeout: 0.5
    max_retries: 1
""")

        manager = await initialize_mcp_manager(
            tool_registry=tool_registry,
            config_path=str(fail_config)
        )

        # 所有服务器失败 → 返回 None（fail-open）
        assert manager is None
        assert get_mcp_manager() is None

    @pytest.mark.asyncio
    async def test_already_initialized_returns_existing(self, tool_registry):
        """重复初始化时返回已有实例（幂等）"""
        # 第一次初始化（无配置 → None）
        first = await initialize_mcp_manager(
            tool_registry=tool_registry,
            config_path="nonexistent.yaml"
        )
        assert first is None

        # 模拟已有管理器的情况
        with patch("backend.app.core.mcp.manager._mcp_manager", new=MagicMock()):
            second = await initialize_mcp_manager(
                tool_registry=tool_registry,
                config_path="any.yaml"
            )
            # 应返回已有实例（mock），不重新初始化
            assert second is not None


class TestMCPShutdownLifecycle:
    """测试 main.py shutdown_event 中的 MCP 清理路径"""

    @pytest.mark.asyncio
    async def test_shutdown_without_init_noop(self):
        """未初始化时调用 shutdown 为空操作（不崩溃）"""
        # 确保未初始化
        assert get_mcp_manager() is None
        # 调用 shutdown 不应抛异常
        await shutdown_mcp_manager()
        assert get_mcp_manager() is None

    @pytest.mark.asyncio
    async def test_shutdown_clears_global_manager(self, tool_registry):
        """shutdown 后全局管理器被清空"""
        # 模拟一个已初始化的管理器
        mock_manager = MagicMock()
        mock_manager.shutdown = AsyncMock()

        with patch("backend.app.core.mcp.manager._mcp_manager", new=mock_manager):
            assert get_mcp_manager() is mock_manager
            await shutdown_mcp_manager()
            # 断言：shutdown 被调用
            mock_manager.shutdown.assert_called_once()

        # 断言：全局管理器已清空
        assert get_mcp_manager() is None


class TestMainAppIntegration:
    """测试 main.py 的 app 实例集成（通过 TestClient）"""

    @pytest.mark.asyncio
    async def test_testclient_triggers_lifecycle(self):
        """TestClient 的 with 块会触发真实 startup/shutdown"""
        # 防止真值默认URL击穿fallback（CLAUDE.md 坑#4）
        os.environ.setdefault("XAGENT_QDRANT_URL", "")

        from starlette.testclient import TestClient
        from backend.app.main import app

        # with 块内会触发 startup_event
        with TestClient(app) as client:
            # 验证 /health 端点可达（说明 app 成功启动）
            response = client.get("/health")
            assert response.status_code == 200
            assert response.json() == {"status": "ok", "service": "x-agent"}

        # with 块退出会触发 shutdown_event
        # 全局管理器应被清空（在无配置情况下本来就是 None）
        assert get_mcp_manager() is None

    @pytest.mark.asyncio
    async def test_ready_endpoint_includes_components(self):
        """验证 /ready 端点返回组件状态"""
        os.environ.setdefault("XAGENT_QDRANT_URL", "")

        from starlette.testclient import TestClient
        from backend.app.main import app

        with TestClient(app) as client:
            response = client.get("/ready")
            # /ready 可能返回 200 或 503，取决于组件状态
            assert response.status_code in (200, 503)
            body = response.json()
            assert "status" in body
            assert "components" in body
            assert "integrations" in body
            # 至少应包含 memory 组件
            assert "memory" in body["components"]
