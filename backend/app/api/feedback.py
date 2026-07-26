"""
用户反馈API端点
"""
from __future__ import annotations

import csv
import io
import json
import logging
from datetime import UTC, datetime, timedelta
from typing import Annotated
from uuid import uuid4

from fastapi import APIRouter, Depends, HTTPException, Query, Response, status
from pydantic import BaseModel, Field

from backend.app.core.feedback_analyzer import feedback_analyzer
from backend.app.core.security import Principal
from backend.app.dependencies import enforce_scope, get_current_principal
from backend.app.models.feedback import (
    FeedbackModel,
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


class FeedbackUpdateRequest(BaseModel):
    """PUT 全量更新反馈请求"""
    feedback_type: str | None = Field(None, description="反馈类型: bug, feature, improvement, other")
    title: str | None = Field(None, min_length=1, max_length=500, description="反馈标题")
    description: str | None = Field(None, min_length=1, max_length=5000, description="反馈描述")
    severity: str | None = Field(None, description="严重程度: low, medium, high, critical")
    status: str | None = Field(None, description="状态: new, acknowledged, in_progress, resolved, closed")
    metadata: dict | None = Field(None, description="额外元数据")


class FeedbackTrendPoint(BaseModel):
    """趋势数据点(按日聚合)"""
    date: str
    count: int
    resolved: int


class FeedbackTrendsResponse(BaseModel):
    """反馈趋势响应"""
    period_days: int
    data_points: list[FeedbackTrendPoint]


class SentimentAnalysisSummaryResponse(BaseModel):
    """情感分布响应"""
    total: int
    distribution: dict[str, int]
    average_sentiment_score: float | None


class CategoryDistributionResponse(BaseModel):
    """分类分布响应"""
    total: int
    distribution: dict[str, int]


def _to_response(feedback: FeedbackModel) -> FeedbackResponse:
    """将 ORM 模型转换为 API 响应模型。"""
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


async def _get_tenant_feedback_or_404(feedback_id: str, principal: Principal) -> FeedbackModel:
    """获取反馈并强制 tenant 收敛: 跨租户一律 404, 避免泄露资源存在性。"""
    store = get_feedback_store()
    feedback = await store.get_feedback_by_id(feedback_id)
    if not feedback or feedback.tenant_id != principal.tenant_id:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Feedback not found"
        )
    return feedback


def _enforce_owner_or_admin(feedback: FeedbackModel, principal: Principal) -> None:
    """写操作权限: 仅反馈所有者或管理员可操作。"""
    if feedback.user_id != principal.user_id and principal.role != "admin":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Access denied"
        )


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


@router.get("/trends", response_model=FeedbackTrendsResponse)
async def get_feedback_trends(
    days: int = Query(30, ge=1, le=365, description="统计天数"),
    principal: Annotated[Principal, Depends(get_current_principal)] = None,
) -> FeedbackTrendsResponse:
    """反馈趋势(按日聚合), 强制 tenant 收敛。"""
    enforce_scope(principal, "feedback:read")
    try:
        store = get_feedback_store()
        since = datetime.now(UTC) - timedelta(days=days)
        feedbacks = await store.list_feedback(
            tenant_id=principal.tenant_id,
            skip=0,
            limit=10000,
        )

        # 按日聚合: count=当日新增, resolved=当日解决
        buckets: dict[str, dict[str, int]] = {}
        for f in feedbacks:
            created = f.created_at
            if created is not None and created.tzinfo is None:
                created = created.replace(tzinfo=UTC)
            if created is not None and created >= since:
                day = created.date().isoformat()
                buckets.setdefault(day, {"count": 0, "resolved": 0})["count"] += 1
            resolved = f.resolved_at
            if resolved is not None and resolved.tzinfo is None:
                resolved = resolved.replace(tzinfo=UTC)
            if resolved is not None and resolved >= since:
                day = resolved.date().isoformat()
                buckets.setdefault(day, {"count": 0, "resolved": 0})["resolved"] += 1

        data_points = [
            FeedbackTrendPoint(date=day, count=b["count"], resolved=b["resolved"])
            for day, b in sorted(buckets.items())
        ]
        return FeedbackTrendsResponse(period_days=days, data_points=data_points)

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"获取反馈趋势失败: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to get feedback trends"
        )


