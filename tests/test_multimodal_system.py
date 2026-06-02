"""
多模态系统测试套件 - 验证融合、检索、生成和评估功能
"""

import asyncio
import pytest
import time
from typing import Any

from backend.app.core.multimodal_fusion import (
    FusionStrategy,
    Modality,
    ModalityFeature,
    MultimodalFusion,
)
from backend.app.core.multimodal_retrieval import (
    RetrievalType,
    RetrievalQuery,
    MultimodalRetriever,
)
from backend.app.core.multimodal_generation import (
    GenerationType,
    GenerationRequest,
    MultimodalGenerator,
)
from backend.app.core.multimodal_evaluation import (
    MultimodalEvaluator,
)
from backend.app.core.multimodal_api import (
    MultimodalAPI,
)


class TestMultimodalFusion:
    """多模态融合测试"""

    @pytest.fixture
    def fusion_engine(self):
        return MultimodalFusion(feature_dim=512)

    @pytest.fixture
    def sample_features(self):
        """生成示例特征"""
        return [
            ModalityFeature(
                modality=Modality.TEXT,
                features=[0.1] * 256,
                confidence=0.9,
            ),
            ModalityFeature(
                modality=Modality.IMAGE,
                features=[0.2] * 256,
                confidence=0.85,
            ),
            ModalityFeature(
                modality=Modality.VIDEO,
                features=[0.15] * 256,
                confidence=0.8,
            ),
        ]

    @pytest.mark.asyncio
    async def test_early_fusion(self, fusion_engine, sample_features):
        """测试早期融合"""
        result = await fusion_engine.fuse(
            sample_features,
            strategy=FusionStrategy.EARLY,
        )

        assert result.fused_features is not None
        assert len(result.fused_features) == 512
        assert result.fusion_strategy == FusionStrategy.EARLY
        assert 0 <= result.confidence <= 1

    @pytest.mark.asyncio
    async def test_late_fusion(self, fusion_engine, sample_features):
        """测试晚期融合"""
        result = await fusion_engine.fuse(
            sample_features,
            strategy=FusionStrategy.LATE,
        )

        assert result.fused_features is not None
        assert len(result.fused_features) == 512
        assert result.fusion_strategy == FusionStrategy.LATE

    @pytest.mark.asyncio
    async def test_hybrid_fusion(self, fusion_engine, sample_features):
        """测试混合融合"""
        result = await fusion_engine.fuse(
            sample_features,
            strategy=FusionStrategy.HYBRID,
        )

        assert result.fused_features is not None
        assert len(result.fused_features) == 512
        assert result.fusion_strategy == FusionStrategy.HYBRID

    @pytest.mark.asyncio
    async def test_attention_fusion(self, fusion_engine, sample_features):
        """测试注意力融合"""
        result = await fusion_engine.fuse(
            sample_features,
            strategy=FusionStrategy.ATTENTION,
        )

        assert result.fused_features is not None
        assert len(result.fused_features) == 512
        assert result.fusion_strategy == FusionStrategy.ATTENTION

    @pytest.mark.asyncio
    async def test_cross_modal_fusion(self, fusion_engine, sample_features):
        """测试跨模态融合"""
        result = await fusion_engine.fuse(
            sample_features,
            strategy=FusionStrategy.CROSS_MODAL,
        )

        assert result.fused_features is not None
        assert len(result.fused_features) == 512
        assert result.alignment_scores is not None

    @pytest.mark.asyncio
    async def test_fusion_with_query(self, fusion_engine, sample_features):
        """测试带查询的融合"""
        query = [0.1] * 512

        result = await fusion_engine.fuse(
            sample_features,
            query=query,
        )

        assert result.fused_features is not None
        assert result.component_weights is not None

    @pytest.mark.asyncio
    async def test_fusion_confidence(self, fusion_engine, sample_features):
        """测试融合置信度"""
        result = await fusion_engine.fuse(sample_features)

        assert 0 <= result.confidence <= 1
        # 高置信度的特征应该产生高置信度的融合
        assert result.confidence > 0.5

    def test_fusion_accuracy(self, fusion_engine):
        """测试融合准确率"""
        features = [
            ModalityFeature(
                modality=Modality.TEXT,
                features=[1.0] * 256,
                confidence=1.0,
            ),
            ModalityFeature(
                modality=Modality.IMAGE,
                features=[1.0] * 256,
                confidence=1.0,
            ),
        ]

        # 同步调用
        loop = asyncio.get_event_loop()
        result = loop.run_until_complete(fusion_engine.fuse(features))

        # 相同的特征应该产生相似的融合结果
        assert result.fused_features is not None


