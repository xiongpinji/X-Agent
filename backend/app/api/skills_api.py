"""Skill System API Routes - FastAPI endpoints for skill management

P1-11 修复（2026-07-20）：
- tenant_id/user_id 不再直信请求体：已认证主体以 Principal 为准，
  请求值与主体不一致显式 403；匿名主体仅本地开发模式可达（生产被 401 拦截）。
- 路由顺序修复：静态路由全部前置，``/{skill_id}`` 参数路由殿后
  （此前 GET /health、GET /stats/* 会被 /{skill_id} 抢占）。
- scope 改用 RBAC 中真实存在的值（tools:read / agent:run / tools:*）。

状态：已挂载（2026-08-04 集成波，``_KEPT_ROUTER_MODULES``）。
注意：本路由服务的是 legacy 管理平面（skills_* 扁平栈），
技能唯一运行时为 backend.app.core.skills（见 SKILLS_SYSTEM_README.md）；
/api/v1/skills 的第二套管理 API（api/skills.py）已归档消除重复。
"""

from __future__ import annotations

import logging
from typing import Annotated, Any

from fastapi import APIRouter, Body, Depends, HTTPException, Query
from pydantic import BaseModel, Field

from backend.app.api.errors import api_error
from backend.app.core.contracts import ErrorCode
from backend.app.core.security import Principal
from backend.app.core.skills_core import SkillCapability
from backend.app.core.skills_manager import get_skill_system_manager
from backend.app.dependencies import enforce_scope, get_current_principal

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/skills", tags=["skills"])

PrincipalDependency = Annotated[Principal, Depends(get_current_principal)]

# RBAC 中真实存在的 scope（见 backend.app.core.security.ROLE_SCOPES）
SCOPE_SKILL_READ = "tools:read"
SCOPE_SKILL_EXECUTE = "agent:run"
SCOPE_SKILL_MANAGE = "tools:*"


class SkillExecuteRequest(BaseModel):
    """Request to execute a skill"""
    skill_name: str
    input_data: dict[str, Any] = Field(default_factory=dict)
    # 仅本地开发（匿名主体）可显式指定；已认证调用会被 Principal 覆盖
    user_id: str = ""
    tenant_id: str = ""
    sandbox_id: str | None = None


class SkillInstallRequest(BaseModel):
    """Request to install a skill"""
    skill_id: str
    user_id: str = ""


def _resolve_tenant_user(
    request_tenant_id: str,
    request_user_id: str,
    principal: Principal,
) -> tuple[str, str]:
    """解析可信 tenant_id / user_id。

    - 已认证主体：以 Principal 为准；请求体显式指定了不一致的 tenant_id
      时拒绝（403），杜绝跨租户直信。
    - 匿名主体：仅本地开发模式可达（生产环境 get_current_principal 已 401），
      允许使用请求值便于联调。
    """
    if principal.authenticated:
        if request_tenant_id and request_tenant_id != principal.tenant_id:
            raise api_error(
                403,
                ErrorCode.AUTHORIZATION_FAILED,
                f"tenant_id mismatch: request '{request_tenant_id}' != principal '{principal.tenant_id}'",
            )
        return principal.tenant_id, principal.user_id
    return request_tenant_id, request_user_id


# ---------- 静态路由（必须位于 /{skill_id} 之前） ----------


@router.get("/discover")
async def discover_skills(
    principal: PrincipalDependency,
    capability: str | None = Query(None),
    tag: str | None = Query(None),
) -> dict[str, Any]:
    """Discover skills by capability or tag"""
    enforce_scope(principal, SCOPE_SKILL_READ)
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
        logger.error(f"Error discovering skills: {e!s}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/search")
async def search_skills(
    principal: PrincipalDependency,
    query: str = Query(...),
    limit: int = Query(20, ge=1, le=100),
) -> dict[str, Any]:
    """Search for skills"""
    enforce_scope(principal, SCOPE_SKILL_READ)
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
        logger.error(f"Error searching skills: {e!s}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/stats/marketplace")
async def get_marketplace_stats(principal: PrincipalDependency) -> dict[str, Any]:
    """Get marketplace statistics"""
    enforce_scope(principal, SCOPE_SKILL_READ)
    try:
        manager = get_skill_system_manager()
        stats = manager.get_marketplace_stats()
        return {"success": True, "stats": stats}
    except Exception as e:
        logger.error(f"Error getting marketplace stats: {e!s}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/stats/top")
