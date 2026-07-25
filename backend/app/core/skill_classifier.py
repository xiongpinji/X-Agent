"""技能分类和标签系统 - 自动分类、标签提取、相似度计算"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from enum import StrEnum

logger = logging.getLogger(__name__)


class SkillDomain(StrEnum):
    """技能领域"""
    OFFICE = "office"  # 办公
    DESIGN = "design"  # 设计
    DEVELOPMENT = "development"  # 开发
    DATA = "data"  # 数据
    AUTOMATION = "automation"  # 自动化
    LEARNING = "learning"  # 学习
    SEARCH = "search"  # 搜索
    CREATIVITY = "creativity"  # 创意


@dataclass
class ClassificationResult:
    """分类结果"""
    domain: SkillDomain
    confidence: float
    tags: list[str]
    keywords: list[str]


class SkillClassifier:
    """技能分类器"""

    # 关键词映射
    DOMAIN_KEYWORDS = {
        SkillDomain.OFFICE: [
            "报告", "文档", "表格", "ppt", "演示", "笔记", "整理",
            "word", "excel", "powerpoint", "文件", "办公", "写作",
            "编辑", "排版", "模板", "表单"
        ],
        SkillDomain.DESIGN: [
            "设计", "图片", "图像", "海报", "配色", "修图", "ui",
            "ux", "视觉", "美化", "排版", "字体", "颜色", "布局",
            "原型", "mockup", "ps", "ai", "figma"
        ],
        SkillDomain.DEVELOPMENT: [
            "代码", "编程", "开发", "调试", "审查", "git", "测试",
            "bug", "优化", "重构", "api", "数据库", "框架", "库",
            "python", "javascript", "java", "c++", "go", "rust"
        ],
        SkillDomain.DATA: [
            "数据", "分析", "统计", "可视化", "报表", "图表", "清洗",
            "挖掘", "预测", "机器学习", "ai", "ml", "sql", "excel",
            "pandas", "numpy", "matplotlib", "tableau"
        ],
        SkillDomain.AUTOMATION: [
            "自动化", "自动", "流程", "任务", "定时", "爬虫", "网页",
            "浏览器", "点击", "输入", "脚本", "机器人", "rpa", "工作流"
        ],
        SkillDomain.LEARNING: [
            "学习", "笔记", "总结", "知识", "教程", "课程", "计划",
            "复习", "记忆", "理解", "掌握", "提升", "进度", "目标"
        ],
        SkillDomain.SEARCH: [
            "搜索", "查找", "搜集", "信息", "资料", "网络", "爬虫",
            "采集", "整理", "分类", "索引", "查询", "检索", "聚合"
        ],
        SkillDomain.CREATIVITY: [
            "创意", "头脑风暴", "创新", "想法", "灵感", "生成", "创作",
            "文案", "故事", "剧本", "音乐", "诗歌", "艺术", "表达"
        ],
    }

    # 常见标签
    COMMON_TAGS = {
        "快速": ["快", "快速", "高效", "迅速", "快捷"],
        "易用": ["简单", "易用", "友好", "直观", "方便"],
        "强大": ["强大", "功能", "完整", "全面", "丰富"],
        "智能": ["智能", "ai", "机器学习", "自动", "聪明"],
        "免费": ["免费", "开源", "无费", "免付费"],
        "专业": ["专业", "企业", "商业", "高级", "pro"],
        "轻量": ["轻量", "小巧", "简洁", "精简", "轻"],
        "跨平台": ["跨平台", "兼容", "通用", "多平台"],
    }

    @classmethod
    def classify(cls, name: str, description: str, keywords: list[str] | None = None) -> ClassificationResult:
        """分类技能"""
        text = f"{name} {description} {' '.join(keywords or [])}".lower()

        # 计算每个领域的匹配分数
        domain_scores = {}
        for domain, domain_keywords in cls.DOMAIN_KEYWORDS.items():
            score = sum(1 for kw in domain_keywords if kw in text)
            domain_scores[domain] = score

        # 找到最高分的领域
        best_domain = max(domain_scores, key=domain_scores.get)
        max_score = domain_scores[best_domain]
        sum(len(kws) for kws in cls.DOMAIN_KEYWORDS.values())

        # 计算置信度
        confidence = min(1.0, max_score / max(1, len(cls.DOMAIN_KEYWORDS[best_domain])))

        # 提取标签
        tags = cls._extract_tags(text)

        # 提取关键词
        extracted_keywords = cls._extract_keywords(text, keywords or [])

        return ClassificationResult(
            domain=best_domain,
            confidence=confidence,
            tags=tags,
            keywords=extracted_keywords
        )

    @classmethod
    def _extract_tags(cls, text: str) -> list[str]:
        """提取标签"""
        tags = []
        for tag, keywords in cls.COMMON_TAGS.items():
            if any(kw in text for kw in keywords):
                tags.append(tag)
        return tags

    @classmethod
    def _extract_keywords(cls, text: str, provided_keywords: list[str]) -> list[str]:
        """提取关键词"""
        keywords = []

        # 添加提供的关键词
        keywords.extend(provided_keywords)

        # 从文本中提取常见关键词
        common_words = [
            "python", "javascript", "java", "c++", "go", "rust",
            "react", "vue", "angular", "django", "flask", "fastapi",
            "mysql", "postgresql", "mongodb", "redis",
            "docker", "kubernetes", "aws", "azure", "gcp",
            "git", "github", "gitlab", "bitbucket",
            "ai", "ml", "nlp", "cv", "llm", "gpt",
            "web", "mobile", "desktop", "cli",
            "api", "rest", "graphql", "grpc",
            "测试", "调试", "性能", "安全", "优化"
        ]

        for word in common_words:
            if word in text and word not in keywords:
                keywords.append(word)

        return keywords[:10]  # 限制关键词数量

    @classmethod
    def calculate_similarity(cls, skill1_keywords: list[str], skill2_keywords: list[str]) -> float:
        """计算技能相似度"""
        if not skill1_keywords or not skill2_keywords:
            return 0.0

        set1 = set(skill1_keywords)
        set2 = set(skill2_keywords)

        intersection = len(set1 & set2)
        union = len(set1 | set2)

        if union == 0:
            return 0.0

        return intersection / union


class SkillTagger:
    """技能标签管理"""

    def __init__(self):
        self.tags = {}
        self.tag_skills = {}

    def add_tag(self, tag: str, skill_id: str):
        """添加标签"""
        if tag not in self.tags:
            self.tags[tag] = []
        if skill_id not in self.tags[tag]:
            self.tags[tag].append(skill_id)

        if tag not in self.tag_skills:
            self.tag_skills[tag] = []
        if skill_id not in self.tag_skills[tag]:
            self.tag_skills[tag].append(skill_id)

    def get_skills_by_tag(self, tag: str) -> list[str]:
        """获取标签下的技能"""
        return self.tags.get(tag, [])

    def get_related_tags(self, tag: str, limit: int = 5) -> list[str]:
        """获取相关标签"""
        if tag not in self.tag_skills:
            return []

        # 找到与该标签共享技能的其他标签
        related = {}
        for skill_id in self.tag_skills[tag]:
            for other_tag, skills in self.tag_skills.items():
                if other_tag != tag and skill_id in skills:
                    related[other_tag] = related.get(other_tag, 0) + 1

        # 按共享技能数排序
        sorted_tags = sorted(related.items(), key=lambda x: x[1], reverse=True)
        return [t[0] for t in sorted_tags[:limit]]

    def get_popular_tags(self, limit: int = 10) -> list[tuple[str, int]]:
        """获取热门标签"""
        tag_counts = [(tag, len(skills)) for tag, skills in self.tags.items()]
        return sorted(tag_counts, key=lambda x: x[1], reverse=True)[:limit]
