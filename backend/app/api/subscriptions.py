"""
订阅管理API - FastAPI路由
"""
from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field

from backend.app.api.errors import api_error
from backend.app.core.contracts import ErrorCode
from backend.app.core.security import Principal
from backend.app.dependencies import get_current_principal
from backend.app.models.subscription import SubscriptionPlan
from backend.app.services.subscription import get_subscription_service

router = APIRouter(prefix="/api/v1/subscriptions", tags=["subscriptions"])
PrincipalDependency = Annotated[Principal, Depends(get_current_principal)]


# 请求/响应模型

class CreateSubscriptionRequest(BaseModel):
    """创建订阅请求"""
    plan: SubscriptionPlan = Field(default=SubscriptionPlan.FREE, description="订阅计划")
    trial_days: int = Field(default=14, ge=0, le=90, description="试用天数")


class UpgradeSubscriptionRequest(BaseModel):
    """升级订阅请求"""
    new_plan: SubscriptionPlan = Field(description="新计划")


class DowngradeSubscriptionRequest(BaseModel):
    """降级订阅请求"""
    new_plan: SubscriptionPlan = Field(description="新计划")


class SubscriptionResponse(BaseModel):
    """订阅响应"""
    subscription_id: str
    user_id: str
    tenant_id: str
    plan: str
    status: str
    price_per_month: float
    currency: str
    created_at: str
    started_at: str | None
    current_period_start: str
    current_period_end: str
    trial_end: str | None
    cancelled_at: str | None
    paused_at: str | None
    auto_renew: bool
    renewal_failed_count: int


class QuotaResponse(BaseModel):
    """配额响应"""
    quota_id: str
    subscription_id: str
    api_calls_limit: int
    api_calls_used: int
    tokens_limit: int
    tokens_used: int
    storage_limit_mb: int
    storage_used_mb: int
    concurrent_connections_limit: int
    concurrent_connections_current: int
    reset_at: str


class SubscriptionHistoryResponse(BaseModel):
    """订阅历史响应"""
    history_id: str
    subscription_id: str
    event_type: str
    old_plan: str | None
    new_plan: str | None
    old_status: str | None
    new_status: str | None
    details: str | None
    created_at: str


# API端点

@router.post("")
async def create_subscription(
    request: CreateSubscriptionRequest,
    principal: PrincipalDependency,
) -> dict[str, object]:
    """创建订阅

    为当前用户创建新的订阅。

    Args:
        request: 创建订阅请求
        principal: 当前用户信息

    Returns:
        创建的订阅信息
    """
    try:
        service = get_subscription_service()
        subscription = await service.create_subscription(
            user_id=principal.user_id,
            tenant_id=principal.tenant_id,
            plan=request.plan,
            trial_days=request.trial_days,
        )

        return {
            "subscription_id": subscription.subscription_id,
            "user_id": subscription.user_id,
            "tenant_id": subscription.tenant_id,
            "plan": subscription.plan.value,
            "status": subscription.status.value,
            "price_per_month": subscription.price_per_month,
            "currency": subscription.currency,
            "created_at": subscription.created_at.isoformat(),
            "started_at": subscription.started_at.isoformat() if subscription.started_at else None,
            "current_period_start": subscription.current_period_start.isoformat(),
            "current_period_end": subscription.current_period_end.isoformat(),
            "trial_end": subscription.trial_end.isoformat() if subscription.trial_end else None,
            "auto_renew": subscription.auto_renew,
        }
    except Exception as e:
        logger.error(f"创建订阅失败: {e!s}")
        raise api_error(
            500,
            ErrorCode.INTERNAL_ERROR,
            "Failed to create subscription",
            details={"error": str(e)},
        )


@router.get("/{subscription_id}")
async def get_subscription(
    subscription_id: str,
    principal: PrincipalDependency,
) -> dict[str, object]:
    """获取订阅详情

    获取指定订阅的详细信息。

    Args:
        subscription_id: 订阅ID
        principal: 当前用户信息

    Returns:
        订阅详情
    """
    try:
        service = get_subscription_service()
        subscription = await service.get_subscription(subscription_id)

        if not subscription:
            raise api_error(
                404,
                ErrorCode.RESOURCE_NOT_FOUND,
                "Subscription not found",
                details={"subscription_id": subscription_id},
            )

        # 检查权限
        if subscription.user_id != principal.user_id or subscription.tenant_id != principal.tenant_id:
            raise api_error(
                403,
                ErrorCode.PERMISSION_DENIED,
                "Access denied",
            )

        return {
            "subscription_id": subscription.subscription_id,
            "user_id": subscription.user_id,
            "tenant_id": subscription.tenant_id,
            "plan": subscription.plan.value,
            "status": subscription.status.value,
            "price_per_month": subscription.price_per_month,
            "currency": subscription.currency,
            "created_at": subscription.created_at.isoformat(),
            "started_at": subscription.started_at.isoformat() if subscription.started_at else None,
            "current_period_start": subscription.current_period_start.isoformat(),
            "current_period_end": subscription.current_period_end.isoformat(),
            "trial_end": subscription.trial_end.isoformat() if subscription.trial_end else None,
            "cancelled_at": subscription.cancelled_at.isoformat() if subscription.cancelled_at else None,
            "paused_at": subscription.paused_at.isoformat() if subscription.paused_at else None,
            "auto_renew": subscription.auto_renew,
            "renewal_failed_count": subscription.renewal_failed_count,
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"获取订阅失败: {e!s}")
        raise api_error(
            500,
            ErrorCode.INTERNAL_ERROR,
            "Failed to get subscription",
            details={"error": str(e)},
        )