@router.get("/sentiment-analysis", response_model=SentimentAnalysisSummaryResponse)
async def get_sentiment_analysis(
    principal: Annotated[Principal, Depends(get_current_principal)],
) -> SentimentAnalysisSummaryResponse:
    """租户内反馈情感分布(基于仓内关键词情感分析结果), 强制 tenant 收敛。"""
    enforce_scope(principal, "feedback:read")
    try:
        store = get_feedback_store()
        feedbacks = await store.list_feedback(
            tenant_id=principal.tenant_id,
            skip=0,
            limit=10000,
        )

        distribution: dict[str, int] = {"positive": 0, "neutral": 0, "negative": 0, "unanalyzed": 0}
        scores: list[float] = []
        for f in feedbacks:
            if f.sentiment in ("positive", "neutral", "negative"):
                distribution[f.sentiment] += 1
            else:
                distribution["unanalyzed"] += 1
            if f.sentiment_score is not None:
                scores.append(f.sentiment_score)

        average = sum(scores) / len(scores) if scores else None
        return SentimentAnalysisSummaryResponse(
            total=len(feedbacks),
            distribution=distribution,
            average_sentiment_score=average,
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"获取情感分布失败: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to get sentiment analysis"
        )


@router.get("/category-distribution", response_model=CategoryDistributionResponse)
async def get_category_distribution(
    principal: Annotated[Principal, Depends(get_current_principal)],
) -> CategoryDistributionResponse:
    """租户内反馈分类分布, 强制 tenant 收敛。"""
    enforce_scope(principal, "feedback:read")
    try:
        store = get_feedback_store()
        feedbacks = await store.list_feedback(
            tenant_id=principal.tenant_id,
            skip=0,
            limit=10000,
        )

        distribution: dict[str, int] = {}
        for f in feedbacks:
            category = f.category or "uncategorized"
            distribution[category] = distribution.get(category, 0) + 1

        return CategoryDistributionResponse(
            total=len(feedbacks),
            distribution=dict(sorted(distribution.items(), key=lambda kv: kv[1], reverse=True)),
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"获取分类分布失败: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to get category distribution"
        )


@router.get("/search", response_model=FeedbackListResponse)
async def search_feedback(
    q: str = Query(..., min_length=1, max_length=200, description="搜索关键词"),
    skip: int = Query(0, ge=0, description="跳过数量"),
    limit: int = Query(100, ge=1, le=1000, description="限制数量"),
    principal: Annotated[Principal, Depends(get_current_principal)] = None,
) -> FeedbackListResponse:
    """按关键词搜索反馈(标题/描述), 强制 tenant 收敛; 非管理员仅搜自己的反馈。"""
    enforce_scope(principal, "feedback:read")
    try:
        store = get_feedback_store()
        user_id = principal.user_id if principal.role != "admin" else None

        feedbacks = await store.search_feedback(
            tenant_id=principal.tenant_id,
            keyword=q,
            user_id=user_id,
            skip=0,
            limit=skip + limit,  # 取足量后内存分页, 同时得到 total
        )

        total = len(feedbacks)
        items = [_to_response(f) for f in feedbacks[skip:skip + limit]]

        return FeedbackListResponse(total=total, skip=skip, limit=limit, items=items)

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"搜索反馈失败: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to search feedback"
        )


