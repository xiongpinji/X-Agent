"""智能上下文压缩模块。

实现多种压缩策略：
- 摘要压缩：将长文本压缩为摘要
- 语义压缩：保留语义核心，去除冗余
- 关键信息保留：确保重要信息不丢失
- 增量压缩：支持流式/增量压缩场景
"""

from __future__ import annotations

import asyncio
import logging
import re
from dataclasses import dataclass, field
from typing import Any, Iterator, Optional
from datetime import timezone

logger = logging.getLogger(__name__)


@dataclass
class KeyInfo:
    """关键信息项。"""

    text: str
    importance: float
    category: str
    position: int


@dataclass
class CompressedContext:
    """压缩后的上下文。"""

    original_tokens: int
    compressed_tokens: int
    content: str
    key_info: list[KeyInfo] = field(default_factory=list)
    compression_ratio: float = 1.0
    strategy: str = "unknown"
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        """转换为字典。"""
        return {
            "original_tokens": self.original_tokens,
            "compressed_tokens": self.compressed_tokens,
            "content": self.content,
            "key_info": [
                {
                    "text": ki.text,
                    "importance": ki.importance,
                    "category": ki.category,
                    "position": ki.position,
                }
                for ki in self.key_info
            ],
            "compression_ratio": self.compression_ratio,
            "strategy": self.strategy,
            "metadata": self.metadata,
        }


@dataclass
class CompressedChunk:
    """增量压缩的单个块。"""

    original_content: str
    compressed_content: str
    original_tokens: int
    compressed_tokens: int
    key_info: list[KeyInfo] = field(default_factory=list)
    chunk_index: int = 0


