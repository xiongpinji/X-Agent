"""File System MCP Plugin - 真实 stdio MCP server（官方 ``mcp`` SDK FastMCP）

迁移说明（原为普通 Python 类占位，握手必然失败）：

- 本模块既是插件子进程入口（``python -m main``，stdio MCP server），也保留
  ``FileSystemPlugin`` 入口类供 PluginRuntime.inspect_entrypoint() 进程内
  真实验证（导入模块 → 实例化 → 比对 manifest 声明工具）。工具实现只有
  一份：类方法；FastMCP 注册的是同一组方法。
- 配置注入契约：从 ``XAGENT_PLUGIN_CONFIG`` 环境变量读取 JSON 对象配置
  （由 X-Agent 运行时经官方 SDK 与默认安全 env 合并注入）。
- fail-closed 契约：``allowed_paths`` 未配置/为空时，进程在进入 MCP 循环
  前向 stderr 输出诊断并以码 2 退出（握手失败，可诊断），绝不以"可访问
  任意路径"或"空插件"姿态伪造可用。
- 信任边界：所有工具的路径参数必须落在 ``allowed_paths`` 之内（resolve 后
  逐段前缀匹配，Windows 大小写不敏感）；越界一律拒绝。

进程内使用（不经 MCP）::

    from main import FileSystemPlugin
    plugin = FileSystemPlugin({"allowed_paths": ["D:/data"]})
    await plugin.read_file("D:/data/a.txt")
"""

from __future__ import annotations

import json
import logging
import os
import sys
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, NoReturn

logger = logging.getLogger(__name__)

# 与 backend.app.core.mcp_plugin_adapter.PLUGIN_CONFIG_ENV_VAR 保持一致
CONFIG_ENV_VAR = "XAGENT_PLUGIN_CONFIG"
PLUGIN_NAME = "filesystem-mcp"


