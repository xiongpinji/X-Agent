"""技能爬虫系统 - 从GitHub、Gitee等开源仓库爬取技能"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import list

logger = logging.getLogger(__name__)


@dataclass
class RepositoryInfo:
    """仓库信息"""
    name: str
    url: str
    description: str
    stars: int
    language: str
    last_updated: datetime
    owner: str


class SkillCrawler:
    """技能爬虫 - 从开源仓库爬取技能"""

    # GitHub搜索关键词
    GITHUB_SEARCH_KEYWORDS = [
        "x-agent-skill",
        "claude-skill",
        "ai-skill",
        "workflow-skill",
        "automation-skill",
        "topic:skill",
    ]

    # Gitee搜索关键词
    GITEE_SEARCH_KEYWORDS = [
        "x-agent-skill",
        "claude-skill",
        "ai-skill",
    ]

    @staticmethod
    async def search_github_skills(
        keyword: str = "x-agent-skill",
        language: str = "python",
        sort: str = "stars",
        limit: int = 30,
    ) -> list[RepositoryInfo]:
        """搜索GitHub上的技能仓库"""

        # 模拟搜索结果（实际应该调用GitHub API）
        # 这里返回示例数据
        example_repos = [
            RepositoryInfo(
                name="code-review-skill",
                url="https://github.com/example/code-review-skill",
                description="代码审查技能 - 帮你检查代码质量",
                stars=150,
                language="python",
                last_updated=datetime.now(UTC),
                owner="example",
            ),
            RepositoryInfo(
                name="data-analysis-skill",
                url="https://github.com/example/data-analysis-skill",
                description="数据分析技能 - 快速分析数据",
                stars=200,
                language="python",
                last_updated=datetime.now(UTC),
                owner="example",
            ),
            RepositoryInfo(
                name="document-generator-skill",
                url="https://github.com/example/document-generator-skill",
                description="文档生成技能 - 自动生成文档",
                stars=100,
                language="python",
                last_updated=datetime.now(UTC),
                owner="example",
            ),
        ]

        return example_repos[:limit]

    @staticmethod
    async def search_gitee_skills(
        keyword: str = "x-agent-skill",
        language: str = "python",
        sort: str = "stars",
        limit: int = 30,
    ) -> list[RepositoryInfo]:
        """搜索Gitee上的技能仓库"""

        # 模拟搜索结果
        example_repos = [
            RepositoryInfo(
                name="chinese-text-skill",
                url="https://gitee.com/example/chinese-text-skill",
                description="中文文本处理技能",
                stars=80,
                language="python",
                last_updated=datetime.now(UTC),
                owner="example",
            ),
            RepositoryInfo(
                name="web-automation-skill",
                url="https://gitee.com/example/web-automation-skill",
                description="网页自动化技能",
                stars=120,
                language="python",
                last_updated=datetime.now(UTC),
                owner="example",
            ),
        ]

        return example_repos[:limit]

    @staticmethod
    async def fetch_skill_md(repo_url: str) -> str | None:
        """获取仓库中的SKILL.md文件"""
        # 模拟获取SKILL.md内容
        # 实际应该从GitHub/Gitee API获取

        skill_md_template = """# 代码审查助手 / Code Review Assistant

**版本**: 1.0.0
**作者**: AI Developer
**描述**: 帮你检查代码有没有问题，就像有个经验丰富的程序员帮你看代码。
**关键词**: 代码, 审查, 质量, 调试, 优化
**能力**: 代码分析, 质量检查, 性能优化, 安全审查
**图标**: 🔍

## 这个技能是干什么的？

帮你检查代码有没有问题，就像有个经验丰富的程序员帮你看代码。

## 适合谁用？

- 新手程序员：学习写出更好的代码
- 团队leader：快速审查团队代码
- 自学者：没人帮忙看代码时用

## 怎么用？

1. 点击"一键使用"按钮
2. 把你的代码粘贴进去
3. 等几秒钟
4. 看到详细的审查报告

## 使用示例

