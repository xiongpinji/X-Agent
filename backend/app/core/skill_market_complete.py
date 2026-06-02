"""技能市场完整管理系统 - 核心业务逻辑"""

from __future__ import annotations

import logging
import uuid
from typing import Optional, List, Dict, Any, Tuple
from datetime import datetime, UTC, timedelta
from enum import Enum

from pydantic import BaseModel, Field
import asyncpg

logger = logging.getLogger(__name__)


class SkillStatus(str, Enum):
    """技能状态"""
    DRAFT = "draft"
    PUBLISHED = "published"
    INSTALLING = "installing"
    INSTALLED = "installed"
    UPDATING = "updating"
    DISABLED = "disabled"
    ERROR = "error"


class ReviewStatus(str, Enum):
    """评论状态"""
    PENDING = "pending"
    APPROVED = "approved"
    REJECTED = "rejected"
    HIDDEN = "hidden"


class SkillPublishRequest(BaseModel):
    """技能发布请求"""
    name: str
    name_zh: str
    version: str
    category: str
    description: str
    description_zh: str
    author: str
    icon_emoji: str = ""
    keywords: List[str] = Field(default_factory=list)
    tags: List[str] = Field(default_factory=list)


class SkillReviewRequest(BaseModel):
    """技能审核请求"""
    skill_id: str
    action: str  # approved, rejected
    reason: Optional[str] = None


class SkillRatingRequest(BaseModel):
    """技能评分请求"""
    skill_id: str
    rating: int  # 1-5
    title: str
    comment: Optional[str] = None