@router.get("")
async def list_subscriptions(
    principal: PrincipalDependency,
    limit: int = Query(50, ge=1, le=1000),
    offset: int = Query(0, ge=0),
) -> dict[str, object]:
    """列出用户订阅

    获取当前用户的所有订阅。

    Args:
        principal: 当前用户信息
        limit: 分页大小
        offset: 分页偏移

    Returns:
        订阅列表
    """
    try:
        service = get_subscription_service()
        subscription = await service.get_user_subscription(
            user_id=principal.user_id,
            tenant_id=principal.tenant_id,
        )

        subscriptions = [subscription] if subscription else []

        return {
            "items": [
                {
                    "subscription_id": s.subscription_id,
                    "user_id": s.user_id,
                    "tenant_id": s.tenant_id,
                    "plan": s.plan.value,
                    "status": s.status.value,
                    "price_per_month": s.price_per_month,
                    "currency": s.currency,
                    "created_at": s.created_at.isoformat(),
                    "current_period_end": s.current_period_end.isoformat(),
                    "auto_renew": s.auto_renew,
                }
                for s in subscriptions
            ],
            "total": len(subscriptions),
        }
    except Exception as e:
        logger.error(f"列出订阅失败: {e!s}")
        raise api_error(
            500,
            ErrorCode.INTERNAL_ERROR,
            "Failed to list subscriptions",
            details={"error": str(e)},
        )


@router.post("/{subscription_id}/upgrade")
async def upgrade_subscription(
    subscription_id: str,
    request: UpgradeSubscriptionRequest,
    principal: PrincipalDependency,
) -> dict[str, object]:
    """升级订阅

    将订阅升级到更高级的计划。

    Args:
        subscription_id: 订阅ID
        request: 升级请求
        principal: 当前用户信息

    Returns:
        升级后的订阅信息
    """
    try:
        service = get_subscription_service()
        subscription = await service.get_subscription(subscription_id)

        if not subscription:
            raise api_error(
                404,
                ErrorCode.RESOURCE_NOT_FOUND,
                "Subscription not found",
                details={"subscription_id": subscription_id},
            )

        # 检查权限
        if subscription.user_id != principal.user_id or subscription.tenant_id != principal.tenant_id:
            raise api_error(
                403,
                ErrorCode.PERMISSION_DENIED,
                "Access denied",
            )

        # 检查升级是否有效
        plan_order = [SubscriptionPlan.FREE, SubscriptionPlan.STARTER, SubscriptionPlan.PROFESSIONAL, SubscriptionPlan.ENTERPRISE]
        if plan_order.index(request.new_plan) <= plan_order.index(subscription.plan):
            raise api_error(
                400,
                ErrorCode.INVALID_REQUEST,
                "Invalid upgrade: new plan must be higher than current plan",
            )

        upgraded = await service.upgrade_subscription(subscription_id, request.new_plan)

        return {
            "subscription_id": upgraded.subscription_id,
            "plan": upgraded.plan.value,
            "status": upgraded.status.value,
            "price_per_month": upgraded.price_per_month,
            "current_period_end": upgraded.current_period_end.isoformat(),
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"升级订阅失败: {e!s}")
        raise api_error(
            500,
            ErrorCode.INTERNAL_ERROR,
            "Failed to upgrade subscription",
            details={"error": str(e)},
        )


