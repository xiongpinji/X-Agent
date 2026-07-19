"""插件适配器 - 解析、验证、安装和管理插件"""

from __future__ import annotations

import json
import logging
import subprocess
import sys
from pathlib import Path
from typing import Optional, Any
from dataclasses import dataclass
from enum import Enum

logger = logging.getLogger(__name__)


class PluginCompatibility(str, Enum):
    """兼容性状态"""
    COMPATIBLE = "compatible"
    PARTIALLY_COMPATIBLE = "partially_compatible"
    INCOMPATIBLE = "incompatible"


@dataclass
class CompatibilityReport:
    """兼容性报告"""
    status: PluginCompatibility
    issues: list[str]
    warnings: list[str]
    recommendations: list[str]


class PluginAdapter:
    """插件适配器 - 处理插件的解析、验证和安装"""

    def __init__(self, plugins_dir: str | Path = "./plugins"):
        self.plugins_dir = Path(plugins_dir)
        self.plugins_dir.mkdir(parents=True, exist_ok=True)

    def parse_manifest(self, manifest_path: str | Path) -> Optional[dict[str, Any]]:
        """解析插件manifest文件"""
        try:
            manifest_path = Path(manifest_path)
            if not manifest_path.exists():
                logger.error(f"Manifest file not found: {manifest_path}")
                return None

            with open(manifest_path) as f:
                manifest = json.load(f)

            logger.info(f"Parsed manifest: {manifest.get('name', 'unknown')}")
            return manifest

        except Exception as e:
            logger.error(f"Failed to parse manifest: {e}")
            return None

    def validate_manifest(self, manifest: dict[str, Any]) -> CompatibilityReport:
        """验证manifest的有效性"""
        issues = []
        warnings = []
        recommendations = []

        # 检查必需字段
        required_fields = ["name", "version", "entry_point"]
        for field in required_fields:
            if field not in manifest:
                issues.append(f"Missing required field: {field}")

        # 检查版本格式
        if "version" in manifest:
            version = manifest["version"]
            if not self._is_valid_version(version):
                warnings.append(f"Invalid version format: {version}")

        # 检查权限
        if "permissions" in manifest:
            permissions = manifest["permissions"]
            dangerous_perms = ["system:admin", "file:write:*", "network:*"]
            for perm in permissions:
                if perm in dangerous_perms:
                    warnings.append(f"Dangerous permission: {perm}")

        # 检查依赖
        if "dependencies" in manifest:
            deps = manifest["dependencies"]
            if not isinstance(deps, dict):
                issues.append("Dependencies must be a dictionary")

        # 生成建议
        if not manifest.get("description"):
            recommendations.append("Add a description to the manifest")
        if not manifest.get("author"):
            recommendations.append("Add author information")
        if not manifest.get("license"):
            recommendations.append("Specify a license")

        # 确定兼容性状态
        if issues:
            status = PluginCompatibility.INCOMPATIBLE
        elif warnings:
            status = PluginCompatibility.PARTIALLY_COMPATIBLE
        else:
            status = PluginCompatibility.COMPATIBLE

        return CompatibilityReport(
            status=status,
            issues=issues,
            warnings=warnings,
            recommendations=recommendations,
        )

    def check_dependencies(self, manifest: dict[str, Any]) -> CompatibilityReport:
        """检查插件依赖"""
        issues = []
        warnings = []
        recommendations = []

        dependencies = manifest.get("dependencies", {})

        for dep_name, dep_version in dependencies.items():
            # 检查依赖是否可用
            if not self._is_dependency_available(dep_name, dep_version):
                issues.append(f"Dependency not available: {dep_name}=={dep_version}")
                recommendations.append(f"Install {dep_name} or update to compatible version")

        # 检查系统要求
        if "system_requirements" in manifest:
            sys_reqs = manifest["system_requirements"]
            if not self._check_system_requirements(sys_reqs):
                warnings.append("System requirements not met")

        status = (
            PluginCompatibility.INCOMPATIBLE
            if issues
            else PluginCompatibility.COMPATIBLE
        )

        return CompatibilityReport(
            status=status,
            issues=issues,
            warnings=warnings,
            recommendations=recommendations,
        )

    def install_dependencies(self, manifest: dict[str, Any]) -> bool:
        """自动安装依赖"""
        try:
            dependencies = manifest.get("dependencies", {})

            for dep_name, dep_version in dependencies.items():
                logger.info(f"Installing dependency: {dep_name}=={dep_version}")

                # 使用pip安装Python依赖
                if dep_name.startswith("python:"):
                    package_name = dep_name.replace("python:", "")
                    subprocess.check_call(
                        [sys.executable, "-m", "pip", "install", f"{package_name}=={dep_version}"],
                        stdout=subprocess.DEVNULL,
                        stderr=subprocess.DEVNULL,
                    )
                    logger.info(f"Installed {package_name}")

            return True

        except Exception as e:
            logger.error(f"Failed to install dependencies: {e}")
            return False

    def install_plugin(
        self,
        plugin_id: str,
        plugin_path: str | Path,
        auto_install_deps: bool = True,
    ) -> tuple[bool, Optional[str]]:
        """安装插件"""
        try:
            plugin_path = Path(plugin_path)

            # 检查插件目录
            if not plugin_path.exists():
                return False, f"Plugin path not found: {plugin_path}"

            # 解析manifest
            manifest_file = plugin_path / "plugin.manifest.json"
            manifest = self.parse_manifest(manifest_file)
            if not manifest:
                return False, "Failed to parse manifest"

            # 验证manifest
            validation_report = self.validate_manifest(manifest)
            if validation_report.status == PluginCompatibility.INCOMPATIBLE:
                return False, f"Manifest validation failed: {validation_report.issues}"

            # 检查依赖
            dep_report = self.check_dependencies(manifest)
            if dep_report.status == PluginCompatibility.INCOMPATIBLE:
                if auto_install_deps:
                    if not self.install_dependencies(manifest):
                        return False, "Failed to install dependencies"
                else:
                    return False, f"Dependencies not met: {dep_report.issues}"

            # 复制插件到插件目录
            install_dir = self.plugins_dir / plugin_id
            if install_dir.exists():
                logger.warning(f"Plugin already installed: {plugin_id}")
            else:
                import shutil
                shutil.copytree(plugin_path, install_dir)
                logger.info(f"Plugin installed: {plugin_id}")

            return True, None

        except Exception as e:
            logger.error(f"Failed to install plugin: {e}")
            return False, str(e)

    def uninstall_plugin(self, plugin_id: str) -> tuple[bool, Optional[str]]:
        """卸载插件"""
        try:
            install_dir = self.plugins_dir / plugin_id

            if not install_dir.exists():
                return False, f"Plugin not found: {plugin_id}"

            import shutil
            shutil.rmtree(install_dir)
            logger.info(f"Plugin uninstalled: {plugin_id}")

            return True, None

        except Exception as e:
            logger.error(f"Failed to uninstall plugin: {e}")
            return False, str(e)

    def get_plugin_info(self, plugin_id: str) -> Optional[dict[str, Any]]:
        """获取插件信息"""
        try:
            install_dir = self.plugins_dir / plugin_id
            manifest_file = install_dir / "plugin.manifest.json"

            if not manifest_file.exists():
                return None

            return self.parse_manifest(manifest_file)

        except Exception as e:
            logger.error(f"Failed to get plugin info: {e}")
            return None

    @staticmethod
    def _is_valid_version(version: str) -> bool:
        """检查版本格式是否有效"""
        import re
        pattern = r"^\d+\.\d+\.\d+(-[a-zA-Z0-9]+)?$"
        return bool(re.match(pattern, version))

    @staticmethod
    def _is_dependency_available(dep_name: str, dep_version: str) -> bool:
        """检查依赖是否可用"""
        try:
            if dep_name.startswith("python:"):
                package_name = dep_name.replace("python:", "")
                subprocess.check_call(
                    [sys.executable, "-m", "pip", "show", package_name],
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.DEVNULL,
                )
                return True
            return True
        except Exception:
            return False

    @staticmethod
    def _check_system_requirements(sys_reqs: dict[str, Any]) -> bool:
        """检查系统要求"""
        import platform

        # 检查操作系统
        if "os" in sys_reqs:
            required_os = sys_reqs["os"]
            current_os = platform.system().lower()
            if current_os not in [os.lower() for os in required_os]:
                return False

        # 检查Python版本
        if "python_version" in sys_reqs:
            required_version = sys_reqs["python_version"]
            current_version = platform.python_version()
            if current_version < required_version:
                return False

        return True