class SkillMarketDB:
    """技能市场数据库管理"""

    def __init__(self, pool: asyncpg.Pool):
        self.pool = pool

    # ==================== 技能发布 ====================

    async def publish_skill(
        self,
        tenant_id: str,
        user_id: str,
        request: SkillPublishRequest,
    ) -> Dict[str, Any]:
        """发布技能"""
        skill_id = str(uuid.uuid4())
        slug = request.name.lower().replace(" ", "-")

        async with self.pool.acquire() as conn:
            await conn.execute("""
                INSERT INTO skills (
                    id, tenant_id, name, name_zh, slug, version, author,
                    description, description_zh, category, status,
                    icon_emoji, keywords, tags
                ) VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11, $12, $13, $14)
            """, skill_id, tenant_id, request.name, request.name_zh, slug,
                request.version, user_id, request.description, request.description_zh,
                request.category, SkillStatus.DRAFT.value, request.icon_emoji,
                request.keywords, request.tags)

            # 创建初始版本
            await conn.execute("""
                INSERT INTO skill_versions (skill_id, version, changelog)
                VALUES ($1, $2, $3)
            """, skill_id, request.version, "Initial release")

        logger.info(f"技能已发布: {skill_id}, 用户: {user_id}")
        return {"skill_id": skill_id, "status": "draft"}

    async def submit_for_review(
        self,
        skill_id: str,
        user_id: str,
    ) -> Dict[str, Any]:
        """提交审核"""
        async with self.pool.acquire() as conn:
            # 更新技能状态
            await conn.execute("""
                UPDATE skills SET status = $1, updated_at = NOW()
                WHERE id = $2
            """, SkillStatus.PUBLISHED.value, skill_id)

            # 记录审核日志
            await conn.execute("""
                INSERT INTO skill_reviews_audit (skill_id, reviewer_id, action)
                VALUES ($1, $2, $3)
            """, skill_id, user_id, "submitted")

        logger.info(f"技能已提交审核: {skill_id}")
        return {"skill_id": skill_id, "status": "submitted"}

    async def approve_skill(
        self,
        skill_id: str,
        reviewer_id: str,
        reason: Optional[str] = None,
    ) -> Dict[str, Any]:
        """批准技能"""
        async with self.pool.acquire() as conn:
            await conn.execute("""
                UPDATE skills SET status = $1, published_at = NOW(), updated_at = NOW()
                WHERE id = $2
            """, SkillStatus.PUBLISHED.value, skill_id)

            await conn.execute("""
                INSERT INTO skill_reviews_audit (skill_id, reviewer_id, action, reason)
                VALUES ($1, $2, $3, $4)
            """, skill_id, reviewer_id, "approved", reason)

        logger.info(f"技能已批准: {skill_id}")
        return {"skill_id": skill_id, "status": "approved"}

    async def reject_skill(
        self,
        skill_id: str,
        reviewer_id: str,
        reason: str,
    ) -> Dict[str, Any]:
        """拒绝技能"""
        async with self.pool.acquire() as conn:
            await conn.execute("""
                UPDATE skills SET status = $1, updated_at = NOW()
                WHERE id = $2
            """, SkillStatus.DRAFT.value, skill_id)

            await conn.execute("""
                INSERT INTO skill_reviews_audit (skill_id, reviewer_id, action, reason)
                VALUES ($1, $2, $3, $4)
            """, skill_id, reviewer_id, "rejected", reason)

        logger.info(f"技能已拒绝: {skill_id}")
        return {"skill_id": skill_id, "status": "rejected"}

    # ==================== 技能搜索 ====================

    async def search_skills(
        self,
        query: str,
        category: Optional[str] = None,
        limit: int = 20,
        offset: int = 0,
    ) -> Tuple[List[Dict[str, Any]], int]:
        """搜索技能"""
        async with self.pool.acquire() as conn:
            # 构建查询
            where_clauses = [
                "s.status = $1",
                "(s.name ILIKE $2 OR s.name_zh ILIKE $2 OR s.description_zh ILIKE $2)"
            ]
            params = [SkillStatus.PUBLISHED.value, f"%{query}%"]

            if category:
                where_clauses.append(f"s.category = ${len(params) + 1}")
                params.append(category)

            where_sql = " AND ".join(where_clauses)

            # 获取总数
            total = await conn.fetchval(
                f"SELECT COUNT(*) FROM skills s WHERE {where_sql}",
                *params
            )

            # 获取结果
            rows = await conn.fetch(f"""
                SELECT s.*, COUNT(DISTINCT sr.id) as review_count
                FROM skills s
                LEFT JOIN skill_reviews sr ON s.id = sr.skill_id AND sr.status = 'approved'
                WHERE {where_sql}
                GROUP BY s.id
                ORDER BY s.rating DESC, s.downloads DESC
                LIMIT ${{len(params) + 1}} OFFSET ${{len(params) + 2}}
            """, *params, limit, offset)

            return [dict(row) for row in rows], total

    async def get_skill_by_id(self, skill_id: str) -> Optional[Dict[str, Any]]:
        """获取技能详情"""
        async with self.pool.acquire() as conn:
            row = await conn.fetchrow("""
                SELECT s.*, COUNT(DISTINCT sr.id) as review_count
                FROM skills s
                LEFT JOIN skill_reviews sr ON s.id = sr.skill_id AND sr.status = 'approved'
                WHERE s.id = $1
                GROUP BY s.id
            """, skill_id)

            return dict(row) if row else None

    async def list_skills_by_category(
        self,
        category: str,
        limit: int = 20,
        offset: int = 0,
    ) -> Tuple[List[Dict[str, Any]], int]:
        """按分类列出技能"""
        async with self.pool.acquire() as conn:
            total = await conn.fetchval(
                "SELECT COUNT(*) FROM skills WHERE category = $1 AND status = $2",
                category, SkillStatus.PUBLISHED.value
            )

            rows = await conn.fetch("""
                SELECT * FROM skills
                WHERE category = $1 AND status = $2
                ORDER BY rating DESC, downloads DESC
                LIMIT $3 OFFSET $4
            """, category, SkillStatus.PUBLISHED.value, limit, offset)

            return [dict(row) for row in rows], total

    # ==================== 技能评分 ====================

    async def add_review(
        self,
        skill_id: str,
        user_id: str,
        user_name: str,
        request: SkillRatingRequest,
    ) -> Dict[str, Any]:
        """添加评论"""
        review_id = str(uuid.uuid4())

        async with self.pool.acquire() as conn:
            await conn.execute("""
                INSERT INTO skill_reviews (
                    id, skill_id, user_id, user_name, rating, title, comment, status
                ) VALUES ($1, $2, $3, $4, $5, $6, $7, $8)
            """, review_id, skill_id, user_id, user_name,
                request.rating, request.title, request.comment, ReviewStatus.APPROVED.value)

            # 更新技能评分
            avg_rating = await conn.fetchval("""
                SELECT AVG(rating) FROM skill_reviews
                WHERE skill_id = $1 AND status = 'approved'
            """, skill_id)

            count = await conn.fetchval("""
                SELECT COUNT(*) FROM skill_reviews
                WHERE skill_id = $1 AND status = 'approved'
            """, skill_id)

            await conn.execute("""
                UPDATE skills SET rating = $1, rating_count = $2, updated_at = NOW()
                WHERE id = $3
            """, float(avg_rating or 0), count, skill_id)

        logger.info(f"评论已添加: {review_id}, 技能: {skill_id}")
        return {"review_id": review_id, "status": "approved"}

    async def get_skill_reviews(
        self,
        skill_id: str,
        limit: int = 20,
        offset: int = 0,
    ) -> Tuple[List[Dict[str, Any]], int]:
        """获取技能评论"""
        async with self.pool.acquire() as conn:
            total = await conn.fetchval(
                "SELECT COUNT(*) FROM skill_reviews WHERE skill_id = $1 AND status = 'approved'",
                skill_id
            )

            rows = await conn.fetch("""
                SELECT * FROM skill_reviews
                WHERE skill_id = $1 AND status = 'approved'
                ORDER BY created_at DESC
                LIMIT $2 OFFSET $3
            """, skill_id, limit, offset)

            return [dict(row) for row in rows], total

    # ==================== 技能版本管理 ====================

    async def create_version(
        self,
        skill_id: str,
        version: str,
        changelog: str,
    ) -> Dict[str, Any]:
        """创建新版本"""
        version_id = str(uuid.uuid4())

        async with self.pool.acquire() as conn:
            await conn.execute("""
                INSERT INTO skill_versions (id, skill_id, version, changelog)
                VALUES ($1, $2, $3, $4)
            """, version_id, skill_id, version, changelog)

            # 更新技能版本
            await conn.execute("""
                UPDATE skills SET version = $1, updated_at = NOW()
                WHERE id = $2
            """, version, skill_id)

        logger.info(f"版本已创建: {version}, 技能: {skill_id}")
        return {"version_id": version_id, "version": version}

    async def get_skill_versions(self, skill_id: str) -> List[Dict[str, Any]]:
        """获取技能版本列表"""
        async with self.pool.acquire() as conn:
            rows = await conn.fetch("""
                SELECT * FROM skill_versions
                WHERE skill_id = $1
                ORDER BY release_date DESC
            """, skill_id)

            return [dict(row) for row in rows]

    # ==================== 技能依赖管理 ====================

    async def add_dependency(
        self,
        skill_id: str,
        dep_skill_id: str,
        version_spec: Optional[str] = None,
        dep_type: str = "required",
    ) -> Dict[str, Any]:
        """添加依赖"""
        dep_id = str(uuid.uuid4())

        async with self.pool.acquire() as conn:
            await conn.execute("""
                INSERT INTO skill_dependencies (
                    id, skill_id, dep_skill_id, version_spec, dep_type
                ) VALUES ($1, $2, $3, $4, $5)
            """, dep_id, skill_id, dep_skill_id, version_spec, dep_type)

        logger.info(f"依赖已添加: {skill_id} -> {dep_skill_id}")
        return {"dependency_id": dep_id}

    async def get_skill_dependencies(self, skill_id: str) -> List[Dict[str, Any]]:
        """获取技能依赖"""
        async with self.pool.acquire() as conn:
            rows = await conn.fetch("""
                SELECT sd.*, s.name, s.name_zh, s.version
                FROM skill_dependencies sd
                JOIN skills s ON sd.dep_skill_id = s.id
                WHERE sd.skill_id = $1
            """, skill_id)

            return [dict(row) for row in rows]

    # ==================== 技能安装 ====================

    async def install_skill(
        self,
        tenant_id: str,
        user_id: str,
        skill_id: str,
        version: str,
        config: Dict[str, Any] = None,
    ) -> Dict[str, Any]:
        """安装技能"""
        install_id = str(uuid.uuid4())

        async with self.pool.acquire() as conn:
            await conn.execute("""
                INSERT INTO skill_installations (
                    id, tenant_id, user_id, skill_id, version, status, config
                ) VALUES ($1, $2, $3, $4, $5, $6, $7)
                ON CONFLICT (tenant_id, user_id, skill_id)
                DO UPDATE SET version = $5, status = 'installed', updated_at = NOW()
            """, install_id, tenant_id, user_id, skill_id, version, "installed", config or {})

            # 更新技能安装数
            await conn.execute("""
                UPDATE skills SET installed_count = installed_count + 1
                WHERE id = $1
            """, skill_id)

        logger.info(f"技能已安装: {skill_id}, 用户: {user_id}")
        return {"install_id": install_id, "status": "installed"}

    async def uninstall_skill(
        self,
        tenant_id: str,
        user_id: str,
        skill_id: str,
    ) -> Dict[str, Any]:
        """卸载技能"""
        async with self.pool.acquire() as conn:
            await conn.execute("""
                DELETE FROM skill_installations
                WHERE tenant_id = $1 AND user_id = $2 AND skill_id = $3
            """, tenant_id, user_id, skill_id)

            # 更新技能安装数
            await conn.execute("""
                UPDATE skills SET installed_count = GREATEST(installed_count - 1, 0)
                WHERE id = $1
            """, skill_id)

        logger.info(f"技能已卸载: {skill_id}, 用户: {user_id}")
        return {"status": "uninstalled"}

    async def get_user_installations(
        self,
        tenant_id: str,
        user_id: str,
    ) -> List[Dict[str, Any]]:
        """获取用户已安装的技能"""
        async with self.pool.acquire() as conn:
            rows = await conn.fetch("""
                SELECT si.*, s.name, s.name_zh, s.icon_emoji, s.category
                FROM skill_installations si
                JOIN skills s ON si.skill_id = s.id
                WHERE si.tenant_id = $1 AND si.user_id = $2 AND si.status = 'installed'
                ORDER BY si.created_at DESC
            """, tenant_id, user_id)

            return [dict(row) for row in rows]

    # ==================== 技能使用记录 ====================

    async def record_usage(
        self,
        tenant_id: str,
        user_id: str,
        skill_id: str,
        input_data: Dict[str, Any],
        output_data: Dict[str, Any],
        status: str = "success",
        error: Optional[str] = None,
        duration_ms: int = 0,
    ) -> Dict[str, Any]:
        """记录技能使用"""
        record_id = str(uuid.uuid4())

        async with self.pool.acquire() as conn:
            await conn.execute("""
                INSERT INTO skill_usage_records (
                    id, tenant_id, user_id, skill_id, input_data, output_data,
                    status, error, duration_ms
                ) VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9)
            """, record_id, tenant_id, user_id, skill_id, input_data, output_data,
                status, error, duration_ms)

            # 更新技能使用数
            await conn.execute("""
                UPDATE skills SET usage_count = usage_count + 1
                WHERE id = $1
            """, skill_id)

        return {"record_id": record_id}

    async def get_skill_usage_stats(
        self,
        skill_id: str,
        days: int = 30,
    ) -> Dict[str, Any]:
        """获取技能使用统计"""
        async with self.pool.acquire() as conn:
            stats = await conn.fetchrow("""
                SELECT
                    COUNT(*) as total_uses,
                    COUNT(CASE WHEN status = 'success' THEN 1 END) as successful_uses,
                    COUNT(CASE WHEN status = 'error' THEN 1 END) as failed_uses,
                    AVG(duration_ms) as avg_duration_ms,
                    MAX(duration_ms) as max_duration_ms,
                    MIN(duration_ms) as min_duration_ms
                FROM skill_usage_records
                WHERE skill_id = $1 AND created_at > NOW() - INTERVAL '1 day' * $2
            """, skill_id, days)

            return dict(stats) if stats else {}

    # ==================== 技能推荐 ====================

    async def get_recommendations(
        self,
        tenant_id: str,
        user_id: str,
        limit: int = 10,
    ) -> List[Dict[str, Any]]:
        """获取技能推荐"""
        async with self.pool.acquire() as conn:
            rows = await conn.fetch("""
                SELECT sr.*, s.name, s.name_zh, s.icon_emoji, s.rating
                FROM skill_recommendations sr
                JOIN skills s ON sr.skill_id = s.id
                WHERE sr.tenant_id = $1 AND sr.user_id = $2
                ORDER BY sr.similarity_score DESC
                LIMIT $3
            """, tenant_id, user_id, limit)

            return [dict(row) for row in rows]

    # ==================== 统计信息 ====================

    async def get_market_stats(self, tenant_id: str) -> Dict[str, Any]:
        """获取市场统计"""
        async with self.pool.acquire() as conn:
            stats = await conn.fetchrow("""
                SELECT
                    COUNT(*) as total_skills,
                    COUNT(DISTINCT si.id) as installed_skills,
                    SUM(s.downloads) as total_downloads,
                    SUM(s.usage_count) as total_usage,
                    AVG(s.rating) as average_rating
                FROM skills s
                LEFT JOIN skill_installations si ON s.id = si.skill_id AND si.tenant_id = $1
                WHERE s.status = 'published'
            """, tenant_id)

            # 按分类统计
            categories = await conn.fetch("""
                SELECT category, COUNT(*) as count
                FROM skills
                WHERE status = 'published'
                GROUP BY category
            """)

            return {
                "total_skills": stats["total_skills"] or 0,
                "installed_skills": stats["installed_skills"] or 0,
                "total_downloads": stats["total_downloads"] or 0,
                "total_usage": stats["total_usage"] or 0,
                "average_rating": float(stats["average_rating"] or 0),
                "categories": {row["category"]: row["count"] for row in categories}
            }


# 全局实例
_skill_market_db: Optional[SkillMarketDB] = None


def get_skill_market_db(pool: asyncpg.Pool) -> SkillMarketDB:
    """获取技能市场数据库管理器"""
    global _skill_market_db
    if _skill_market_db is None:
        _skill_market_db = SkillMarketDB(pool)
    return _skill_market_db
