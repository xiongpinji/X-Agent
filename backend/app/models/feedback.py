"""
用户反馈数据模型 - PostgreSQL实现
"""
from __future__ import annotations

import logging
from datetime import UTC, datetime
from enum import StrEnum

from sqlalchemy import (
    JSON,
    Column,
    DateTime,
    Float,
    Index,
    String,
    Text,
    select,
)
from sqlalchemy.orm import declarative_base

from backend.app.core.session import SessionManager

logger = logging.getLogger(__name__)

Base = declarative_base()


class FeedbackType(StrEnum):
    """反馈类型"""
    BUG = "bug"
    FEATURE = "feature"
    IMPROVEMENT = "improvement"
    OTHER = "other"


class FeedbackSeverity(StrEnum):
    """反馈严重程度"""
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


class FeedbackStatus(StrEnum):
    """反馈状态"""
    NEW = "new"
    ACKNOWLEDGED = "acknowledged"
    IN_PROGRESS = "in_progress"
    RESOLVED = "resolved"
    CLOSED = "closed"


class SentimentType(StrEnum):
    """情感类型"""
    POSITIVE = "positive"
    NEUTRAL = "neutral"
    NEGATIVE = "negative"


class FeedbackModel(Base):
    """反馈表模型"""
    __tablename__ = "feedback"

    id = Column(String(36), primary_key=True)
    user_id = Column(String(255), nullable=False, index=True)
    tenant_id = Column(String(255), nullable=False, index=True)
    feedback_type = Column(String(50), nullable=False)  # bug, feature, improvement, other
    title = Column(String(500), nullable=False)
    description = Column(Text, nullable=False)
    severity = Column(String(50), nullable=False)  # low, medium, high, critical
    status = Column(String(50), default="new", nullable=False, index=True)
    sentiment = Column(String(50), nullable=True)  # positive, neutral, negative
    sentiment_score = Column(Float, nullable=True)  # -1.0 to 1.0
    priority_score = Column(Float, nullable=True)  # 0.0 to 1.0
    category = Column(String(255), nullable=True)
    tags = Column(JSON, nullable=True)  # List of tags
    extra_metadata = Column("metadata", JSON, nullable=True)
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(UTC), nullable=False, index=True)
    updated_at = Column(DateTime(timezone=True), default=lambda: datetime.now(UTC), onupdate=lambda: datetime.now(UTC), nullable=False)
    resolved_at = Column(DateTime(timezone=True), nullable=True)

    __table_args__ = (
        Index("idx_feedback_user_tenant", "user_id", "tenant_id"),
        Index("idx_feedback_status_created", "status", "created_at"),
        Index("idx_feedback_severity_priority", "severity", "priority_score"),
    )


class FeedbackAnalysisModel(Base):
    """反馈分析表模型"""
    __tablename__ = "feedback_analysis"

    id = Column(String(36), primary_key=True)
    feedback_id = Column(String(36), nullable=False, index=True)
    sentiment_score = Column(Float, nullable=False)  # -1.0 to 1.0
    sentiment_type = Column(String(50), nullable=False)  # positive, neutral, negative
    category = Column(String(255), nullable=False)
    subcategory = Column(String(255), nullable=True)
    tags = Column(JSON, nullable=False)  # List of tags
    priority_score = Column(Float, nullable=False)  # 0.0 to 1.0
    urgency_score = Column(Float, nullable=False)  # 0.0 to 1.0
    impact_score = Column(Float, nullable=False)  # 0.0 to 1.0
    keywords = Column(JSON, nullable=True)  # Extracted keywords
    entities = Column(JSON, nullable=True)  # Named entities
    analysis_metadata = Column(JSON, nullable=True)
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(UTC), nullable=False)
    updated_at = Column(DateTime(timezone=True), default=lambda: datetime.now(UTC), onupdate=lambda: datetime.now(UTC), nullable=False)

    __table_args__ = (
        Index("idx_analysis_feedback", "feedback_id"),
        Index("idx_analysis_category", "category"),
    )


