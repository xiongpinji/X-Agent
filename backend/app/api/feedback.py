"""
用户反馈API端点
"""
from __future__ import annotations

import csv
import io
import json
import logging
import os
from datetime import UTC, datetime, timedelta
from typing import Annotated
from uuid import uuid4

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Query, Response, status
from pydantic import BaseModel, Field

from backend.app.core.feedback_analyzer import feedback_analyzer
from backend.app.core.feedback_store_file import FeedbackStoreFile
from backend.app.core.notification_dispatch import (
    FeedbackEvent,
    dispatch_created_feedback,
    dispatch_feedback_event,
)
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
_feedback_store: FeedbackStorePostgres | FeedbackStoreFile | None = None
_feedback_store_backend: str | None = None
_feedback_fallback_warned = False

FEEDBACK_STORE_BACKEND_ENV = "XAGENT_FEEDBACK_STORE_BACKEND"


def _postgres_available() -> bool:
    """全局 DatabaseManager 已初始化且持有 session factory 时, Postgres 路径可用。"""
    try:
        from backend.app.core.database import get_db_manager

        manager = get_db_manager()
    except Exception:
        return False
    return getattr(manager, "_session_factory", None) is not None


def get_feedback_store_backend() -> str | None:
    """当前反馈存储后端(postgres/file), 未初始化时为 None。状态可查。"""
    if _feedback_store is None:
        get_feedback_store()
    return _feedback_store_backend


def get_feedback_store() -> FeedbackStorePostgres | FeedbackStoreFile:
    """反馈存储工厂。

    后端选择(与 workflow_store 的 auto 模式同哲学):
        XAGENT_FEEDBACK_STORE_BACKEND = postgres | file | auto   (默认 auto)
    - postgres: 强制 Postgres 存储(生产; 数据库不可用时在调用处显式报错, 不静默降级)。
    - file    : JSON 文件存储(dev)。
    - auto    : SessionManager 可用时走 Postgres; 不可用时 WARNING 一次并显式
                降级到文件存储(不静默、不报错), 状态可经 get_feedback_store_backend() 查询。
    """
    global _feedback_store, _feedback_store_backend, _feedback_fallback_warned
    if _feedback_store is not None:
        return _feedback_store

    backend = (os.getenv(FEEDBACK_STORE_BACKEND_ENV) or "auto").strip().lower()
    if backend not in {"postgres", "file", "auto"}:
        raise ValueError(
            f"Unknown feedback store backend {backend!r}; expected one of: postgres, file, auto."
        )

    if backend == "file":
        store: FeedbackStorePostgres | FeedbackStoreFile = FeedbackStoreFile()
        name = "file"
    elif backend == "postgres" or _postgres_available():
        store = FeedbackStorePostgres()
        name = "postgres"
    else:  # auto + Postgres 不可用 -> 显式降级
        if not _feedback_fallback_warned:
            logger.warning(
                "反馈存储: 数据库管理器未初始化, 显式降级为 JSON 文件存储(dev)。"
                "生产环境请设置 %s=postgres 并确保 init_db_manager 已调用。",
                FEEDBACK_STORE_BACKEND_ENV,
            )
            _feedback_fallback_warned = True
        store = FeedbackStoreFile()
        name = "file"

    _feedback_store = store
    _feedback_store_backend = name
    return store


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
    # 「解决说明」。前端 Feedback.response 一直有这个字段，但后端从未承接，
    # 于是 resolveFeedback 传的值被静默丢弃。
    resolution_note: str | None = None

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


class ResolveFeedbackRequest(BaseModel):
    """解决反馈请求（``POST /{id}/resolve`` 的可选请求体）。

    说明文本可选：不发请求体、发空体、或发 ``{"resolution_note": null}`` 都表示
    「只解决、不附说明」。这三种情况都**不会**覆盖记录上已有的说明 ——
    调用方没说删除，就不该被删除。
    """
    resolution_note: str | None = Field(None, max_length=5000, description="解决说明")


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
        resolution_note=feedback.resolution_note,
    )