class ContextCompressor:
    """智能上下文压缩器。"""

    FILLER_WORDS = {
        "的", "了", "和", "是", "在", "有", "这", "那", "就", "也",
        "很", "比较", "相对", "似乎", "好像", "可能", "也许", "大概",
        "actually", "basically", "essentially", "literally", "really",
        "very", "quite", "rather", "somewhat", "kind of", "sort of",
    }

    KEY_PATTERNS = {
        "error": r"(?:error|错误|异常|exception|failed|失败)",
        "action": r"(?:执行|运行|调用|处理|完成|开始|结束)",
        "entity": r"(?:用户|系统|模块|组件|服务|数据库)",
        "result": r"(?:结果|返回|输出|成功|完成)",
    }

    def __init__(self, token_counter=None):
        """初始化压缩器。"""
        self.token_counter = token_counter or self._default_token_counter

    @staticmethod
    def _default_token_counter(text: str) -> int:
        """默认的 token 计数函数。"""
        chinese_chars = len(re.findall(r"[一-鿿]", text))
        english_words = len(re.findall(r"\b[a-zA-Z]+\b", text))
        return int(chinese_chars + english_words * 1.3)

    def compress(
        self,
        content: str,
        target_ratio: float = 0.5,
        strategy: str = "hybrid",
    ) -> CompressedContext:
        """压缩文本内容。"""
        if not content or not content.strip():
            return CompressedContext(
                original_tokens=0,
                compressed_tokens=0,
                content="",
                strategy=strategy,
            )

        original_tokens = self.token_counter(content)
        target_tokens = max(int(original_tokens * target_ratio), 50)

        if strategy == "summary":
            compressed = self._compress_by_summary(content, target_tokens)
        elif strategy == "semantic":
            compressed = self._compress_by_semantic(content, target_tokens)
        else:
            compressed = self._compress_by_hybrid(content, target_tokens)

        compressed_tokens = self.token_counter(compressed)
        key_info = self.extract_key_info(content)

        return CompressedContext(
            original_tokens=original_tokens,
            compressed_tokens=compressed_tokens,
            content=compressed,
            key_info=key_info,
            compression_ratio=compressed_tokens / original_tokens if original_tokens > 0 else 1.0,
            strategy=strategy,
        )

    def compress_incremental(
        self,
        chunks: Iterator[str],
        target_ratio: float = 0.5,
    ) -> Iterator[CompressedChunk]:
        """增量压缩文本块。"""
        chunk_index = 0
        for chunk in chunks:
            if not chunk or not chunk.strip():
                continue

            original_tokens = self.token_counter(chunk)
            target_tokens = max(int(original_tokens * target_ratio), 20)

            compressed = self._compress_by_hybrid(chunk, target_tokens)
            compressed_tokens = self.token_counter(compressed)
            key_info = self.extract_key_info(chunk)

            yield CompressedChunk(
                original_content=chunk,
                compressed_content=compressed,
                original_tokens=original_tokens,
                compressed_tokens=compressed_tokens,
                key_info=key_info,
                chunk_index=chunk_index,
            )

            chunk_index += 1

    def extract_key_info(self, content: str) -> list[KeyInfo]:
        """提取关键信息。"""
        key_info = []
        position = 0

        sentences = re.split(r"[。！？\n]", content)

        for sentence in sentences:
            if not sentence.strip():
                continue

            for category, pattern in self.KEY_PATTERNS.items():
                matches = re.finditer(pattern, sentence, re.IGNORECASE)
                for match in matches:
                    importance = self._calculate_importance(category, position, len(content))

                    start = max(0, match.start() - 10)
                    end = min(len(sentence), match.end() + 10)
                    context = sentence[start:end].strip()

                    key_info.append(
                        KeyInfo(
                            text=context,
                            importance=importance,
                            category=category,
                            position=position + match.start(),
                        )
                    )

            position += len(sentence) + 1

        key_info = sorted(key_info, key=lambda x: x.importance, reverse=True)
        seen = set()
        unique_key_info = []
        for ki in key_info:
            if ki.text not in seen:
                seen.add(ki.text)
                unique_key_info.append(ki)

        return unique_key_info[:10]

    def _calculate_importance(self, category: str, position: int, total_length: int) -> float:
        """计算信息重要性。"""
        base_importance = {
            "error": 1.0,
            "action": 0.8,
            "result": 0.7,
            "entity": 0.6,
        }.get(category, 0.5)

        position_ratio = position / total_length if total_length > 0 else 0
        if position_ratio < 0.2 or position_ratio > 0.8:
            position_factor = 1.2
        else:
            position_factor = 1.0

        return min(base_importance * position_factor, 1.0)

    def _compress_by_summary(self, content: str, target_tokens: int) -> str:
        """摘要压缩策略。"""
        sentences = re.split(r"[。！？\n]+", content)
        sentences = [s.strip() for s in sentences if s.strip()]

        if not sentences:
            return content

        sentence_scores = []
        for i, sentence in enumerate(sentences):
            length_score = min(len(sentence) / 50, 1.0)
            position_score = 1.0 - abs(i - len(sentences) / 2) / (len(sentences) / 2)
            keyword_score = sum(1 for pattern in self.KEY_PATTERNS.values()
                              if re.search(pattern, sentence, re.IGNORECASE)) / len(self.KEY_PATTERNS)

            score = length_score * 0.3 + position_score * 0.3 + keyword_score * 0.4
            sentence_scores.append((sentence, score))

        sentence_scores.sort(key=lambda x: x[1], reverse=True)
        selected_sentences = sorted(
            sentence_scores[:max(1, len(sentences) // 3)],
            key=lambda x: sentences.index(x[0]),
        )

        result = "。".join([s[0] for s in selected_sentences])
        if result and not result.endswith("。"):
            result += "。"

        return result

    def _compress_by_semantic(self, content: str, target_tokens: int) -> str:
        """语义压缩策略。"""
        # 注意：Python 标准库 re 不支持 \p{P} Unicode 属性转义（那是 regex/PCRE 特性）。
        # [\s\W]+ 是等价的纯标准库写法：对 str 模式 \W 是 Unicode 感知的，
        # 会切分空白与标点，同时保留 CJK 表意文字与字母数字（它们属于 \w 词字符）。
        words = re.split(r"[\s\W]+", content)
        words = [w for w in words if w and w not in self.FILLER_WORDS]

        result = " ".join(words)

        current_tokens = self.token_counter(result)
        if current_tokens > target_tokens:
            words = words[: max(10, int(len(words) * target_tokens / current_tokens))]
            result = " ".join(words)

        return result

    def _compress_by_hybrid(self, content: str, target_tokens: int) -> str:
        """混合压缩策略。"""
        summarized = self._compress_by_summary(content, target_tokens)

        current_tokens = self.token_counter(summarized)
        if current_tokens > target_tokens:
            words = re.split(r"[\s\W]+", summarized)
            words = [w for w in words if w and w not in self.FILLER_WORDS]

            result = " ".join(words)
            current_tokens = self.token_counter(result)

            if current_tokens > target_tokens:
                words = words[: max(10, int(len(words) * target_tokens / current_tokens))]
                result = " ".join(words)

            return result

        return summarized

    async def compress_async(
        self,
        content: str,
        target_ratio: float = 0.5,
        strategy: str = "hybrid",
    ) -> CompressedContext:
        """异步压缩文本内容。"""
        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(
            None,
            self.compress,
            content,
            target_ratio,
            strategy,
        )

    async def compress_incremental_async(
        self,
        chunks: Iterator[str],
        target_ratio: float = 0.5,
    ) -> list[CompressedChunk]:
        """异步增量压缩。"""
        loop = asyncio.get_event_loop()
        result = []

        for index, chunk in enumerate(chunks):
            compressed_chunk = await loop.run_in_executor(
                None,
                lambda c=chunk: next(
                    self.compress_incremental(iter([c]), target_ratio)
                ),
            )
            # 每个 chunk 单独喂进新生成器，chunk_index 会重置为 0，
            # 这里按外层枚举顺序回填正确的全局序号。
            compressed_chunk.chunk_index = index
            result.append(compressed_chunk)

        return result