async def get_top_skills(
    principal: PrincipalDependency,
    limit: int = Query(10, ge=1, le=100),
) -> dict[str, Any]:
    """Get top-rated skills"""
    enforce_scope(principal, SCOPE_SKILL_READ)
    try:
        manager = get_skill_system_manager()
        skills = manager.get_top_skills(limit)
        return {"success": True, "skills": skills, "count": len(skills)}
    except Exception as e:
        logger.error(f"Error getting top skills: {e!s}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/health")
async def get_system_health(principal: PrincipalDependency) -> dict[str, Any]:
    """Get skill system health"""
    enforce_scope(principal, SCOPE_SKILL_READ)
    try:
        manager = get_skill_system_manager()
        health = await manager.get_system_health()
        return {"success": True, "health": health}
    except Exception as e:
        logger.error(f"Error getting system health: {e!s}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@router.get("")
async def list_skills(
    principal: PrincipalDependency,
    installed_only: bool = Query(False),
) -> dict[str, Any]:
    """List all skills"""
    enforce_scope(principal, SCOPE_SKILL_READ)
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
        logger.error(f"Error listing skills: {e!s}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/execute")
async def execute_skill(
    request: SkillExecuteRequest,
    principal: PrincipalDependency,
) -> dict[str, Any]:
    """Execute a skill"""
    enforce_scope(principal, SCOPE_SKILL_EXECUTE)
    tenant_id, user_id = _resolve_tenant_user(request.tenant_id, request.user_id, principal)
    try:
        manager = get_skill_system_manager()
        result = await manager.execute_skill(
            skill_name=request.skill_name,
            input_data=request.input_data,
            user_id=user_id,
            tenant_id=tenant_id,
            sandbox_id=request.sandbox_id,
        )
        return {
            "success": result.success,
            "data": result.data,
            "error": result.error,
            "execution_time_ms": result.execution_time_ms,
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error executing skill: {e!s}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


# ---------- 参数路由（殿后，避免抢占静态路由） ----------


@router.get("/{skill_id}")
async def get_skill_info(skill_id: str, principal: PrincipalDependency) -> dict[str, Any]:
    """Get detailed skill information"""
    enforce_scope(principal, SCOPE_SKILL_READ)
    try:
        manager = get_skill_system_manager()
        info = await manager.get_skill_info(skill_id)
        if not info:
            raise HTTPException(status_code=404, detail=f"Skill not found: {skill_id}")
        return {"success": True, "skill": info}
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting skill info: {e!s}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/{skill_id}/install")
async def install_skill(
    skill_id: str,
    principal: PrincipalDependency,
    request: SkillInstallRequest = Body(...),
) -> dict[str, Any]:
    """Install a skill"""
    enforce_scope(principal, SCOPE_SKILL_MANAGE)
    try:
        manager = get_skill_system_manager()
        success, error = await manager.install_skill(skill_id=skill_id, user_id=principal.user_id)
        if not success:
            raise HTTPException(status_code=400, detail=error)
        return {"success": True, "message": f"Skill installed: {skill_id}"}
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error installing skill: {e!s}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/{skill_id}/uninstall")
async def uninstall_skill(skill_id: str, principal: PrincipalDependency) -> dict[str, Any]:
    """Uninstall a skill"""
    enforce_scope(principal, SCOPE_SKILL_MANAGE)
    try:
        manager = get_skill_system_manager()
        success, error = await manager.uninstall_skill(skill_id)
        if not success:
            raise HTTPException(status_code=400, detail=error)
        return {"success": True, "message": f"Skill uninstalled: {skill_id}"}
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error uninstalling skill: {e!s}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/{skill_id}/rate")
async def rate_skill(
    skill_id: str,
    principal: PrincipalDependency,
    rating: float = Query(..., ge=1.0, le=5.0),
) -> dict[str, Any]:
    """Rate a skill"""
    enforce_scope(principal, SCOPE_SKILL_READ)
    try:
        manager = get_skill_system_manager()
        success, error = await manager.rate_skill(skill_id, rating)
        if not success:
            raise HTTPException(status_code=400, detail=error)
        return {"success": True, "message": f"Skill rated: {rating}/5.0"}
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error rating skill: {e!s}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


__all__ = ["router"]
