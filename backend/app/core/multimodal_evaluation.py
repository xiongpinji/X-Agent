"""
多模态评估模块 - 评估多模态系统的性能和准确率

评估指标:
1. 融合准确率 (Fusion Accuracy)
2. 检索指标 (Retrieval Metrics): MRR, NDCG, MAP
3. 生成质量 (Generation Quality): BLEU, ROUGE, 困惑度
4. 延迟指标 (Latency Metrics)
5. 对齐质量 (Alignment Quality)
"""

from __future__ import annotations

import math
import time
from dataclasses import dataclass, field
from enum import Enum
from typing import Any

import numpy as np


class MetricType(str, Enum):
    """指标类型枚举"""
    ACCURACY = "accuracy"
    PRECISION = "precision"
    RECALL = "recall"
    F1_SCORE = "f1_score"
    MRR = "mrr"
    NDCG = "ndcg"
    MAP = "map"
    BLEU = "bleu"
    ROUGE = "rouge"
    LATENCY = "latency"
    THROUGHPUT = "throughput"
    ALIGNMENT_SCORE = "alignment_score"


@dataclass
class EvaluationMetric:
    """评估指标"""
    metric_type: MetricType
    value: float
    timestamp: float = field(default_factory=time.time)
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass
class EvaluationResult:
    """评估结果"""
    task_id: str
    task_type: str
    metrics: dict[MetricType, EvaluationMetric]
    overall_score: float
    evaluation_time_ms: float
    metadata: dict[str, Any] = field(default_factory=dict)


class FusionEvaluator:
    """融合评估器"""

    @staticmethod
    def evaluate_fusion_accuracy(
        fused_output: list[float],
        ground_truth: list[float],
        threshold: float = 0.1,
    ) -> float:
        """评估融合准确率"""
        if not fused_output or not ground_truth:
            return 0.0

        # 计算欧氏距离
        distance = math.sqrt(sum((a - b) ** 2 for a, b in zip(fused_output, ground_truth)))

        # 转换为准确率
        accuracy = max(0.0, 1.0 - distance / (threshold + 1.0))

        return min(1.0, accuracy)

    @staticmethod
    def evaluate_alignment_quality(
        alignment_scores: dict[str, float],
    ) -> float:
        """评估对齐质量"""
        if not alignment_scores:
            return 0.5

        # 计算平均对齐分数
        avg_score = sum(alignment_scores.values()) / len(alignment_scores)

        # 计算分数的方差（越小越好）
        variance = sum((score - avg_score) ** 2 for score in alignment_scores.values()) / len(alignment_scores)

        # 综合质量分数
        quality = avg_score * (1.0 - min(0.5, variance))

        return min(1.0, max(0.0, quality))

    @staticmethod
    def evaluate_modality_balance(
        component_weights: dict[str, float],
    ) -> float:
        """评估模态平衡度"""
        if not component_weights:
            return 0.0

        weights = list(component_weights.values())
        if not weights:
            return 0.0

        # 计算权重的标准差
        avg_weight = sum(weights) / len(weights)
        variance = sum((w - avg_weight) ** 2 for w in weights) / len(weights)
        std_dev = math.sqrt(variance)

        # 标准差越小，平衡度越好
        balance = 1.0 - min(1.0, std_dev)

        return balance