@router.post("/{subscription_id}/downgrade")
async def downgrade_subscription(
    subscription_id: str,
    request: DowngradeSubscriptionRequest,
    principal: PrincipalDependency,
) -> dict[str, object]:
    """降级订阅

    将订阅降级到更低级的计划。

    Args:
        subscription_id: 订阅ID
        request: 降级请求
        principal: 当前用户信息

    Returns:
        降级后的订阅信息
    """
    try:
        service = get_subscription_service()
        subscription = await service.get_subscription(subscription_id)

        if not subscription:
            raise api_error(
                404,
                ErrorCode.RESOURCE_NOT_FOUND,
                "Subscription not found",
                details={"subscription_id": subscription_id},
            )

        # 检查权限
        if subscription.user_id != principal.user_id or subscription.tenant_id != principal.tenant_id:
            raise api_error(
                403,
                ErrorCode.PERMISSION_DENIED,
                "Access denied",
            )

        # 检查降级是否有效
        plan_order = [SubscriptionPlan.FREE, SubscriptionPlan.STARTER, SubscriptionPlan.PROFESSIONAL, SubscriptionPlan.ENTERPRISE]
        if plan_order.index(request.new_plan) >= plan_order.index(subscription.plan):
            raise api_error(
                400,
                ErrorCode.INVALID_REQUEST,
                "Invalid downgrade: new plan must be lower than current plan",
            )

        downgraded = await service.downgrade_subscription(subscription_id, request.new_plan)

        return {
            "subscription_id": downgraded.subscription_id,
            "plan": downgraded.plan.value,
            "status": downgraded.status.value,
            "price_per_month": downgraded.price_per_month,
            "current_period_end": downgraded.current_period_end.isoformat(),
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"降级订阅失败: {e!s}")
        raise api_error(
            500,
            ErrorCode.INTERNAL_ERROR,
            "Failed to downgrade subscription",
            details={"error": str(e)},
        )


@router.post("/{subscription_id}/pause")
async def pause_subscription(
    subscription_id: str,
    principal: PrincipalDependency,
) -> dict[str, object]:
    """暂停订阅

    暂停指定的订阅。

    Args:
        subscription_id: 订阅ID
        principal: 当前用户信息

    Returns:
        暂停后的订阅信息
    """
    try:
        service = get_subscription_service()
        subscription = await service.get_subscription(subscription_id)

        if not subscription:
            raise api_error(
                404,
                ErrorCode.RESOURCE_NOT_FOUND,
                "Subscription not found",
                details={"subscription_id": subscription_id},
            )

        # 检查权限
        if subscription.user_id != principal.user_id or subscription.tenant_id != principal.tenant_id:
            raise api_error(
                403,
                ErrorCode.PERMISSION_DENIED,
                "Access denied",
            )

        paused = await service.pause_subscription(subscription_id)

        return {
            "subscription_id": paused.subscription_id,
            "status": paused.status.value,
            "paused_at": paused.paused_at.isoformat() if paused.paused_at else None,
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"暂停订阅失败: {e!s}")
        raise api_error(
            500,
            ErrorCode.INTERNAL_ERROR,
            "Failed to pause subscription",
            details={"error": str(e)},
        )


@router.post("/{subscription_id}/resume")
async def resume_subscription(
    subscription_id: str,
    principal: PrincipalDependency,
) -> dict[str, object]:
    """恢复订阅

    恢复已暂停的订阅。

    Args:
        subscription_id: 订阅ID
        principal: 当前用户信息

    Returns:
        恢复后的订阅信息
    """
    try:
        service = get_subscription_service()
        subscription = await service.get_subscription(subscription_id)

        if not subscription:
            raise api_error(
                404,
                ErrorCode.RESOURCE_NOT_FOUND,
                "Subscription not found",
                details={"subscription_id": subscription_id},
            )

        # 检查权限
        if subscription.user_id != principal.user_id or subscription.tenant_id != principal.tenant_id:
            raise api_error(
                403,
                ErrorCode.PERMISSION_DENIED,
                "Access denied",
            )

        resumed = await service.resume_subscription(subscription_id)

        return {
            "subscription_id": resumed.subscription_id,
            "status": resumed.status.value,
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"恢复订阅失败: {e!s}")
        raise api_error(
            500,
            ErrorCode.INTERNAL_ERROR,
            "Failed to resume subscription",
            details={"error": str(e)},
        )


@router.post("/{subscription_id}/cancel")
async def cancel_subscription(
    subscription_id: str,
    principal: PrincipalDependency,
) -> dict[str, object]:
    """取消订阅

    取消指定的订阅。

    Args:
        subscription_id: 订阅ID
        principal: 当前用户信息

    Returns:
        取消后的订阅信息
    """
    try:
        service = get_subscription_service()
        subscription = await service.get_subscription(subscription_id)

        if not subscription:
            raise api_error(
                404,
                ErrorCode.RESOURCE_NOT_FOUND,
                "Subscription not found",
                details={"subscription_id": subscription_id},
            )

        # 检查权限
        if subscription.user_id != principal.user_id or subscription.tenant_id != principal.tenant_id:
            raise api_error(
                403,
                ErrorCode.PERMISSION_DENIED,
                "Access denied",
            )

        cancelled = await service.cancel_subscription(subscription_id)

        return {
            "subscription_id": cancelled.subscription_id,
            "status": cancelled.status.value,
            "cancelled_at": cancelled.cancelled_at.isoformat() if cancelled.cancelled_at else None,
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"取消订阅失败: {e!s}")
        raise api_error(
            500,
            ErrorCode.INTERNAL_ERROR,
            "Failed to cancel subscription",
            details={"error": str(e)},
        )


