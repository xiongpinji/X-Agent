"""
用户反馈API端点
"""
from __future__ import annotations

import logging
from datetime import UTC, datetime
from typing import Annotated
from uuid import uuid4

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel, Field

from backend.app.core.feedback_analyzer import feedback_analyzer
from backend.app.core.security import Principal
from backend.app.dependencies import get_current_principal
from backend.app.models.feedback import (
    FeedbackSeverity,
    FeedbackStatus,
    FeedbackStorePostgres,
    FeedbackType,
)

logger = logging.getLogger("xagent.feedback")

router = APIRouter(prefix="/api/v1/feedback", tags=["feedback"])

# 全局反馈存储实例
_feedback_store: FeedbackStorePostgres | None = None


def get_feedback_store() -> FeedbackStorePostgres:
    """获取反馈存储实例"""
    global _feedback_store
    if _feedback_store is None:
        _feedback_store = FeedbackStorePostgres()
    return _feedback_store


# Pydantic模型
class FeedbackCreateRequest(BaseModel):
    """创建反馈请求"""
    feedback_type: str = Field(..., description="反馈类型: bug, feature, improvement, other")
    title: str = Field(..., min_length=1, max_length=500, description="反馈标题")
    description: str = Field(..., min_length=1, max_length=5000, description="反馈描述")
    severity: str = Field(..., description="严重程度: low, medium, high, critical")
    metadata: dict | None = Field(None, description="额外元数据")


class FeedbackResponse(BaseModel):
    """反馈响应"""
    id: str
    user_id: str
    feedback_type: str
    title: str
    description: str
    severity: str
    status: str
    sentiment: str | None
    sentiment_score: float | None
    priority_score: float | None
    category: str | None
    tags: list[str] | None
    created_at: str
    updated_at: str
    resolved_at: str | None

    class Config:
        from_attributes = True


class FeedbackAnalysisResponse(BaseModel):
    """反馈分析响应"""
    feedback_id: str
    sentiment_type: str
    sentiment_score: float
    category: str
    subcategory: str | None
    tags: list[str]
    priority_score: float
    urgency_score: float
    impact_score: float
    keywords: list[str]
    entities: dict


class FeedbackListResponse(BaseModel):
    """反馈列表响应"""
    total: int
    skip: int
    limit: int
    items: list[FeedbackResponse]


class FeedbackStatsResponse(BaseModel):
    """反馈统计响应"""
    total: int
    by_status: dict[str, int]
    by_severity: dict[str, int]
    by_type: dict[str, int]
    average_priority_score: float
    critical_count: int


@router.post("/", response_model=FeedbackResponse, status_code=status.HTTP_201_CREATED)
async def create_feedback(
    request: FeedbackCreateRequest,
    principal: Annotated[Principal, Depends(get_current_principal)],
) -> FeedbackResponse:
    """
    创建用户反馈

    - **feedback_type**: bug, feature, improvement, other
    - **severity**: low, medium, high, critical
    """
    try:
        # 验证输入
        if request.feedback_type not in [t.value for t in FeedbackType]:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Invalid feedback_type. Must be one of: {[t.value for t in FeedbackType]}"
            )

        if request.severity not in [s.value for s in FeedbackSeverity]:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Invalid severity. Must be one of: {[s.value for s in FeedbackSeverity]}"
            )

        # 获取用户信息
        user_id = principal.user_id
        tenant_id = principal.tenant_id

        # 创建反馈
        feedback_id = str(uuid4())
        store = get_feedback_store()

        feedback = await store.create_feedback(
            feedback_id=feedback_id,
            user_id=user_id,
            tenant_id=tenant_id,
            feedback_type=request.feedback_type,
            title=request.title,
            description=request.description,
            severity=request.severity,
            metadata=request.metadata,
        )

        # 异步分析反馈
        try:
            analysis_result = await feedback_analyzer.analyze_feedback(
                feedback_id=feedback_id,
                title=request.title,
                description=request.description,
                feedback_type=request.feedback_type,
                severity=request.severity,
            )

            # 更新反馈的分析结果
            await store.update_feedback(
                feedback_id=feedback_id,
                sentiment=analysis_result["sentiment_type"],
                sentiment_score=analysis_result["sentiment_score"],
                category=analysis_result["category"],
                tags=analysis_result["tags"],
                priority_score=analysis_result["priority_score"],
            )

            # 创建分析记录
            analysis_id = str(uuid4())
            await store.create_analysis(
                analysis_id=analysis_id,
                feedback_id=feedback_id,
                sentiment_score=analysis_result["sentiment_score"],
                sentiment_type=analysis_result["sentiment_type"],
                category=analysis_result["category"],
                tags=analysis_result["tags"],
                priority_score=analysis_result["priority_score"],
                urgency_score=analysis_result["urgency_score"],
                impact_score=analysis_result["impact_score"],
                keywords=analysis_result["keywords"],
                entities=analysis_result["entities"],
            )

            logger.info(f"反馈分析完成: {feedback_id}")
        except Exception as e:
            logger.error(f"反馈分析失败: {e}")

        # 重新获取反馈以获取最新数据
        feedback = await store.get_feedback_by_id(feedback_id)

        return FeedbackResponse(
            id=feedback.id,
            user_id=feedback.user_id,
            feedback_type=feedback.feedback_type,
            title=feedback.title,
            description=feedback.description,
            severity=feedback.severity,
            status=feedback.status,
            sentiment=feedback.sentiment,
            sentiment_score=feedback.sentiment_score,
            priority_score=feedback.priority_score,
            category=feedback.category,
            tags=feedback.tags,
            created_at=feedback.created_at.isoformat(),
            updated_at=feedback.updated_at.isoformat(),
            resolved_at=feedback.resolved_at.isoformat() if feedback.resolved_at else None,
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"创建反馈失败: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to create feedback"
        )