class RetrievalEvaluator:
    """检索评估器"""

    @staticmethod
    def compute_mrr(
        results: list[tuple[str, float]],
        relevant_ids: set[str],
    ) -> float:
        """计算平均倒数排名"""
        for rank, (item_id, _) in enumerate(results, 1):
            if item_id in relevant_ids:
                return 1.0 / rank
        return 0.0

    @staticmethod
    def compute_ndcg(
        results: list[tuple[str, float]],
        relevant_ids: set[str],
        k: int = 10,
    ) -> float:
        """计算归一化折扣累积增益"""
        # 计算DCG
        dcg = 0.0
        for rank, (item_id, _) in enumerate(results[:k], 1):
            if item_id in relevant_ids:
                dcg += 1.0 / math.log2(rank + 1)

        # 计算IDCG
        idcg = 0.0
        for i in range(1, min(len(relevant_ids), k) + 1):
            idcg += 1.0 / math.log2(i + 1)

        if idcg == 0:
            return 0.0

        return dcg / idcg

    @staticmethod
    def compute_map(
        results: list[tuple[str, float]],
        relevant_ids: set[str],
        k: int = 10,
    ) -> float:
        """计算平均精度"""
        if not relevant_ids:
            return 0.0

        ap = 0.0
        relevant_count = 0

        for rank, (item_id, _) in enumerate(results[:k], 1):
            if item_id in relevant_ids:
                relevant_count += 1
                precision_at_k = relevant_count / rank
                ap += precision_at_k

        return ap / len(relevant_ids)

    @staticmethod
    def compute_precision_at_k(
        results: list[tuple[str, float]],
        relevant_ids: set[str],
        k: int = 10,
    ) -> float:
        """计算P@K"""
        if k == 0:
            return 0.0

        relevant_count = sum(
            1 for item_id, _ in results[:k]
            if item_id in relevant_ids
        )

        return relevant_count / k

    @staticmethod
    def compute_recall_at_k(
        results: list[tuple[str, float]],
        relevant_ids: set[str],
        k: int = 10,
    ) -> float:
        """计算R@K"""
        if not relevant_ids:
            return 0.0

        relevant_count = sum(
            1 for item_id, _ in results[:k]
            if item_id in relevant_ids
        )

        return relevant_count / len(relevant_ids)


class GenerationEvaluator:
    """生成评估器"""

    @staticmethod
    def compute_bleu_score(reference: str, generated: str) -> float:
        """计算BLEU分数"""
        if not reference or not generated:
            return 0.0

        ref_words = reference.lower().split()
        gen_words = generated.lower().split()

        if not ref_words:
            return 0.0

        # 计算1-gram精度
        overlap = sum(1 for word in gen_words if word in ref_words)
        precision = overlap / len(gen_words) if gen_words else 0.0

        # 计算长度惩罚
        length_ratio = len(gen_words) / len(ref_words) if ref_words else 0.0
        if length_ratio > 1.0:
            length_penalty = 1.0
        else:
            length_penalty = math.exp(1.0 - 1.0 / length_ratio) if length_ratio > 0 else 0.0

        bleu = precision * length_penalty

        return min(1.0, max(0.0, bleu))

    @staticmethod
    def compute_rouge_score(reference: str, generated: str) -> float:
        """计算ROUGE分数"""
        if not reference or not generated:
            return 0.0

        ref_words = set(reference.lower().split())
        gen_words = set(generated.lower().split())

        if not ref_words:
            return 0.0

        # 计算Jaccard相似度
        intersection = len(ref_words & gen_words)
        union = len(ref_words | gen_words)

        if union == 0:
            return 0.0

        rouge = intersection / union

        return min(1.0, max(0.0, rouge))

    @staticmethod
    def compute_meteor_score(reference: str, generated: str) -> float:
        """计算METEOR分数"""
        if not reference or not generated:
            return 0.0

        ref_words = reference.lower().split()
        gen_words = generated.lower().split()

        if not ref_words or not gen_words:
            return 0.0

        # 计算匹配词数
        matches = sum(1 for word in gen_words if word in ref_words)

        # 精度和召回
        precision = matches / len(gen_words) if gen_words else 0.0
        recall = matches / len(ref_words) if ref_words else 0.0

        if precision + recall == 0:
            return 0.0

        # F-score
        f_score = 2 * (precision * recall) / (precision + recall)

        # 惩罚碎片化
        num_chunks = 1
        if matches > 0:
            num_chunks = sum(1 for i in range(len(gen_words) - 1)
                           if gen_words[i] in ref_words and gen_words[i + 1] not in ref_words)

        penalty = 0.5 * (num_chunks / matches) if matches > 0 else 0.0

        meteor = f_score * (1.0 - penalty)

        return min(1.0, max(0.0, meteor))

    @staticmethod
    def compute_perplexity(logits: list[float]) -> float:
        """计算困惑度"""
        if not logits:
            return float('inf')

        # 计算平均对数概率
        avg_logit = sum(logits) / len(logits)

        # 困惑度 = exp(-avg_logit)
        perplexity = math.exp(-avg_logit)

        return perplexity


