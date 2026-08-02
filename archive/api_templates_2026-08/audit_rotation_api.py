"""P1-04: 审计日志轮转管理 API。

端点:
- GET  /api/v1/audit/rotation/stats   — 轮转状态统计
- POST /api/v1/audit/rotation/trigger — 手动触发轮转
"""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends

from backend.app.core.audit_rotation import AuditLogRotator, AuditRotationConfig
from backend.app.core.security import Principal
from backend.app.dependencies import enforce_scope, get_current_principal
from backend.app.settings import get_settings

router = APIRouter(prefix="/api/v1/audit/rotation", tags=["audit"])
PrincipalDependency = Annotated[Principal, Depends(get_current_principal)]


def _get_rotator() -> AuditLogRotator:
    """从全局配置构建 AuditLogRotator 实例。"""
    settings = get_settings()
    config = AuditRotationConfig(
        max_bytes=settings.audit_max_size_mb * 1024 * 1024,
        retention_days=settings.audit_retention_days,
    )
    return AuditLogRotator(config=config, log_path=settings.audit_store_path)


@router.get("/stats")
async def get_rotation_stats(
    principal: PrincipalDependency,
) -> dict[str, object]:
    """获取审计日志轮转统计信息。

    返回: 活动文件大小、总大小、段数量、最旧/最新段、配置参数等。
    """
    enforce_scope(principal, "audit:read")
    settings = get_settings()
    rotator = _get_rotator()
    stats = rotator.get_stats()
    stats["rotation_enabled_setting"] = settings.audit_rotation_enabled
    stats["ship_enabled"] = settings.audit_ship_enabled
    stats["webhook_configured"] = bool(settings.audit_webhook_url)
    return stats


@router.post("/trigger")
async def trigger_rotation(
    principal: PrincipalDependency,
) -> dict[str, object]:
    """手动触发审计日志轮转。

    强制将当前活动审计文件轮转为归档段, 并执行过期清理。
    需要 admin 角色。
    """
    enforce_scope(principal, "audit:read")
    if principal.role != "admin":
        from fastapi import HTTPException

        raise HTTPException(status_code=403, detail="Admin role required to trigger rotation")

    rotator = _get_rotator()

    # 执行轮转
    archive_path = rotator.rotate()
    # 清理过期段
    cleaned = rotator.cleanup_old()
    # 获取最新统计
    stats = rotator.get_stats()

    return {
        "rotated": bool(archive_path),
        "archive_path": archive_path or None,
        "cleaned_expired": cleaned,
        "stats": stats,
    }