@router.get("/{feedback_id}", response_model=FeedbackResponse)
async def get_feedback(
    feedback_id: str,
    principal: Annotated[Principal, Depends(get_current_principal)],
) -> FeedbackResponse:
    """获取反馈详情"""
    try:
        store = get_feedback_store()
        feedback = await store.get_feedback_by_id(feedback_id)

        if not feedback:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Feedback not found"
            )

        # 检查权限
        if feedback.user_id != principal.user_id and principal.role != "admin":
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Access denied"
            )

        return FeedbackResponse(
            id=feedback.id,
            user_id=feedback.user_id,
            feedback_type=feedback.feedback_type,
            title=feedback.title,
            description=feedback.description,
            severity=feedback.severity,
            status=feedback.status,
            sentiment=feedback.sentiment,
            sentiment_score=feedback.sentiment_score,
            priority_score=feedback.priority_score,
            category=feedback.category,
            tags=feedback.tags,
            created_at=feedback.created_at.isoformat(),
            updated_at=feedback.updated_at.isoformat(),
            resolved_at=feedback.resolved_at.isoformat() if feedback.resolved_at else None,
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"获取反馈失败: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to get feedback"
        )


@router.get("/", response_model=FeedbackListResponse)
async def list_feedback(
    feedback_type: str | None = Query(None, description="反馈类型过滤"),
    status_filter: str | None = Query(None, alias="status", description="状态过滤"),
    severity: str | None = Query(None, description="严重程度过滤"),
    skip: int = Query(0, ge=0, description="跳过数量"),
    limit: int = Query(100, ge=1, le=1000, description="限制数量"),
    principal: Annotated[Principal, Depends(get_current_principal)] = None,
) -> FeedbackListResponse:
    """列出反馈"""
    try:
        store = get_feedback_store()
        user_id = principal.user_id if principal.role != "admin" else None
        tenant_id = principal.tenant_id

        feedbacks = await store.list_feedback(
            tenant_id=tenant_id,
            user_id=user_id,
            feedback_type=feedback_type,
            status=status_filter,
            severity=severity,
            skip=skip,
            limit=limit,
        )

        total = await store.count_feedback(
            tenant_id=tenant_id,
            status=status_filter,
            severity=severity,
        )

        items = [
            FeedbackResponse(
                id=f.id,
                user_id=f.user_id,
                feedback_type=f.feedback_type,
                title=f.title,
                description=f.description,
                severity=f.severity,
                status=f.status,
                sentiment=f.sentiment,
                sentiment_score=f.sentiment_score,
                priority_score=f.priority_score,
                category=f.category,
                tags=f.tags,
                created_at=f.created_at.isoformat(),
                updated_at=f.updated_at.isoformat(),
                resolved_at=f.resolved_at.isoformat() if f.resolved_at else None,
            )
            for f in feedbacks
        ]

        return FeedbackListResponse(
            total=total,
            skip=skip,
            limit=limit,
            items=items,
        )

    except Exception as e:
        logger.error(f"列出反馈失败: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to list feedback"
        )


