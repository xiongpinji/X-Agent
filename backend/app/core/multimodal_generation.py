"""
多模态生成模块 - 实现跨模态内容生成能力

支持的生成类型:
1. 文生图 (Text-to-Image)
2. 图生文 (Image-to-Text)
3. 文生视频 (Text-to-Video)
4. 视频生文 (Video-to-Text)
5. 音频生文 (Audio-to-Text)
6. 文生音频 (Text-to-Audio)
7. 多模态摘要 (Multimodal Summarization)
"""

from __future__ import annotations

import asyncio
import time
from dataclasses import dataclass, field
from enum import StrEnum
from typing import Any

import numpy as np


class GenerationType(StrEnum):
    """生成类型枚举"""
    TEXT_TO_IMAGE = "text_to_image"
    IMAGE_TO_TEXT = "image_to_text"
    TEXT_TO_VIDEO = "text_to_video"
    VIDEO_TO_TEXT = "video_to_text"
    AUDIO_TO_TEXT = "audio_to_text"
    TEXT_TO_AUDIO = "text_to_audio"
    SUMMARIZATION = "summarization"
    CAPTIONING = "captioning"


@dataclass
class GenerationRequest:
    """生成请求"""
    generation_type: GenerationType
    input_data: str | list[float]  # 输入数据（文本或向量）
    input_modality: str
    output_modality: str
    parameters: dict[str, Any] = field(default_factory=dict)
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass
class GenerationResult:
    """生成结果"""
    request_id: str
    generation_type: GenerationType
    output_data: str | list[float]  # 生成的数据
    output_modality: str
    quality_score: float  # 质量分数 [0, 1]
    generation_time_ms: float
    metadata: dict[str, Any] = field(default_factory=dict)


class TextEncoder:
    """文本编码器"""

    def __init__(self, vocab_size: int = 10000, embedding_dim: int = 512):
        self.vocab_size = vocab_size
        self.embedding_dim = embedding_dim
        self._vocab: dict[str, int] = {}
        self._embeddings: dict[int, list[float]] = {}
        self._initialize_vocab()

    def _initialize_vocab(self):
        """初始化词汇表"""
        # 简单的词汇表初始化
        common_words = [
            "the", "a", "an", "and", "or", "but", "in", "on", "at", "to",
            "image", "text", "video", "audio", "content", "generate", "create",
            "describe", "summarize", "caption", "translate", "convert",
        ]

        for i, word in enumerate(common_words):
            self._vocab[word] = i
            # 为每个词生成随机嵌入
            np.random.seed(i)
            self._embeddings[i] = np.random.randn(self.embedding_dim).tolist()

    def encode(self, text: str) -> list[float]:
        """将文本编码为向量"""
        words = text.lower().split()
        embeddings = []

        for word in words:
            if word in self._vocab:
                embeddings.append(self._embeddings[self._vocab[word]])
            else:
                # 未知词使用随机向量
                np.random.seed(hash(word) % 2**32)
                embeddings.append(np.random.randn(self.embedding_dim).tolist())

        if not embeddings:
            return [0.0] * self.embedding_dim

        # 平均池化
        avg_embedding = np.mean(embeddings, axis=0)
        return avg_embedding.tolist()

    def decode(self, vector: list[float]) -> str:
        """将向量解码为文本"""
        # 简单的解码 - 找最相似的词
        best_words = []

        for word_id, embedding in self._embeddings.items():
            similarity = self._cosine_similarity(vector, embedding)
            if similarity > 0.5:
                # 反向查找词
                for word, wid in self._vocab.items():
                    if wid == word_id:
                        best_words.append((word, similarity))
                        break

        best_words.sort(key=lambda x: x[1], reverse=True)
        return " ".join([word for word, _ in best_words[:5]])

    @staticmethod
    def _cosine_similarity(vec1: list[float], vec2: list[float]) -> float:
        """计算余弦相似度"""
        if not vec1 or not vec2:
            return 0.0

        dot_product = sum(a * b for a, b in zip(vec1, vec2, strict=False))
        norm1 = np.sqrt(sum(a * a for a in vec1))
        norm2 = np.sqrt(sum(b * b for b in vec2))

        if norm1 == 0 or norm2 == 0:
            return 0.0

        return dot_product / (norm1 * norm2)