class FileSystemPlugin:
    """File System MCP Plugin Server（工具实现本体，供 FastMCP 注册）"""

    def __init__(self, config: dict[str, Any] | None = None):
        """Initialize File System plugin"""
        self.config = config or {}
        raw_allowed = self.config.get("allowed_paths") or []
        if not isinstance(raw_allowed, (list, tuple)) or not raw_allowed:
            raise ValueError(
                "allowed_paths is required (non-empty list of directories); "
                "without it the plugin refuses to start (fail-closed)"
            )
        self.max_file_size_mb = self.config.get("max_file_size_mb", 100)
        self.enable_write = self.config.get("enable_write", True)

        # Normalize to resolved Path objects (the trust boundary)
        self.allowed_paths = [Path(p).expanduser().resolve() for p in raw_allowed]

        logger.info(
            "FileSystemPlugin initialized with %d allowed path(s)", len(self.allowed_paths)
        )

    # ------------------------------------------------------------------
    # 信任边界（路径越界拒绝）
    # ------------------------------------------------------------------

    def _is_path_allowed(self, file_path: str | Path) -> bool:
        """路径必须解析后落在任一 allowed_paths 内（Windows 大小写不敏感）"""
        try:
            resolved = Path(file_path).expanduser().resolve()
        except (OSError, ValueError, RuntimeError):
            return False
        resolved_key = os.path.normcase(str(resolved))
        for allowed in self.allowed_paths:
            allowed_key = os.path.normcase(str(allowed))
            if resolved_key == allowed_key or resolved_key.startswith(
                allowed_key.rstrip("\\/") + os.sep
            ):
                return True
        return False

    def _check(self, file_path: str, *, write: bool = False) -> dict[str, Any] | None:
        """统一前置校验：返回错误 dict（软失败）或 None（通过）"""
        if write and not self.enable_write:
            return {"status": "error", "message": "Write operations are disabled"}
        if not self._is_path_allowed(file_path):
            return {
                "status": "error",
                "message": f"Path not allowed (outside allowed_paths): {file_path}",
            }
        return None

    # ------------------------------------------------------------------
    # 工具实现（与 manifest.tools 一一对应）
    # ------------------------------------------------------------------

    async def read_file(self, path: str, encoding: str = "utf-8") -> dict[str, Any]:
        """Read file content"""
        try:
            denied = self._check(path)
            if denied:
                return denied

            file_path = Path(path).expanduser().resolve()

            if not file_path.exists():
                return {"status": "error", "message": f"File not found: {path}"}
            if not file_path.is_file():
                return {"status": "error", "message": f"Not a file: {path}"}

            file_size_mb = file_path.stat().st_size / (1024 * 1024)
            if file_size_mb > self.max_file_size_mb:
                return {
                    "status": "error",
                    "message": (
                        f"File too large: {file_size_mb:.2f}MB "
                        f"(max: {self.max_file_size_mb}MB)"
                    ),
                }

            with open(file_path, "r", encoding=encoding) as f:
                content = f.read()

            return {
                "status": "success",
                "data": {
                    "path": str(file_path),
                    "content": content,
                    "size": len(content),
                    "encoding": encoding,
                },
            }
        except Exception as e:
            logger.error(f"Read file error: {e}")
            return {"status": "error", "message": f"Read file error: {e}"}

    async def write_file(
        self, path: str, content: str, append: bool = False
    ) -> dict[str, Any]:
        """Write content to file"""
        try:
            denied = self._check(path, write=True)
            if denied:
                return denied

            file_path = Path(path).expanduser().resolve()

            content_mb = len(content.encode("utf-8", errors="replace")) / (1024 * 1024)
            if content_mb > self.max_file_size_mb:
                return {
                    "status": "error",
                    "message": (
                        f"Content too large: {content_mb:.2f}MB "
                        f"(max: {self.max_file_size_mb}MB)"
                    ),
                }

            file_path.parent.mkdir(parents=True, exist_ok=True)

            mode = "a" if append else "w"
            with open(file_path, mode, encoding="utf-8") as f:
                f.write(content)

            return {
                "status": "success",
                "data": {
                    "path": str(file_path),
                    "size": len(content),
                    "mode": "append" if append else "write",
                },
            }
        except Exception as e:
            logger.error(f"Write file error: {e}")
            return {"status": "error", "message": f"Write file error: {e}"}

    async def list_files(self, path: str, recursive: bool = False) -> dict[str, Any]:
        """List files in directory"""
        try:
            denied = self._check(path)
            if denied:
                return denied

            dir_path = Path(path).expanduser().resolve()

            if not dir_path.exists():
                return {"status": "error", "message": f"Directory not found: {path}"}
            if not dir_path.is_dir():
                return {"status": "error", "message": f"Not a directory: {path}"}

            files = []
            items = dir_path.rglob("*") if recursive else dir_path.iterdir()

            for item in items:
                try:
                    stat = item.stat()
                    files.append({
                        "name": item.name,
                        "path": str(item),
                        "type": "directory" if item.is_dir() else "file",
                        "size": stat.st_size,
                        "modified": datetime.fromtimestamp(stat.st_mtime, UTC).isoformat(),
                    })
                except OSError as e:
                    logger.warning(f"Error listing {item}: {e}")

            return {
                "status": "success",
                "data": sorted(files, key=lambda x: x["name"]),
                "count": len(files),
            }
        except Exception as e:
            logger.error(f"List files error: {e}")
            return {"status": "error", "message": f"List files error: {e}"}

    async def search_files(
        self, path: str, pattern: str, recursive: bool = True
    ) -> dict[str, Any]:
        """Search files by glob pattern"""
        try:
            denied = self._check(path)
            if denied:
                return denied

            dir_path = Path(path).expanduser().resolve()

            if not dir_path.exists():
                return {"status": "error", "message": f"Directory not found: {path}"}
            if not dir_path.is_dir():
                return {"status": "error", "message": f"Not a directory: {path}"}

            files = []
            items = dir_path.rglob(pattern) if recursive else dir_path.glob(pattern)

            for item in items:
                try:
                    stat = item.stat()
                    files.append({
                        "name": item.name,
                        "path": str(item),
                        "type": "directory" if item.is_dir() else "file",
                        "size": stat.st_size,
                        "modified": datetime.fromtimestamp(stat.st_mtime, UTC).isoformat(),
                    })
                except OSError as e:
                    logger.warning(f"Error searching {item}: {e}")

            return {
                "status": "success",
                "data": sorted(files, key=lambda x: x["name"]),
                "count": len(files),
            }
        except Exception as e:
            logger.error(f"Search files error: {e}")
            return {"status": "error", "message": f"Search files error: {e}"}

    async def delete_file(self, path: str) -> dict[str, Any]:
        """Delete a file"""
        try:
            denied = self._check(path, write=True)
            if denied:
                return denied

            file_path = Path(path).expanduser().resolve()

            if not file_path.exists():
                return {"status": "error", "message": f"File not found: {path}"}
            if not file_path.is_file():
                return {"status": "error", "message": f"Not a file: {path}"}

            file_path.unlink()

            return {
                "status": "success",
                "data": {"path": str(file_path), "message": "File deleted"},
            }
        except Exception as e:
            logger.error(f"Delete file error: {e}")
            return {"status": "error", "message": f"Delete file error: {e}"}

    async def get_file_info(self, path: str) -> dict[str, Any]:
        """Get file information (size, timestamps, permissions)"""
        try:
            denied = self._check(path)
            if denied:
                return denied

            file_path = Path(path).expanduser().resolve()

            if not file_path.exists():
                return {"status": "error", "message": f"File not found: {path}"}

            stat = file_path.stat()

            return {
                "status": "success",
                "data": {
                    "path": str(file_path),
                    "name": file_path.name,
                    "type": "directory" if file_path.is_dir() else "file",
                    "size": stat.st_size,
                    "size_mb": stat.st_size / (1024 * 1024),
                    "created": datetime.fromtimestamp(stat.st_ctime, UTC).isoformat(),
                    "modified": datetime.fromtimestamp(stat.st_mtime, UTC).isoformat(),
                    "accessed": datetime.fromtimestamp(stat.st_atime, UTC).isoformat(),
                    "permissions": oct(stat.st_mode)[-3:],
                },
            }
        except Exception as e:
            logger.error(f"Get file info error: {e}")
            return {"status": "error", "message": f"Get file info error: {e}"}


