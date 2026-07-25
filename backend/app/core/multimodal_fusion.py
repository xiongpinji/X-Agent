"""
多模态融合模块 - 实现跨模态推理和融合能力

支持的融合策略:
1. 早期融合 (Early Fusion): 特征级融合
2. 晚期融合 (Late Fusion): 决策级融合
3. 混合融合 (Hybrid Fusion): 多层次融合
4. 注意力融合 (Attention Fusion): 基于注意力机制的融合
5. 跨模态对齐 (Cross-modal Alignment): 模态间对齐
"""

from __future__ import annotations

import asyncio
import math
from dataclasses import dataclass, field
from enum import StrEnum
from typing import Any

import numpy as np


class FusionStrategy(StrEnum):
    """融合策略枚举"""
    EARLY = "early"  # 特征级融合
    LATE = "late"  # 决策级融合
    HYBRID = "hybrid"  # 混合融合
    ATTENTION = "attention"  # 注意力融合
    CROSS_MODAL = "cross_modal"  # 跨模态对齐


class Modality(StrEnum):
    """模态类型枚举"""
    TEXT = "text"
    IMAGE = "image"
    VIDEO = "video"
    AUDIO = "audio"
    STRUCTURED = "structured"


@dataclass
class ModalityFeature:
    """单个模态的特征表示"""
    modality: Modality
    features: list[float]  # 特征向量
    confidence: float = 1.0  # 置信度 [0, 1]
    metadata: dict[str, Any] = field(default_factory=dict)
    timestamp: float | None = None  # 时间戳（用于视频/音频）

    def __post_init__(self):
        if not 0 <= self.confidence <= 1:
            raise ValueError(f"Confidence must be in [0, 1], got {self.confidence}")
        if not self.features:
            raise ValueError("Features cannot be empty")


@dataclass
class FusedRepresentation:
    """融合后的多模态表示"""
    fused_features: list[float]  # 融合特征向量
    modalities: list[Modality]  # 参与融合的模态
    fusion_strategy: FusionStrategy
    confidence: float  # 融合置信度
    component_weights: dict[Modality, float]  # 各模态的权重
    alignment_scores: dict[str, float] = field(default_factory=dict)  # 对齐分数
    metadata: dict[str, Any] = field(default_factory=dict)


class ModalityEncoder:
    """模态编码器 - 将不同模态转换为统一的特征空间"""

    def __init__(self, target_dim: int = 512):
        self.target_dim = target_dim
        self._projection_matrices: dict[Modality, list[list[float]]] = {}
        self._initialize_projections()

    def _initialize_projections(self):
        """初始化投影矩阵"""
        for modality in Modality:
            # 使用随机投影矩阵进行维度转换
            # 在生产环境中应使用预训练的编码器
            matrix = self._random_projection_matrix(256, self.target_dim)
            self._projection_matrices[modality] = matrix

    @staticmethod
    def _random_projection_matrix(input_dim: int, output_dim: int) -> list[list[float]]:
        """生成随机投影矩阵"""
        np.random.seed(42)  # 确保可重复性
        matrix = np.random.randn(input_dim, output_dim) / math.sqrt(input_dim)
        return matrix.tolist()

    def encode(self, feature: ModalityFeature) -> list[float]:
        """将模态特征编码到统一空间"""
        if len(feature.features) == 0:
            return [0.0] * self.target_dim

        # 获取投影矩阵
        matrix = np.array(self._projection_matrices[feature.modality])
        features = np.array(feature.features)

        # 投影到目标维度
        if len(features) != matrix.shape[0]:
            # 如果维度不匹配，进行填充或截断
            if len(features) < matrix.shape[0]:
                features = np.pad(features, (0, matrix.shape[0] - len(features)))
            else:
                features = features[:matrix.shape[0]]

        encoded = np.dot(features, matrix)

        # 应用置信度加权
        encoded = encoded * feature.confidence

        return encoded.tolist()


