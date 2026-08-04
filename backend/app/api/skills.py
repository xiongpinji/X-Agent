"""
技能API端点 - 提供技能管理和执行接口
"""

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException

from backend.app.core.security import Principal
from backend.app.core.skills import SkillContext, SkillLoader, SkillRegistry
from backend.app.dependencies import enforce_scope, get_current_principal

router = APIRouter(prefix="/api/v1/skills", tags=["skills"])
PrincipalDependency = Annotated[Principal, Depends(get_current_principal)]

# 全局技能管理器
_skill_registry = SkillRegistry()
_skill_loader = SkillLoader(registry=_skill_registry)


@router.on_event("startup")
async def initialize_skills():
    """初始化技能系统"""
    await _skill_loader.load_all_skills()


@router.get("")
async def list_skills(principal: PrincipalDependency) -> dict:
    """
    列出所有可用的技能

    Returns:
        dict: 技能列表和元数据
    """
    enforce_scope(principal, "skills:read")

    skills = _skill_registry.list_skills()
    metadata_list = _skill_registry.list_metadata()

    return {
        "total": len(skills),
        "skills": [m.model_dump() for m in metadata_list],
    }


@router.get("/{skill_name}")
async def get_skill_info(skill_name: str, principal: PrincipalDependency) -> dict:
    """
    获取技能详情

    Args:
        skill_name: 技能名称

    Returns:
        dict: 技能元数据和信息
    """
    enforce_scope(principal, "skills:read")

    skill = _skill_registry.get(skill_name)
    if not skill:
        raise HTTPException(status_code=404, detail=f"Skill not found: {skill_name}")

    metadata = _skill_registry.get_metadata(skill_name)
    return {
        "name": skill_name,
        "metadata": metadata.model_dump() if metadata else None,
        "capabilities": skill.get_capabilities(),
        "dependencies": skill.get_dependencies(),
    }


@router.post("/{skill_name}/execute")
async def execute_skill(
    skill_name: str,
    request: dict,
    principal: PrincipalDependency,
) -> dict:
    """
    执行技能

    Args:
        skill_name: 技能名称
        request: 执行请求

    Returns:
        dict: 执行结果
    """
    enforce_scope(principal, "skills:execute")

    skill = _skill_registry.get(skill_name)
    if not skill:
        raise HTTPException(status_code=404, detail=f"Skill not found: {skill_name}")

    try:
        # 创建执行上下文
        context = SkillContext(
            skill_name=skill_name,
            execution_id=request.get("execution_id", ""),
            user_id=principal.user_id if hasattr(principal, "user_id") else None,
            tenant_id=principal.tenant_id if hasattr(principal, "tenant_id") else None,
            metadata=request.get("metadata", {}),
        )

        # 验证输入
        if not await skill.validate(context, **request.get("params", {})):
            raise ValueError("Input validation failed")

        # 执行技能
        result = await skill.execute(context, **request.get("params", {}))

        return {
            "success": result.success,
            "data": result.data,
            "error": result.error,
            "execution_time": result.execution_time,
        }

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/install")
async def install_skill(
    request: dict,
    principal: PrincipalDependency,
) -> dict:
    """
    安装技能

    Args:
        request: 安装请求

    Returns:
        dict: 安装结果
    """
    enforce_scope(principal, "skills:manage")

    skill_name = request.get("skill_name")
    if not skill_name:
        raise HTTPException(status_code=400, detail="skill_name is required")

    try:
        skill = await _skill_loader.load_skill(skill_name)
        if not skill:
            raise ValueError(f"Failed to load skill: {skill_name}")

        return {
            "success": True,
            "message": f"Skill '{skill_name}' installed successfully",
        }

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.delete("/{skill_name}")
async def uninstall_skill(
    skill_name: str,
    principal: PrincipalDependency,
) -> dict:
    """
    卸载技能

    Args:
        skill_name: 技能名称

    Returns:
        dict: 卸载结果
    """
    enforce_scope(principal, "skills:manage")

    try:
        success = await _skill_loader.unload_skill(skill_name)
        if not success:
            raise ValueError(f"Failed to unload skill: {skill_name}")

        return {
            "success": True,
            "message": f"Skill '{skill_name}' uninstalled successfully",
        }

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/search/by-capability")
async def search_by_capability(
    capability: str,
    principal: PrincipalDependency,
) -> dict:
    """
    根据能力搜索技能

    Args:
        capability: 能力名称

    Returns:
        dict: 匹配的技能列表
    """
    enforce_scope(principal, "skills:read")

    skills = _skill_registry.get_by_capability(capability)
    return {
        "capability": capability,
        "total": len(skills),
        "skills": [s.metadata.model_dump() for s in skills],
    }


@router.get("/search/by-tag")
async def search_by_tag(
    tag: str,
    principal: PrincipalDependency,
) -> dict:
    """
    根据标签搜索技能

    Args:
        tag: 标签名称

    Returns:
        dict: 匹配的技能列表
    """
    enforce_scope(principal, "skills:read")

    skills = _skill_registry.get_by_tag(tag)
    return {
        "tag": tag,
        "total": len(skills),
        "skills": [s.metadata.model_dump() for s in skills],
    }