@router.get("/{subscription_id}/quota")
async def get_quota(
    subscription_id: str,
    principal: PrincipalDependency,
) -> dict[str, object]:
    """获取配额信息

    获取订阅的配额使用情况。

    Args:
        subscription_id: 订阅ID
        principal: 当前用户信息

    Returns:
        配额信息
    """
    try:
        service = get_subscription_service()
        subscription = await service.get_subscription(subscription_id)

        if not subscription:
            raise api_error(
                404,
                ErrorCode.RESOURCE_NOT_FOUND,
                "Subscription not found",
                details={"subscription_id": subscription_id},
            )

        # 检查权限
        if subscription.user_id != principal.user_id or subscription.tenant_id != principal.tenant_id:
            raise api_error(
                403,
                ErrorCode.PERMISSION_DENIED,
                "Access denied",
            )

        quota = await service.get_quota(subscription_id)

        if not quota:
            raise api_error(
                404,
                ErrorCode.RESOURCE_NOT_FOUND,
                "Quota not found",
                details={"subscription_id": subscription_id},
            )

        return {
            "quota_id": quota.quota_id,
            "subscription_id": quota.subscription_id,
            "api_calls": {
                "limit": quota.api_calls_limit,
                "used": quota.api_calls_used,
                "remaining": quota.api_calls_limit - quota.api_calls_used,
                "percentage": (quota.api_calls_used / quota.api_calls_limit * 100) if quota.api_calls_limit > 0 else 0,
            },
            "tokens": {
                "limit": quota.tokens_limit,
                "used": quota.tokens_used,
                "remaining": quota.tokens_limit - quota.tokens_used,
                "percentage": (quota.tokens_used / quota.tokens_limit * 100) if quota.tokens_limit > 0 else 0,
            },
            "storage": {
                "limit_mb": quota.storage_limit_mb,
                "used_mb": quota.storage_used_mb,
                "remaining_mb": quota.storage_limit_mb - quota.storage_used_mb,
                "percentage": (quota.storage_used_mb / quota.storage_limit_mb * 100) if quota.storage_limit_mb > 0 else 0,
            },
            "concurrent_connections": {
                "limit": quota.concurrent_connections_limit,
                "current": quota.concurrent_connections_current,
                "available": quota.concurrent_connections_limit - quota.concurrent_connections_current,
            },
            "reset_at": quota.reset_at.isoformat(),
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"获取配额失败: {e!s}")
        raise api_error(
            500,
            ErrorCode.INTERNAL_ERROR,
            "Failed to get quota",
            details={"error": str(e)},
        )


@router.get("/{subscription_id}/history")
async def get_subscription_history(
    subscription_id: str,
    principal: PrincipalDependency,
    limit: int = Query(50, ge=1, le=1000),
    offset: int = Query(0, ge=0),
) -> dict[str, object]:
    """获取订阅历史

    获取订阅的事件历史记录。

    Args:
        subscription_id: 订阅ID
        principal: 当前用户信息
        limit: 分页大小
        offset: 分页偏移

    Returns:
        历史记录列表
    """
    try:
        service = get_subscription_service()
        subscription = await service.get_subscription(subscription_id)

        if not subscription:
            raise api_error(
                404,
                ErrorCode.RESOURCE_NOT_FOUND,
                "Subscription not found",
                details={"subscription_id": subscription_id},
            )

        # 检查权限
        if subscription.user_id != principal.user_id or subscription.tenant_id != principal.tenant_id:
            raise api_error(
                403,
                ErrorCode.PERMISSION_DENIED,
                "Access denied",
            )

        history = await service.get_subscription_history(subscription_id, limit, offset)

        return {
            "items": [
                {
                    "history_id": h.history_id,
                    "event_type": h.event_type,
                    "old_plan": h.old_plan,
                    "new_plan": h.new_plan,
                    "old_status": h.old_status,
                    "new_status": h.new_status,
                    "details": h.details,
                    "created_at": h.created_at.isoformat(),
                }
                for h in history
            ],
            "total": len(history),
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"获取订阅历史失败: {e!s}")
        raise api_error(
            500,
            ErrorCode.INTERNAL_ERROR,
            "Failed to get subscription history",
            details={"error": str(e)},
        )


import logging

logger = logging.getLogger(__name__)