class ImageGenerator:
    """图像生成器"""

    def __init__(self, image_dim: int = 512):
        self.image_dim = image_dim

    async def generate_from_text(self, text: str, parameters: dict[str, Any] | None = None) -> list[float]:
        """从文本生成图像特征"""

        # 模拟图像生成过程
        await asyncio.sleep(0.1)

        # 生成图像特征向量
        np.random.seed(hash(text) % 2**32)
        image_features = np.random.randn(self.image_dim).tolist()

        return image_features

    async def generate_caption(self, image_features: list[float]) -> str:
        """为图像生成描述"""
        # 模拟描述生成过程
        await asyncio.sleep(0.05)

        # 简单的描述生成
        if not image_features:
            return "An image"

        # 基于特征向量生成描述
        feature_sum = sum(image_features)
        if feature_sum > 0:
            return "A colorful and detailed image"
        else:
            return "A simple image"


class VideoGenerator:
    """视频生成器"""

    def __init__(self, frame_dim: int = 512, num_frames: int = 30):
        self.frame_dim = frame_dim
        self.num_frames = num_frames

    async def generate_from_text(self, text: str, parameters: dict[str, Any] | None = None) -> list[list[float]]:
        """从文本生成视频帧特征"""
        params = parameters or {}
        num_frames = params.get("num_frames", self.num_frames)

        # 模拟视频生成过程
        await asyncio.sleep(0.2)

        # 生成视频帧特征
        frames = []
        np.random.seed(hash(text) % 2**32)

        for _i in range(num_frames):
            frame_features = np.random.randn(self.frame_dim).tolist()
            frames.append(frame_features)

        return frames

    async def extract_summary(self, video_frames: list[list[float]]) -> str:
        """从视频帧提取摘要"""
        # 模拟摘要提取过程
        await asyncio.sleep(0.1)

        if not video_frames:
            return "A video"

        # 基于帧数生成摘要
        num_frames = len(video_frames)
        if num_frames > 100:
            return "A long and detailed video"
        elif num_frames > 30:
            return "A medium-length video"
        else:
            return "A short video"


class AudioGenerator:
    """音频生成器"""

    def __init__(self, audio_dim: int = 256, sample_rate: int = 16000):
        self.audio_dim = audio_dim
        self.sample_rate = sample_rate

    async def generate_from_text(self, text: str, parameters: dict[str, Any] | None = None) -> list[float]:
        """从文本生成音频特征"""

        # 模拟音频生成过程
        await asyncio.sleep(0.15)

        # 生成音频特征向量
        np.random.seed(hash(text) % 2**32)
        audio_features = np.random.randn(self.audio_dim).tolist()

        return audio_features

    async def transcribe(self, audio_features: list[float]) -> str:
        """转录音频为文本"""
        # 模拟转录过程
        await asyncio.sleep(0.1)

        if not audio_features:
            return "Audio content"

        # 简单的转录
        feature_sum = sum(audio_features)
        if feature_sum > 0:
            return "The audio contains speech"
        else:
            return "Silent audio"


class MultimodalSummarizer:
    """多模态摘要生成器"""

    def __init__(self):
        self.text_encoder = TextEncoder()

    async def summarize(
        self,
        content: dict[str, Any],
        max_length: int = 100,
    ) -> str:
        """生成多模态内容摘要"""
        # 模拟摘要生成过程
        await asyncio.sleep(0.1)

        summaries = []

        # 处理文本
        if "text" in content:
            text = content["text"]
            if len(text) > max_length:
                summaries.append(text[:max_length] + "...")
            else:
                summaries.append(text)

        # 处理图像
        if "image" in content:
            summaries.append("Image content")

        # 处理视频
        if "video" in content:
            summaries.append("Video content")

        # 处理音频
        if "audio" in content:
            summaries.append("Audio content")

        return " ".join(summaries)


