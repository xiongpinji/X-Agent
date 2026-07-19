"""MCP Client — 基于官方 ``mcp`` Python SDK 的真实 MCP 协议客户端。

P1-01：取代旧的自造 JSON 协议客户端（HTTP POST ``/mcp/request`` 私有格式）。
本实现讲标准 Model Context Protocol（JSON-RPC 2.0，``initialize`` /
``tools/list`` / ``tools/call``），支持两种官方传输：

* ``transport="stdio"`` — 以子进程方式拉起 MCP server，经 stdin/stdout
  通信（``mcp.client.stdio.stdio_client``）。
* ``transport="http"`` — Streamable HTTP 传输
  （``mcp.client.streamable_http.streamablehttp_client``）。

若官方 SDK 未安装（``pip install mcp`` 失败的环境），模块仍可导入，
但任何连接尝试会显式抛出 ``MCPUnavailableError``——不静默降级、不伪造成功。

向后兼容：构造函数仍接受 ``MCPClient(server_url, timeout=..., max_retries=...,
enable_cache=...)``；``MCPConnectionPool`` / ``MCPResultCache`` 原样保留。
"""

from __future__ import annotations

import asyncio
import logging
from typing import Any, Dict, List, Optional, Tuple
from datetime import datetime, timedelta
import hashlib
import json

logger = logging.getLogger(__name__)

# --- 官方 MCP SDK（可选导入模式：缺失时显式报错，不静默伪造） -----------------
try:  # pragma: no cover - 取决于部署环境
    from mcp import ClientSession, StdioServerParameters
    from mcp.client.stdio import stdio_client
    from mcp.client.streamable_http import streamablehttp_client

    MCP_SDK_AVAILABLE = True
    _MCP_IMPORT_ERROR: Exception | None = None
except ImportError as exc:  # pragma: no cover
    ClientSession = None  # type: ignore[assignment]
    StdioServerParameters = None  # type: ignore[assignment]
    stdio_client = None  # type: ignore[assignment]
    streamablehttp_client = None  # type: ignore[assignment]
    MCP_SDK_AVAILABLE = False
    _MCP_IMPORT_ERROR = exc


class MCPUnavailableError(RuntimeError):
    """官方 MCP SDK 不可用（未安装）时抛出。"""


# JSON-RPC 单次调用的默认读取超时（秒）。Streamable HTTP 的 SSE 长读不受其限。
DEFAULT_READ_TIMEOUT = 60.0


class MCPConnectionPool:
    """Connection pool for managing MCP client connections."""

    def __init__(self, max_connections: int = 10):
        """Initialize connection pool.

        Args:
            max_connections: Maximum number of concurrent connections
        """
        self.max_connections = max_connections
        self.semaphore = asyncio.Semaphore(max_connections)
        self.active_connections = 0

    async def acquire(self) -> None:
        """Acquire a connection slot."""
        await self.semaphore.acquire()
        self.active_connections += 1

    def release(self) -> None:
        """Release a connection slot."""
        self.active_connections -= 1
        self.semaphore.release()

    def get_stats(self) -> Dict[str, int]:
        """Get connection pool statistics."""
        return {
            "active": self.active_connections,
            "max": self.max_connections,
            "available": self.max_connections - self.active_connections,
        }


class MCPResultCache:
    """Simple in-memory cache for tool results."""

    def __init__(self, ttl_seconds: int = 300):
        """Initialize result cache.

        Args:
            ttl_seconds: Time-to-live for cached results in seconds
        """
        self.ttl_seconds = ttl_seconds
        self.cache: Dict[str, Tuple[Any, datetime]] = {}

    def _make_key(self, tool_name: str, args: Dict[str, Any]) -> str:
        """Generate cache key from tool name and arguments."""
        args_str = json.dumps(args, sort_keys=True, default=str)
        key_str = f"{tool_name}:{args_str}"
        return hashlib.md5(key_str.encode()).hexdigest()

    def get(self, tool_name: str, args: Dict[str, Any]) -> Optional[Any]:
        """Get cached result if available and not expired.

        Args:
            tool_name: Name of the tool
            args: Tool arguments

        Returns:
            Cached result or None if not found or expired
        """
        key = self._make_key(tool_name, args)
        if key not in self.cache:
            return None

        result, timestamp = self.cache[key]
        if datetime.now() - timestamp > timedelta(seconds=self.ttl_seconds):
            del self.cache[key]
            return None

        logger.debug(f"Cache hit for {tool_name}")
        return result

    def set(self, tool_name: str, args: Dict[str, Any], result: Any) -> None:
        """Cache a tool result.

        Args:
            tool_name: Name of the tool
            args: Tool arguments
            result: Result to cache
        """
        key = self._make_key(tool_name, args)
        self.cache[key] = (result, datetime.now())

    def clear(self) -> None:
        """Clear all cached results."""
        self.cache.clear()

    def get_stats(self) -> Dict[str, int]:
        """Get cache statistics."""
        return {"size": len(self.cache), "ttl_seconds": self.ttl_seconds}