@router.get("/{feedback_id}/analysis", response_model=FeedbackAnalysisResponse)
async def get_feedback_analysis(
    feedback_id: str,
    principal: Annotated[Principal, Depends(get_current_principal)],
) -> FeedbackAnalysisResponse:
    """获取反馈分析"""
    try:
        store = get_feedback_store()
        analysis = await store.get_analysis_by_feedback_id(feedback_id)

        if not analysis:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Analysis not found"
            )

        return FeedbackAnalysisResponse(
            feedback_id=analysis.feedback_id,
            sentiment_type=analysis.sentiment_type,
            sentiment_score=analysis.sentiment_score,
            category=analysis.category,
            subcategory=analysis.subcategory,
            tags=analysis.tags,
            priority_score=analysis.priority_score,
            urgency_score=analysis.urgency_score,
            impact_score=analysis.impact_score,
            keywords=analysis.keywords or [],
            entities=analysis.entities or {},
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"获取反馈分析失败: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to get feedback analysis"
        )


@router.patch("/{feedback_id}", response_model=FeedbackResponse)
async def update_feedback(
    feedback_id: str,
    new_status: str | None = Query(None, alias="status", description="新状态"),
    principal: Annotated[Principal, Depends(get_current_principal)] = None,
) -> FeedbackResponse:
    """更新反馈状态"""
    try:
        if new_status and new_status not in [s.value for s in FeedbackStatus]:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Invalid status. Must be one of: {[s.value for s in FeedbackStatus]}"
            )

        store = get_feedback_store()
        feedback = await store.get_feedback_by_id(feedback_id)

        if not feedback:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Feedback not found"
            )

        # 检查权限
        if feedback.user_id != principal.user_id and principal.role != "admin":
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Access denied"
            )

        # 更新反馈
        update_data = {}
        if new_status:
            update_data["status"] = new_status
            if new_status == "resolved":
                update_data["resolved_at"] = datetime.now(UTC)

        feedback = await store.update_feedback(feedback_id, **update_data)

        return FeedbackResponse(
            id=feedback.id,
            user_id=feedback.user_id,
            feedback_type=feedback.feedback_type,
            title=feedback.title,
            description=feedback.description,
            severity=feedback.severity,
            status=feedback.status,
            sentiment=feedback.sentiment,
            sentiment_score=feedback.sentiment_score,
            priority_score=feedback.priority_score,
            category=feedback.category,
            tags=feedback.tags,
            created_at=feedback.created_at.isoformat(),
            updated_at=feedback.updated_at.isoformat(),
            resolved_at=feedback.resolved_at.isoformat() if feedback.resolved_at else None,
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"更新反馈失败: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to update feedback"
        )


@router.get("/stats/summary", response_model=FeedbackStatsResponse)
async def get_feedback_stats(
    principal: Annotated[Principal, Depends(get_current_principal)],
) -> FeedbackStatsResponse:
    """获取反馈统计"""
    try:
        store = get_feedback_store()
        tenant_id = principal.tenant_id

        # 获取各状态的计数
        statuses = ["new", "acknowledged", "in_progress", "resolved", "closed"]
        by_status = {}
        for s in statuses:
            count = await store.count_feedback(tenant_id=tenant_id, status=s)
            by_status[s] = count

        # 获取各严重程度的计数
        severities = ["low", "medium", "high", "critical"]
        by_severity = {}
        for sev in severities:
            count = await store.count_feedback(tenant_id=tenant_id, severity=sev)
            by_severity[sev] = count

        # 获取各类型的计数
        by_type = {
            "bug": 0,
            "feature": 0,
            "improvement": 0,
            "other": 0,
        }

        total = await store.count_feedback(tenant_id=tenant_id)
        critical_count = by_severity.get("critical", 0)

        return FeedbackStatsResponse(
            total=total,
            by_status=by_status,
            by_severity=by_severity,
            by_type=by_type,
            average_priority_score=0.5,  # 简化计算
            critical_count=critical_count,
        )

    except Exception as e:
        logger.error(f"获取反馈统计失败: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to get feedback stats"
        )
