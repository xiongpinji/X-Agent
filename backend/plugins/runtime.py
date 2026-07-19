"""插件运行时 - 扫描、加载、检查项目 plugins/ 目录

P1-12 决策：接线现存 MCP 插件框架（backend.app.core.mcp_plugin_adapter），
而非重做或放弃。旧插件框架（plugin_system 等 16 个模块）已归档至
archive/dead_code_2026-07-19/，本运行时不复用、不复活归档代码。

状态机（显式、无静默）：
- ``loadable``            manifest.json 通过 MCP manifest 校验，可加载
- ``loaded``              已通过 MCPPluginAdapter 加载进内存
- ``invalid``             manifest.json 存在但校验失败（附错误列表）
- ``legacy_unsupported``  仅含旧格式 plugin.manifest.json（归档框架格式），
                          本运行时不支持，待 Phase 3 迁移或重做
- ``no_manifest``         目录不含任何清单（examples/templates 等辅助目录）

诚实性说明：
- 本运行时不自动启动插件子进程（安全默认）；start() 仅做进程拉起，
  MCP 协议握手在 mcp_plugin_adapter 中仍是 TODO，调用方不得声称
  "插件工具已可通过 MCP 协议调用"。
- inspect_entrypoint() 提供进程内真实验证：导入入口模块并实例化入口类，
  比对 manifest 声明的 tools 与类方法，结果如实上报。
"""

from __future__ import annotations

import importlib.util
import json
import logging
import sys
import uuid
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Optional

from backend.app.core.mcp_plugin_adapter import (
    MCPManifest,
    MCPPlugin,
    MCPPluginAdapter,
    MCPPluginStatus,
)

logger = logging.getLogger(__name__)

# 旧格式清单文件名（归档框架使用）
LEGACY_MANIFEST_NAME = "plugin.manifest.json"
# MCP 清单文件名
MCP_MANIFEST_NAME = "manifest.json"
# 非插件辅助目录（扫描时显式归类）
AUX_DIRS = {"examples", "templates", "__pycache__"}


def get_default_plugins_dir() -> Path:
    """项目根 plugins/ 目录（相对本文件解析，不受 cwd 影响）"""
    return Path(__file__).resolve().parents[2] / "plugins"


@dataclass
class PluginInfo:
    """插件扫描/加载信息（JSON 可序列化）"""
    name: str                       # 目录名
    path: str
    format: str                     # "mcp" | "legacy" | "unknown"
    status: str                     # loadable/loaded/invalid/legacy_unsupported/no_manifest
    manifest_name: Optional[str] = None     # MCP manifest 中的 name
    manifest_version: Optional[str] = None
    display_name: Optional[str] = None
    description: Optional[str] = None
    tools: list[str] = field(default_factory=list)
    errors: list[str] = field(default_factory=list)
    detail: Optional[str] = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "path": self.path,
            "format": self.format,
            "status": self.status,
            "manifest_name": self.manifest_name,
            "manifest_version": self.manifest_version,
            "display_name": self.display_name,
            "description": self.description,
            "tools": self.tools,
            "errors": self.errors,
            "detail": self.detail,
        }


