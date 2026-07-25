"""技能评论评分系统 - 支持5星评分、评论、有用投票、举报、审核"""

from __future__ import annotations

import logging
import uuid
from dataclasses import dataclass, field
from datetime import UTC, datetime
from enum import StrEnum
from typing import Any

logger = logging.getLogger(__name__)


class ReviewStatus(StrEnum):
    """评论状态"""
    PENDING = "pending"  # 待审核
    APPROVED = "approved"  # 已批准
    REJECTED = "rejected"  # 已拒绝
    HIDDEN = "hidden"  # 已隐藏


class ReportReason(StrEnum):
    """举报原因"""
    SPAM = "spam"  # 垃圾信息
    INAPPROPRIATE = "inappropriate"  # 不当内容
    OFFENSIVE = "offensive"  # 冒犯性内容
    MISLEADING = "misleading"  # 误导性内容
    OTHER = "other"  # 其他


@dataclass
class SkillReview:
    """技能评论"""
    id: str = field(default_factory=lambda: str(uuid.uuid4()))
    skill_id: str = ""
    user_id: str = ""
    user_name: str = ""
    rating: int = 5  # 1-5星
    title: str = ""
    comment: str = ""
    status: ReviewStatus = ReviewStatus.PENDING
    helpful_count: int = 0  # 有用投票数
    unhelpful_count: int = 0  # 无用投票数
    verified_purchase: bool = False  # 是否已验证购买
    created_at: datetime = field(default_factory=lambda: datetime.now(UTC))
    updated_at: datetime = field(default_factory=lambda: datetime.now(UTC))

    def to_dict(self) -> dict[str, Any]:
        """转换为字典"""
        return {
            "id": self.id,
            "skill_id": self.skill_id,
            "user_id": self.user_id,
            "user_name": self.user_name,
            "rating": self.rating,
            "title": self.title,
            "comment": self.comment,
            "status": self.status.value,
            "helpful_count": self.helpful_count,
            "unhelpful_count": self.unhelpful_count,
            "verified_purchase": self.verified_purchase,
            "created_at": self.created_at.isoformat(),
            "updated_at": self.updated_at.isoformat(),
        }


@dataclass
class ReviewReport:
    """评论举报"""
    id: str = field(default_factory=lambda: str(uuid.uuid4()))
    review_id: str = ""
    reporter_id: str = ""
    reason: ReportReason = ReportReason.OTHER
    description: str = ""
    status: str = "pending"  # pending, investigating, resolved
    created_at: datetime = field(default_factory=lambda: datetime.now(UTC))
    resolved_at: datetime | None = None

    def to_dict(self) -> dict[str, Any]:
        """转换为字典"""
        return {
            "id": self.id,
            "review_id": self.review_id,
            "reporter_id": self.reporter_id,
            "reason": self.reason.value,
            "description": self.description,
            "status": self.status,
            "created_at": self.created_at.isoformat(),
            "resolved_at": self.resolved_at.isoformat() if self.resolved_at else None,
        }