class PluginIntegration:
    """插件整合系统 - 注册、加载和管理插件生命周期"""

    def __init__(self, plugins_dir: str | Path = "./plugins"):
        self.plugins_dir = Path(plugins_dir)
        self._loaded_plugins: dict[str, Any] = {}
        self._plugin_instances: dict[str, Any] = {}
        self._adapter = PluginAdapter(plugins_dir)

    def register_plugin(self, plugin_id: str, plugin_info: dict[str, Any]) -> bool:
        """注册插件"""
        try:
            self._loaded_plugins[plugin_id] = plugin_info
            logger.info(f"Plugin registered: {plugin_id}")
            return True
        except Exception as e:
            logger.error(f"Failed to register plugin: {e}")
            return False

    def load_plugin(self, plugin_id: str) -> tuple[bool, Optional[str]]:
        """加载插件"""
        try:
            plugin_info = self._adapter.get_plugin_info(plugin_id)
            if not plugin_info:
                return False, f"Plugin info not found: {plugin_id}"

            # 这里应该动态加载插件模块
            # 为了演示，我们只记录加载
            self._plugin_instances[plugin_id] = {
                "id": plugin_id,
                "info": plugin_info,
                "status": "loaded",
            }

            logger.info(f"Plugin loaded: {plugin_id}")
            return True, None

        except Exception as e:
            logger.error(f"Failed to load plugin: {e}")
            return False, str(e)

    def unload_plugin(self, plugin_id: str) -> tuple[bool, Optional[str]]:
        """卸载插件"""
        try:
            if plugin_id in self._plugin_instances:
                del self._plugin_instances[plugin_id]
                logger.info(f"Plugin unloaded: {plugin_id}")
                return True, None
            return False, f"Plugin not loaded: {plugin_id}"

        except Exception as e:
            logger.error(f"Failed to unload plugin: {e}")
            return False, str(e)

    def enable_plugin(self, plugin_id: str) -> tuple[bool, Optional[str]]:
        """启用插件"""
        try:
            if plugin_id not in self._plugin_instances:
                success, error = self.load_plugin(plugin_id)
                if not success:
                    return False, error

            self._plugin_instances[plugin_id]["status"] = "enabled"
            logger.info(f"Plugin enabled: {plugin_id}")
            return True, None

        except Exception as e:
            logger.error(f"Failed to enable plugin: {e}")
            return False, str(e)

    def disable_plugin(self, plugin_id: str) -> tuple[bool, Optional[str]]:
        """禁用插件"""
        try:
            if plugin_id in self._plugin_instances:
                self._plugin_instances[plugin_id]["status"] = "disabled"
                logger.info(f"Plugin disabled: {plugin_id}")
                return True, None
            return False, f"Plugin not found: {plugin_id}"

        except Exception as e:
            logger.error(f"Failed to disable plugin: {e}")
            return False, str(e)

    def get_plugin_status(self, plugin_id: str) -> Optional[dict[str, Any]]:
        """获取插件状态"""
        return self._plugin_instances.get(plugin_id)

    def list_loaded_plugins(self) -> list[dict[str, Any]]:
        """列出已加载的插件"""
        return list(self._plugin_instances.values())

    def execute_plugin_action(
        self,
        plugin_id: str,
        action: str,
        params: dict[str, Any] | None = None,
    ) -> tuple[bool, Any]:
        """执行插件操作"""
        try:
            plugin = self._plugin_instances.get(plugin_id)
            if not plugin:
                return False, f"Plugin not loaded: {plugin_id}"

            if plugin["status"] != "enabled":
                return False, f"Plugin not enabled: {plugin_id}"

            # 这里应该调用插件的实际方法
            # 为了演示，我们返回模拟结果
            result = {
                "plugin_id": plugin_id,
                "action": action,
                "params": params or {},
                "status": "success",
            }

            logger.info(f"Plugin action executed: {plugin_id}.{action}")
            return True, result

        except Exception as e:
            logger.error(f"Failed to execute plugin action: {e}")
            return False, str(e)
