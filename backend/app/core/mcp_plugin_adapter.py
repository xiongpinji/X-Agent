"""MCP Plugin Adapter - Load, validate, and manage MCP plugins for X-Agent

P1-12 后续：``start_server`` 现在执行**真实的 stdio MCP 协议握手**（官方
``mcp`` Python SDK），不再是"仅拉起进程"的占位实现：

* spawn 子进程 → ``initialize`` 请求（protocolVersion / capabilities /
  clientInfo）→ ``notifications/initialized`` 通知 → ``tools/list`` 工具发现；
* ``call_tool`` 经 ``tools/call`` 真实调用插件进程内工具；
* 握手失败 fail-closed：``plugin.status=ERROR`` + 可诊断错误（命令行、
  cwd、插件进程 stderr 尾部），绝不伪造成功；
* 进程退出/传输断开时会话标记为 dead，后续调用立即失败并触发清理。

会话实现（``MCPPluginStdioSession``）运行在专用后台事件循环线程上；
``stdio_client`` / ``ClientSession`` 上下文在同一个长驻协程内进入与退出
（anyio 取消作用域不允许跨任务进出）。
"""

from __future__ import annotations

import asyncio
import contextlib
import json
import logging
import os
import subprocess
import sys
import tempfile
import threading
from concurrent.futures import TimeoutError as FutureTimeoutError
from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta
from enum import StrEnum
from pathlib import Path
from threading import RLock
from typing import Any, Callable
from uuid import uuid4

from pydantic import BaseModel, Field, validator

logger = logging.getLogger(__name__)

# --- 官方 MCP SDK（可选导入：缺失时握手显式报错，不静默伪造） -----------------
try:  # pragma: no cover - 取决于部署环境
    from mcp import ClientSession, StdioServerParameters
    from mcp.client.stdio import stdio_client
    from mcp.types import Implementation

    MCP_SDK_AVAILABLE = True
    _MCP_IMPORT_ERROR: Exception | None = None
except ImportError as exc:  # pragma: no cover
    ClientSession = None  # type: ignore[assignment]
    StdioServerParameters = None  # type: ignore[assignment]
    stdio_client = None  # type: ignore[assignment]
    Implementation = None  # type: ignore[assignment]
    MCP_SDK_AVAILABLE = False
    _MCP_IMPORT_ERROR = exc


# --- 错误类型（调用方可据此区分握手失败 / 传输失败 / 工具级失败） --------------

class MCPPluginHandshakeError(RuntimeError):
    """插件子进程 MCP 握手失败（spawn / initialize / tools/list 阶段）。"""


class MCPPluginTransportError(RuntimeError):
    """插件进程传输失败（进程退出、请求超时、会话不可用）——会话已判死。"""


class MCPPluginToolError(ValueError):
    """远端工具执行失败（tools/call 返回 isError=True）——会话保持可用。"""


# --- 可配置超时（环境变量覆盖，per-server 经 start_server(timeout=...) 覆盖） --

ENV_START_TIMEOUT = "XAGENT_MCP_PLUGIN_START_TIMEOUT"
ENV_REQUEST_TIMEOUT = "XAGENT_MCP_PLUGIN_REQUEST_TIMEOUT"
DEFAULT_START_TIMEOUT = 15.0
DEFAULT_REQUEST_TIMEOUT = 60.0

# 插件子进程读取自身配置的约定环境变量：值为 manifest.configuration 校验后的
# JSON 对象（经官方 SDK 与默认安全 env 合并注入；密钥类配置只走环境变量，
# 不落盘、不进工具 schema）。插件端约定：缺必填配置时向 stderr 输出诊断并
# 以非零码退出（握手 fail-closed，可诊断），绝不伪造可用。
PLUGIN_CONFIG_ENV_VAR = "XAGENT_PLUGIN_CONFIG"


def _env_float(name: str, default: float) -> float:
    """从环境变量读取 float 配置，非法值告警回退默认（不静默崩溃）。"""
    raw = os.environ.get(name)
    if not raw:
        return default
    try:
        value = float(raw)
        if value <= 0:
            raise ValueError("must be positive")
        return value
    except ValueError:
        logger.warning("Invalid %s=%r, using default %.1fs", name, raw, default)
        return default


# 握手阶段 stderr 捕获保留的尾部长度（用于错误诊断）
_STDERR_TAIL_CHARS = 2000
# future.result() 相对于内部 asyncio.wait_for 的宽限余量：
# 让内部超时（TimeoutError，消息更具体）先于外层 future 超时触发。
_SUBMIT_GRACE_SECONDS = 5.0