class AttentionFusion:
    """注意力融合机制"""

    def __init__(self, feature_dim: int = 512):
        self.feature_dim = feature_dim
        self._attention_weights: dict[str, list[float]] = {}

    def compute_attention_weights(
        self,
        features: list[ModalityFeature],
        query: list[float] | None = None,
    ) -> dict[Modality, float]:
        """计算注意力权重"""
        if not features:
            return {}

        weights = {}
        total_score = 0.0

        for feature in features:
            # 基于特征的L2范数和置信度计算注意力分数
            feature_norm = math.sqrt(sum(f * f for f in feature.features))

            if query:
                # 如果提供了查询向量，计算相似度
                similarity = self._cosine_similarity(feature.features, query)
                score = feature_norm * feature.confidence * (0.5 + 0.5 * similarity)
            else:
                score = feature_norm * feature.confidence

            weights[feature.modality] = score
            total_score += score

        # 归一化权重
        if total_score > 0:
            weights = {k: v / total_score for k, v in weights.items()}
        else:
            # 均匀分布
            uniform_weight = 1.0 / len(features)
            weights = {f.modality: uniform_weight for f in features}

        return weights

    @staticmethod
    def _cosine_similarity(vec1: list[float], vec2: list[float]) -> float:
        """计算余弦相似度"""
        if len(vec1) != len(vec2):
            return 0.0

        dot_product = sum(a * b for a, b in zip(vec1, vec2, strict=False))
        norm1 = math.sqrt(sum(a * a for a in vec1))
        norm2 = math.sqrt(sum(b * b for b in vec2))

        if norm1 == 0 or norm2 == 0:
            return 0.0

        return dot_product / (norm1 * norm2)


class CrossModalAlignment:
    """跨模态对齐"""

    def __init__(self, feature_dim: int = 512):
        self.feature_dim = feature_dim

    def compute_alignment_scores(
        self,
        features: list[ModalityFeature],
    ) -> dict[str, float]:
        """计算模态间的对齐分数"""
        scores = {}

        if len(features) < 2:
            return scores

        # 计算所有模态对之间的对齐分数
        for i in range(len(features)):
            for j in range(i + 1, len(features)):
                feat1 = features[i]
                feat2 = features[j]

                # 计算特征相似度
                similarity = self._compute_similarity(feat1.features, feat2.features)

                # 考虑置信度
                alignment_score = similarity * feat1.confidence * feat2.confidence

                key = f"{feat1.modality.value}-{feat2.modality.value}"
                scores[key] = alignment_score

        return scores

    @staticmethod
    def _compute_similarity(vec1: list[float], vec2: list[float]) -> float:
        """计算向量相似度"""
        if not vec1 or not vec2:
            return 0.0

        # 填充到相同长度
        max_len = max(len(vec1), len(vec2))
        v1 = vec1 + [0.0] * (max_len - len(vec1))
        v2 = vec2 + [0.0] * (max_len - len(vec2))

        # 余弦相似度
        dot_product = sum(a * b for a, b in zip(v1, v2, strict=False))
        norm1 = math.sqrt(sum(a * a for a in v1))
        norm2 = math.sqrt(sum(b * b for b in v2))

        if norm1 == 0 or norm2 == 0:
            return 0.0

        return dot_product / (norm1 * norm2)


