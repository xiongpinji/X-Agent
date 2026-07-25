"""
反馈分析引擎 - 情感分析、分类、优先级计算
"""
from __future__ import annotations

import logging
import re

logger = logging.getLogger(__name__)


class FeedbackAnalyzer:
    """反馈分析引擎"""

    # 关键词映射
    SENTIMENT_KEYWORDS = {
        "positive": [
            "great", "excellent", "amazing", "wonderful", "fantastic", "love", "perfect",
            "awesome", "brilliant", "outstanding", "impressed", "satisfied", "happy",
            "better", "improve", "improved", "improvement",
            "好", "很好", "优秀", "完美", "喜欢", "棒", "太好了", "满意", "高兴",
        ],
        "negative": [
            "bad", "terrible", "awful", "horrible", "hate", "broken", "crash", "error",
            "bug", "issue", "problem", "fail", "disappointed", "frustrated", "angry",
            "vulnerability", "vulnerable", "exploit", "breach",
            "差", "很差", "糟糕", "讨厌", "坏", "崩溃", "错误", "失败", "失望",
        ],
    }

    # 分类关键词
    CATEGORY_KEYWORDS = {
        "performance": [
            "slow", "fast", "speed", "lag", "latency", "timeout", "freeze",
            "慢", "快", "速度", "卡", "延迟", "超时", "冻结",
        ],
        "usability": [
            "confusing", "unclear", "difficult", "easy", "intuitive", "ui", "ux",
            "interface", "button", "menu", "navigation",
            "困惑", "不清楚", "困难", "容易", "直观", "界面", "按钮", "菜单", "导航",
        ],
        "functionality": [
            "feature", "function", "work", "not working", "missing", "add", "implement",
            "功能", "特性", "工作", "不工作", "缺失", "添加", "实现",
        ],
        "compatibility": [
            "browser", "device", "os", "windows", "mac", "linux", "mobile", "tablet",
            "浏览器", "设备", "操作系统", "视窗", "苹果", "安卓", "移动", "平板",
        ],
        "documentation": [
            "doc", "documentation", "guide", "tutorial", "help", "manual", "readme",
            "文档", "指南", "教程", "帮助", "手册", "说明",
        ],
        "security": [
            "security", "safe", "unsafe", "vulnerability", "exploit", "hack", "breach",
            "安全", "漏洞", "攻击", "破解", "泄露",
        ],
    }

    # 严重程度关键词
    SEVERITY_KEYWORDS = {
        "critical": [
            "critical", "crash", "data loss", "security", "urgent", "emergency",
            "严重", "崩溃", "数据丢失", "安全", "紧急", "应急",
        ],
        "high": [
            "high", "major", "significant", "important", "blocking",
            "高", "主要", "重要", "阻塞",
        ],
        "medium": [
            "medium", "moderate", "normal", "regular",
            "中等", "适度", "正常", "常规",
        ],
    }

    def __init__(self):
        """初始化分析器"""
        self.sentiment_model = None
        self._init_sentiment_model()

    def _init_sentiment_model(self):
        """初始化情感分析模型"""
        try:
            from textblob import TextBlob  # noqa: F401
            self.sentiment_model = "textblob"
            logger.info("TextBlob情感分析模型已加载")
        except ImportError:
            logger.warning("TextBlob未安装，使用基于关键词的情感分析")
            self.sentiment_model = "keyword"

    def analyze_sentiment(self, text: str) -> tuple[str, float]:
        """
        分析文本情感
        返回: (sentiment_type, sentiment_score)
        sentiment_type: positive, neutral, negative
        sentiment_score: -1.0 to 1.0
        """
        if not text:
            return "neutral", 0.0

        text_lower = text.lower()

        if self.sentiment_model == "textblob":
            try:
                from textblob import TextBlob
                blob = TextBlob(text)
                polarity = blob.sentiment.polarity  # -1.0 to 1.0

                if polarity > 0.1:
                    sentiment_type = "positive"
                elif polarity < -0.1:
                    sentiment_type = "negative"
                else:
                    sentiment_type = "neutral"

                return sentiment_type, polarity
            except Exception as e:
                logger.warning(f"TextBlob分析失败: {e}，使用关键词分析")

        # 基于关键词的情感分析
        positive_count = sum(1 for keyword in self.SENTIMENT_KEYWORDS["positive"] if keyword in text_lower)
        negative_count = sum(1 for keyword in self.SENTIMENT_KEYWORDS["negative"] if keyword in text_lower)

        if positive_count > negative_count:
            sentiment_type = "positive"
            sentiment_score = min(positive_count / max(positive_count + negative_count, 1), 1.0)
        elif negative_count > positive_count:
            sentiment_type = "negative"
            sentiment_score = -min(negative_count / max(positive_count + negative_count, 1), 1.0)
        else:
            sentiment_type = "neutral"
            sentiment_score = 0.0

        return sentiment_type, sentiment_score

    def categorize_feedback(self, text: str, feedback_type: str) -> tuple[str, str | None, list[str]]:
        """
        分类反馈
        返回: (category, subcategory, tags)
        """
        if not text:
            return "general", None, []

        text_lower = text.lower()
        category_scores = {}

        # 计算每个分类的匹配分数
        for category, keywords in self.CATEGORY_KEYWORDS.items():
            score = sum(1 for keyword in keywords if keyword in text_lower)
            if score > 0:
                category_scores[category] = score

        # 选择得分最高的分类
        if category_scores:
            category = max(category_scores, key=category_scores.get)
        else:
            category = feedback_type if feedback_type in self.CATEGORY_KEYWORDS else "general"

        # 提取标签
        tags = self._extract_tags(text)

        return category, None, tags

    def _extract_tags(self, text: str) -> list[str]:
        """提取标签"""
        tags = []
        text_lower = text.lower()

        # 从所有关键词中提取
        for _category, keywords in self.CATEGORY_KEYWORDS.items():
            for keyword in keywords:
                if keyword in text_lower and keyword not in tags:
                    tags.append(keyword)

        return tags[:10]  # 限制标签数量

    def calculate_priority(
        self,
        severity: str,
        sentiment_score: float,
        feedback_type: str,
        category: str,
    ) -> tuple[float, float, float]:
        """
        计算优先级
        返回: (priority_score, urgency_score, impact_score)
        """
        # 严重程度权重
        severity_weights = {
            "critical": 1.0,
            "high": 0.75,
            "medium": 0.5,
            "low": 0.25,
        }

        # 反馈类型权重
        type_weights = {
            "bug": 0.9,
            "feature": 0.6,
            "improvement": 0.5,
            "other": 0.3,
        }

        # 分类权重
        category_weights = {
            "security": 1.0,
            "performance": 0.8,
            "functionality": 0.7,
            "usability": 0.6,
            "compatibility": 0.7,
            "documentation": 0.3,
            "general": 0.4,
        }

        severity_score = severity_weights.get(severity, 0.5)
        type_score = type_weights.get(feedback_type, 0.5)
        category_score = category_weights.get(category, 0.4)

        # 情感分数影响（负面反馈优先级更高）
        sentiment_impact = abs(sentiment_score) if sentiment_score < 0 else 0

        # 计算各项分数
        urgency_score = min((severity_score + sentiment_impact) / 2, 1.0)
        impact_score = min((type_score + category_score) / 2, 1.0)
        priority_score = min((urgency_score * 0.6 + impact_score * 0.4), 1.0)

        return priority_score, urgency_score, impact_score

    def extract_keywords(self, text: str, max_keywords: int = 10) -> list[str]:
        """提取关键词"""
        if not text:
            return []

        # 简单的关键词提取：去除停用词，提取名词和动词
        words = re.findall(r'\b\w+\b', text.lower())

        # 停用词
        stopwords = {
            "the", "a", "an", "and", "or", "but", "in", "on", "at", "to", "for",
            "of", "with", "by", "from", "is", "are", "was", "were", "be", "been",
            "的", "了", "和", "是", "在", "有", "一", "个", "这", "那",
        }

        keywords = [w for w in words if w not in stopwords and len(w) > 2]

        # 去重并限制数量
        return list(dict.fromkeys(keywords))[:max_keywords]

    def extract_entities(self, text: str) -> dict:
        """提取命名实体"""
        entities = {
            "features": [],
            "components": [],
            "errors": [],
        }

        text_lower = text.lower()

        # 简单的实体提取
        # 特性
        feature_patterns = [
            r"feature[s]?:?\s+([^,.\n]+)",
            r"add[ing]?\s+([^,.\n]+)",
            r"implement[ing]?\s+([^,.\n]+)",
        ]
        for pattern in feature_patterns:
            matches = re.findall(pattern, text_lower)
            entities["features"].extend(matches)

        # 错误
        error_patterns = [
            r"error[s]?:?\s+([^,.\n]+)",
            r"bug[s]?:?\s+([^,.\n]+)",
            r"issue[s]?:?\s+([^,.\n]+)",
        ]
        for pattern in error_patterns:
            matches = re.findall(pattern, text_lower)
            entities["errors"].extend(matches)

        return entities

    async def analyze_feedback(
        self,
        feedback_id: str,
        title: str,
        description: str,
        feedback_type: str,
        severity: str,
    ) -> dict:
        """
        完整的反馈分析
        返回分析结果字典
        """
        # 合并标题和描述进行分析
        full_text = f"{title} {description}"

        # 情感分析
        sentiment_type, sentiment_score = self.analyze_sentiment(full_text)

        # 分类
        category, subcategory, tags = self.categorize_feedback(full_text, feedback_type)

        # 优先级计算
        priority_score, urgency_score, impact_score = self.calculate_priority(
            severity, sentiment_score, feedback_type, category
        )

        # 关键词提取
        keywords = self.extract_keywords(full_text)

        # 实体提取
        entities = self.extract_entities(full_text)

        return {
            "feedback_id": feedback_id,
            "sentiment_type": sentiment_type,
            "sentiment_score": sentiment_score,
            "category": category,
            "subcategory": subcategory,
            "tags": tags,
            "priority_score": priority_score,
            "urgency_score": urgency_score,
            "impact_score": impact_score,
            "keywords": keywords,
            "entities": entities,
        }


# 全局分析器实例
feedback_analyzer = FeedbackAnalyzer()
