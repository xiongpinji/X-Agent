"""技能市场管理器 - 核心业务逻辑"""

from __future__ import annotations

import logging
from typing import Optional, list, dict, Any
from datetime import datetime, UTC

from backend.app.core.skill_market_models import (
    SkillRecord, SkillCategory, SkillStatus, SkillInstallRequest,
    SkillUninstallRequest, SkillExecuteRequest, SkillSearchRequest,
    SkillInstallationProgress, SkillUsageRecord, SkillRecommendation,
)
from backend.app.core.skill_classifier import SkillClassifier, SkillTagger
from backend.app.core.skill_adapter import SkillAdapter
from backend.app.core.skill_content_generator import SkillContentGenerator
from backend.app.core.skill_crawler import SkillCrawler, SkillCacheManager

logger = logging.getLogger(__name__)


class SkillMarketManager:
    """技能市场管理器"""

    def __init__(self):
        self.skills: dict[str, SkillRecord] = {}
        self.installed_skills: dict[str, SkillRecord] = {}
        self.usage_history: list[SkillUsageRecord] = []
        self.tagger = SkillTagger()
        self.cache_manager = SkillCacheManager()
        self.crawler = SkillCrawler()

    # ==================== 技能发现 ====================

    async def discover_skills(
        self,
        category: Optional[SkillCategory] = None,
        tag: Optional[str] = None,
        limit: int = 20,
    ) -> list[SkillRecord]:
        """发现技能"""
        skills = list(self.skills.values())

        # 按分类过滤
        if category:
            skills = [s for s in skills if s.category == category]

        # 按标签过滤
        if tag:
            skills = [s for s in skills if tag in s.manifest.keywords]

        # 按评分排序
        skills.sort(key=lambda s: s.rating, reverse=True)

        return skills[:limit]

    async def search_skills(
        self,
        query: str,
        limit: int = 20,
    ) -> list[SkillRecord]:
        """搜索技能"""
        query_lower = query.lower()
        results = []

        for skill in self.skills.values():
            # 搜索名称
            if query_lower in skill.manifest.name.lower():
                results.append((skill, 1.0))
                continue

            # 搜索中文名称
            if query_lower in skill.manifest.name_zh.lower():
                results.append((skill, 1.0))
                continue

            # 搜索描述
            if query_lower in skill.manifest.description_zh.lower():
                results.append((skill, 0.8))
                continue

            # 搜索关键词
            if any(query_lower in kw.lower() for kw in skill.manifest.keywords):
                results.append((skill, 0.6))
                continue

        # 按相关性排序
        results.sort(key=lambda x: x[1], reverse=True)
        return [s[0] for s in results[:limit]]

    async def get_skill_info(self, skill_id: str) -> Optional[SkillRecord]:
        """获取技能详情"""
        return self.skills.get(skill_id)

    # ==================== 技能安装 ====================

    async def install_skill(
        self,
        request: SkillInstallRequest,
        user_id: str = "",
    ) -> SkillInstallationProgress:
        """安装技能"""
        skill = self.skills.get(request.skill_id)
        if not skill:
            return SkillInstallationProgress(
                skill_id=request.skill_id,
                status="error",
                progress=0,
                error="技能未找到",
            )

        if skill.is_installed:
            return SkillInstallationProgress(
                skill_id=request.skill_id,
                status="error",
                progress=0,
                error="技能已安装",
            )

        # 模拟安装过程
        progress = SkillInstallationProgress(
            skill_id=request.skill_id,
            status="installing",
            progress=0,
            message="开始安装...",
        )

        # 更新技能状态
        skill.status = SkillStatus.INSTALLING
        skill.is_installed = True
        skill.is_enabled = request.auto_enable
        skill.install_time = datetime.now(UTC)
        skill.installed_count += 1

        self.installed_skills[request.skill_id] = skill

        progress.status = "completed"
        progress.progress = 100
        progress.message = "安装完成"

        logger.info(f"技能 {request.skill_id} 已安装，用户: {user_id}")

        return progress

    async def uninstall_skill(
        self,
        request: SkillUninstallRequest,
        user_id: str = "",
    ) -> bool:
        """卸载技能"""
        skill = self.skills.get(request.skill_id)
        if not skill:
            return False

        if not skill.is_installed:
            return False

        # 更新技能状态
        skill.is_installed = False
        skill.is_enabled = False
        skill.installed_count = max(0, skill.installed_count - 1)

        if request.skill_id in self.installed_skills:
            del self.installed_skills[request.skill_id]

        logger.info(f"技能 {request.skill_id} 已卸载，用户: {user_id}")

        return True

    # ==================== 技能执行 ====================

    async def execute_skill(
        self,
        request: SkillExecuteRequest,
    ) -> dict[str, Any]:
        """执行技能"""
        skill = self.skills.get(request.skill_id)
        if not skill:
            return {
                "success": False,
                "error": "技能未找到",
            }

        if not skill.is_installed or not skill.is_enabled:
            return {
                "success": False,
                "error": "技能未安装或未启用",
            }

        # 记录使用
        usage = SkillUsageRecord(
            id=f"usage_{datetime.now(UTC).timestamp()}",
            skill_id=request.skill_id,
            user_id=request.user_id,
            input_data=request.input_data,
            output_data={},
            status="completed",
        )

        self.usage_history.append(usage)
        skill.usage_count += 1

        logger.info(f"技能 {request.skill_id} 已执行，用户: {request.user_id}")

        return {
            "success": True,
            "skill_id": request.skill_id,
            "result": "技能执行成功",
        }

    # ==================== 技能管理 ====================

    async def add_skill(self, skill: SkillRecord) -> bool:
        """添加技能"""
        # 验证技能格式
        is_valid, errors = SkillAdapter.validate_skill_format(skill)
        if not is_valid:
            logger.error(f"技能格式验证失败: {errors}")
            return False

        # 自动分类
        classification = SkillClassifier.classify(
            skill.manifest.name_zh,
            skill.manifest.description_zh,
            skill.manifest.keywords,
        )

        # 生成中文化内容
        chinese_content = SkillContentGenerator.generate_chinese_content(
            skill.manifest.name_zh,
            skill.manifest.description_zh,
            classification.domain.value,
        )

        # 更新技能
        skill.what_is_it = chinese_content.what_is_it
        skill.who_is_it_for = chinese_content.who_is_it_for
        skill.how_to_use = chinese_content.how_to_use
        skill.use_cases = chinese_content.use_cases
        skill.faq = chinese_content.faq
        skill.tutorial = chinese_content.tutorial
        skill.examples = chinese_content.examples
        skill.manifest.keywords.extend(classification.tags)

        self.skills[skill.id] = skill

        # 添加标签
        for tag in classification.tags:
            self.tagger.add_tag(tag, skill.id)

        logger.info(f"技能 {skill.id} 已添加")

        return True

    async def update_skill(self, skill: SkillRecord) -> bool:
        """更新技能"""
        if skill.id not in self.skills:
            return False

        self.skills[skill.id] = skill
        logger.info(f"技能 {skill.id} 已更新")

        return True

    async def delete_skill(self, skill_id: str) -> bool:
        """删除技能"""
        if skill_id not in self.skills:
            return False

        del self.skills[skill_id]
        if skill_id in self.installed_skills:
            del self.installed_skills[skill_id]

        logger.info(f"技能 {skill_id} 已删除")

        return True

    # ==================== 技能推荐 ====================

    async def get_recommendations(
        self,
        skill_id: str,
        limit: int = 5,
    ) -> list[SkillRecommendation]:
        """获取推荐技能"""
        skill = self.skills.get(skill_id)
        if not skill:
            return []

        recommendations = []

        # 找到相同分类的技能
        similar_skills = [
            s for s in self.skills.values()
            if s.category == skill.category and s.id != skill_id
        ]

        # 计算相似度
        for similar_skill in similar_skills:
            similarity = SkillClassifier.calculate_similarity(
                skill.manifest.keywords,
                similar_skill.manifest.keywords,
            )

            if similarity > 0:
                recommendations.append(
                    SkillRecommendation(
                        skill_id=similar_skill.id,
                        name_zh=similar_skill.manifest.name_zh,
                        reason=f"与{skill.manifest.name_zh}相关",
                        similarity_score=similarity,
                    )
                )

        # 按相似度排序
        recommendations.sort(key=lambda r: r.similarity_score, reverse=True)

        return recommendations[:limit]

    # ==================== 统计信息 ====================

    async def get_statistics(self) -> dict[str, Any]:
        """获取统计信息"""
        return {
            "total_skills": len(self.skills),
            "installed_skills": len(self.installed_skills),
            "total_downloads": sum(s.downloads for s in self.skills.values()),
            "total_usage": sum(s.usage_count for s in self.skills.values()),
            "average_rating": sum(s.rating for s in self.skills.values()) / max(1, len(self.skills)),
            "categories": {
                cat.value: len([s for s in self.skills.values() if s.category == cat])
                for cat in SkillCategory
            },
        }

    async def get_usage_history(
        self,
        user_id: str = "",
        limit: int = 20,
    ) -> list[SkillUsageRecord]:
        """获取使用历史"""
        history = self.usage_history

        if user_id:
            history = [h for h in history if h.user_id == user_id]

        # 按时间排序
        history.sort(key=lambda h: h.created_at, reverse=True)

        return history[:limit]

    # ==================== 爬虫集成 ====================

    async def sync_from_repositories(self) -> int:
        """从开源仓库同步技能"""
        logger.info("开始从开源仓库同步技能...")

        try:
            skills_data = await self.crawler.crawl_all_skills(limit=50)

            for skill_data in skills_data:
                try:
                    # 解析技能
                    from backend.app.core.skill_adapter import SkillMarkdownParser
                    parsed = SkillMarkdownParser.parse_skill_md(skill_data["skill_md"])

                    # 自动分类
                    classification = SkillClassifier.classify(
                        parsed.name_zh,
                        parsed.description_zh,
                        parsed.keywords,
                    )

                    # 创建技能记录
                    skill = SkillAdapter.adapt_from_github(
                        skill_data["name"],
                        skill_data["skill_md"],
                        skill_data["url"],
                        SkillCategory(classification.domain.value),
                    )

                    # 添加技能
                    await self.add_skill(skill)

                except Exception as e:
                    logger.error(f"处理技能 {skill_data['name']} 失败: {str(e)}")
                    continue

            logger.info(f"同步完成，共添加 {len(skills_data)} 个技能")
            return len(skills_data)

        except Exception as e:
            logger.error(f"同步技能失败: {str(e)}", exc_info=True)
            return 0


# 全局实例
_skill_market_manager: Optional[SkillMarketManager] = None


def get_skill_market_manager() -> SkillMarketManager:
    """获取技能市场管理器实例"""
    global _skill_market_manager
    if _skill_market_manager is None:
        _skill_market_manager = SkillMarketManager()
    return _skill_market_manager