class MultimodalFusion:
    """多模态融合引擎"""

    def __init__(
        self,
        feature_dim: int = 512,
        fusion_strategy: FusionStrategy = FusionStrategy.HYBRID,
    ):
        self.feature_dim = feature_dim
        self.fusion_strategy = fusion_strategy
        self.encoder = ModalityEncoder(target_dim=feature_dim)
        self.attention = AttentionFusion(feature_dim=feature_dim)
        self.alignment = CrossModalAlignment(feature_dim=feature_dim)

    async def fuse(
        self,
        features: list[ModalityFeature],
        query: list[float] | None = None,
        strategy: FusionStrategy | None = None,
    ) -> FusedRepresentation:
        """融合多个模态的特征"""
        if not features:
            raise ValueError("At least one feature is required for fusion")

        strategy = strategy or self.fusion_strategy

        # 编码所有特征到统一空间
        encoded_features = [self.encoder.encode(f) for f in features]

        # 计算注意力权重
        attention_weights = self.attention.compute_attention_weights(features, query)

        # 计算对齐分数
        alignment_scores = self.alignment.compute_alignment_scores(features)

        # 根据策略进行融合
        if strategy == FusionStrategy.EARLY:
            fused = self._early_fusion(encoded_features, attention_weights)
        elif strategy == FusionStrategy.LATE:
            fused = self._late_fusion(encoded_features, attention_weights)
        elif strategy == FusionStrategy.ATTENTION:
            fused = self._attention_fusion(encoded_features, attention_weights)
        elif strategy == FusionStrategy.CROSS_MODAL:
            fused = self._cross_modal_fusion(encoded_features, attention_weights, alignment_scores)
        else:  # HYBRID
            fused = self._hybrid_fusion(encoded_features, attention_weights, alignment_scores)

        # 计算融合置信度
        confidence = self._compute_fusion_confidence(features, alignment_scores)

        return FusedRepresentation(
            fused_features=fused,
            modalities=[f.modality for f in features],
            fusion_strategy=strategy,
            confidence=confidence,
            component_weights=attention_weights,
            alignment_scores=alignment_scores,
        )

    def _early_fusion(
        self,
        encoded_features: list[list[float]],
        weights: dict[Modality, float],
    ) -> list[float]:
        """早期融合 - 特征级融合"""
        if not encoded_features:
            return [0.0] * self.feature_dim

        # 加权平均
        fused = np.zeros(self.feature_dim)
        total_weight = 0.0

        for features, (_modality, weight) in zip(encoded_features, weights.items(), strict=False):
            fused += np.array(features) * weight
            total_weight += weight

        if total_weight > 0:
            fused = fused / total_weight

        return fused.tolist()

    def _late_fusion(
        self,
        encoded_features: list[list[float]],
        weights: dict[Modality, float],
    ) -> list[float]:
        """晚期融合 - 决策级融合"""
        if not encoded_features:
            return [0.0] * self.feature_dim

        # 连接所有特征
        concatenated = np.concatenate([np.array(f) for f in encoded_features])

        # 应用权重
        weight_vector = np.array(list(weights.values()))
        weight_vector = np.repeat(weight_vector, self.feature_dim)

        fused = concatenated * weight_vector

        # 投影回原始维度
        fused = fused[:self.feature_dim]

        return fused.tolist()

    def _attention_fusion(
        self,
        encoded_features: list[list[float]],
        weights: dict[Modality, float],
    ) -> list[float]:
        """注意力融合"""
        if not encoded_features:
            return [0.0] * self.feature_dim

        # 使用注意力权重进行加权融合
        fused = np.zeros(self.feature_dim)

        for features, weight in zip(encoded_features, weights.values(), strict=False):
            fused += np.array(features) * weight

        return fused.tolist()

    def _cross_modal_fusion(
        self,
        encoded_features: list[list[float]],
        weights: dict[Modality, float],
        alignment_scores: dict[str, float],
    ) -> list[float]:
        """跨模态对齐融合"""
        if not encoded_features:
            return [0.0] * self.feature_dim

        # 基于对齐分数调整权重
        adjusted_weights = dict(weights)

        if alignment_scores:
            avg_alignment = sum(alignment_scores.values()) / len(alignment_scores)
            for modality in adjusted_weights:
                # 根据对齐质量调整权重
                adjusted_weights[modality] *= (0.5 + 0.5 * max(0, avg_alignment))

        # 归一化权重
        total_weight = sum(adjusted_weights.values())
        if total_weight > 0:
            adjusted_weights = {k: v / total_weight for k, v in adjusted_weights.items()}

        # 加权融合
        fused = np.zeros(self.feature_dim)
        for features, weight in zip(encoded_features, adjusted_weights.values(), strict=False):
            fused += np.array(features) * weight

        return fused.tolist()

    def _hybrid_fusion(
        self,
        encoded_features: list[list[float]],
        weights: dict[Modality, float],
        alignment_scores: dict[str, float],
    ) -> list[float]:
        """混合融合 - 结合早期和晚期融合"""
        if not encoded_features:
            return [0.0] * self.feature_dim

        # 早期融合部分
        early_fused = np.array(self._early_fusion(encoded_features, weights))

        # 晚期融合部分
        late_fused = np.array(self._late_fusion(encoded_features, weights))

        # 基于对齐分数混合
        if alignment_scores:
            avg_alignment = sum(alignment_scores.values()) / len(alignment_scores)
            alpha = 0.3 + 0.4 * max(0, avg_alignment)  # [0.3, 0.7]
        else:
            alpha = 0.5

        # 混合融合
        fused = alpha * early_fused + (1 - alpha) * late_fused

        return fused.tolist()

    def _compute_fusion_confidence(
        self,
        features: list[ModalityFeature],
        alignment_scores: dict[str, float],
    ) -> float:
        """计算融合置信度"""
        if not features:
            return 0.0

        # 基于各模态的置信度
        avg_confidence = sum(f.confidence for f in features) / len(features)

        # 基于对齐分数
        if alignment_scores:
            avg_alignment = sum(alignment_scores.values()) / len(alignment_scores)
            # 对齐分数越高，融合置信度越高
            alignment_factor = 0.5 + 0.5 * max(0, avg_alignment)
        else:
            alignment_factor = 0.5

        # 综合置信度
        confidence = avg_confidence * alignment_factor

        return min(1.0, max(0.0, confidence))