class FeedbackStorePostgres:
    """PostgreSQL反馈存储实现"""

    async def create_feedback(
        self,
        feedback_id: str,
        user_id: str,
        tenant_id: str,
        feedback_type: str,
        title: str,
        description: str,
        severity: str,
        metadata: dict | None = None,
    ) -> FeedbackModel:
        """创建反馈"""
        async with SessionManager.get_session() as session:
            feedback = FeedbackModel(
                id=feedback_id,
                user_id=user_id,
                tenant_id=tenant_id,
                feedback_type=feedback_type,
                title=title,
                description=description,
                severity=severity,
                status="new",
                extra_metadata=metadata or {},
            )
            session.add(feedback)
            await session.flush()
            logger.info(f"反馈创建成功: {feedback_id}")
            return feedback

    async def get_feedback_by_id(self, feedback_id: str) -> FeedbackModel | None:
        """根据ID获取反馈"""
        async with SessionManager.get_session() as session:
            stmt = select(FeedbackModel).where(FeedbackModel.id == feedback_id)
            result = await session.execute(stmt)
            return result.scalar_one_or_none()

    async def list_feedback(
        self,
        tenant_id: str,
        user_id: str | None = None,
        feedback_type: str | None = None,
        status: str | None = None,
        severity: str | None = None,
        skip: int = 0,
        limit: int = 100,
    ) -> list[FeedbackModel]:
        """列出反馈"""
        async with SessionManager.get_session() as session:
            stmt = select(FeedbackModel).where(FeedbackModel.tenant_id == tenant_id)

            if user_id:
                stmt = stmt.where(FeedbackModel.user_id == user_id)
            if feedback_type:
                stmt = stmt.where(FeedbackModel.feedback_type == feedback_type)
            if status:
                stmt = stmt.where(FeedbackModel.status == status)
            if severity:
                stmt = stmt.where(FeedbackModel.severity == severity)

            stmt = stmt.order_by(FeedbackModel.created_at.desc()).offset(skip).limit(limit)
            result = await session.execute(stmt)
            return result.scalars().all()

    async def update_feedback(
        self,
        feedback_id: str,
        **kwargs,
    ) -> FeedbackModel | None:
        """更新反馈"""
        async with SessionManager.get_session() as session:
            stmt = select(FeedbackModel).where(FeedbackModel.id == feedback_id)
            result = await session.execute(stmt)
            feedback = result.scalar_one_or_none()

            if not feedback:
                return None

            for key, value in kwargs.items():
                if hasattr(feedback, key):
                    setattr(feedback, key, value)

            feedback.updated_at = datetime.now(UTC)
            await session.flush()
            logger.info(f"反馈更新成功: {feedback_id}")
            return feedback

    async def create_analysis(
        self,
        analysis_id: str,
        feedback_id: str,
        sentiment_score: float,
        sentiment_type: str,
        category: str,
        tags: list[str],
        priority_score: float,
        urgency_score: float,
        impact_score: float,
        subcategory: str | None = None,
        keywords: list[str] | None = None,
        entities: dict | None = None,
        analysis_metadata: dict | None = None,
    ) -> FeedbackAnalysisModel:
        """创建反馈分析"""
        async with SessionManager.get_session() as session:
            analysis = FeedbackAnalysisModel(
                id=analysis_id,
                feedback_id=feedback_id,
                sentiment_score=sentiment_score,
                sentiment_type=sentiment_type,
                category=category,
                subcategory=subcategory,
                tags=tags,
                priority_score=priority_score,
                urgency_score=urgency_score,
                impact_score=impact_score,
                keywords=keywords or [],
                entities=entities or {},
                analysis_metadata=analysis_metadata or {},
            )
            session.add(analysis)
            await session.flush()
            logger.info(f"反馈分析创建成功: {analysis_id}")
            return analysis

    async def get_analysis_by_feedback_id(self, feedback_id: str) -> FeedbackAnalysisModel | None:
        """根据反馈ID获取分析"""
        async with SessionManager.get_session() as session:
            stmt = select(FeedbackAnalysisModel).where(FeedbackAnalysisModel.feedback_id == feedback_id)
            result = await session.execute(stmt)
            return result.scalar_one_or_none()

    async def count_feedback(
        self,
        tenant_id: str,
        status: str | None = None,
        severity: str | None = None,
    ) -> int:
        """统计反馈数量"""
        async with SessionManager.get_session() as session:
            stmt = select(FeedbackModel).where(FeedbackModel.tenant_id == tenant_id)

            if status:
                stmt = stmt.where(FeedbackModel.status == status)
            if severity:
                stmt = stmt.where(FeedbackModel.severity == severity)

            result = await session.execute(stmt)
            return len(result.scalars().all())