@router.get("/export")
async def export_feedback(
    export_format: str = Query("csv", alias="format", pattern="^(csv|json)$", description="导出格式: csv 或 json"),
    principal: Annotated[Principal, Depends(get_current_principal)] = None,
) -> Response:
    """导出反馈(csv/json), 强制 tenant 收敛; 非管理员仅导出自己的反馈。"""
    enforce_scope(principal, "feedback:read")
    try:
        store = get_feedback_store()
        user_id = principal.user_id if principal.role != "admin" else None

        feedbacks = await store.list_feedback(
            tenant_id=principal.tenant_id,
            user_id=user_id,
            skip=0,
            limit=10000,
        )
        records = [_to_response(f).model_dump() for f in feedbacks]

        timestamp = datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ")
        if export_format == "json":
            return Response(
                content=json.dumps(records, ensure_ascii=False, indent=2),
                media_type="application/json",
                headers={
                    "Content-Disposition": f'attachment; filename="feedback_export_{timestamp}.json"'
                },
            )

        # CSV 导出
        output = io.StringIO()
        fieldnames = [
            "id", "user_id", "feedback_type", "title", "description", "severity",
            "status", "sentiment", "sentiment_score", "priority_score", "category",
            "tags", "created_at", "updated_at", "resolved_at",
        ]
        writer = csv.DictWriter(output, fieldnames=fieldnames)
        writer.writeheader()
        for record in records:
            row = dict(record)
            row["tags"] = json.dumps(row.get("tags") or [], ensure_ascii=False)
            writer.writerow(row)

        return Response(
            content="﻿" + output.getvalue(),  # BOM 便于 Excel 识别 UTF-8
            media_type="text/csv; charset=utf-8",
            headers={
                "Content-Disposition": f'attachment; filename="feedback_export_{timestamp}.csv"'
            },
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"导出反馈失败: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to export feedback"
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

        if not feedback or feedback.tenant_id != principal.tenant_id:
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

        if not feedback or feedback.tenant_id != principal.tenant_id:
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


@router.put("/{feedback_id}", response_model=FeedbackResponse)
async def replace_feedback(
    feedback_id: str,
    request: FeedbackUpdateRequest,
    principal: Annotated[Principal, Depends(get_current_principal)],
) -> FeedbackResponse:
    """更新反馈(标题/描述/类型/严重程度/状态/元数据)。

    仅反馈所有者或管理员可操作, 强制 tenant 收敛。
    """
    enforce_scope(principal, "feedback:write")
    try:
        # 枚举校验
        if request.feedback_type and request.feedback_type not in [t.value for t in FeedbackType]:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Invalid feedback_type. Must be one of: {[t.value for t in FeedbackType]}"
            )
        if request.severity and request.severity not in [s.value for s in FeedbackSeverity]:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Invalid severity. Must be one of: {[s.value for s in FeedbackSeverity]}"
            )
        if request.status and request.status not in [s.value for s in FeedbackStatus]:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Invalid status. Must be one of: {[s.value for s in FeedbackStatus]}"
            )

        feedback = await _get_tenant_feedback_or_404(feedback_id, principal)
        _enforce_owner_or_admin(feedback, principal)

        update_data: dict = {}
        if request.feedback_type is not None:
            update_data["feedback_type"] = request.feedback_type
        if request.title is not None:
            update_data["title"] = request.title
        if request.description is not None:
            update_data["description"] = request.description
        if request.severity is not None:
            update_data["severity"] = request.severity
        if request.metadata is not None:
            update_data["extra_metadata"] = request.metadata
        if request.status is not None:
            update_data["status"] = request.status
            if request.status == "resolved" and feedback.resolved_at is None:
                update_data["resolved_at"] = datetime.now(UTC)

        store = get_feedback_store()
        updated = await store.update_feedback(feedback_id, **update_data)
        return _to_response(updated)

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"更新反馈失败: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to update feedback"
        )


@router.delete("/{feedback_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_feedback(
    feedback_id: str,
    principal: Annotated[Principal, Depends(get_current_principal)],
) -> Response:
    """删除反馈(级联删除分析记录)。

    仅反馈所有者或管理员可操作, 强制 tenant 收敛。
    """
    enforce_scope(principal, "feedback:write")
    try:
        feedback = await _get_tenant_feedback_or_404(feedback_id, principal)
        _enforce_owner_or_admin(feedback, principal)

        store = get_feedback_store()
        deleted = await store.delete_feedback(feedback_id)
        if not deleted:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Feedback not found"
            )
        return Response(status_code=status.HTTP_204_NO_CONTENT)

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"删除反馈失败: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to delete feedback"
        )


@router.post("/{feedback_id}/resolve", response_model=FeedbackResponse)
async def resolve_feedback(
    feedback_id: str,
    principal: Annotated[Principal, Depends(get_current_principal)],
) -> FeedbackResponse:
    """将反馈标记为已解决(status=resolved 并记录 resolved_at)。

    仅反馈所有者或管理员可操作, 强制 tenant 收敛。
    """
    enforce_scope(principal, "feedback:write")
    try:
        feedback = await _get_tenant_feedback_or_404(feedback_id, principal)
        _enforce_owner_or_admin(feedback, principal)

        store = get_feedback_store()
        updated = await store.update_feedback(
            feedback_id,
            status="resolved",
            resolved_at=datetime.now(UTC),
        )
        logger.info(f"反馈已解决: {feedback_id} (by {principal.user_id})")
        return _to_response(updated)

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"解决反馈失败: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to resolve feedback"
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