class LatencyEvaluator:
    """延迟评估器"""

    @staticmethod
    def compute_p50_latency(latencies: list[float]) -> float:
        """计算P50延迟"""
        if not latencies:
            return 0.0

        sorted_latencies = sorted(latencies)
        index = int(len(sorted_latencies) * 0.5)

        return sorted_latencies[index]

    @staticmethod
    def compute_p95_latency(latencies: list[float]) -> float:
        """计算P95延迟"""
        if not latencies:
            return 0.0

        sorted_latencies = sorted(latencies)
        index = int(len(sorted_latencies) * 0.95)

        return sorted_latencies[index]

    @staticmethod
    def compute_p99_latency(latencies: list[float]) -> float:
        """计算P99延迟"""
        if not latencies:
            return 0.0

        sorted_latencies = sorted(latencies)
        index = int(len(sorted_latencies) * 0.99)

        return sorted_latencies[index]

    @staticmethod
    def compute_avg_latency(latencies: list[float]) -> float:
        """计算平均延迟"""
        if not latencies:
            return 0.0

        return sum(latencies) / len(latencies)

    @staticmethod
    def compute_throughput(num_requests: int, total_time_ms: float) -> float:
        """计算吞吐量 (请求/秒)"""
        if total_time_ms <= 0:
            return 0.0

        return (num_requests / total_time_ms) * 1000


