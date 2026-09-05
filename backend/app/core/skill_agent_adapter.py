"""技能 → AgentLoop 工具注册适配器（主循环消费接口）

P1-11 交付物：把"唯一技能运行时"（backend.app.core.skills）中加载的技能
桥接为 AgentLoop 可消费的工具。

集成波接线方式（本模块不自作主张接线，仅供调用）::

    from backend.app.core.skill_agent_adapter import register_skills_into_tool_registry

    # 在构建 AgentLoop 的 ToolRegistry 之后、启动主循环之前：
    registered_names = await register_skills_into_tool_registry(tool_registry)
    # 此后 AgentLoop 即可通过 "skill__<skill-name>" 工具名调用技能。

设计要点：
- 工具名统一加 ``skill__`` 前缀，避免与内置工具冲突；
- handler 签名为 ``async (**kwargs) -> dict``，与 ToolRegistry 的
  ``await tool.handler(**arguments)`` 调用约定一致；
- 技能的 ``parameters_schema`` 类属性（可选）作为 LLM 可见的参数 schema；
  未声明时退化为宽松 object schema；
- 执行失败返回 ``{"success": False, "error": ...}``，显式失败，不静默；
- 租户/用户：ToolRegistry 调用 handler 时不会传入 RunContext，
  集成方如需租户隔离，可用 ``functools.partial`` 或闭包把
  ``context_defaults={"tenant_id": ..., "user_id": ...}`` 注入
  ``build_skill_tool_handler``。
"""

from __future__ import annotations

import logging
import time
import uuid
from collections.abc import Awaitable, Callable
from typing import Any

from backend.app.core.skills import Skill, SkillContext, SkillLoader

logger = logging.getLogger(__name__)

# 技能工具名前缀：skill__<skill-name>
SKILL_TOOL_PREFIX = "skill__"

# 技能工具的默认风险级别（与 backend.app.core.tools.RiskLevel 取值一致，
# 此处用字符串避免硬依赖；register_skills_into_tool_registry 会解析为枚举）
DEFAULT_SKILL_RISK_LEVEL = "LOW"

# 技能工具的默认授权 scope（RBAC 中真实存在；admin 持 tools:* 通配）
DEFAULT_SKILL_REQUIRED_SCOPE = "tools:read"


def skill_tool_name(skill_name: str) -> str:
    """技能名 → 工具名（加前缀）"""
    return f"{SKILL_TOOL_PREFIX}{skill_name}"


def skill_name_from_tool(tool_name: str) -> str | None:
    """工具名 → 技能名；非技能工具返回 None"""
    if tool_name.startswith(SKILL_TOOL_PREFIX):
        return tool_name[len(SKILL_TOOL_PREFIX):]
    return None


def get_skill_parameters_schema(skill: Skill) -> dict[str, Any]:
    """获取技能的参数 schema（未声明时退化为宽松 object）"""
    schema = getattr(skill, "parameters_schema", None)
    if isinstance(schema, dict) and schema:
        return schema
    return {"type": "object", "properties": {}, "additionalProperties": True}


async def list_skill_tools(loader: SkillLoader | None = None) -> list[dict[str, Any]]:
    """列出所有可消费的技能工具描述。

    返回: [{name, description, parameters_schema, risk_level, required_scope, skill_name}]
    未加载的技能不在列表中；加载失败原因见 loader.load_report。
    """
    loader = loader or SkillLoader()
    if not loader.list_loaded_skills():
        await loader.load_all_skills()

    tools: list[dict[str, Any]] = []
    for skill_name in loader.list_loaded_skills():
        skill = loader.get_skill(skill_name)
        if skill is None:
            continue
        metadata = skill.metadata
        tools.append({
            "name": skill_tool_name(metadata.name),
            "skill_name": metadata.name,
            "description": metadata.description or f"Skill: {metadata.name}",
            "parameters_schema": get_skill_parameters_schema(skill),
            "risk_level": DEFAULT_SKILL_RISK_LEVEL,
            "required_scope": DEFAULT_SKILL_REQUIRED_SCOPE,
        })
    return tools


def build_skill_tool_handler(
    skill_name: str,
    loader: SkillLoader | None = None,
    context_defaults: dict[str, str | None] | None = None,
) -> Callable[..., Awaitable[dict[str, Any]]]:
    """为指定技能构建 ToolRegistry 兼容的 handler（async (**kwargs) -> dict）。

    Args:
        skill_name: 技能名称
        loader: 技能加载器（缺省新建并按默认目录加载）
        context_defaults: 注入 SkillContext 的默认 tenant_id/user_id/metadata
    """
    defaults = dict(context_defaults or {})

    async def _handler(**kwargs: Any) -> dict[str, Any]:
        nonlocal loader
        if loader is None:
            loader = SkillLoader()
            await loader.load_all_skills()

        skill = loader.get_skill(skill_name)
        if skill is None:
            report = loader.load_report.get(skill_name, {})
            return {
                "success": False,
                "error": f"Skill not loaded: {skill_name} "
                         f"(reason: {report.get('error') or 'not found'})",
            }

        context = SkillContext(
            skill_name=skill_name,
            execution_id=str(uuid.uuid4()),
            tenant_id=kwargs.pop("_tenant_id", None) or defaults.get("tenant_id"),
            user_id=kwargs.pop("_user_id", None) or defaults.get("user_id"),
            metadata=dict(defaults.get("metadata") or {}),
        )

        started = time.perf_counter()
        outcome_success: bool | None = None  # None = 基础设施失败，不计 usage
        try:
            if not await skill.validate(context, **kwargs):
                outcome_success = False
                return {"success": False, "error": f"Skill input validation failed: {skill_name}"}
            result = await skill.execute(context, **kwargs)
            outcome_success = bool(result.success)
        except Exception as e:  # 技能异常显式上抛为失败结果，不静默
            logger.error(f"Skill '{skill_name}' raised: {e}", exc_info=True)
            outcome_success = False
            return {"success": False, "error": f"Skill '{skill_name}' execution error: {e}"}
        finally:
            # P2-12: usage 反哺进化引擎（best-effort，绝不影响技能执行结果）。
            # 低成功率（needs_improvement）触发的自改进依赖这里的数据源。
            if outcome_success is not None:
                try:
                    from backend.app.core.evolution_engine import (
                        evolution_engine as _evolution_engine,
                    )

                    await _evolution_engine.record_skill_usage(
                        skill_name,
                        outcome_success,
                        execution_context={
                            "skill": skill_name,
                            "execution_id": context.execution_id,
                            "tenant_id": context.tenant_id,
                        },
                    )
                except Exception as usage_exc:
                    logger.debug(
                        "Skill usage recording failed (non-blocking): %s", usage_exc
                    )

        return {
            "success": result.success,
            "data": result.data,
            "error": result.error,
            "execution_time": result.execution_time or (time.perf_counter() - started),
            "metadata": result.metadata,
        }

    _handler.__name__ = f"skill_handler_{skill_name.replace('-', '_')}"
    return _handler