class MCPClient:
    """真实 MCP 协议客户端（官方 SDK，stdio + Streamable HTTP）。

    Args:
        server_url: Streamable HTTP 端点 URL（``transport="http"`` 时必填）。
        timeout: 单次请求超时（秒）。
        max_retries: 传输级失败的最大重试次数（工具级业务错误不重试）。
        retry_backoff_factor: 指数退避因子。
        max_connections: 并发调用上限（连接池信号量）。
        cache_ttl_seconds: 结果缓存 TTL（秒）。
        enable_cache: 是否启用结果缓存。
        transport: ``"http"``（Streamable HTTP）或 ``"stdio"``（子进程）。
        command: stdio 传输下要拉起的命令（如 ``"python"`` / ``"npx"``）。
        args: stdio 命令参数列表。
        env: stdio 子进程环境变量（None = SDK 默认安全环境）。
        cwd: stdio 子进程工作目录。
        headers: Streamable HTTP 额外请求头（如鉴权）。
    """

    def __init__(
        self,
        server_url: Optional[str] = None,
        timeout: float = 30.0,
        max_retries: int = 3,
        retry_backoff_factor: float = 2.0,
        max_connections: int = 10,
        cache_ttl_seconds: int = 300,
        enable_cache: bool = True,
        *,
        transport: str = "http",
        command: Optional[str] = None,
        args: Optional[List[str]] = None,
        env: Optional[Dict[str, str]] = None,
        cwd: Optional[str] = None,
        headers: Optional[Dict[str, str]] = None,
    ):
        transport = (transport or "http").lower()
        if transport not in {"http", "stdio"}:
            raise ValueError(
                f"Unsupported MCP transport: {transport!r} (expected 'http' or 'stdio')"
            )
        if transport == "http" and not server_url:
            raise ValueError("server_url is required for Streamable HTTP transport")
        if transport == "stdio" and not command:
            raise ValueError("command is required for stdio transport")

        self.server_url = (server_url or "").rstrip("/")
        self.transport = transport
        self.command = command
        self.args = list(args or [])
        self.env = env
        self.cwd = cwd
        self.headers = dict(headers or {})
        self.timeout = timeout
        self.max_retries = max_retries
        self.retry_backoff_factor = retry_backoff_factor
        self.enable_cache = enable_cache

        self.connection_pool = MCPConnectionPool(max_connections)
        self.cache = MCPResultCache(cache_ttl_seconds) if enable_cache else None

        # 会话状态（惰性连接，首次 RPC 时建立）。
        self._session: Any = None  # mcp.ClientSession
        self._exit_stack: Any = None  # contextlib.AsyncExitStack
        self._connect_lock = asyncio.Lock()
        self._server_info: Dict[str, Any] = {}

        logger.info(
            "MCPClient initialized: transport=%s, target=%s, retries=%s, cache=%s",
            self.transport,
            self.server_url or f"{self.command} {' '.join(self.args)}".strip(),
            max_retries,
            enable_cache,
        )

    # ------------------------------------------------------------------
    # 连接生命周期
    # ------------------------------------------------------------------

    @property
    def connected(self) -> bool:
        """是否已建立 MCP 会话。"""
        return self._session is not None

    async def connect(self) -> None:
        """建立传输并完成 ``initialize`` 握手（幂等）。

        Raises:
            MCPUnavailableError: 官方 ``mcp`` SDK 未安装。
            Exception: 传输建立或握手失败（交由重试/健康检查处理）。
        """
        if self._session is not None:
            return
        async with self._connect_lock:
            if self._session is not None:
                return
            if not MCP_SDK_AVAILABLE:
                raise MCPUnavailableError(
                    "官方 mcp Python SDK 未安装，无法建立 MCP 连接。"
                    "请执行 `pip install mcp`（见 requirements.txt）。"
                    f"原始导入错误: {_MCP_IMPORT_ERROR}"
                )

            from contextlib import AsyncExitStack

            stack = AsyncExitStack()
            try:
                if self.transport == "stdio":
                    params = StdioServerParameters(
                        command=self.command,
                        args=self.args,
                        env=self.env,
                        cwd=self.cwd,
                    )
                    read_stream, write_stream = await stack.enter_async_context(
                        stdio_client(params)
                    )
                else:
                    read_stream, write_stream, _get_session_id = (
                        await stack.enter_async_context(
                            streamablehttp_client(
                                self.server_url,
                                headers=self.headers or None,
                                timeout=self.timeout,
                            )
                        )
                    )

                session = await stack.enter_async_context(
                    ClientSession(read_stream, write_stream)
                )
                init_result = await session.initialize()
            except BaseException as exc:
                # 握手/传输失败：完整回滚，不允许留下半连接状态。
                try:
                    await stack.aclose()
                except BaseException:  # noqa: BLE001 - 清理失败不掩盖原始错误
                    pass
                if isinstance(exc, asyncio.CancelledError):
                    # SDK 内部的 anyio task group 在连接失败清理时会把
                    # CancelledError 抛给调用方——这是传输失败而非调用方
                    # 被取消。仅在调用方任务真的被取消时才原样上抛。
                    task = asyncio.current_task()
                    if task is not None and task.cancelling():
                        raise
                    raise ConnectionError(
                        f"MCP {self.transport} connect to "
                        f"{self.server_url or self.command} failed: "
                        f"cancelled during handshake"
                    ) from exc
                raise

            self._exit_stack = stack
            self._session = session
            self._server_info = {
                "server_name": getattr(init_result, "serverInfo", None)
                and getattr(init_result.serverInfo, "name", None),
                "server_version": getattr(init_result, "serverInfo", None)
                and getattr(init_result.serverInfo, "version", None),
                "protocol_version": getattr(init_result, "protocolVersion", None),
            }
            logger.info("MCP session established: %s", self._server_info)

    # ------------------------------------------------------------------
    # MCP RPC
    # ------------------------------------------------------------------

    async def list_tools(self) -> List[Dict[str, Any]]:
        """列出远端 MCP server 的全部工具（自动处理分页）。

        Returns:
            归一化为 snake_case 的字典列表：
            ``name`` / ``description`` / ``input_schema`` / ``output_schema`` /
            ``tags`` / ``annotations``。
        """

        async def _list() -> List[Dict[str, Any]]:
            await self.connect()
            tools: List[Dict[str, Any]] = []
            cursor: Optional[str] = None
            while True:
                result = await self._session.list_tools(cursor=cursor)
                for tool in result.tools:
                    tools.append(self._normalize_tool(tool))
                cursor = getattr(result, "nextCursor", None)
                if not cursor:
                    break
            return tools

        return await self._rpc_with_retry("tools/list", _list)

    async def call_tool(self, tool_name: str, args: Dict[str, Any]) -> Any:
        """调用远端 MCP 工具。

        Returns:
            工具结果：优先 ``structuredContent``；否则单文本块返回字符串，
            多块返回归一化字典列表。

        Raises:
            ValueError: 远端返回 ``isError=True``（工具级失败，不重试）。
            MCPUnavailableError: 官方 SDK 缺失。
        """
        if self.enable_cache:
            cached = self.cache.get(tool_name, args)
            if cached is not None:
                return cached

        async def _call() -> Any:
            await self.connect()
            await self.connection_pool.acquire()
            try:
                result = await self._session.call_tool(tool_name, args or {})
            finally:
                self.connection_pool.release()
            if getattr(result, "isError", False):
                raise ValueError(
                    f"MCP tool '{tool_name}' failed: {self._result_text(result)}"
                )
            return self._unwrap_result(result)

        output = await self._rpc_with_retry(f"tools/call:{tool_name}", _call)

        if self.enable_cache and output is not None:
            self.cache.set(tool_name, args, output)
        return output

    async def call_tools_batch(
        self, calls: List[Tuple[str, Dict[str, Any]]]
    ) -> List[Any]:
        """Call multiple tools concurrently.

        Args:
            calls: List of (tool_name, args) tuples

        Returns:
            List of results in the same order as input
        """
        tasks = [self.call_tool(tool_name, args) for tool_name, args in calls]
        return await asyncio.gather(*tasks, return_exceptions=True)

    # ------------------------------------------------------------------
    # 运维
    # ------------------------------------------------------------------

    async def health_check(self) -> bool:
        """Check if the MCP server is reachable and speaks MCP.

        Returns:
            True if initialize + tools/list succeeded, False otherwise
        """
        try:
            tools = await self.list_tools()
            logger.info(f"Health check passed: {len(tools)} tools available")
            return True
        except Exception as e:
            logger.error(f"Health check failed: {e}")
            return False

    def get_stats(self) -> Dict[str, Any]:
        """Get client statistics.

        Returns:
            Dictionary with connection pool, cache and transport stats
        """
        stats: Dict[str, Any] = {
            "connection_pool": self.connection_pool.get_stats(),
            "transport": self.transport,
            "connected": self.connected,
        }
        if self._server_info:
            stats["server_info"] = dict(self._server_info)
        if self.enable_cache:
            stats["cache"] = self.cache.get_stats()
        return stats

    async def close(self) -> None:
        """Close the MCP session and underlying transport/subprocess."""
        await self._reset_connection()
        if self.enable_cache:
            self.cache.clear()
        logger.info("MCPClient closed")

    async def _reset_connection(self) -> None:
        """丢弃当前会话与传输（重连前/关闭时），清理异常不抛出。"""
        stack, self._exit_stack, self._session = self._exit_stack, None, None
        self._server_info = {}
        if stack is not None:
            try:
                await stack.aclose()
            except Exception as e:  # noqa: BLE001
                # anyio 取消作用域要求 __aexit__ 与 __aenter__ 处于同一任务；
                # 跨任务关闭时记录告警而不是让关停流程崩溃。
                logger.warning(f"MCP client close raised (suppressed): {e}")

    async def __aenter__(self) -> "MCPClient":
        """Async context manager entry."""
        await self.connect()
        return self

    async def __aexit__(self, exc_type: Any, exc_val: Any, exc_tb: Any) -> None:
        """Async context manager exit."""
        await self.close()

    # ------------------------------------------------------------------
    # 内部
    # ------------------------------------------------------------------

    async def _rpc_with_retry(self, label: str, fn) -> Any:
        """传输级失败指数退避重试；工具级 ValueError 不重试。

        每次传输失败后丢弃当前会话，下次重试将重新建立连接（含握手）。
        """
        last_error: Exception | None = None
        for attempt in range(self.max_retries + 1):
            try:
                return await fn()
            except ValueError:
                raise
            except Exception as e:  # noqa: BLE001 - 传输/协议错误均可重试
                last_error = e
                await self._reset_connection()
                if attempt < self.max_retries:
                    wait_time = self.retry_backoff_factor**attempt
                    logger.warning(
                        "%s failed (attempt %d/%d), retrying in %.1fs: %s",
                        label,
                        attempt + 1,
                        self.max_retries + 1,
                        wait_time,
                        e,
                    )
                    await asyncio.sleep(wait_time)
                else:
                    logger.error(
                        "%s failed after %d attempts: %s",
                        label,
                        self.max_retries + 1,
                        e,
                    )
        raise last_error  # type: ignore[misc]

    @staticmethod
    def _normalize_tool(tool: Any) -> Dict[str, Any]:
        """官方 ``mcp.types.Tool`` → 发现层使用的 snake_case 字典。"""
        annotations = getattr(tool, "annotations", None)
        return {
            "name": tool.name,
            "description": getattr(tool, "description", "") or "",
            "input_schema": getattr(tool, "inputSchema", None) or {},
            "output_schema": getattr(tool, "outputSchema", None),
            "tags": [],
            "annotations": (
                annotations.model_dump(mode="json", exclude_none=True)
                if annotations is not None and hasattr(annotations, "model_dump")
                else {}
            ),
        }

    @staticmethod
    def _result_text(result: Any) -> str:
        """提取 CallToolResult 的文本内容（用于错误消息）。"""
        texts: List[str] = []
        for block in getattr(result, "content", None) or []:
            if getattr(block, "type", None) == "text":
                texts.append(getattr(block, "text", ""))
            else:
                texts.append(str(block))
        return "\n".join(texts) or "<no content>"

    @classmethod
    def _unwrap_result(cls, result: Any) -> Any:
        """CallToolResult → Python 值。

        structuredContent 优先；单个 text 块返回纯字符串；多块返回列表。
        """
        structured = getattr(result, "structuredContent", None)
        if structured is not None:
            return structured
        parts: List[Any] = []
        for block in getattr(result, "content", None) or []:
            if getattr(block, "type", None) == "text":
                parts.append(getattr(block, "text", ""))
            elif hasattr(block, "model_dump"):
                parts.append(block.model_dump(mode="json"))
            else:
                parts.append(str(block))
        if len(parts) == 1:
            return parts[0]
        return parts