class MultimodalFusionManager:
    """多模态融合管理器"""

    def __init__(self, feature_dim: int = 512):
        self.feature_dim = feature_dim
        self.fusion_engines: dict[FusionStrategy, MultimodalFusion] = {}
        self._initialize_engines()

    def _initialize_engines(self):
        """初始化各种融合策略的引擎"""
        for strategy in FusionStrategy:
            self.fusion_engines[strategy] = MultimodalFusion(
                feature_dim=self.feature_dim,
                fusion_strategy=strategy,
            )

    async def fuse(
        self,
        features: list[ModalityFeature],
        query: list[float] | None = None,
        strategy: FusionStrategy = FusionStrategy.HYBRID,
    ) -> FusedRepresentation:
        """融合多模态特征"""
        engine = self.fusion_engines[strategy]
        return await engine.fuse(features, query, strategy)

    async def fuse_all_strategies(
        self,
        features: list[ModalityFeature],
        query: list[float] | None = None,
    ) -> dict[FusionStrategy, FusedRepresentation]:
        """使用所有策略进行融合"""
        results = {}

        tasks = [
            self.fuse(features, query, strategy)
            for strategy in FusionStrategy
        ]

        fused_results = await asyncio.gather(*tasks)

        for strategy, result in zip(FusionStrategy, fused_results, strict=False):
            results[strategy] = result

        return results

    def select_best_fusion(
        self,
        fusions: dict[FusionStrategy, FusedRepresentation],
    ) -> tuple[FusionStrategy, FusedRepresentation]:
        """选择最佳融合结果"""
        if not fusions:
            raise ValueError("No fusion results provided")

        # 基于置信度和对齐分数选择最佳结果
        best_strategy = None
        best_score = -1.0
        best_result = None

        for strategy, result in fusions.items():
            # 计算综合分数
            alignment_score = (
                sum(result.alignment_scores.values()) / len(result.alignment_scores)
                if result.alignment_scores
                else 0.5
            )

            score = result.confidence * 0.6 + alignment_score * 0.4

            if score > best_score:
                best_score = score
                best_strategy = strategy
                best_result = result

        return best_strategy, best_result


# 全局融合管理器实例
_fusion_manager: MultimodalFusion | None = None


def get_fusion_manager(feature_dim: int = 512) -> MultimodalFusion:
    """获取全局融合管理器"""
    global _fusion_manager
    if _fusion_manager is None:
        _fusion_manager = MultimodalFusion(feature_dim=feature_dim)
    return _fusion_manager
