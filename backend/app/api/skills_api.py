"""Skill System API Routes - FastAPI endpoints for skill management"""

from __future__ import annotations

import logging
from typing import Annotated, Any

from fastapi import APIRouter, Depends, HTTPException, Query, Body
from pydantic import BaseModel, Field

from backend.app.api.errors import api_error
from backend.app.core.contracts import ErrorCode
from backend.app.core.security import Principal
from backend.app.core.skills_manager import get_skill_system_manager
from backend.app.core.skills_core import SkillCapability
from backend.app.dependencies import enforce_scope, get_current_principal

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/skills", tags=["skills"])

# 认证授权依赖(SECURITY P0-03):写操作端点必须校验已认证主体与权限。
PrincipalDependency = Annotated[Principal, Depends(get_current_principal)]


class SkillExecuteRequest(BaseModel):
    """Request to execute a skill.

    Note: user_id/tenant_id 字段保留以向后兼容旧客户端,但服务端始终以
    认证主体(principal)的值为准,忽略客户端传入值,防止越权(SECURITY P0-03)。
    """
    skill_name: str
    input_data: dict[str, Any] = Field(default_factory=dict)
    user_id: str = ""
    tenant_id: str = ""
    sandbox_id: str | None = None


class SkillInstallRequest(BaseModel):
    """Request to install a skill.

    user_id 字段保留向后兼容,服务端以 principal.user_id 为准(SECURITY P0-03)。
    """
    skill_id: str
    user_id: str = ""


@router.get("/discover")
async def discover_skills(
    capability: str | None = Query(None),
    tag: str | None = Query(None),
) -> dict[str, Any]:
    """Discover skills by capability or tag"""
    try:
        manager = get_skill_system_manager()
        cap_enum = None
        if capability:
            try:
                cap_enum = SkillCapability(capability)
            except ValueError:
                raise HTTPException(status_code=400, detail=f"Invalid capability: {capability}")

        skills = await manager.discover_skills(capability=cap_enum, tag=tag)
        return {
            "success": True,
            "skills": [s.to_dict() for s in skills],
            "count": len(skills),
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error discovering skills: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/search")
async def search_skills(
    query: str = Query(...),
    limit: int = Query(20, ge=1, le=100),
) -> dict[str, Any]:
    """Search for skills"""
    try:
        manager = get_skill_system_manager()
        results = await manager.search_skills(query, limit)
        return {
            "success": True,
            "results": [
                {
                    "skill_id": r.skill_id,
                    "name": r.name,
                    "version": r.version,
                    "description": r.description,
                    "rating": r.rating,
                    "downloads": r.download_count,
                    "relevance_score": r.relevance_score,
                }
                for r in results
            ],
            "count": len(results),
        }
    except Exception as e:
        logger.error(f"Error searching skills: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/{skill_id}")
async def get_skill_info(skill_id: str) -> dict[str, Any]:
    """Get detailed skill information"""
    try:
        manager = get_skill_system_manager()
        info = await manager.get_skill_info(skill_id)
        if not info:
            raise HTTPException(status_code=404, detail=f"Skill not found: {skill_id}")
        return {"success": True, "skill": info}
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting skill info: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@router.get("")
async def list_skills(
    installed_only: bool = Query(False),
) -> dict[str, Any]:
    """List all skills"""
    try:
        manager = get_skill_system_manager()
        if installed_only:
            skills = await manager.list_installed_skills()
        else:
            skills = await manager.discover_skills()
        return {
            "success": True,
            "skills": skills if installed_only else [s.to_dict() for s in skills],
            "count": len(skills),
        }
    except Exception as e:
        logger.error(f"Error listing skills: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/execute")
async def execute_skill(
    request: SkillExecuteRequest,
    principal: PrincipalDependency,
) -> dict[str, Any]:
    """Execute a skill.

    SECURITY P0-03: user_id/tenant_id 一律取自认证主体,忽略请求体传入值,
    防止跨用户/跨租户越权执行技能。
    """
    enforce_scope(principal, "skill:run")
    try:
        manager = get_skill_system_manager()
        result = await manager.execute_skill(
            skill_name=request.skill_name,
            input_data=request.input_data,
            user_id=principal.user_id,
            tenant_id=principal.tenant_id,
            sandbox_id=request.sandbox_id,
        )
        return {
            "success": result.success,
            "data": result.data,
            "error": result.error,
            "execution_time_ms": result.execution_time_ms,
        }
    except Exception as e:
        logger.error(f"Error executing skill: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/{skill_id}/install")
async def install_skill(
    skill_id: str,
    principal: PrincipalDependency,
    request: SkillInstallRequest = Body(...),
) -> dict[str, Any]:
    """Install a skill.

    SECURITY P0-03: 以 principal.user_id 为准,忽略请求体 user_id。
    """
    enforce_scope(principal, "skill:install")
    try:
        manager = get_skill_system_manager()
        success, error = await manager.install_skill(skill_id=skill_id, user_id=principal.user_id)
        if not success:
            raise HTTPException(status_code=400, detail=error)
        return {"success": True, "message": f"Skill installed: {skill_id}"}
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error installing skill: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/{skill_id}/uninstall")
async def uninstall_skill(
    skill_id: str,
    principal: PrincipalDependency,
) -> dict[str, Any]:
    """Uninstall a skill.

    SECURITY P0-03: 需要已认证主体与 skill:install 权限(卸载与安装同等敏感)。
    """
    enforce_scope(principal, "skill:install")
    try:
        manager = get_skill_system_manager()
        success, error = await manager.uninstall_skill(skill_id)
        if not success:
            raise HTTPException(status_code=400, detail=error)
        return {"success": True, "message": f"Skill uninstalled: {skill_id}"}
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error uninstalling skill: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/{skill_id}/rate")
async def rate_skill(
    skill_id: str,
    principal: PrincipalDependency,
    rating: float = Query(..., ge=1.0, le=5.0),
) -> dict[str, Any]:
    """Rate a skill.

    SECURITY P0-03: 需要已认证主体与 skill:run 权限,防止匿名/低权刷分。
    """
    if not principal.authenticated:
        raise api_error(401, ErrorCode.AUTHENTICATION_FAILED, "Authentication required to rate skills.")
    enforce_scope(principal, "skill:run")
    try:
        manager = get_skill_system_manager()
        success, error = await manager.rate_skill(skill_id, rating)
        if not success:
            raise HTTPException(status_code=400, detail=error)
        return {"success": True, "message": f"Skill rated: {rating}/5.0"}
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error rating skill: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/stats/marketplace")
async def get_marketplace_stats() -> dict[str, Any]:
    """Get marketplace statistics"""
    try:
        manager = get_skill_system_manager()
        stats = manager.get_marketplace_stats()
        return {"success": True, "stats": stats}
    except Exception as e:
        logger.error(f"Error getting marketplace stats: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/stats/top")
async def get_top_skills(limit: int = Query(10, ge=1, le=100)) -> dict[str, Any]:
    """Get top-rated skills"""
    try:
        manager = get_skill_system_manager()
        skills = manager.get_top_skills(limit)
        return {"success": True, "skills": skills, "count": len(skills)}
    except Exception as e:
        logger.error(f"Error getting top skills: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/health")
async def get_system_health() -> dict[str, Any]:
    """Get skill system health"""
    try:
        manager = get_skill_system_manager()
        health = await manager.get_system_health()
        return {"success": True, "health": health}
    except Exception as e:
        logger.error(f"Error getting system health: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


__all__ = ["router"]