class MultimodalEvaluator:
    """多模态系统评估器"""

    def __init__(self):
        self.fusion_evaluator = FusionEvaluator()
        self.retrieval_evaluator = RetrievalEvaluator()
        self.generation_evaluator = GenerationEvaluator()
        self.latency_evaluator = LatencyEvaluator()

    def evaluate_fusion_task(
        self,
        fused_output: list[float],
        ground_truth: list[float],
        alignment_scores: dict[str, float],
        component_weights: dict[str, float],
        latency_ms: float,
    ) -> EvaluationResult:
        """评估融合任务"""
        start_time = time.time()

        metrics = {}

        # 融合准确率
        accuracy = self.fusion_evaluator.evaluate_fusion_accuracy(fused_output, ground_truth)
        metrics[MetricType.ACCURACY] = EvaluationMetric(
            metric_type=MetricType.ACCURACY,
            value=accuracy,
        )

        # 对齐质量
        alignment_quality = self.fusion_evaluator.evaluate_alignment_quality(alignment_scores)
        metrics[MetricType.ALIGNMENT_SCORE] = EvaluationMetric(
            metric_type=MetricType.ALIGNMENT_SCORE,
            value=alignment_quality,
        )

        # 模态平衡度
        balance = self.fusion_evaluator.evaluate_modality_balance(component_weights)
        metrics[MetricType.PRECISION] = EvaluationMetric(
            metric_type=MetricType.PRECISION,
            value=balance,
        )

        # 延迟
        metrics[MetricType.LATENCY] = EvaluationMetric(
            metric_type=MetricType.LATENCY,
            value=latency_ms,
        )

        # 计算综合分数
        overall_score = (accuracy * 0.4 + alignment_quality * 0.3 + balance * 0.2 +
                        (1.0 - min(1.0, latency_ms / 2000.0)) * 0.1)

        evaluation_time_ms = (time.time() - start_time) * 1000

        return EvaluationResult(
            task_id="fusion_task",
            task_type="fusion",
            metrics=metrics,
            overall_score=overall_score,
            evaluation_time_ms=evaluation_time_ms,
        )

    def evaluate_retrieval_task(
        self,
        results: list[tuple[str, float]],
        relevant_ids: set[str],
        latency_ms: float,
        k: int = 10,
    ) -> EvaluationResult:
        """评估检索任务"""
        start_time = time.time()

        metrics = {}

        # MRR
        mrr = self.retrieval_evaluator.compute_mrr(results, relevant_ids)
        metrics[MetricType.MRR] = EvaluationMetric(
            metric_type=MetricType.MRR,
            value=mrr,
        )

        # NDCG
        ndcg = self.retrieval_evaluator.compute_ndcg(results, relevant_ids, k)
        metrics[MetricType.NDCG] = EvaluationMetric(
            metric_type=MetricType.NDCG,
            value=ndcg,
        )

        # MAP
        map_score = self.retrieval_evaluator.compute_map(results, relevant_ids, k)
        metrics[MetricType.MAP] = EvaluationMetric(
            metric_type=MetricType.MAP,
            value=map_score,
        )

        # 精度和召回
        precision = self.retrieval_evaluator.compute_precision_at_k(results, relevant_ids, k)
        metrics[MetricType.PRECISION] = EvaluationMetric(
            metric_type=MetricType.PRECISION,
            value=precision,
        )

        recall = self.retrieval_evaluator.compute_recall_at_k(results, relevant_ids, k)
        metrics[MetricType.RECALL] = EvaluationMetric(
            metric_type=MetricType.RECALL,
            value=recall,
        )

        # F1分数
        if precision + recall > 0:
            f1 = 2 * (precision * recall) / (precision + recall)
        else:
            f1 = 0.0

        metrics[MetricType.F1_SCORE] = EvaluationMetric(
            metric_type=MetricType.F1_SCORE,
            value=f1,
        )

        # 延迟
        metrics[MetricType.LATENCY] = EvaluationMetric(
            metric_type=MetricType.LATENCY,
            value=latency_ms,
        )

        # 计算综合分数
        overall_score = (mrr * 0.2 + ndcg * 0.3 + map_score * 0.2 + f1 * 0.2 +
                        (1.0 - min(1.0, latency_ms / 2000.0)) * 0.1)

        evaluation_time_ms = (time.time() - start_time) * 1000

        return EvaluationResult(
            task_id="retrieval_task",
            task_type="retrieval",
            metrics=metrics,
            overall_score=overall_score,
            evaluation_time_ms=evaluation_time_ms,
        )

    def evaluate_generation_task(
        self,
        generated_text: str,
        reference_text: str,
        latency_ms: float,
    ) -> EvaluationResult:
        """评估生成任务"""
        start_time = time.time()

        metrics = {}

        # BLEU分数
        bleu = self.generation_evaluator.compute_bleu_score(reference_text, generated_text)
        metrics[MetricType.BLEU] = EvaluationMetric(
            metric_type=MetricType.BLEU,
            value=bleu,
        )

        # ROUGE分数
        rouge = self.generation_evaluator.compute_rouge_score(reference_text, generated_text)
        metrics[MetricType.ROUGE] = EvaluationMetric(
            metric_type=MetricType.ROUGE,
            value=rouge,
        )

        # 延迟
        metrics[MetricType.LATENCY] = EvaluationMetric(
            metric_type=MetricType.LATENCY,
            value=latency_ms,
        )

        # 计算综合分数
        overall_score = (bleu * 0.4 + rouge * 0.4 +
                        (1.0 - min(1.0, latency_ms / 2000.0)) * 0.2)

        evaluation_time_ms = (time.time() - start_time) * 1000

        return EvaluationResult(
            task_id="generation_task",
            task_type="generation",
            metrics=metrics,
            overall_score=overall_score,
            evaluation_time_ms=evaluation_time_ms,
        )


# 全局评估器实例
_evaluator: MultimodalEvaluator | None = None


def get_evaluator() -> MultimodalEvaluator:
    """获取全局评估器"""
    global _evaluator
    if _evaluator is None:
        _evaluator = MultimodalEvaluator()
    return _evaluator
