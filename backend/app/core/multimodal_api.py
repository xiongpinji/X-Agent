"""
多模态API接口 - 提供统一的多模态能力访问接口
"""

from __future__ import annotations

import asyncio
from typing import Any

from backend.app.core.multimodal_fusion import (
    FusionStrategy,
    Modality,
    ModalityFeature,
    MultimodalFusion,
    get_fusion_manager,
)
from backend.app.core.multimodal_generation import (
    GenerationRequest,
    GenerationType,
    MultimodalGenerator,
    get_generator,
)
from backend.app.core.multimodal_retrieval import (
    MultimodalRetriever,
    RetrievalType,
    get_retriever,
)
from backend.app.core.multimodal_evaluation import (
    MultimodalEvaluator,
    get_evaluator,
)


class MultimodalAPI:
    """多模态API - 统一接口"""

    def __init__(self):
        self.fusion_manager = get_fusion_manager()
        self.retriever = get_retriever()
        self.generator = get_generator()
        self.evaluator = get_evaluator()

    async def fuse_modalities(
        self,
        features: dict[str, list[float]],
        strategy: str = "hybrid",
        query: list[float] | None = None,
    ) -> dict[str, Any]:
        """融合多个模态的特征"""
        # 转换输入格式
        modality_features = []

        for modality_name, feature_vector in features.items():
            try:
                modality = Modality[modality_name.upper()]
            except KeyError:
                continue

            feature = ModalityFeature(
                modality=modality,
                features=feature_vector,
                confidence=1.0,
            )
            modality_features.append(feature)

        if not modality_features:
            raise ValueError("No valid modalities provided")

        # 执行融合
        try:
            fusion_strategy = FusionStrategy[strategy.upper()]
        except KeyError:
            fusion_strategy = FusionStrategy.HYBRID

        fused = await self.fusion_manager.fuse(
            modality_features,
            query=query,
            strategy=fusion_strategy,
        )

        return {
            "fused_features": fused.fused_features,
            "modalities": [m.value for m in fused.modalities],
            "fusion_strategy": fused.fusion_strategy.value,
            "confidence": fused.confidence,
            "component_weights": {k.value: v for k, v in fused.component_weights.items()},
            "alignment_scores": fused.alignment_scores,
        }

    async def retrieve_multimodal(
        self,
        query_vector: list[float],
        query_type: str = "hybrid",
        modality: str = "text",
        top_k: int = 10,
        threshold: float = 0.0,
    ) -> dict[str, Any]:
        """执行多模态检索"""
        try:
            retrieval_type = RetrievalType[query_type.upper()]
        except KeyError:
            retrieval_type = RetrievalType.HYBRID

        results = await self.retriever.retrieve(
            query_vector=query_vector,
            query_type=retrieval_type,
            modality=modality,
            top_k=top_k,
            threshold=threshold,
        )

        return {
            "query_id": results.query_id,
            "retrieval_type": results.retrieval_type.value,
            "results": [
                {
                    "item_id": r.item_id,
                    "similarity_score": r.similarity_score,
                    "modality": r.modality,
                    "rank": r.rank,
                }
                for r in results.results
            ],
            "total_count": results.total_count,
            "query_time_ms": results.query_time_ms,
        }

    async def generate_multimodal(
        self,
        generation_type: str,
        input_data: str | list[float],
        input_modality: str,
        output_modality: str,
        parameters: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """执行多模态生成"""
        try:
            gen_type = GenerationType[generation_type.upper()]
        except KeyError:
            gen_type = GenerationType.TEXT_TO_IMAGE

        request = GenerationRequest(
            generation_type=gen_type,
            input_data=input_data,
            input_modality=input_modality,
            output_modality=output_modality,
            parameters=parameters or {},
        )

        result = await self.generator.generate(request)

        return {
            "request_id": result.request_id,
            "generation_type": result.generation_type.value,
            "output_data": result.output_data,
            "output_modality": result.output_modality,
            "quality_score": result.quality_score,
            "generation_time_ms": result.generation_time_ms,
        }

    async def evaluate_fusion(
        self,
        fused_output: list[float],
        ground_truth: list[float],
        alignment_scores: dict[str, float],
        component_weights: dict[str, float],
        latency_ms: float,
    ) -> dict[str, Any]:
        """评估融合结果"""
        result = self.evaluator.evaluate_fusion_task(
            fused_output=fused_output,
            ground_truth=ground_truth,
            alignment_scores=alignment_scores,
            component_weights=component_weights,
            latency_ms=latency_ms,
        )

        return {
            "task_id": result.task_id,
            "task_type": result.task_type,
            "metrics": {
                k.value: {
                    "value": v.value,
                    "timestamp": v.timestamp,
                }
                for k, v in result.metrics.items()
            },
            "overall_score": result.overall_score,
            "evaluation_time_ms": result.evaluation_time_ms,
        }

    async def evaluate_retrieval(
        self,
        results: list[tuple[str, float]],
        relevant_ids: set[str],
        latency_ms: float,
        k: int = 10,
    ) -> dict[str, Any]:
        """评估检索结果"""
        result = self.evaluator.evaluate_retrieval_task(
            results=results,
            relevant_ids=relevant_ids,
            latency_ms=latency_ms,
            k=k,
        )

        return {
            "task_id": result.task_id,
            "task_type": result.task_type,
            "metrics": {
                k.value: {
                    "value": v.value,
                    "timestamp": v.timestamp,
                }
                for k, v in result.metrics.items()
            },
            "overall_score": result.overall_score,
            "evaluation_time_ms": result.evaluation_time_ms,
        }

    async def evaluate_generation(
        self,
        generated_text: str,
        reference_text: str,
        latency_ms: float,
    ) -> dict[str, Any]:
        """评估生成结果"""
        result = self.evaluator.evaluate_generation_task(
            generated_text=generated_text,
            reference_text=reference_text,
            latency_ms=latency_ms,
        )

        return {
            "task_id": result.task_id,
            "task_type": result.task_type,
            "metrics": {
                k.value: {
                    "value": v.value,
                    "timestamp": v.timestamp,
                }
                for k, v in result.metrics.items()
            },
            "overall_score": result.overall_score,
            "evaluation_time_ms": result.evaluation_time_ms,
        }

    async def batch_fuse(
        self,
        batch_features: list[dict[str, list[float]]],
        strategy: str = "hybrid",
    ) -> list[dict[str, Any]]:
        """批量融合"""
        tasks = [
            self.fuse_modalities(features, strategy)
            for features in batch_features
        ]

        return await asyncio.gather(*tasks)

    async def batch_retrieve(
        self,
        batch_queries: list[dict[str, Any]],
    ) -> list[dict[str, Any]]:
        """批量检索"""
        tasks = [
            self.retrieve_multimodal(**query)
            for query in batch_queries
        ]

        return await asyncio.gather(*tasks)

    async def batch_generate(
        self,
        batch_requests: list[dict[str, Any]],
    ) -> list[dict[str, Any]]:
        """批量生成"""
        tasks = [
            self.generate_multimodal(**request)
            for request in batch_requests
        ]

        return await asyncio.gather(*tasks)


# 全局API实例
_api: MultimodalAPI | None = None


def get_multimodal_api() -> MultimodalAPI:
    """获取全局多模态API"""
    global _api
    if _api is None:
        _api = MultimodalAPI()
    return _api