class TestMultimodalRetrieval:
    """多模态检索测试"""

    @pytest.fixture
    def retriever(self):
        return MultimodalRetriever(index_dim=512)

    @pytest.fixture
    def sample_index(self, retriever):
        """构建示例索引"""
        # 添加文本项
        for i in range(10):
            retriever.add_item(
                item_id=f"text_{i}",
                vector=[0.1 * (i + 1)] * 512,
                modality="text",
            )

        # 添加图像项
        for i in range(10):
            retriever.add_item(
                item_id=f"image_{i}",
                vector=[0.2 * (i + 1)] * 512,
                modality="image",
            )

        return retriever

    @pytest.mark.asyncio
    async def test_text_to_image_retrieval(self, sample_index):
        """测试文本到图像检索"""
        query_vector = [0.15] * 512

        results = await sample_index.retrieve(
            query_vector=query_vector,
            query_type=RetrievalType.TEXT_TO_IMAGE,
            top_k=5,
        )

        assert results.results is not None
        assert len(results.results) <= 5
        assert results.query_time_ms > 0

    @pytest.mark.asyncio
    async def test_hybrid_retrieval(self, sample_index):
        """测试混合检索"""
        query_vector = [0.15] * 512

        results = await sample_index.retrieve(
            query_vector=query_vector,
            query_type=RetrievalType.HYBRID,
            top_k=10,
        )

        assert results.results is not None
        assert len(results.results) <= 10

    @pytest.mark.asyncio
    async def test_retrieval_ranking(self, sample_index):
        """测试检索排名"""
        query_vector = [0.2] * 512

        results = await sample_index.retrieve(
            query_vector=query_vector,
            query_type=RetrievalType.HYBRID,
            top_k=5,
        )

        # 检查排名是否递减
        scores = [r.similarity_score for r in results.results]
        assert scores == sorted(scores, reverse=True)

    @pytest.mark.asyncio
    async def test_retrieval_threshold(self, sample_index):
        """测试检索阈值"""
        query_vector = [0.15] * 512

        results_no_threshold = await sample_index.retrieve(
            query_vector=query_vector,
            query_type=RetrievalType.HYBRID,
            threshold=0.0,
            top_k=100,
        )

        results_with_threshold = await sample_index.retrieve(
            query_vector=query_vector,
            query_type=RetrievalType.HYBRID,
            threshold=0.5,
            top_k=100,
        )

        # 有阈值的结果应该更少
        assert len(results_with_threshold.results) <= len(results_no_threshold.results)