class MCPPluginStdioSession:
    """单个插件子进程的 stdio MCP 会话（同步门面 + 后台事件循环线程）。

    生命周期（官方 ``mcp`` SDK 执行真实 JSON-RPC 2.0 消息序列）::

        start()   spawn 子进程 → initialize 请求（protocolVersion /
                  capabilities / clientInfo）→ notifications/initialized
                  → tools/list 发现工具；任一步失败 fail-closed 抛
                  ``MCPPluginHandshakeError``（附命令行与 stderr 尾部）。
        list_tools() / call_tool()   经同一会话发起 tools/list / tools/call。
        stop()    关闭传输（SDK 按 MCP stdio 关停序列：关 stdin → 等待退出
                  → SIGTERM → SIGKILL），线程与临时资源清理。

    实现约束：``stdio_client`` / ``ClientSession`` 上下文必须在**同一个
    任务**内进入与退出（anyio 取消作用域限制），因此整个会话生命周期
    由 ``_main`` 这一个长驻协程持有；请求经 ``run_coroutine_threadsafe``
    提交到同一事件循环，仅使用会话（不进出作用域），跨任务安全。
    """

    def __init__(
        self,
        *,
        command: str,
        args: list[str] | None = None,
        cwd: str | None = None,
        env: dict[str, str] | None = None,
        client_name: str = "x-agent-plugin-runtime",
        client_version: str = "1.0.0",
        start_timeout: float | None = None,
        request_timeout: float | None = None,
    ):
        self._command = command
        self._args = list(args or [])
        self._cwd = cwd
        self._env = dict(env) if env else None
        self._client_name = client_name
        self._client_version = client_version
        self._start_timeout = (
            float(start_timeout)
            if start_timeout is not None
            else _env_float(ENV_START_TIMEOUT, DEFAULT_START_TIMEOUT)
        )
        self._request_timeout = (
            float(request_timeout)
            if request_timeout is not None
            else _env_float(ENV_REQUEST_TIMEOUT, DEFAULT_REQUEST_TIMEOUT)
        )

        # 会话状态（跨线程读，loop 线程写）
        self._loop: asyncio.AbstractEventLoop | None = None
        self._thread: threading.Thread | None = None
        self._ready = threading.Event()       # 握手完成（成功或失败）
        self._stopped = threading.Event()     # _main 协程彻底退出
        self._shutdown_requested = False      # stop() 已请求关停
        self._async_shutdown: asyncio.Event | None = None  # 仅 loop 线程触碰
        self._session: Any = None             # ClientSession，仅 loop 线程触碰
        self._start_error: BaseException | None = None
        self._dead_error: str | None = None   # 传输断开后的判死原因
        self._server_info: dict[str, Any] = {}
        self._initial_tools: list[dict[str, Any]] = []
        self._stderr_file: Any = None         # tempfile，捕获插件 stderr

    # ------------------------------------------------------------------
    # 同步门面
    # ------------------------------------------------------------------

    @property
    def command_line(self) -> str:
        return f"{self._command} {' '.join(self._args)}".strip()

    @property
    def server_info(self) -> dict[str, Any]:
        """initialize 结果摘要（serverInfo / protocolVersion / capabilities）。"""
        return dict(self._server_info)

    @property
    def tools_discovered(self) -> list[dict[str, Any]]:
        """握手阶段 tools/list 发现的工具（归一化 snake_case 字典）。"""
        return list(self._initial_tools)

    @property
    def is_alive(self) -> bool:
        """会话可用：线程存活、会话建立且未判死。"""
        return (
            self._thread is not None
            and self._thread.is_alive()
            and self._session is not None
            and self._dead_error is None
            and self._start_error is None
        )

    @property
    def dead_error(self) -> str | None:
        return self._dead_error

    def start(self) -> "MCPPluginStdioSession":
        """拉起子进程并完成 initialize/initialized/tools/list 握手。

        Raises:
            MCPPluginHandshakeError: SDK 缺失、spawn 失败、握手超时、
                initialize/tools/list 失败（消息含命令行、cwd 与 stderr 尾部）。
        """
        if self._thread is not None:
            raise RuntimeError("MCPPluginStdioSession already started")
        if not MCP_SDK_AVAILABLE:
            raise MCPPluginHandshakeError(
                "官方 mcp Python SDK 未安装，无法与插件子进程进行 MCP 握手。"
                "请执行 `pip install mcp`（见 requirements.txt）。"
                f"原始导入错误: {_MCP_IMPORT_ERROR}"
            )

        self._stderr_file = tempfile.TemporaryFile(
            mode="w+", encoding="utf-8", errors="replace"
        )
        self._loop = asyncio.new_event_loop()
        self._thread = threading.Thread(
            target=self._run_loop,
            name=f"mcp-plugin-stdio-{self._command}",
            daemon=True,
        )
        self._thread.start()

        if not self._ready.wait(timeout=self._start_timeout):
            stderr_tail = self._read_stderr_tail()
            self.stop()
            raise MCPPluginHandshakeError(
                f"MCP stdio 握手超时（{self._start_timeout:.1f}s）："
                f"command='{self.command_line}' cwd='{self._cwd}'。"
                "插件进程未在超时内完成 initialize/tools/list "
                "（可能未实现 stdio MCP 协议或启动挂起）。"
                + (f" 插件 stderr 尾部: {stderr_tail}" if stderr_tail else "")
            )
        if self._start_error is not None:
            stderr_tail = self._read_stderr_tail()
            self.stop()
            raise MCPPluginHandshakeError(
                f"MCP stdio 握手失败：command='{self.command_line}' "
                f"cwd='{self._cwd}'：{self._start_error!r}。"
                "常见原因：插件进程未讲 stdio MCP 协议即退出、"
                "入口命令/模块不可执行。"
                + (f" 插件 stderr 尾部: {stderr_tail}" if stderr_tail else "")
            ) from self._start_error
        logger.info(
            "MCP plugin session established: %s -> %s (%d tools)",
            self.command_line,
            self._server_info.get("server_name"),
            len(self._initial_tools),
        )
        return self

    def list_tools(self, timeout: float | None = None) -> list[dict[str, Any]]:
        """tools/list（自动分页），归一化为 snake_case 字典列表。"""

        async def _rpc(session: Any) -> list[dict[str, Any]]:
            tools: list[dict[str, Any]] = []
            cursor: str | None = None
            while True:
                result = await session.list_tools(cursor=cursor)
                tools.extend(self._normalize_tool(t) for t in result.tools)
                cursor = getattr(result, "nextCursor", None)
                if not cursor:
                    break
            return tools

        return self._submit(_rpc, timeout)

    def call_tool(
        self, tool_name: str, arguments: dict[str, Any] | None = None,
        timeout: float | None = None,
    ) -> Any:
        """tools/call：structuredContent 优先，单 text 块返回字符串。"""

        async def _rpc(session: Any) -> Any:
            result = await session.call_tool(tool_name, dict(arguments or {}))
            if getattr(result, "isError", False):
                raise MCPPluginToolError(
                    f"MCP tool '{tool_name}' failed: "
                    f"{self._result_text(result)}"
                )
            return self._unwrap_result(result)

        return self._submit(_rpc, timeout)

    def stop(self, timeout: float = 5.0) -> None:
        """关停会话（幂等）：请求后台协程退出 → SDK 执行 stdio 关停序列。"""
        self._shutdown_requested = True
        loop = self._loop
        if loop is not None and loop.is_running():
            def _set_shutdown() -> None:
                if self._async_shutdown is not None:
                    self._async_shutdown.set()
            try:
                loop.call_soon_threadsafe(_set_shutdown)
            except RuntimeError:  # loop 已关闭
                pass
        if self._thread is not None and self._thread.is_alive():
            self._thread.join(timeout=timeout)
        if self._stderr_file is not None:
            with contextlib.suppress(Exception):
                self._stderr_file.close()
            self._stderr_file = None

    # ------------------------------------------------------------------
    # 后台事件循环
    # ------------------------------------------------------------------

    def _run_loop(self) -> None:
        """后台线程入口：跑完 _main 协程后关闭事件循环。"""
        assert self._loop is not None
        try:
            self._loop.run_until_complete(self._main())
        except BaseException as exc:  # 防御：_main 自身不应抛出
            if self._start_error is None:
                self._start_error = exc
            self._ready.set()
        finally:
            self._stopped.set()
            try:
                self._loop.close()
            except Exception:  # pragma: no cover
                pass

    async def _main(self) -> None:
        """会话主协程：握手 → 等待关停 → 同任务清理（anyio 约束）。"""
        from contextlib import AsyncExitStack

        stack = AsyncExitStack()
        try:
            params = StdioServerParameters(
                command=self._command,
                args=self._args,
                env=self._env,
                cwd=self._cwd,
            )
            read_stream, write_stream = await stack.enter_async_context(
                stdio_client(params, errlog=self._stderr_file)
            )
            session = await stack.enter_async_context(
                ClientSession(
                    read_stream,
                    write_stream,
                    read_timeout_seconds=timedelta(seconds=self._request_timeout),
                    client_info=Implementation(
                        name=self._client_name, version=self._client_version
                    ),
                )
            )
            # initialize 请求（protocolVersion/capabilities/clientInfo）+
            # notifications/initialized 通知由官方 SDK 在此发送
            init_result = await asyncio.wait_for(
                session.initialize(), timeout=self._start_timeout
            )
            self._session = session
            self._server_info = self._summarize_server_info(init_result)
            # 握手收尾：立即 tools/list 发现工具（不可列出则视为不可用）
            self._initial_tools = await asyncio.wait_for(
                self._collect_tools(session), timeout=self._start_timeout
            )
        except BaseException as exc:
            # 握手失败：完整回滚（终止子进程），不允许半连接状态
            self._start_error = exc
            with contextlib.suppress(BaseException):
                await stack.aclose()
            self._ready.set()
            return

        self._ready.set()
        self._async_shutdown = asyncio.Event()
        if self._shutdown_requested:
            self._async_shutdown.set()
        try:
            await self._async_shutdown.wait()
        finally:
            self._session = None
            with contextlib.suppress(BaseException):
                await stack.aclose()

    @staticmethod
    async def _collect_tools(session: Any) -> list[dict[str, Any]]:
        """分页收集 tools/list 结果并归一化。"""
        tools: list[dict[str, Any]] = []
        cursor: str | None = None
        while True:
            result = await session.list_tools(cursor=cursor)
            tools.extend(
                MCPPluginStdioSession._normalize_tool(t) for t in result.tools
            )
            cursor = getattr(result, "nextCursor", None)
            if not cursor:
                break
        return tools

    # ------------------------------------------------------------------
    # 请求提交与判死
    # ------------------------------------------------------------------

    def _submit(self, make_rpc: Callable[[Any], Any], timeout: float | None) -> Any:
        """把 RPC 协程提交到后台循环并同步等待结果。

        工具级错误（MCPPluginToolError）原样上抛且不判死；
        其它任何异常视为传输/协议故障：判死会话并触发关停清理。
        """
        if self._dead_error is not None:
            raise MCPPluginTransportError(
                f"插件 MCP 会话已不可用：{self._dead_error}"
            )
        if self._stopped.is_set() or self._start_error is not None or not self._ready.is_set():
            raise MCPPluginTransportError(
                "插件 MCP 会话未在运行（先调用 start()；若已 stop() 需重新 start）"
            )

        effective = float(timeout) if timeout is not None else self._request_timeout

        async def _wrapped() -> Any:
            session = self._session
            if session is None:  # pragma: no cover - 判死竞态兜底
                raise MCPPluginTransportError("MCP session 未建立")
            return await asyncio.wait_for(make_rpc(session), timeout=effective)

        future = asyncio.run_coroutine_threadsafe(_wrapped(), self._loop)
        try:
            return future.result(timeout=effective + _SUBMIT_GRACE_SECONDS)
        except FutureTimeoutError:
            future.cancel()
            self._mark_dead(f"请求超时（{effective:.1f}s）")
            raise MCPPluginTransportError(
                f"MCP 请求超时（{effective:.1f}s）：command='{self.command_line}'"
            ) from None
        except MCPPluginToolError:
            raise  # 远端工具级失败，会话保持可用
        except BaseException as exc:
            self._mark_dead(f"传输失败：{exc!r}")
            raise MCPPluginTransportError(
                f"MCP 请求失败（插件进程可能已退出）："
                f"command='{self.command_line}'：{exc!r}"
            ) from exc

    def _mark_dead(self, reason: str) -> None:
        """会话判死（进程退出/传输断开/请求超时）：记录原因并触发关停。"""
        if self._dead_error is None:
            self._dead_error = reason
            logger.warning("MCP plugin session dead: %s (%s)", self.command_line, reason)
        self.stop()

    def _read_stderr_tail(self, limit: int = _STDERR_TAIL_CHARS) -> str:
        """读取插件进程 stderr 捕获文件的尾部（诊断用，尽力而为）。"""
        stderr_file = self._stderr_file
        if stderr_file is None:
            return ""
        try:
            stderr_file.flush()
            stderr_file.seek(0)
            text = stderr_file.read() or ""
            return text.strip()[-limit:]
        except Exception:  # pragma: no cover
            return ""

    # ------------------------------------------------------------------
    # 结果归一化（与 core/mcp/client.py 的 MCPClient 保持一致契约）
    # ------------------------------------------------------------------

    @staticmethod
    def _normalize_tool(tool: Any) -> dict[str, Any]:
        """官方 ``mcp.types.Tool`` → snake_case 字典（同 MCPClient 契约）。"""
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
        """提取 CallToolResult 文本内容（错误消息用）。"""
        texts: list[str] = []
        for block in getattr(result, "content", None) or []:
            if getattr(block, "type", None) == "text":
                texts.append(getattr(block, "text", ""))
            else:
                texts.append(str(block))
        return "\n".join(texts) or "<no content>"

    @classmethod
    def _unwrap_result(cls, result: Any) -> Any:
        """CallToolResult → Python 值：structuredContent 优先，单 text 块为字符串。"""
        structured = getattr(result, "structuredContent", None)
        if structured is not None:
            return structured
        parts: list[Any] = []
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

    @staticmethod
    def _summarize_server_info(init_result: Any) -> dict[str, Any]:
        """initialize 结果 → JSON 可序列化摘要。"""
        server_info = getattr(init_result, "serverInfo", None)
        capabilities = getattr(init_result, "capabilities", None)
        return {
            "server_name": getattr(server_info, "name", None),
            "server_version": getattr(server_info, "version", None),
            "protocol_version": str(getattr(init_result, "protocolVersion", "") or ""),
            "capabilities": (
                capabilities.model_dump(mode="json", exclude_none=True)
                if capabilities is not None and hasattr(capabilities, "model_dump")
                else {}
            ),
        }