def _to_dispatch_event(feedback: FeedbackModel) -> FeedbackEvent:
    """把反馈记录压成分发用的事件快照。

    只有分发需要的那几个字段 —— 事件对象刻意不含 user_id / tenant_id, 避免
    把租户与用户标识顺手带进通知正文和投递记录。
    """
    return FeedbackEvent(
        feedback_id=feedback.id,
        title=feedback.title,
        description=feedback.description or "",
        feedback_type=feedback.feedback_type,
        severity=feedback.severity or "",
        status=feedback.status or "",
        sentiment=feedback.sentiment,
        category=feedback.category,
        tags=list(feedback.tags or []),
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
    background_tasks: BackgroundTasks,
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

        # 事件分发接线点。放在分析**之后**: sentiment 由分析器算出,
        # sentiment_negative 这个 trigger 只有到这里才判得准。
        #
        # 用 BackgroundTasks 而非同步 await —— Webhook provider 超时 10s, 同步
        # 会把创建反馈的响应一起拖住。dispatch_* 自带失败隔离, 通知发不出去
        # 绝不会把「反馈已创建」这个事实弄失败。
        if feedback is not None:
            background_tasks.add_task(
                dispatch_created_feedback,
                tenant_id=tenant_id,
                event=_to_dispatch_event(feedback),
            )

        # 复用手写构造点 _to_response。此前 create / get / update / replace 四个
        # 端点各自手抄了一份与它逐字段相同的构造，list_feedback 的列表推导里还藏了
        # 第五份 —— 给 FeedbackResponse 加字段必须记得改满 5 处。本轮加
        # resolution_note 就是实例：漏掉 get_feedback，刚存进去的解决说明会在
        # 重新拉取时凭空消失。
        return _to_response(feedback)

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

        # 复用手写构造点 _to_response。此前 create / get / update / replace 四个
        # 端点各自手抄了一份与它逐字段相同的构造，list_feedback 的列表推导里还藏了
        # 第五份 —— 给 FeedbackResponse 加字段必须记得改满 5 处。本轮加
        # resolution_note 就是实例：漏掉 get_feedback，刚存进去的解决说明会在
        # 重新拉取时凭空消失。
        return _to_response(feedback)

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

        items = [_to_response(f) for f in feedbacks]

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

        # 复用手写构造点 _to_response。此前 create / get / update / replace 四个
        # 端点各自手抄了一份与它逐字段相同的构造，list_feedback 的列表推导里还藏了
        # 第五份 —— 给 FeedbackResponse 加字段必须记得改满 5 处。本轮加
        # resolution_note 就是实例：漏掉 get_feedback，刚存进去的解决说明会在
        # 重新拉取时凭空消失。
        return _to_response(feedback)

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
    background_tasks: BackgroundTasks,
    payload: ResolveFeedbackRequest | None = None,
    principal: Annotated[Principal, Depends(get_current_principal)] = None,
) -> FeedbackResponse:
    """将反馈标记为已解决(status=resolved 并记录 resolved_at)。

    请求体可选，承载「解决说明」resolution_note。不发体 = 只解决不附说明，
    此时记录上已有的说明保持不变。

    仅反馈所有者或管理员可操作, 强制 tenant 收敛。
    """
    enforce_scope(principal, "feedback:write")
    try:
        feedback = await _get_tenant_feedback_or_404(feedback_id, principal)
        _enforce_owner_or_admin(feedback, principal)

        updates = {"status": "resolved", "resolved_at": datetime.now(UTC)}
        # 只有显式带了说明才写入。否则一次不带说明的「重新解决」会抹掉上一次填的
        # 说明 —— 调用方从未要求删除它。
        # 注: store.update_feedback 走 hasattr 过滤, 未知键被静默忽略, 所以
        # resolution_note 必须真的存在于 FeedbackModel 上(本轮已加)。
        if payload is not None and payload.resolution_note is not None:
            updates["resolution_note"] = payload.resolution_note

        store = get_feedback_store()
        updated = await store.update_feedback(feedback_id, **updates)
        logger.info(f"反馈已解决: {feedback_id} (by {principal.user_id})")

        # 事件分发。刻意**只**在这个专用端点上触发 feedback_resolved, 不认
        # PATCH {status:"resolved"} —— 两条路径会让同一次「解决」投递两次通知。
        if updated is not None:
            background_tasks.add_task(
                dispatch_feedback_event,
                tenant_id=principal.tenant_id,
                trigger="feedback_resolved",
                event=_to_dispatch_event(updated),
            )

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