class TestMultimodalGeneration:
    """多模态生成测试"""

    @pytest.fixture
    def generator(self):
        return MultimodalGenerator()

    @pytest.mark.asyncio
    async def test_text_to_image_generation(self, generator):
        """测试文生图"""
        request = GenerationRequest(
            generation_type=GenerationType.TEXT_TO_IMAGE,
            input_data="A beautiful sunset",
            input_modality="text",
            output_modality="image",
        )

        result = await generator.generate(request)

        assert result.output_data is not None
        assert result.generation_time_ms > 0
        assert 0 <= result.quality_score <= 1

    @pytest.mark.asyncio
    async def test_image_to_text_generation(self, generator):
        """测试图生文"""
        image_features = [0.1] * 512

        request = GenerationRequest(
            generation_type=GenerationType.IMAGE_TO_TEXT,
            input_data=image_features,
            input_modality="image",
            output_modality="text",
        )

        result = await generator.generate(request)

        assert isinstance(result.output_data, str)
        assert len(result.output_data) > 0

    @pytest.mark.asyncio
    async def test_text_to_video_generation(self, generator):
        """测试文生视频"""
        request = GenerationRequest(
            generation_type=GenerationType.TEXT_TO_VIDEO,
            input_data="A cat playing with a ball",
            input_modality="text",
            output_modality="video",
            parameters={"num_frames": 30},
        )

        result = await generator.generate(request)

        assert result.output_data is not None
        assert isinstance(result.output_data, list)

    @pytest.mark.asyncio
    async def test_batch_generation(self, generator):
        """测试批量生成"""
        requests = [
            GenerationRequest(
                generation_type=GenerationType.TEXT_TO_IMAGE,
                input_data=f"Image {i}",
                input_modality="text",
                output_modality="image",
            )
            for i in range(5)
        ]

        results = await generator.batch_generate(requests)

        assert len(results) == 5
        assert all(r.output_data is not None for r in results)

    @pytest.mark.asyncio
    async def test_generation_caching(self, generator):
        """测试生成缓存"""
        request = GenerationRequest(
            generation_type=GenerationType.TEXT_TO_IMAGE,
            input_data="Test image",
            input_modality="text",
            output_modality="image",
        )

        # 第一次生成
        start_time = time.time()
        result1 = await generator.generate(request, use_cache=True)
        time1 = time.time() - start_time

        # 第二次生成（应该从缓存获取）
        start_time = time.time()
        result2 = await generator.generate(request, use_cache=True)
        time2 = time.time() - start_time

        # 缓存应该更快
        assert time2 < time1


class TestMultimodalEvaluation:
    """多模态评估测试"""

    @pytest.fixture
    def evaluator(self):
        return MultimodalEvaluator()

    def test_fusion_evaluation(self, evaluator):
        """测试融合评估"""
        fused_output = [0.5] * 512
        ground_truth = [0.5] * 512
        alignment_scores = {"text-image": 0.9, "image-video": 0.85}
        component_weights = {"text": 0.4, "image": 0.35, "video": 0.25}

        result = evaluator.evaluate_fusion_task(
            fused_output=fused_output,
            ground_truth=ground_truth,
            alignment_scores=alignment_scores,
            component_weights=component_weights,
            latency_ms=100,
        )

        assert result.overall_score > 0.5
        assert len(result.metrics) > 0

    def test_retrieval_evaluation(self, evaluator):
        """测试检索评估"""
        results = [
            ("item_1", 0.95),
            ("item_2", 0.85),
            ("item_3", 0.75),
            ("item_4", 0.65),
            ("item_5", 0.55),
        ]
        relevant_ids = {"item_1", "item_3", "item_5"}

        result = evaluator.evaluate_retrieval_task(
            results=results,
            relevant_ids=relevant_ids,
            latency_ms=50,
            k=5,
        )

        assert result.overall_score > 0
        assert result.metrics["mrr"].value > 0

    def test_generation_evaluation(self, evaluator):
        """测试生成评估"""
        generated = "The cat is playing with a ball"
        reference = "A cat is playing with a ball"

        result = evaluator.evaluate_generation_task(
            generated_text=generated,
            reference_text=reference,
            latency_ms=200,
        )

        assert result.overall_score > 0
        assert result.metrics["bleu"].value > 0