class PluginRuntime:
    """插件运行时：扫描 plugins/ 目录并管理 MCP 插件生命周期"""

    def __init__(self, plugins_dir: str | Path | None = None):
        self.plugins_dir = Path(plugins_dir) if plugins_dir else get_default_plugins_dir()
        self._adapter = MCPPluginAdapter(self.plugins_dir)
        self._loaded: dict[str, MCPPlugin] = {}   # dir_name -> MCPPlugin
        self._scan_cache: dict[str, PluginInfo] = {}

    # ---------- 扫描 ----------

    def scan(self, refresh: bool = False) -> list[PluginInfo]:
        """扫描插件目录，返回每个目录的显式状态（含失败原因）"""
        if self._scan_cache and not refresh:
            return [self._scan_cache[k] for k in sorted(self._scan_cache)]

        infos: dict[str, PluginInfo] = {}
        if not self.plugins_dir.is_dir():
            logger.warning(f"Plugins directory does not exist: {self.plugins_dir}")
            self._scan_cache = {}
            return []

        for entry in sorted(self.plugins_dir.iterdir()):
            if not entry.is_dir() or entry.name.startswith((".", "_")):
                continue
            infos[entry.name] = self._inspect_dir(entry)

        # 已加载插件的状态覆盖
        for dir_name in self._loaded:
            if dir_name in infos:
                infos[dir_name].status = "loaded"

        self._scan_cache = infos
        return [infos[k] for k in sorted(infos)]

    def _inspect_dir(self, path: Path) -> PluginInfo:
        """检查单个插件目录"""
        name = path.name
        mcp_manifest = path / MCP_MANIFEST_NAME
        legacy_manifest = path / LEGACY_MANIFEST_NAME

        if mcp_manifest.exists():
            info = PluginInfo(name=name, path=str(path), format="mcp", status="loadable")
            try:
                manifest = self._adapter.load_manifest(path)
                valid, errors = self._adapter.validate_manifest(manifest)
                info.manifest_name = manifest.name
                info.manifest_version = manifest.version
                info.display_name = manifest.metadata.get("display_name")
                info.description = manifest.metadata.get("description_zh") or manifest.metadata.get("description")
                info.tools = [t.get("name", "") for t in manifest.tools]
                if not valid:
                    info.status = "invalid"
                    info.errors = errors
            except Exception as e:
                info.status = "invalid"
                info.errors = [str(e)]
            return info

        if legacy_manifest.exists():
            detail = (
                "旧插件框架（plugin_system，已归档 archive/dead_code_2026-07-19）格式，"
                "当前 MCP 运行时不支持加载；待 Phase 3 迁移为 manifest.json 或重做。"
            )
            display = None
            try:
                data = json.loads(legacy_manifest.read_text(encoding="utf-8"))
                display = data.get("name")
            except Exception:
                pass
            return PluginInfo(
                name=name,
                path=str(path),
                format="legacy",
                status="legacy_unsupported",
                display_name=display,
                detail=detail,
            )

        if name in AUX_DIRS:
            return PluginInfo(
                name=name, path=str(path), format="unknown",
                status="no_manifest", detail="辅助目录（示例/模板），非插件包",
            )
        return PluginInfo(
            name=name, path=str(path), format="unknown",
            status="no_manifest", detail="目录中未找到 manifest.json 或 plugin.manifest.json",
        )

    # ---------- 加载 / 卸载 ----------

    def load(self, name: str) -> PluginInfo:
        """加载指定插件（仅 mcp 格式且校验通过）。

        Returns:
            PluginInfo（status=loaded 或附 errors 的失败状态，显式不静默）
        """
        path = self.plugins_dir / name
        info = self._inspect_dir(path) if path.is_dir() else PluginInfo(
            name=name, path=str(path), format="unknown",
            status="invalid", errors=[f"plugin directory not found: {path}"],
        )
        if info.status != "loadable" and name not in self._loaded:
            return info

        if name in self._loaded:
            info.status = "loaded"
            info.detail = "already loaded"
            return info

        try:
            plugin = self._adapter.load_plugin(path)
            # 现存适配器缺陷规避：MCPPlugin 是 dataclass 但 plugin_id /
            # created_at / updated_at 用 pydantic Field(default_factory=...)
            # 声明，dataclass 不会调用 default_factory，这些字段会变成
            # FieldInfo 对象（不可 JSON 序列化、无 isoformat）。
            # 此处显式修正为真实值，保证插件对象可安全使用与序列化。
            from datetime import UTC, datetime
            if not isinstance(plugin.plugin_id, str):
                plugin.plugin_id = str(uuid.uuid4())
            if not isinstance(plugin.created_at, datetime):
                plugin.created_at = datetime.now(UTC)
            if not isinstance(plugin.updated_at, datetime):
                plugin.updated_at = datetime.now(UTC)
            self._loaded[name] = plugin
            info.status = "loaded"
            info.detail = f"loaded (plugin_id={plugin.plugin_id})"
            self._scan_cache.pop(name, None)
            return info
        except Exception as e:
            logger.error(f"Failed to load plugin '{name}': {e}")
            info.status = "invalid"
            info.errors = [str(e)]
            return info

    def unload(self, name: str) -> bool:
        """卸载插件"""
        plugin = self._loaded.pop(name, None)
        if plugin is None:
            return False
        try:
            if plugin.status == MCPPluginStatus.RUNNING:
                self._adapter.stop_server(plugin)
        except Exception as e:
            logger.error(f"Error stopping plugin '{name}': {e}")
        self._scan_cache.pop(name, None)
        return True

    def load_all(self) -> list[PluginInfo]:
        """加载所有 loadable 插件，返回逐项结果（失败项显式标注）"""
        results = []
        for info in self.scan(refresh=True):
            if info.status == "loadable":
                results.append(self.load(info.name))
            else:
                results.append(info)
        return results

    def get_loaded(self, name: str) -> Optional[MCPPlugin]:
        return self._loaded.get(name)

    def list_loaded(self) -> list[str]:
        return list(self._loaded.keys())

    # ---------- 进程内功能验证 ----------

    def inspect_entrypoint(self, name: str, config: dict[str, Any] | None = None) -> dict[str, Any]:
        """进程内真实验证：导入入口模块、实例化入口类、比对 manifest tools。

        不启动子进程、不走 MCP 协议；结果如实上报（含 import/实例化失败）。
        """
        plugin = self._loaded.get(name)
        manifest: MCPManifest | None = plugin.manifest if plugin else None
        path = self.plugins_dir / name

        if manifest is None:
            try:
                manifest = self._adapter.load_manifest(path)
            except Exception as e:
                return {"name": name, "ok": False, "error": f"manifest load failed: {e}"}

        entry = manifest.entry_point
        if entry.type != "python":
            return {"name": name, "ok": False, "error": f"entry_point.type '{entry.type}' 暂不支持进程内检查"}

        module_file = path / f"{entry.module.replace('.', '/')}.py"
        if not module_file.exists():
            return {"name": name, "ok": False, "error": f"entry module not found: {module_file}"}

        module_name = f"xagent_plugin_inspect.{name.replace('-', '_')}"
        try:
            spec = importlib.util.spec_from_file_location(module_name, module_file)
            if spec is None or spec.loader is None:
                return {"name": name, "ok": False, "error": "failed to create module spec"}
            module = importlib.util.module_from_spec(spec)
            sys.modules[module_name] = module
            try:
                spec.loader.exec_module(module)
            finally:
                sys.modules.pop(module_name, None)
        except Exception as e:
            return {"name": name, "ok": False, "error": f"entry module import failed: {e}"}

        cls = getattr(module, entry.class_name, None)
        if cls is None:
            return {"name": name, "ok": False, "error": f"entry class '{entry.class_name}' not found in {module_file.name}"}

        try:
            instance = cls(config or self._default_config_for(manifest))
        except Exception as e:
            return {"name": name, "ok": False, "error": f"entry class init failed: {e}"}

        declared = [t.get("name") for t in manifest.tools]
        implemented = {t: callable(getattr(instance, t, None)) for t in declared}
        missing = [t for t, ok in implemented.items() if not ok]

        return {
            "name": name,
            "ok": not missing,
            "entry_class": entry.class_name,
            "declared_tools": declared,
            "implemented_tools": implemented,
            "missing_tools": missing,
        }

    @staticmethod
    def _default_config_for(manifest: MCPManifest) -> dict[str, Any]:
        """从 manifest configuration 构造默认配置（仅取 default 值）"""
        config: dict[str, Any] = {}
        for key, spec in manifest.configuration.items():
            if isinstance(spec, dict) and "default" in spec:
                config[key] = spec["default"]
        return config

    # ---------- 子进程（安全默认：不自动启动） ----------

    def start(self, name: str) -> dict[str, Any]:
        """拉起插件子进程。

        注意：仅进程级拉起；MCP 协议握手在适配器中仍是 TODO，
        返回结果显式标注该限制，不得据此声称工具已可经 MCP 调用。
        """
        plugin = self._loaded.get(name)
        if plugin is None:
            return {"name": name, "ok": False, "error": "plugin not loaded; call load() first"}
        ok = self._adapter.start_server(plugin)
        return {
            "name": name,
            "ok": ok,
            "status": plugin.status.value,
            "pid": plugin.process.pid if plugin.process else None,
            "error": plugin.error_message,
            "limitation": "MCP 协议握手未实现（mcp_plugin_adapter TODO）；仅验证进程可拉起",
        }

    def stop(self, name: str) -> dict[str, Any]:
        """停止插件子进程"""
        plugin = self._loaded.get(name)
        if plugin is None:
            return {"name": name, "ok": False, "error": "plugin not loaded"}
        ok = self._adapter.stop_server(plugin)
        return {"name": name, "ok": ok, "status": plugin.status.value, "error": plugin.error_message}


# 全局运行时实例（惰性）
_runtime: PluginRuntime | None = None


def get_plugin_runtime() -> PluginRuntime:
    """获取全局插件运行时（默认指向项目根 plugins/）"""
    global _runtime
    if _runtime is None:
        _runtime = PluginRuntime()
    return _runtime


__all__ = [
    "PluginRuntime",
    "PluginInfo",
    "get_plugin_runtime",
    "get_default_plugins_dir",
]