class MultimodalGenerator:
    """多模态生成引擎"""

    def __init__(self):
        self.text_encoder = TextEncoder()
        self.image_generator = ImageGenerator()
        self.video_generator = VideoGenerator()
        self.audio_generator = AudioGenerator()
        self.summarizer = MultimodalSummarizer()
        self._generation_cache: dict[str, GenerationResult] = {}

    async def generate(
        self,
        request: GenerationRequest,
        use_cache: bool = True,
    ) -> GenerationResult:
        """执行生成任务"""
        start_time = time.time()

        # 检查缓存
        cache_key = self._get_cache_key(request)
        if use_cache and cache_key in self._generation_cache:
            return self._generation_cache[cache_key]

        # 执行生成
        if request.generation_type == GenerationType.TEXT_TO_IMAGE:
            output_data = await self.image_generator.generate_from_text(
                request.input_data,
                request.parameters,
            )
        elif request.generation_type == GenerationType.IMAGE_TO_TEXT:
            output_data = await self.image_generator.generate_caption(request.input_data)
        elif request.generation_type == GenerationType.TEXT_TO_VIDEO:
            output_data = await self.video_generator.generate_from_text(
                request.input_data,
                request.parameters,
            )
        elif request.generation_type == GenerationType.VIDEO_TO_TEXT:
            output_data = await self.video_generator.extract_summary(request.input_data)
        elif request.generation_type == GenerationType.TEXT_TO_AUDIO:
            output_data = await self.audio_generator.generate_from_text(
                request.input_data,
                request.parameters,
            )
        elif request.generation_type == GenerationType.AUDIO_TO_TEXT:
            output_data = await self.audio_generator.transcribe(request.input_data)
        elif request.generation_type == GenerationType.SUMMARIZATION:
            output_data = await self.summarizer.summarize(
                request.input_data,
                request.parameters.get("max_length", 100),
            )
        else:
            output_data = ""

        generation_time_ms = (time.time() - start_time) * 1000

        # 计算质量分数
        quality_score = self._compute_quality_score(request, output_data)

        result = GenerationResult(
            request_id=request.metadata.get("request_id", "unknown"),
            generation_type=request.generation_type,
            output_data=output_data,
            output_modality=request.output_modality,
            quality_score=quality_score,
            generation_time_ms=generation_time_ms,
        )

        # 缓存结果
        if use_cache:
            self._generation_cache[cache_key] = result

        return result

    async def batch_generate(
        self,
        requests: list[GenerationRequest],
    ) -> list[GenerationResult]:
        """批量生成"""
        tasks = [self.generate(request) for request in requests]
        return await asyncio.gather(*tasks)

    def _compute_quality_score(
        self,
        request: GenerationRequest,
        output_data: Any,
    ) -> float:
        """计算生成质量分数"""
        score = 0.8  # 基础分数

        # 根据输出数据调整分数
        if isinstance(output_data, (str, list)) and len(output_data) > 0:
            score += 0.1

        # 根据参数调整分数
        if request.parameters:
            score += 0.05

        return min(1.0, score)

    def clear_cache(self) -> None:
        """清除生成缓存"""
        self._generation_cache.clear()

    @staticmethod
    def _get_cache_key(request: GenerationRequest) -> str:
        """生成缓存键"""
        import hashlib
        key_str = f"{request.generation_type}_{request.input_modality}_{request.output_modality}"
        return hashlib.md5(key_str.encode()).hexdigest()


class GenerationEvaluator:
    """生成评估器"""

    @staticmethod
    def compute_bleu_score(reference: str, generated: str) -> float:
        """计算BLEU分数（简化版）"""
        if not reference or not generated:
            return 0.0

        ref_words = set(reference.lower().split())
        gen_words = set(generated.lower().split())

        if not ref_words:
            return 0.0

        overlap = len(ref_words & gen_words)
        return overlap / len(ref_words)

    @staticmethod
    def compute_rouge_score(reference: str, generated: str) -> float:
        """计算ROUGE分数（简化版）"""
        if not reference or not generated:
            return 0.0

        ref_words = reference.lower().split()
        gen_words = generated.lower().split()

        if not ref_words:
            return 0.0

        # 计算重叠词数
        overlap = sum(1 for word in gen_words if word in ref_words)

        return overlap / len(ref_words)

    @staticmethod
    def compute_perplexity(logits: list[float]) -> float:
        """计算困惑度"""
        if not logits:
            return float('inf')

        # 简化的困惑度计算
        avg_logit = sum(logits) / len(logits)
        return np.exp(-avg_logit)

    @staticmethod
    def compute_diversity_score(generated_samples: list[str]) -> float:
        """计算生成多样性分数"""
        if len(generated_samples) < 2:
            return 0.0

        # 计算样本间的差异
        total_similarity = 0.0
        count = 0

        for i in range(len(generated_samples)):
            for j in range(i + 1, len(generated_samples)):
                s1 = set(generated_samples[i].lower().split())
                s2 = set(generated_samples[j].lower().split())

                if s1 and s2:
                    similarity = len(s1 & s2) / len(s1 | s2)
                    total_similarity += similarity
                    count += 1

        if count == 0:
            return 0.0

        avg_similarity = total_similarity / count
        return 1.0 - avg_similarity  # 多样性 = 1 - 相似度


# 全局生成器实例
_generator: MultimodalGenerator | None = None


def get_generator() -> MultimodalGenerator:
    """获取全局生成器"""
    global _generator
    if _generator is None:
        _generator = MultimodalGenerator()
    return _generator