class TestMultimodalAPI:
    """多模态API测试"""

    @pytest.fixture
    def api(self):
        return MultimodalAPI()

    @pytest.mark.asyncio
    async def test_fuse_modalities(self, api):
        """测试融合API"""
        features = {
            "text": [0.1] * 256,
            "image": [0.2] * 256,
        }

        result = await api.fuse_modalities(features, strategy="hybrid")

        assert "fused_features" in result
        assert "confidence" in result
        assert result["confidence"] > 0

    @pytest.mark.asyncio
    async def test_retrieve_multimodal(self, api):
        """测试检索API"""
        # 先添加一些项
        api.retriever.add_item(
            item_id="test_1",
            vector=[0.1] * 512,
            modality="text",
        )

        query_vector = [0.1] * 512

        result = await api.retrieve_multimodal(
            query_vector=query_vector,
            query_type="hybrid",
            top_k=5,
        )

        assert "results" in result
        assert "query_time_ms" in result

    @pytest.mark.asyncio
    async def test_generate_multimodal(self, api):
        """测试生成API"""
        result = await api.generate_multimodal(
            generation_type="text_to_image",
            input_data="A beautiful landscape",
            input_modality="text",
            output_modality="image",
        )

        assert "output_data" in result
        assert "quality_score" in result

    @pytest.mark.asyncio
    async def test_batch_operations(self, api):
        """测试批量操作"""
        batch_features = [
            {"text": [0.1] * 256, "image": [0.2] * 256},
            {"text": [0.15] * 256, "image": [0.25] * 256},
        ]

        results = await api.batch_fuse(batch_features)

        assert len(results) == 2
        assert all("fused_features" in r for r in results)


class TestPerformance:
    """性能测试"""

    @pytest.mark.asyncio
    async def test_fusion_latency(self):
        """测试融合延迟"""
        fusion_engine = MultimodalFusion()
        features = [
            ModalityFeature(
                modality=Modality.TEXT,
                features=[0.1] * 256,
            ),
            ModalityFeature(
                modality=Modality.IMAGE,
                features=[0.2] * 256,
            ),
        ]

        start_time = time.time()
        await fusion_engine.fuse(features)
        latency = (time.time() - start_time) * 1000

        # 融合延迟应该 < 2s
        assert latency < 2000

    @pytest.mark.asyncio
    async def test_retrieval_latency(self):
        """测试检索延迟"""
        retriever = MultimodalRetriever()

        # 添加项
        for i in range(100):
            retriever.add_item(
                item_id=f"item_{i}",
                vector=[0.1 * (i % 10)] * 512,
                modality="text",
            )

        query_vector = [0.15] * 512

        start_time = time.time()
        await retriever.retrieve(
            query_vector=query_vector,
            query_type=RetrievalType.HYBRID,
            top_k=10,
        )
        latency = (time.time() - start_time) * 1000

        # 检索延迟应该 < 2s
        assert latency < 2000

    @pytest.mark.asyncio
    async def test_generation_latency(self):
        """测试生成延迟"""
        generator = MultimodalGenerator()

        request = GenerationRequest(
            generation_type=GenerationType.TEXT_TO_IMAGE,
            input_data="Test image",
            input_modality="text",
            output_modality="image",
        )

        start_time = time.time()
        await generator.generate(request)
        latency = (time.time() - start_time) * 1000

        # 生成延迟应该 < 2s
        assert latency < 2000

    @pytest.mark.asyncio
    async def test_accuracy_metrics(self):
        """测试准确率指标"""
        evaluator = MultimodalEvaluator()

        # 测试融合准确率
        fused = [0.5] * 512
        ground_truth = [0.5] * 512

        accuracy = evaluator.fusion_evaluator.evaluate_fusion_accuracy(
            fused,
            ground_truth,
        )

        # 完全匹配应该有高准确率
        assert accuracy > 0.9

        # 测试检索准确率
        results = [
            ("item_1", 0.95),
            ("item_2", 0.85),
        ]
        relevant_ids = {"item_1"}

        mrr = evaluator.retrieval_evaluator.compute_mrr(results, relevant_ids)

        # 第一个结果相关应该有高MRR
        assert mrr == 1.0


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