class MCPPluginStatus(StrEnum):
    """MCP Plugin Status"""
    UNLOADED = "unloaded"
    LOADING = "loading"
    LOADED = "loaded"
    RUNNING = "running"
    STOPPED = "stopped"
    ERROR = "error"
    UNLOADING = "unloading"


class MCPCapability(BaseModel):
    """MCP Capability"""
    tools: bool = False
    resources: bool = False
    prompts: bool = False


class MCPPermission(BaseModel):
    """MCP Permission"""
    network: dict[str, Any] = Field(default_factory=dict)
    filesystem: dict[str, Any] = Field(default_factory=dict)
    environment: dict[str, Any] = Field(default_factory=dict)


class MCPEntryPoint(BaseModel):
    """MCP Entry Point"""
    type: str  # python, node, docker
    module: str
    class_name: str = Field(alias="class")

    class Config:
        populate_by_name = True


class MCPManifest(BaseModel):
    """MCP Plugin Manifest"""
    schema_version: str
    name: str
    version: str
    type: str = "mcp-plugin"
    xagent_compatibility: dict[str, str]
    metadata: dict[str, Any]
    chinese: dict[str, Any]
    capabilities: MCPCapability
    permissions: MCPPermission
    entry_point: MCPEntryPoint
    dependencies: dict[str, Any]
    configuration: dict[str, Any] = Field(default_factory=dict)
    tools: list[dict[str, Any]] = Field(default_factory=list)
    resources: list[dict[str, Any]] = Field(default_factory=list)
    security: dict[str, Any] = Field(default_factory=dict)
    quality_metrics: dict[str, Any] = Field(default_factory=dict)

    @validator("schema_version")
    def validate_schema_version(cls, v):
        if v != "1.0":
            raise ValueError("schema_version must be '1.0'")
        return v

    @validator("type")
    def validate_type(cls, v):
        if v != "mcp-plugin":
            raise ValueError("type must be 'mcp-plugin'")
        return v

    @validator("name")
    def validate_name(cls, v):
        import re
        if not re.match(r"^[a-z0-9-]+$", v):
            raise ValueError("name must contain only lowercase letters, numbers, and hyphens")
        return v


