"""技能搜索引擎 - 支持全文搜索、模糊搜索、语义搜索、搜索建议"""

from __future__ import annotations

import logging
from typing import Optional, List, Dict, Any, Tuple
from datetime import datetime, UTC
from dataclasses import dataclass, field
import re
from difflib import SequenceMatcher

logger = logging.getLogger(__name__)


@dataclass
class SearchResult:
    """搜索结果"""
    skill_id: str
    name: str
    name_zh: str
    description: str
    relevance_score: float  # 0-1
    match_type: str  # exact, partial, fuzzy, semantic
    matched_fields: List[str] = field(default_factory=list)


@dataclass
class SearchSuggestion:
    """搜索建议"""
    query: str
    frequency: int = 0
    category: Optional[str] = None


class SkillSearchEngine:
    """技能搜索引擎"""

    def __init__(self):
        self.search_history: Dict[str, int] = {}  # query -> frequency
        self.search_cache: Dict[str, List[SearchResult]] = {}  # query -> results
        self.skills_index: Dict[str, Any] = {}  # skill_id -> indexed_data

    def index_skill(
        self,
        skill_id: str,
        name: str,
        name_zh: str,
        description: str,
        description_zh: str,
        keywords: List[str],
        category: str,
        tags: List[str],
    ) -> bool:
        """索引技能"""
        try:
            self.skills_index[skill_id] = {
                "name": name,
                "name_zh": name_zh,
                "description": description,
                "description_zh": description_zh,
                "keywords": keywords,
                "category": category,
                "tags": tags,
                "name_lower": name.lower(),
                "name_zh_lower": name_zh.lower(),
                "description_lower": description.lower(),
                "description_zh_lower": description_zh.lower(),
                "keywords_lower": [k.lower() for k in keywords],
                "tags_lower": [t.lower() for t in tags],
            }
            logger.info(f"索引技能: {skill_id}")
            return True
        except Exception as e:
            logger.error(f"索引技能失败: {str(e)}")
            return False

    def search(
        self,
        query: str,
        filters: Optional[Dict[str, Any]] = None,
        limit: int = 20,
    ) -> List[SearchResult]:
        """综合搜索 - 结合多种搜索方法"""
        try:
            if not query or len(query.strip()) == 0:
                return []

            query = query.strip()

            # 检查缓存
            cache_key = f"{query}:{str(filters)}"
            if cache_key in self.search_cache:
                return self.search_cache[cache_key][:limit]

            # 记录搜索历史
            self._record_search(query)

            # 执行多种搜索
            results = []

            # 1. 精确匹配
            exact_results = self._exact_search(query)
            results.extend(exact_results)

            # 2. 部分匹配
            partial_results = self._partial_search(query)
            results.extend([r for r in partial_results if r not in results])

            # 3. 模糊搜索
            fuzzy_results = self._fuzzy_search(query)
            results.extend([r for r in fuzzy_results if r not in results])

            # 4. 语义搜索
            semantic_results = self._semantic_search(query)
            results.extend([r for r in semantic_results if r not in results])

            # 应用过滤器
            if filters:
                results = self._apply_filters(results, filters)

            # 按相关性排序
            results.sort(key=lambda r: r.relevance_score, reverse=True)

            # 缓存结果
            self.search_cache[cache_key] = results

            return results[:limit]

        except Exception as e:
            logger.error(f"搜索失败: {str(e)}")
            return []

    def _exact_search(self, query: str) -> List[SearchResult]:
        """精确搜索"""
        results = []
        query_lower = query.lower()

        for skill_id, skill_data in self.skills_index.items():
            matched_fields = []

            # 检查名称
            if query_lower == skill_data["name_lower"]:
                matched_fields.append("name")
            elif query_lower == skill_data["name_zh_lower"]:
                matched_fields.append("name_zh")

            # 检查关键词
            if query_lower in skill_data["keywords_lower"]:
                matched_fields.append("keywords")

            if matched_fields:
                results.append(SearchResult(
                    skill_id=skill_id,
                    name=skill_data["name"],
                    name_zh=skill_data["name_zh"],
                    description=skill_data["description"],
                    relevance_score=1.0,
                    match_type="exact",
                    matched_fields=matched_fields,
                ))

        return results

    def _partial_search(self, query: str) -> List[SearchResult]:
        """部分匹配搜索"""
        results = []
        query_lower = query.lower()

        for skill_id, skill_data in self.skills_index.items():
            matched_fields = []
            score = 0.0

            # 检查名称
            if query_lower in skill_data["name_lower"]:
                matched_fields.append("name")
                score = max(score, 0.9)
            elif query_lower in skill_data["name_zh_lower"]:
                matched_fields.append("name_zh")
                score = max(score, 0.9)

            # 检查描述
            if query_lower in skill_data["description_lower"]:
                matched_fields.append("description")
                score = max(score, 0.7)
            elif query_lower in skill_data["description_zh_lower"]:
                matched_fields.append("description_zh")
                score = max(score, 0.7)

            # 检查关键词
            for kw in skill_data["keywords_lower"]:
                if query_lower in kw:
                    matched_fields.append("keywords")
                    score = max(score, 0.8)
                    break

            if matched_fields:
                results.append(SearchResult(
                    skill_id=skill_id,
                    name=skill_data["name"],
                    name_zh=skill_data["name_zh"],
                    description=skill_data["description"],
                    relevance_score=score,
                    match_type="partial",
                    matched_fields=matched_fields,
                ))

        return results

    def fuzzy_search(self, query: str, threshold: float = 0.6) -> List[SearchResult]:
        """模糊搜索"""
        return self._fuzzy_search(query, threshold)

    def _fuzzy_search(self, query: str, threshold: float = 0.6) -> List[SearchResult]:
        """模糊搜索 - 使用相似度匹配"""
        results = []
        query_lower = query.lower()

        for skill_id, skill_data in self.skills_index.items():
            matched_fields = []
            max_score = 0.0

            # 检查名称相似度
            name_similarity = SequenceMatcher(
                None,
                query_lower,
                skill_data["name_lower"]
            ).ratio()
            if name_similarity >= threshold:
                matched_fields.append("name")
                max_score = max(max_score, name_similarity * 0.9)

            # 检查中文名称相似度
            name_zh_similarity = SequenceMatcher(
                None,
                query_lower,
                skill_data["name_zh_lower"]
            ).ratio()
            if name_zh_similarity >= threshold:
                matched_fields.append("name_zh")
                max_score = max(max_score, name_zh_similarity * 0.9)

            # 检查关键词相似度
            for kw in skill_data["keywords_lower"]:
                kw_similarity = SequenceMatcher(None, query_lower, kw).ratio()
                if kw_similarity >= threshold:
                    matched_fields.append("keywords")
                    max_score = max(max_score, kw_similarity * 0.7)
                    break

            if matched_fields and max_score > 0:
                results.append(SearchResult(
                    skill_id=skill_id,
                    name=skill_data["name"],
                    name_zh=skill_data["name_zh"],
                    description=skill_data["description"],
                    relevance_score=max_score,
                    match_type="fuzzy",
                    matched_fields=matched_fields,
                ))

        return results

    def semantic_search(self, query: str, limit: int = 10) -> List[SearchResult]:
        """语义搜索"""
        return self._semantic_search(query, limit)

    def _semantic_search(self, query: str, limit: int = 10) -> List[SearchResult]:
        """语义搜索 - 基于关键词和标签的语义相似度"""
        results = []
        query_lower = query.lower()
        query_words = set(query_lower.split())

        for skill_id, skill_data in self.skills_index.items():
            # 计算与关键词的相似度
            skill_keywords = set(skill_data["keywords_lower"])
            skill_tags = set(skill_data["tags_lower"])
            all_skill_terms = skill_keywords | skill_tags

            # 计算Jaccard相似度
            intersection = query_words & all_skill_terms
            union = query_words | all_skill_terms

            if union:
                similarity = len(intersection) / len(union)

                if similarity > 0:
                    results.append(SearchResult(
                        skill_id=skill_id,
                        name=skill_data["name"],
                        name_zh=skill_data["name_zh"],
                        description=skill_data["description"],
                        relevance_score=similarity * 0.6,
                        match_type="semantic",
                        matched_fields=["keywords", "tags"],
                    ))

        results.sort(key=lambda r: r.relevance_score, reverse=True)
        return results[:limit]

    def get_suggestions(self, query: str, limit: int = 10) -> List[str]:
        """获取搜索建议"""
        try:
            if not query or len(query.strip()) == 0:
                return self._get_popular_searches(limit)

            query_lower = query.lower()
            suggestions = set()

            # 1. 从搜索历史中获取
            for search_query in self.search_history.keys():
                if search_query.lower().startswith(query_lower):
                    suggestions.add(search_query)

            # 2. 从技能名称中获取
            for skill_data in self.skills_index.values():
                if skill_data["name_lower"].startswith(query_lower):
                    suggestions.add(skill_data["name"])
                elif skill_data["name_zh_lower"].startswith(query_lower):
                    suggestions.add(skill_data["name_zh"])

            # 3. 从关键词中获取
            for skill_data in self.skills_index.values():
                for kw in skill_data["keywords"]:
                    if kw.lower().startswith(query_lower):
                        suggestions.add(kw)

            # 按频率排序
            suggestions_list = list(suggestions)
            suggestions_list.sort(
                key=lambda s: self.search_history.get(s, 0),
                reverse=True
            )

            return suggestions_list[:limit]

        except Exception as e:
            logger.error(f"获取搜索建议失败: {str(e)}")
            return []

    def _get_popular_searches(self, limit: int = 10) -> List[str]:
        """获取热门搜索"""
        popular = sorted(
            self.search_history.items(),
            key=lambda x: x[1],
            reverse=True
        )
        return [query for query, _ in popular[:limit]]

    def get_search_history(self, user_id: str = "", limit: int = 20) -> List[str]:
        """获取搜索历史"""
        # 注: 这里简化实现，实际应该按用户存储
        popular = sorted(
            self.search_history.items(),
            key=lambda x: x[1],
            reverse=True
        )
        return [query for query, _ in popular[:limit]]

    def _record_search(self, query: str) -> None:
        """记录搜索"""
        if query not in self.search_history:
            self.search_history[query] = 0
        self.search_history[query] += 1

    def _apply_filters(
        self,
        results: List[SearchResult],
        filters: Dict[str, Any],
    ) -> List[SearchResult]:
        """应用过滤器"""
        filtered = results

        # 按分类过滤
        if "category" in filters:
            category = filters["category"]
            filtered = [
                r for r in filtered
                if self.skills_index[r.skill_id]["category"] == category
            ]

        # 按标签过滤
        if "tags" in filters:
            tags = set(filters["tags"])
            filtered = [
                r for r in filtered
                if tags & set(self.skills_index[r.skill_id]["tags"])
            ]

        # 按最小相关性分数过滤
        if "min_score" in filters:
            min_score = filters["min_score"]
            filtered = [r for r in filtered if r.relevance_score >= min_score]

        return filtered

    def clear_cache(self) -> None:
        """清除搜索缓存"""
        self.search_cache.clear()
        logger.info("搜索缓存已清除")

    def get_search_stats(self) -> Dict[str, Any]:
        """获取搜索统计"""
        return {
            "total_searches": sum(self.search_history.values()),
            "unique_queries": len(self.search_history),
            "indexed_skills": len(self.skills_index),
            "cache_size": len(self.search_cache),
        }


# 全局实例
_skill_search_engine: Optional[SkillSearchEngine] = None


def get_skill_search_engine() -> SkillSearchEngine:
    """获取技能搜索引擎实例"""
    global _skill_search_engine
    if _skill_search_engine is None:
        _skill_search_engine = SkillSearchEngine()
    return _skill_search_engine


__all__ = [
    "SkillSearchEngine",
    "SearchResult",
    "SearchSuggestion",
    "get_skill_search_engine",
]