async def register_skills_into_tool_registry(
    tool_registry: Any,
    loader: SkillLoader | None = None,
    context_defaults: dict[str, str | None] | None = None,
) -> list[str]:
    """把所有已加载技能注册进 AgentLoop 的 ToolRegistry（集成波入口）。

    Args:
        tool_registry: backend.app.core.tools.ToolRegistry 实例
        loader: 技能加载器（缺省新建并按默认目录 skills/ + custom-skills/ 加载）
        context_defaults: 注入 SkillContext 的默认 tenant_id/user_id

    Returns:
        注册成功的工具名列表（"skill__<name>"）。
        加载失败的技能不会注册，失败原因见 loader.load_report（显式，不静默）。
    """
    loader = loader or SkillLoader()
    if not loader.list_loaded_skills():
        await loader.load_all_skills()

    registered: list[str] = []
    for skill_name in loader.list_loaded_skills():
        skill = loader.get_skill(skill_name)
        if skill is None:
            continue
        if _register_skill_tool(tool_registry, skill, loader, context_defaults):
            registered.append(skill_tool_name(skill.metadata.name))

    return registered


async def register_skill_into_tool_registry(
    tool_registry: Any,
    skill_name: str,
    loader: SkillLoader | None = None,
    context_defaults: dict[str, str | None] | None = None,
    base_dir: str | None = None,
    reload: bool = False,
) -> bool:
    """增量注册单个技能（P2-12: 技能自沉淀 promote 最后一公里）。

    与 :func:`register_skills_into_tool_registry` 的区别：
    - 只处理一个技能，不做全目录扫描；
    - ``base_dir`` 指定加载目录（如自沉淀引擎的 custom-skills/ 隔离目录）；
    - ``reload=True`` 时先卸载再加载，热更新磁盘上的新版本
      （evolution_engine 自改进产物落盘后经此生效）。

    Args:
        tool_registry: backend.app.core.tools.ToolRegistry 实例
        skill_name: 技能名（目录名）
        loader: 复用的技能加载器（缺省按 base_dir/默认目录新建）
        context_defaults: 注入 SkillContext 的默认 tenant_id/user_id
        base_dir: 技能目录（缺省用 loader 既有目录或默认目录）
        reload: 是否强制从磁盘重新加载

    Returns:
        是否注册成功（加载失败返回 False，原因见 loader.load_report）。
    """
    if loader is None:
        loader = SkillLoader(base_dir) if base_dir else SkillLoader()

    skill = loader.get_skill(skill_name)
    if skill is not None and reload:
        await loader.unload_skill(skill_name)
        skill = None
    if skill is None:
        skill = await loader.load_skill(skill_name)
    if skill is None:
        logger.warning(
            "Incremental skill registration failed for '%s' (see loader.load_report)", skill_name
        )
        return False

    return _register_skill_tool(tool_registry, skill, loader, context_defaults)


def _register_skill_tool(
    tool_registry: Any,
    skill: Skill,
    loader: SkillLoader,
    context_defaults: dict[str, str | None] | None = None,
) -> bool:
    """把单个已加载技能注册为一个 skill__ 工具（注册约定与批量入口一致）。"""
    from backend.app.core.tools import RiskLevel  # 延迟导入避免循环

    skill_name = skill.metadata.name
    tool_name = skill_tool_name(skill_name)
    handler = build_skill_tool_handler(skill_name, loader, context_defaults)
    tool_registry.register(
        tool_name,
        description=skill.metadata.description or f"Skill: {skill_name}",
        handler=handler,
        risk_level=RiskLevel[DEFAULT_SKILL_RISK_LEVEL],
        required_scope=DEFAULT_SKILL_REQUIRED_SCOPE,
        parameters_schema=get_skill_parameters_schema(skill),
    )
    logger.info(f"Registered skill tool: {tool_name}")
    return True


__all__ = [
    "DEFAULT_SKILL_REQUIRED_SCOPE",
    "DEFAULT_SKILL_RISK_LEVEL",
    "SKILL_TOOL_PREFIX",
    "build_skill_tool_handler",
    "get_skill_parameters_schema",
    "list_skill_tools",
    "register_skill_into_tool_registry",
    "register_skills_into_tool_registry",
    "skill_name_from_tool",
    "skill_tool_name",
]