# ----------------------------------------------------------------------
# stdio MCP server 入口（python -m main）
# ----------------------------------------------------------------------

def _fail_closed(message: str) -> NoReturn:
    """输出可诊断错误并退出（不进入 MCP 循环，握手 fail-closed）。

    附加短暂停顿让宿主进程的 stderr 捕获线程把管道排空，确保诊断信息
    出现在握手错误消息中。
    """
    import time

    sys.stderr.write(f"[{PLUGIN_NAME}] fail-closed: {message}\n")
    sys.stderr.write(
        f"[{PLUGIN_NAME}] configure this plugin via the {CONFIG_ENV_VAR} "
        "environment variable (JSON object; provided by the X-Agent plugin "
        "runtime, e.g. PluginRuntime.start(name, config={...})).\n"
    )
    sys.stderr.flush()
    time.sleep(0.25)
    raise SystemExit(2)


def load_config_from_env() -> dict[str, Any]:
    """从约定环境变量读取 JSON 配置（缺失返回空 dict，由插件自行校验）。"""
    raw = (os.environ.get(CONFIG_ENV_VAR) or "").strip()
    if not raw:
        return {}
    try:
        parsed = json.loads(raw)
    except json.JSONDecodeError as e:
        _fail_closed(f"{CONFIG_ENV_VAR} is not valid JSON: {e}")
    if not isinstance(parsed, dict):
        _fail_closed(
            f"{CONFIG_ENV_VAR} must be a JSON object, got {type(parsed).__name__}"
        )
    return parsed


def build_server(config: dict[str, Any]) -> Any:
    """构建 FastMCP stdio server（工具 = FileSystemPlugin 类方法）。"""
    from mcp.server.fastmcp import FastMCP

    plugin = FileSystemPlugin(config)

    mcp = FastMCP(PLUGIN_NAME)

    mcp.tool()(plugin.read_file)
    mcp.tool()(plugin.write_file)
    mcp.tool()(plugin.list_files)
    mcp.tool()(plugin.search_files)
    mcp.tool()(plugin.delete_file)
    mcp.tool()(plugin.get_file_info)

    return mcp


def main() -> None:
    # stderr 诊断用 UTF-8（宿主按 UTF-8 解码 stderr 尾部）
    if sys.stderr and hasattr(sys.stderr, "reconfigure"):
        sys.stderr.reconfigure(encoding="utf-8", errors="replace")

    config = load_config_from_env()

    if not config.get("allowed_paths"):
        _fail_closed(
            "required configuration 'allowed_paths' is missing or empty "
            "(type: array of directory paths)"
        )

    try:
        server = build_server(config)
    except ValueError as e:
        _fail_closed(str(e))

    server.run()  # stdio 传输：stdin/stdout JSON-RPC，日志走 stderr


if __name__ == "__main__":
    main()