```python
# 你的代码
def add(a, b):
    return a + b

# 审查结果会告诉你：
# ✓ 代码逻辑正确
# ⚠ 建议添加类型提示
# ⚠ 建议添加文档字符串
```
"""
        return skill_md_template

    @staticmethod
    async def validate_skill_repo(repo_url: str) -> bool:
        """验证仓库是否包含有效的技能"""
        # 检查是否有SKILL.md文件
        skill_md = await SkillCrawler.fetch_skill_md(repo_url)
        return skill_md is not None and len(skill_md) > 0

    @staticmethod
    async def crawl_all_skills(
        sources: list[str] | None = None,
        limit: int = 100,
    ) -> list[dict]:
        """爬取所有技能"""
        if sources is None:
            sources = ["github", "gitee"]

        all_skills = []

        # 从GitHub爬取
        if "github" in sources:
            logger.info("正在从GitHub爬取技能...")
            github_repos = await SkillCrawler.search_github_skills(limit=limit // 2)
            for repo in github_repos:
                skill_md = await SkillCrawler.fetch_skill_md(repo.url)
                if skill_md:
                    all_skills.append({
                        "name": repo.name,
                        "url": repo.url,
                        "description": repo.description,
                        "stars": repo.stars,
                        "source": "github",
                        "skill_md": skill_md,
                    })

        # 从Gitee爬取
        if "gitee" in sources:
            logger.info("正在从Gitee爬取技能...")
            gitee_repos = await SkillCrawler.search_gitee_skills(limit=limit // 2)
            for repo in gitee_repos:
                skill_md = await SkillCrawler.fetch_skill_md(repo.url)
                if skill_md:
                    all_skills.append({
                        "name": repo.name,
                        "url": repo.url,
                        "description": repo.description,
                        "stars": repo.stars,
                        "source": "gitee",
                        "skill_md": skill_md,
                    })

        logger.info(f"爬取完成，共找到 {len(all_skills)} 个技能")
        return all_skills


class SkillCacheManager:
    """技能缓存管理"""

    def __init__(self, cache_dir: str = "/tmp/skill_cache"):
        self.cache_dir = cache_dir
        self.cache = {}

    def get(self, key: str) -> dict | None:
        """获取缓存"""
        return self.cache.get(key)

    def set(self, key: str, value: dict, ttl: int = 3600):
        """设置缓存"""
        self.cache[key] = {
            "value": value,
            "timestamp": datetime.now(UTC),
            "ttl": ttl,
        }

    def is_expired(self, key: str) -> bool:
        """检查缓存是否过期"""
        if key not in self.cache:
            return True

        cache_entry = self.cache[key]
        age = (datetime.now(UTC) - cache_entry["timestamp"]).total_seconds()
        return age > cache_entry["ttl"]

    def clear(self):
        """清空缓存"""
        self.cache.clear()

    def cleanup_expired(self):
        """清理过期缓存"""
        expired_keys = [k for k in self.cache if self.is_expired(k)]
        for key in expired_keys:
            del self.cache[key]


class SkillUpdateScheduler:
    """技能更新调度器 - 定期更新技能信息"""

    def __init__(self, update_interval: int = 86400):  # 默认24小时
        self.update_interval = update_interval
        self.last_update = None
        self.is_updating = False

    async def should_update(self) -> bool:
        """检查是否需要更新"""
        if self.last_update is None:
            return True

        age = (datetime.now(UTC) - self.last_update).total_seconds()
        return age > self.update_interval

    async def update_skills(self, crawler: SkillCrawler) -> list[dict]:
        """更新技能列表"""
        if self.is_updating:
            logger.warning("技能更新已在进行中，跳过本次更新")
            return []

        self.is_updating = True
        try:
            logger.info("开始更新技能列表...")
            skills = await crawler.crawl_all_skills()
            self.last_update = datetime.now(UTC)
            logger.info(f"技能列表更新完成，共 {len(skills)} 个技能")
            return skills
        except Exception as e:
            logger.error(f"技能更新失败: {e!s}", exc_info=True)
            return []
        finally:
            self.is_updating = False