@dataclass
class MCPPlugin:
    """MCP Plugin Instance"""
    plugin_id: str = Field(default_factory=lambda: str(uuid4()))
    manifest: MCPManifest = None
    plugin_path: Path = None
    status: MCPPluginStatus = MCPPluginStatus.UNLOADED
    process: subprocess.Popen | None = None
    # stdio MCP 会话（官方 SDK 管理子进程；process 字段保留兼容旧引用，
    # SDK 模式下为 None）
    session: "MCPPluginStdioSession | None" = None
    # 握手阶段 tools/list 发现的远端工具与 server 信息
    remote_tools: list[dict[str, Any]] = field(default_factory=list)
    server_info: dict[str, Any] = field(default_factory=dict)
    config: dict[str, Any] = field(default_factory=dict)
    created_at: datetime = field(default_factory=lambda: datetime.now(UTC))
    updated_at: datetime = field(default_factory=lambda: datetime.now(UTC))
    error_message: str | None = None

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary"""
        return {
            "plugin_id": self.plugin_id,
            "name": self.manifest.name if self.manifest else None,
            "version": self.manifest.version if self.manifest else None,
            "status": self.status.value,
            "plugin_path": str(self.plugin_path) if self.plugin_path else None,
            "config": self.config,
            "created_at": self.created_at.isoformat(),
            "updated_at": self.updated_at.isoformat(),
            "error_message": self.error_message,
            # MCP 会话真实状态（握手完成后才有；JSON 可序列化）
            "mcp_session_active": self.session is not None and self.session.is_alive,
            "server_info": dict(self.server_info) if self.server_info else {},
            "remote_tools": [t.get("name") for t in self.remote_tools],
        }


class MCPPluginAdapter:
    """Adapter for loading and managing MCP plugins"""

    def __init__(
        self,
        plugins_dir: str | Path | None = None,
        *,
        start_timeout: float | None = None,
        request_timeout: float | None = None,
        client_name: str = "x-agent-plugin-runtime",
        client_version: str = "1.0.0",
    ):
        self.plugins_dir = Path(plugins_dir) if plugins_dir else Path("./plugins")
        self.plugins_dir.mkdir(parents=True, exist_ok=True)
        self._plugins: dict[str, MCPPlugin] = {}
        self._lock = RLock()
        self._manifest_cache: dict[str, MCPManifest] = {}
        # 握手/请求超时：显式参数 > 环境变量 > 默认值；per-server 可经
        # start_server(plugin, timeout=...) 逐个覆盖。
        self.start_timeout = (
            float(start_timeout)
            if start_timeout is not None
            else _env_float(ENV_START_TIMEOUT, DEFAULT_START_TIMEOUT)
        )
        self.request_timeout = (
            float(request_timeout)
            if request_timeout is not None
            else _env_float(ENV_REQUEST_TIMEOUT, DEFAULT_REQUEST_TIMEOUT)
        )
        self.client_name = client_name
        self.client_version = client_version

    def load_manifest(self, plugin_path: str | Path) -> MCPManifest:
        """Load and parse plugin manifest"""
        plugin_path = Path(plugin_path)
        manifest_file = plugin_path / "manifest.json"

        if not manifest_file.exists():
            raise FileNotFoundError(f"Manifest not found: {manifest_file}")

        try:
            with open(manifest_file, encoding="utf-8") as f:
                manifest_data = json.load(f)

            manifest = MCPManifest(**manifest_data)
            self._manifest_cache[manifest.name] = manifest
            logger.info(f"Loaded manifest for plugin: {manifest.name} v{manifest.version}")
            return manifest

        except json.JSONDecodeError as e:
            raise ValueError(f"Invalid JSON in manifest: {e}")
        except Exception as e:
            raise ValueError(f"Failed to parse manifest: {e}")

    def validate_manifest(self, manifest: MCPManifest) -> tuple[bool, list[str]]:
        """Validate plugin manifest"""
        errors = []

        # Check schema version
        if manifest.schema_version != "1.0":
            errors.append(f"Invalid schema_version: {manifest.schema_version}")

        # Check type
        if manifest.type != "mcp-plugin":
            errors.append(f"Invalid type: {manifest.type}")

        # Check name format
        import re
        if not re.match(r"^[a-z0-9-]+$", manifest.name):
            errors.append(f"Invalid name format: {manifest.name}")

        # Check version format
        if not self._is_valid_semver(manifest.version):
            errors.append(f"Invalid version format: {manifest.version}")

        # Check compatibility
        if not self._is_valid_version_range(manifest.xagent_compatibility):
            errors.append("Invalid xagent_compatibility version range")

        # Check metadata
        if not manifest.metadata.get("author"):
            errors.append("metadata.author is required")

        # Check entry point
        if manifest.entry_point.type not in ["python", "node", "docker"]:
            errors.append(f"Invalid entry_point.type: {manifest.entry_point.type}")

        return len(errors) == 0, errors

    def check_compatibility(self, manifest: MCPManifest, xagent_version: str = "0.1.0") -> tuple[bool, list[str]]:
        """Check plugin compatibility with X-Agent version"""
        warnings = []

        min_version = manifest.xagent_compatibility.get("min_version", "0.1.0")
        max_version = manifest.xagent_compatibility.get("max_version", "1.0.0")

        if not self._version_in_range(xagent_version, min_version, max_version):
            return False, [f"X-Agent version {xagent_version} not in range [{min_version}, {max_version}]"]

        # Check Python version if applicable
        if manifest.entry_point.type == "python":
            python_req = manifest.dependencies.get("python", ">=3.8")
            if not self._check_python_version(python_req):
                warnings.append(f"Current Python version may not meet requirement: {python_req}")

        return True, warnings

    def load_plugin(self, plugin_path: str | Path) -> MCPPlugin:
        """Load a plugin from path"""
        plugin_path = Path(plugin_path)

        if not plugin_path.is_dir():
            raise ValueError(f"Plugin path is not a directory: {plugin_path}")

        try:
            # Load manifest
            manifest = self.load_manifest(plugin_path)

            # Validate manifest
            is_valid, errors = self.validate_manifest(manifest)
            if not is_valid:
                raise ValueError(f"Manifest validation failed: {', '.join(errors)}")

            # Create plugin instance
            plugin = MCPPlugin(
                manifest=manifest,
                plugin_path=plugin_path,
                status=MCPPluginStatus.LOADED,
            )

            with self._lock:
                self._plugins[plugin.plugin_id] = plugin

            logger.info(f"Plugin loaded: {manifest.name} ({plugin.plugin_id})")
            return plugin

        except Exception as e:
            logger.error(f"Failed to load plugin from {plugin_path}: {e}")
            raise

    @staticmethod
    def _build_server_command(plugin: MCPPlugin) -> tuple[str, list[str], str]:
        """由 manifest entry_point 推导 stdio MCP server 命令。

        Returns:
            (command, args, cwd)

        Raises:
            MCPPluginHandshakeError: entry_point.type 不支持 stdio 传输。
        """
        entry_point = plugin.manifest.entry_point
        plugin_path = Path(plugin.plugin_path)
        if entry_point.type == "python":
            # 以当前解释器运行插件模块（cwd=插件目录，模块可相对导入）。
            # sys.executable 保证 venv 下用同一解释器（Windows 下为绝对路径
            # 的 python.exe，避免依赖 PATH）。
            return sys.executable, ["-m", entry_point.module], str(plugin_path)
        if entry_point.type == "node":
            return "node", [str(plugin_path / entry_point.module)], str(plugin_path)
        raise MCPPluginHandshakeError(
            f"entry_point.type '{entry_point.type}' 暂不支持 stdio MCP 传输"
            f"（插件：{plugin.manifest.name}）；仅支持 python/node。"
        )

    @staticmethod
    def _build_plugin_env(plugin: MCPPlugin) -> dict[str, str] | None:
        """把插件配置序列化进子进程环境变量（插件配置注入契约）。

        契约：插件子进程从 ``XAGENT_PLUGIN_CONFIG`` 读取 JSON 对象配置。
        官方 SDK 会在默认安全 env（PATH/SYSTEMROOT 等白名单）之上合并本
        字典，因此这里只携带配置本身。配置不可序列化时显式报错（fail
        fast，不静默丢弃配置后拉起一个"缺配置"的插件）。
        """
        if not plugin.config:
            return None
        try:
            payload = json.dumps(plugin.config, ensure_ascii=True, default=str)
        except (TypeError, ValueError) as exc:
            raise MCPPluginHandshakeError(
                f"插件 {plugin.manifest.name} 的配置无法序列化为"
                f" {PLUGIN_CONFIG_ENV_VAR} 环境变量：{exc}"
            ) from exc
        return {PLUGIN_CONFIG_ENV_VAR: payload}

    def start_server(self, plugin: MCPPlugin, timeout: float | None = None) -> bool:
        """Start MCP server for plugin：真实 stdio MCP 握手。

        生命周期：spawn 子进程 → initialize 请求（protocolVersion /
        capabilities / clientInfo）→ initialized 通知 → tools/list 工具发现。
        任一步失败即 fail-closed：进程被终止、status=ERROR、
        error_message 含可诊断信息（命令行/cwd/stderr 尾部）。

        配置注入：``plugin.config``（经 update_config / PluginRuntime.start
        校验后）以 ``XAGENT_PLUGIN_CONFIG`` 环境变量传给子进程（JSON 对象，
        与官方 SDK 默认安全 env 合并）；插件缺必填配置应在握手前退出并
        输出 stderr 诊断（fail-closed，可诊断）。

        Args:
            plugin: 已加载的插件实例。
            timeout: per-server 握手超时（秒）；None 用适配器默认
                （环境变量 ``XAGENT_MCP_PLUGIN_START_TIMEOUT``）。
        """
        if plugin.status == MCPPluginStatus.RUNNING and plugin.session is not None and plugin.session.is_alive:
            logger.warning(f"Plugin {plugin.manifest.name} is already running")
            return True

        # 清理残留（半死会话 / 旧 Popen），不允许叠加进程
        self._terminate_transport(plugin)

        plugin.status = MCPPluginStatus.LOADING
        plugin.updated_at = datetime.now(UTC)
        plugin.error_message = None

        try:
            command, args, cwd = self._build_server_command(plugin)
            env = self._build_plugin_env(plugin)
        except MCPPluginHandshakeError as e:
            plugin.status = MCPPluginStatus.ERROR
            plugin.error_message = str(e)
            logger.error(f"Failed to start server for {plugin.manifest.name}: {e}")
            return False

        session = MCPPluginStdioSession(
            command=command,
            args=args,
            cwd=cwd,
            env=env,
            client_name=self.client_name,
            client_version=self.client_version,
            start_timeout=timeout if timeout is not None else self.start_timeout,
            request_timeout=self.request_timeout,
        )
        try:
            session.start()
        except MCPPluginHandshakeError as e:
            plugin.status = MCPPluginStatus.ERROR
            plugin.error_message = str(e)
            logger.error(
                f"MCP handshake failed for plugin {plugin.manifest.name}: {e}"
            )
            return False

        plugin.session = session
        plugin.remote_tools = session.tools_discovered
        plugin.server_info = session.server_info
        plugin.status = MCPPluginStatus.RUNNING
        plugin.updated_at = datetime.now(UTC)
        logger.info(
            f"Started MCP stdio server for {plugin.manifest.name} "
            f"(server={plugin.server_info.get('server_name')} "
            f"protocol={plugin.server_info.get('protocol_version')} "
            f"tools={len(plugin.remote_tools)})"
        )
        return True

    def _terminate_transport(self, plugin: MCPPlugin) -> None:
        """终止插件的全部传输资源：MCP 会话 + 兼容旧 Popen。"""
        session = plugin.session
        if session is not None:
            try:
                session.stop()
            except Exception as e:  # pragma: no cover
                logger.warning(f"Session stop raised (suppressed): {e}")
            plugin.session = None
        process = plugin.process
        if process is not None:  # 兼容旧调用方直接注入的 Popen
            with contextlib.suppress(Exception):
                process.terminate()
                try:
                    process.wait(timeout=5)
                except subprocess.TimeoutExpired:
                    process.kill()
                    process.wait()
            plugin.process = None

    def stop_server(self, plugin: MCPPlugin) -> bool:
        """Stop MCP server for plugin（含 stdio 关停序列与进程清理）。"""
        if (
            plugin.status != MCPPluginStatus.RUNNING
            and plugin.session is None
            and plugin.process is None
        ):
            logger.warning(f"Plugin {plugin.manifest.name} is not running")
            return True

        try:
            plugin.status = MCPPluginStatus.UNLOADING
            plugin.updated_at = datetime.now(UTC)

            self._terminate_transport(plugin)

            plugin.status = MCPPluginStatus.STOPPED
            logger.info(f"Stopped MCP server for {plugin.manifest.name}")
            return True

        except Exception as e:
            plugin.status = MCPPluginStatus.ERROR
            plugin.error_message = str(e)
            logger.error(f"Failed to stop server for {plugin.manifest.name}: {e}")
            return False

    def call_tool(self, plugin: MCPPlugin, tool_name: str, args: dict[str, Any]) -> Any:
        """Call a tool provided by the plugin（经 stdio MCP ``tools/call``）。

        契约：工具须在 manifest.tools 中声明（manifest 是信任边界，输入
        按 input_schema.required 校验）；随后路由到插件进程的真实 MCP 调用。

        Raises:
            RuntimeError: 插件未运行 / 会话不可用（进程退出等，可诊断）。
            ValueError: 工具未声明、必填参数缺失，或远端返回 isError=True。
        """
        if plugin.status != MCPPluginStatus.RUNNING or plugin.session is None:
            state = (
                "not running"
                if plugin.status != MCPPluginStatus.RUNNING
                else "MCP session lost"
            )
            raise RuntimeError(
                f"Plugin {plugin.manifest.name} is {state} "
                f"(status={plugin.status.value}); start() the plugin first"
            )

        # Find tool definition（manifest 声明为信任边界）
        tool_def = None
        for tool in plugin.manifest.tools:
            if tool.get("name") == tool_name:
                tool_def = tool
                break

        if not tool_def:
            raise ValueError(f"Tool not found: {tool_name}")

        # Validate input schema
        self._validate_tool_input(tool_def, args)

        try:
            return plugin.session.call_tool(tool_name, args)
        except MCPPluginTransportError as e:
            # 进程退出/传输断开：插件进入 ERROR，显式暴露原因
            plugin.status = MCPPluginStatus.ERROR
            plugin.error_message = str(e)
            plugin.updated_at = datetime.now(UTC)
            raise
        except MCPPluginToolError:
            raise  # 远端工具级失败，插件保持 RUNNING

    def list_remote_tools(self, plugin: MCPPlugin) -> list[dict[str, Any]]:
        """实时 tools/list（刷新 plugin.remote_tools 缓存）。"""
        if plugin.session is None:
            raise RuntimeError(
                f"Plugin {plugin.manifest.name} has no MCP session "
                f"(status={plugin.status.value})"
            )
        tools = plugin.session.list_tools()
        plugin.remote_tools = tools
        plugin.updated_at = datetime.now(UTC)
        return tools

    def get_resources(self, plugin: MCPPlugin) -> list[dict[str, Any]]:
        """Get resources provided by plugin"""
        if not plugin.manifest.capabilities.resources:
            return []

        return plugin.manifest.resources

    def get_tools(self, plugin: MCPPlugin) -> list[dict[str, Any]]:
        """Get tools provided by plugin"""
        if not plugin.manifest.capabilities.tools:
            return []

        return plugin.manifest.tools

    def update_config(self, plugin: MCPPlugin, config: dict[str, Any]) -> bool:
        """Update plugin configuration"""
        try:
            # Validate configuration
            self._validate_config(plugin.manifest, config)

            plugin.config.update(config)
            plugin.updated_at = datetime.now(UTC)
            logger.info(f"Updated config for plugin {plugin.manifest.name}")
            return True

        except Exception as e:
            logger.error(f"Failed to update config for {plugin.manifest.name}: {e}")
            return False

    def get_plugin(self, plugin_id: str) -> MCPPlugin | None:
        """Get plugin by ID"""
        with self._lock:
            return self._plugins.get(plugin_id)

    def list_plugins(self) -> list[MCPPlugin]:
        """List all loaded plugins"""
        with self._lock:
            return list(self._plugins.values())

    def unload_plugin(self, plugin_id: str) -> bool:
        """Unload a plugin"""
        plugin = self.get_plugin(plugin_id)
        if not plugin:
            return False

        try:
            # Stop server if running
            if plugin.status == MCPPluginStatus.RUNNING:
                self.stop_server(plugin)

            with self._lock:
                del self._plugins[plugin_id]

            logger.info(f"Unloaded plugin {plugin.manifest.name}")
            return True

        except Exception as e:
            logger.error(f"Failed to unload plugin {plugin_id}: {e}")
            return False

    # Helper methods

    @staticmethod
    def _is_valid_semver(version: str) -> bool:
        """Check if version is valid semantic version"""
        import re
        pattern = r"^\d+\.\d+\.\d+(-[a-zA-Z0-9]+)?(\+[a-zA-Z0-9]+)?$"
        return bool(re.match(pattern, version))

    @staticmethod
    def _is_valid_version_range(version_range: dict[str, str]) -> bool:
        """Check if version range is valid"""
        min_v = version_range.get("min_version")
        max_v = version_range.get("max_version")

        if not min_v or not max_v:
            return False

        if not MCPPluginAdapter._is_valid_semver(min_v):
            return False

        if not MCPPluginAdapter._is_valid_semver(max_v):
            return False

        return MCPPluginAdapter._compare_versions(min_v, max_v) <= 0

    @staticmethod
    def _version_in_range(version: str, min_v: str, max_v: str) -> bool:
        """Check if version is in range"""
        return (MCPPluginAdapter._compare_versions(version, min_v) >= 0 and
                MCPPluginAdapter._compare_versions(version, max_v) <= 0)

    @staticmethod
    def _compare_versions(v1: str, v2: str) -> int:
        """Compare two semantic versions. Returns -1 if v1 < v2, 0 if equal, 1 if v1 > v2"""
        def parse_version(v):
            parts = v.split("-")[0].split("+")[0].split(".")
            return tuple(int(p) for p in parts)

        p1 = parse_version(v1)
        p2 = parse_version(v2)

        if p1 < p2:
            return -1
        elif p1 > p2:
            return 1
        else:
            return 0

    @staticmethod
    def _check_python_version(requirement: str) -> bool:
        """Check if current Python version meets requirement"""
        import re
        current = sys.version_info

        # Parse requirement like ">=3.11" or "3.8"
        match = re.match(r"([><=!]+)?(\d+\.\d+)", requirement)
        if not match:
            return True

        op = match.group(1) or ">="
        required = tuple(int(x) for x in match.group(2).split("."))

        if op == ">=":
            return (current.major, current.minor) >= required
        elif op == ">":
            return (current.major, current.minor) > required
        elif op == "<=":
            return (current.major, current.minor) <= required
        elif op == "<":
            return (current.major, current.minor) < required
        elif op == "==":
            return (current.major, current.minor) == required
        elif op == "!=":
            return (current.major, current.minor) != required

        return True

    @staticmethod
    def _validate_tool_input(tool_def: dict[str, Any], args: dict[str, Any]) -> None:
        """Validate tool input against schema"""
        schema = tool_def.get("input_schema", {})
        required = schema.get("required", [])

        for field_name in required:
            if field_name not in args:
                raise ValueError(f"Required field missing: {field_name}")

    @staticmethod
    def _validate_config(manifest: MCPManifest, config: dict[str, Any]) -> None:
        """Validate configuration against manifest"""
        config_schema = manifest.configuration

        for key, value in config.items():
            if key not in config_schema:
                raise ValueError(f"Unknown configuration key: {key}")

            field_schema = config_schema[key]
            expected_type = field_schema.get("type")

            # Type validation
            if expected_type == "string" and not isinstance(value, str):
                raise ValueError(f"Configuration {key} must be string")
            elif expected_type == "integer" and not isinstance(value, int):
                raise ValueError(f"Configuration {key} must be integer")
            elif expected_type == "boolean" and not isinstance(value, bool):
                raise ValueError(f"Configuration {key} must be boolean")

        # Check required fields
        for key, field_schema in config_schema.items():
            if field_schema.get("required") and key not in config:
                raise ValueError(f"Required configuration missing: {key}")