class SkillReviewSystem:
    """技能评论评分系统"""

    def __init__(self):
        self.reviews: dict[str, list[SkillReview]] = {}  # skill_id -> [reviews]
        self.user_reviews: dict[str, list[SkillReview]] = {}  # user_id -> [reviews]
        self.reports: dict[str, ReviewReport] = {}  # report_id -> report
        self.helpful_votes: dict[str, set[str]] = {}  # review_id -> {user_ids}
        self.unhelpful_votes: dict[str, set[str]] = {}  # review_id -> {user_ids}

    def add_review(
        self,
        skill_id: str,
        user_id: str,
        user_name: str,
        rating: int,
        title: str = "",
        comment: str = "",
        verified_purchase: bool = False,
    ) -> tuple[bool, str | None, SkillReview | None]:
        """添加评论"""
        try:
            # 验证评分
            if not 1 <= rating <= 5:
                return False, "评分必须在1-5之间", None

            # 验证评论内容
            if not title and not comment:
                return False, "标题和评论不能同时为空", None

            # 检查用户是否已评论
            user_reviews = self.user_reviews.get(user_id, [])
            existing = [r for r in user_reviews if r.skill_id == skill_id]
            if existing:
                return False, "您已评论过此技能", None

            # 创建评论
            review = SkillReview(
                skill_id=skill_id,
                user_id=user_id,
                user_name=user_name,
                rating=rating,
                title=title,
                comment=comment,
                verified_purchase=verified_purchase,
                status=ReviewStatus.PENDING,
            )

            # 添加到技能评论列表
            if skill_id not in self.reviews:
                self.reviews[skill_id] = []
            self.reviews[skill_id].append(review)

            # 添加到用户评论列表
            if user_id not in self.user_reviews:
                self.user_reviews[user_id] = []
            self.user_reviews[user_id].append(review)

            logger.info(f"添加评论: {skill_id} by {user_id}")
            return True, None, review

        except Exception as e:
            error = f"添加评论失败: {e!s}"
            logger.error(error, exc_info=True)
            return False, error, None

    def get_reviews(
        self,
        skill_id: str,
        limit: int = 10,
        offset: int = 0,
        sort_by: str = "helpful",
        status: ReviewStatus | None = ReviewStatus.APPROVED,
    ) -> list[SkillReview]:
        """获取评论列表"""
        reviews = self.reviews.get(skill_id, [])

        # 过滤状态
        if status:
            reviews = [r for r in reviews if r.status == status]

        # 排序
        if sort_by == "helpful":
            reviews.sort(
                key=lambda r: (r.helpful_count - r.unhelpful_count),
                reverse=True
            )
        elif sort_by == "rating":
            reviews.sort(key=lambda r: r.rating, reverse=True)
        elif sort_by == "newest":
            reviews.sort(key=lambda r: r.created_at, reverse=True)
        elif sort_by == "oldest":
            reviews.sort(key=lambda r: r.created_at)

        return reviews[offset:offset + limit]

    def update_review(
        self,
        review_id: str,
        rating: int | None = None,
        title: str | None = None,
        comment: str | None = None,
    ) -> tuple[bool, str | None]:
        """更新评论"""
        try:
            # 查找评论
            review = None
            for reviews in self.reviews.values():
                for r in reviews:
                    if r.id == review_id:
                        review = r
                        break

            if not review:
                return False, "评论不存在"

            # 更新字段
            if rating is not None:
                if not 1 <= rating <= 5:
                    return False, "评分必须在1-5之间"
                review.rating = rating

            if title is not None:
                review.title = title

            if comment is not None:
                review.comment = comment

            review.updated_at = datetime.now(UTC)

            logger.info(f"更新评论: {review_id}")
            return True, None

        except Exception as e:
            error = f"更新评论失败: {e!s}"
            logger.error(error, exc_info=True)
            return False, error

    def delete_review(self, review_id: str) -> tuple[bool, str | None]:
        """删除评论"""
        try:
            # 查找并删除评论
            for _skill_id, reviews in self.reviews.items():
                for i, r in enumerate(reviews):
                    if r.id == review_id:
                        del reviews[i]

                        # 从用户评论列表中删除
                        user_reviews = self.user_reviews.get(r.user_id, [])
                        user_reviews = [ur for ur in user_reviews if ur.id != review_id]
                        self.user_reviews[r.user_id] = user_reviews

                        logger.info(f"删除评论: {review_id}")
                        return True, None

            return False, "评论不存在"

        except Exception as e:
            error = f"删除评论失败: {e!s}"
            logger.error(error, exc_info=True)
            return False, error

    def get_average_rating(self, skill_id: str) -> float:
        """获取平均评分"""
        reviews = self.reviews.get(skill_id, [])
        approved_reviews = [r for r in reviews if r.status == ReviewStatus.APPROVED]

        if not approved_reviews:
            return 0.0

        total_rating = sum(r.rating for r in approved_reviews)
        return round(total_rating / len(approved_reviews), 2)

    def get_rating_distribution(self, skill_id: str) -> dict[int, int]:
        """获取评分分布"""
        reviews = self.reviews.get(skill_id, [])
        approved_reviews = [r for r in reviews if r.status == ReviewStatus.APPROVED]

        distribution = {1: 0, 2: 0, 3: 0, 4: 0, 5: 0}
        for review in approved_reviews:
            distribution[review.rating] += 1

        return distribution

    def mark_helpful(self, review_id: str, user_id: str) -> tuple[bool, str | None]:
        """标记为有用"""
        try:
            # 查找评论
            review = self._find_review(review_id)
            if not review:
                return False, "评论不存在"

            # 检查是否已投票
            if review_id not in self.helpful_votes:
                self.helpful_votes[review_id] = set()

            if user_id in self.helpful_votes[review_id]:
                return False, "您已投过票"

            # 移除无用投票（如果存在）
            if review_id in self.unhelpful_votes:
                self.unhelpful_votes[review_id].discard(user_id)
                if user_id in self.unhelpful_votes[review_id]:
                    review.unhelpful_count = max(0, review.unhelpful_count - 1)

            # 添加有用投票
            self.helpful_votes[review_id].add(user_id)
            review.helpful_count += 1

            logger.info(f"标记为有用: {review_id} by {user_id}")
            return True, None

        except Exception as e:
            error = f"标记为有用失败: {e!s}"
            logger.error(error, exc_info=True)
            return False, error

    def mark_unhelpful(self, review_id: str, user_id: str) -> tuple[bool, str | None]:
        """标记为无用"""
        try:
            # 查找评论
            review = self._find_review(review_id)
            if not review:
                return False, "评论不存在"

            # 检查是否已投票
            if review_id not in self.unhelpful_votes:
                self.unhelpful_votes[review_id] = set()

            if user_id in self.unhelpful_votes[review_id]:
                return False, "您已投过票"

            # 移除有用投票（如果存在）
            if review_id in self.helpful_votes:
                self.helpful_votes[review_id].discard(user_id)
                if user_id in self.helpful_votes[review_id]:
                    review.helpful_count = max(0, review.helpful_count - 1)

            # 添加无用投票
            self.unhelpful_votes[review_id].add(user_id)
            review.unhelpful_count += 1

            logger.info(f"标记为无用: {review_id} by {user_id}")
            return True, None

        except Exception as e:
            error = f"标记为无用失败: {e!s}"
            logger.error(error, exc_info=True)
            return False, error

    def report_review(
        self,
        review_id: str,
        reporter_id: str,
        reason: ReportReason,
        description: str = "",
    ) -> tuple[bool, str | None, ReviewReport | None]:
        """举报评论"""
        try:
            # 查找评论
            review = self._find_review(review_id)
            if not review:
                return False, "评论不存在", None

            # 创建举报
            report = ReviewReport(
                review_id=review_id,
                reporter_id=reporter_id,
                reason=reason,
                description=description,
            )

            self.reports[report.id] = report

            logger.info(f"举报评论: {review_id} by {reporter_id}")
            return True, None, report

        except Exception as e:
            error = f"举报评论失败: {e!s}"
            logger.error(error, exc_info=True)
            return False, error, None

    def approve_review(self, review_id: str) -> tuple[bool, str | None]:
        """批准评论"""
        try:
            review = self._find_review(review_id)
            if not review:
                return False, "评论不存在"

            review.status = ReviewStatus.APPROVED
            review.updated_at = datetime.now(UTC)

            logger.info(f"批准评论: {review_id}")
            return True, None

        except Exception as e:
            error = f"批准评论失败: {e!s}"
            logger.error(error, exc_info=True)
            return False, error

    def reject_review(self, review_id: str) -> tuple[bool, str | None]:
        """拒绝评论"""
        try:
            review = self._find_review(review_id)
            if not review:
                return False, "评论不存在"

            review.status = ReviewStatus.REJECTED
            review.updated_at = datetime.now(UTC)

            logger.info(f"拒绝评论: {review_id}")
            return True, None

        except Exception as e:
            error = f"拒绝评论失败: {e!s}"
            logger.error(error, exc_info=True)
            return False, error

    def get_pending_reviews(self, limit: int = 20) -> list[SkillReview]:
        """获取待审核评论"""
        pending = []
        for reviews in self.reviews.values():
            pending.extend([r for r in reviews if r.status == ReviewStatus.PENDING])

        pending.sort(key=lambda r: r.created_at)
        return pending[:limit]

    def get_reports(self, status: str = "pending", limit: int = 20) -> list[ReviewReport]:
        """获取举报列表"""
        reports = [r for r in self.reports.values() if r.status == status]
        reports.sort(key=lambda r: r.created_at)
        return reports[:limit]

    def resolve_report(self, report_id: str, action: str) -> tuple[bool, str | None]:
        """处理举报 (action: approve, reject, hide)"""
        try:
            report = self.reports.get(report_id)
            if not report:
                return False, "举报不存在"

            review = self._find_review(report.review_id)
            if not review:
                return False, "评论不存在"

            if action == "approve":
                review.status = ReviewStatus.APPROVED
            elif action == "reject":
                review.status = ReviewStatus.REJECTED
            elif action == "hide":
                review.status = ReviewStatus.HIDDEN
            else:
                return False, "无效的操作"

            report.status = "resolved"
            report.resolved_at = datetime.now(UTC)

            logger.info(f"处理举报: {report_id} -> {action}")
            return True, None

        except Exception as e:
            error = f"处理举报失败: {e!s}"
            logger.error(error, exc_info=True)
            return False, error

    def _find_review(self, review_id: str) -> SkillReview | None:
        """查找评论"""
        for reviews in self.reviews.values():
            for r in reviews:
                if r.id == review_id:
                    return r
        return None


# 全局实例
_skill_review_system: SkillReviewSystem | None = None


def get_skill_review_system() -> SkillReviewSystem:
    """获取技能评论评分系统实例"""
    global _skill_review_system
    if _skill_review_system is None:
        _skill_review_system = SkillReviewSystem()
    return _skill_review_system


__all__ = [
    "ReportReason",
    "ReviewReport",
    "ReviewStatus",
    "SkillReview",
    "SkillReviewSystem",
    "get_skill_review_system",
]
