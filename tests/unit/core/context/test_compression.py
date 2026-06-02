"""Tests for context compression module."""

import pytest
from datetime import datetime, timezone

from backend.app.core.context.compression import (
    ContextCompressor,
    CompressedContext,
    CompressedChunk,
    KeyInfo,
)


class TestContextCompressor:
    """ContextCompressor 类的测试套件。"""

    @pytest.fixture
    def compressor(self):
        """创建压缩器实例。"""
        return ContextCompressor()

    def test_compress_basic(self, compressor):
        """测试基本压缩功能。

        验证压缩后的内容长度小于原始内容，
        且返回的 CompressedContext 对象包含正确的元数据。
        """
        content = "这是一个测试内容。" * 20
        result = compressor.compress(content)

        assert isinstance(result, CompressedContext)
        assert result.original_tokens > 0
        assert result.compressed_tokens > 0
        assert result.compressed_tokens <= result.original_tokens
        assert result.content
        assert result.strategy == "hybrid"

    def test_compress_with_different_strategies(self, compressor):
        """测试不同的压缩策略。

        验证 summary、semantic 和 hybrid 三种策略都能正常工作，
        且都能产生有效的压缩结果。
        """
        content = "这是一个测试内容。" * 20

        # 测试 summary 策略
        result_summary = compressor.compress(content, strategy="summary")
        assert result_summary.strategy == "summary"
        assert result_summary.content
        assert result_summary.compressed_tokens <= result_summary.original_tokens

        # 测试 semantic 策略
        result_semantic = compressor.compress(content, strategy="semantic")
        assert result_semantic.strategy == "semantic"
        assert result_semantic.content
        assert result_semantic.compressed_tokens <= result_semantic.original_tokens

        # 测试 hybrid 策略
        result_hybrid = compressor.compress(content, strategy="hybrid")
        assert result_hybrid.strategy == "hybrid"
        assert result_hybrid.content
        assert result_hybrid.compressed_tokens <= result_hybrid.original_tokens

    def test_compress_preserves_key_info(self, compressor):
        """测试关键信息保留。

        验证压缩过程中能够正确提取和保留关键信息，
        包括错误、操作、实体和结果等类别。
        """
        content = "系统执行了一个操作，结果返回了错误。用户收到了异常信息。"
        result = compressor.compress(content)

        assert result.key_info
        assert len(result.key_info) > 0

        # 验证关键信息包含预期的类别
        categories = {ki.category for ki in result.key_info}
        assert len(categories) > 0

        # 验证每个关键信息都有有效的重要性分数
        for ki in result.key_info:
            assert 0.0 <= ki.importance <= 1.0
            assert ki.text
            assert ki.category in ["error", "action", "entity", "result"]

    def test_compress_incremental(self, compressor):
        """测试增量压缩。

        验证增量压缩能够正确处理多个文本块，
        并为每个块返回独立的压缩结果。
        """
        chunks = [
            "这是第一个块。" * 10,
            "这是第二个块。" * 10,
            "这是第三个块。" * 10,
        ]

        results = list(compressor.compress_incremental(iter(chunks)))

        assert len(results) == 3
        for i, result in enumerate(results):
            assert isinstance(result, CompressedChunk)
            assert result.chunk_index == i
            assert result.original_tokens > 0
            assert result.compressed_tokens > 0
            assert result.compressed_content

    def test_extract_key_info(self, compressor):
        """测试关键信息提取。

        验证能够从文本中正确提取各种类型的关键信息，
        并按重要性排序。
        """
        content = "系统发生了错误。执行了处理操作。用户收到了结果。"
        key_info = compressor.extract_key_info(content)

        assert isinstance(key_info, list)
        assert len(key_info) > 0

        # 验证关键信息按重要性排序
        for i in range(len(key_info) - 1):
            assert key_info[i].importance >= key_info[i + 1].importance

        # 验证没有重复的关键信息
        texts = [ki.text for ki in key_info]
        assert len(texts) == len(set(texts))

    def test_compression_ratio(self, compressor):
        """测试压缩比例验证。

        验证压缩比例计算正确，
        且在合理的范围内。
        """
        content = "这是一个测试内容。" * 50
        result = compressor.compress(content, target_ratio=0.5)

        assert result.compression_ratio > 0
        assert result.compression_ratio <= 1.0

        # 验证压缩比例计算正确
        expected_ratio = result.compressed_tokens / result.original_tokens
        assert abs(result.compression_ratio - expected_ratio) < 0.01

    def test_compress_empty_content(self, compressor):
        """测试边界情况：空内容。

        验证压缩器能够正确处理空字符串和仅包含空格的内容。
        """
        # 测试空字符串
        result_empty = compressor.compress("")
        assert result_empty.original_tokens == 0
        assert result_empty.compressed_tokens == 0
        assert result_empty.content == ""

        # 测试仅包含空格的内容
        result_whitespace = compressor.compress("   \n\t  ")
        assert result_whitespace.original_tokens == 0
        assert result_whitespace.compressed_tokens == 0
        assert result_whitespace.content == ""

    @pytest.mark.asyncio
    async def test_compress_async(self, compressor):
        """测试异步压缩。

        验证异步压缩功能能够正确执行，
        并返回与同步压缩相同的结果。
        """
        content = "这是一个测试内容。" * 20

        # 同步压缩
        sync_result = compressor.compress(content)

        # 异步压缩
        async_result = await compressor.compress_async(content)

        # 验证结果一致
        assert async_result.original_tokens == sync_result.original_tokens
        assert async_result.compressed_tokens == sync_result.compressed_tokens
        assert async_result.strategy == sync_result.strategy

    def test_compress_with_custom_target_ratio(self, compressor):
        """测试自定义目标压缩比例。

        验证不同的目标压缩比例能够产生不同的压缩结果。
        """
        content = "这是一个测试内容。" * 50

        # 高压缩比例
        result_high = compressor.compress(content, target_ratio=0.3)

        # 低压缩比例
        result_low = compressor.compress(content, target_ratio=0.7)

        # 高压缩比例应该产生更小的结果
        assert result_high.compressed_tokens <= result_low.compressed_tokens

    def test_compressed_context_to_dict(self, compressor):
        """测试 CompressedContext 的字典转换。

        验证 CompressedContext 能够正确转换为字典格式。
        """
        content = "这是一个测试内容。" * 20
        result = compressor.compress(content)

        result_dict = result.to_dict()

        assert isinstance(result_dict, dict)
        assert "original_tokens" in result_dict
        assert "compressed_tokens" in result_dict
        assert "content" in result_dict
        assert "key_info" in result_dict
        assert "compression_ratio" in result_dict
        assert "strategy" in result_dict
        assert "metadata" in result_dict

    def test_key_info_structure(self, compressor):
        """测试 KeyInfo 数据结构。

        验证 KeyInfo 对象包含所有必需的字段。
        """
        content = "系统执行了错误处理。"
        key_info = compressor.extract_key_info(content)

        if key_info:
            ki = key_info[0]
            assert hasattr(ki, "text")
            assert hasattr(ki, "importance")
            assert hasattr(ki, "category")
            assert hasattr(ki, "position")
            assert isinstance(ki.text, str)
            assert isinstance(ki.importance, float)
            assert isinstance(ki.category, str)
            assert isinstance(ki.position, int)

    def test_compress_with_english_content(self, compressor):
        """测试英文内容压缩。

        验证压缩器能够正确处理英文内容。
        """
        content = "This is a test content. " * 20
        result = compressor.compress(content)

        assert result.original_tokens > 0
        assert result.compressed_tokens > 0
        assert result.content
        assert result.compressed_tokens <= result.original_tokens

    def test_compress_mixed_language_content(self, compressor):
        """测试混合语言内容压缩。

        验证压缩器能够正确处理中英文混合的内容。
        """
        content = "这是一个 test 内容。" * 20
        result = compressor.compress(content)

        assert result.original_tokens > 0
        assert result.compressed_tokens > 0
        assert result.content

    @pytest.mark.asyncio
    async def test_compress_incremental_async(self, compressor):
        """测试异步增量压缩。

        验证异步增量压缩能够正确处理多个块。
        """
        chunks = [
            "这是第一个块。" * 10,
            "这是第二个块。" * 10,
            "这是第三个块。" * 10,
        ]

        results = await compressor.compress_incremental_async(iter(chunks))

        assert len(results) == 3
        for i, result in enumerate(results):
            assert isinstance(result, CompressedChunk)
            assert result.chunk_index == i
