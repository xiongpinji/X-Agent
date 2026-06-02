"""
视觉处理器集成测试
"""

import pytest
import tempfile
from pathlib import Path
from PIL import Image
import numpy as np
from unittest.mock import Mock, patch, AsyncMock

from backend.app.core.vision_processors.ocr_processor import OCRProcessor
from backend.app.core.vision_processors.object_detector import ObjectDetector
from backend.app.core.vision_processors.scene_analyzer import SceneAnalyzer
from backend.app.core.vision_processors.vqa_processor import VQAProcessor
from backend.app.core.vision_processors.similarity_searcher import SimilaritySearcher


@pytest.fixture
def sample_image():
    """创建示例图像"""
    # Windows 上 NamedTemporaryFile 在 with 块内持有打开句柄，跨 yield 不退出
    # → teardown 的 unlink 触发 WinError 32（文件被占用）。先退出 with 关句柄，
    # 再用 PIL 按路径写入，teardown 即可安全删除。
    with tempfile.NamedTemporaryFile(suffix=".png", delete=False) as f:
        name = f.name
    img = Image.new("RGB", (200, 200), color="blue")
    img.save(name)
    yield name
    Path(name).unlink(missing_ok=True)


@pytest.fixture
def sample_images():
    """创建多个示例图像"""
    images = []
    for i in range(3):
        with tempfile.NamedTemporaryFile(suffix=".png", delete=False) as f:
            name = f.name
        color = ["red", "green", "blue"][i]
        img = Image.new("RGB", (100, 100), color=color)
        img.save(name)
        images.append(name)

    yield images

    for img_path in images:
        Path(img_path).unlink(missing_ok=True)


class TestOCRProcessor:
    """OCR处理器测试"""

    def test_ocr_initialization(self):
        """测试OCR初始化"""
        processor = OCRProcessor(engine="tesseract")
        assert processor.engine == "tesseract"

    @pytest.mark.asyncio
    async def test_ocr_extract_text_no_engine(self, sample_image):
        """测试无可用引擎的文本提取"""
        processor = OCRProcessor()
        processor._tesseract_available = False
        processor._paddleocr_available = False

        result = await processor.extract_text(sample_image)
        assert result["success"] is False

    @pytest.mark.asyncio
    async def test_ocr_extract_with_layout(self, sample_image):
        """测试保留布局的文本提取"""
        pytest.importorskip("pytesseract")  # patch() 需可导入 pytesseract，未装则跳过
        processor = OCRProcessor()

        with patch("pytesseract.image_to_pdf_or_hocr") as mock_hocr:
            mock_hocr.return_value = b"<html>test</html>"
            result = await processor.extract_text_with_layout(sample_image)

            if result["success"]:
                assert "hocr" in result["data"]

    @pytest.mark.asyncio
    async def test_ocr_extract_handwriting(self, sample_image):
        """测试手写文本提取"""
        pytest.importorskip("pytesseract")  # patch() 需可导入 pytesseract，未装则跳过
        processor = OCRProcessor()

        with patch("pytesseract.image_to_string") as mock_ocr:
            mock_ocr.return_value = "Handwritten text"
            result = await processor.extract_handwriting(sample_image)

            if result["success"]:
                assert "handwritten_text" in result["data"]


class TestObjectDetector:
    """对象检测器测试"""

    def test_detector_initialization(self):
        """测试检测器初始化"""
        detector = ObjectDetector(model="yolov8")
        assert detector.model == "yolov8"

    def test_detector_custom_model(self):
        """测试自定义检测模型"""
        detector = ObjectDetector(model="faster_rcnn")
        assert detector.model == "faster_rcnn"

    @pytest.mark.asyncio
    async def test_detector_no_model(self, sample_image):
        """测试无可用模型的检测"""
        detector = ObjectDetector()
        detector._yolo_available = False
        detector._rcnn_available = False

        result = await detector.detect_objects(sample_image)
        assert result["success"] is False

    @pytest.mark.asyncio
    async def test_detector_specific_objects(self, sample_image):
        """测试检测特定对象"""
        detector = ObjectDetector()

        with patch.object(detector, "detect_objects") as mock_detect:
            mock_detect.return_value = {
                "success": True,
                "data": {
                    "detections": [
                        {"label": "person", "confidence": 0.9, "bbox": [0, 0, 100, 100]},
                        {"label": "car", "confidence": 0.8, "bbox": [100, 100, 200, 200]},
                    ]
                }
            }

            result = await detector.detect_specific_objects(
                sample_image,
                target_labels=["person"]
            )

            if result["success"]:
                assert len(result["data"]["detections"]) <= 2

    @pytest.mark.asyncio
    async def test_detector_statistics(self, sample_image):
        """测试对象统计"""
        detector = ObjectDetector()

        with patch.object(detector, "detect_objects") as mock_detect:
            mock_detect.return_value = {
                "success": True,
                "data": {
                    "detections": [
                        {"label": "person", "confidence": 0.9, "bbox": [0, 0, 100, 100]},
                        {"label": "person", "confidence": 0.85, "bbox": [50, 50, 150, 150]},
                    ]
                }
            }

            result = await detector.get_object_statistics(sample_image)

            if result["success"]:
                assert "label_counts" in result["data"]
                assert "average_confidences" in result["data"]


class TestSceneAnalyzer:
    """场景分析器测试"""

    def test_analyzer_initialization(self):
        """测试分析器初始化"""
        analyzer = SceneAnalyzer()
        assert analyzer is not None

    @pytest.mark.asyncio
    async def test_analyzer_no_models(self, sample_image):
        """测试无可用模型的分析"""
        analyzer = SceneAnalyzer()
        analyzer._blip_available = False
        analyzer._clip_available = False

        result = await analyzer.analyze_scene(sample_image)
        assert result["success"] is False

    @pytest.mark.asyncio
    async def test_analyzer_extract_elements(self, sample_image):
        """测试提取场景元素"""
        analyzer = SceneAnalyzer()

        with patch.object(analyzer, "_analyze_with_clip") as mock_analyze:
            mock_analyze.return_value = {
                "success": True,
                "data": {
                    "detected_elements": {"people": 0.8, "trees": 0.6}
                }
            }

            result = await analyzer.extract_scene_elements(sample_image)

            if result["success"]:
                assert "detected_elements" in result["data"]

    @pytest.mark.asyncio
    async def test_analyzer_composition(self, sample_image):
        """测试分析构图"""
        analyzer = SceneAnalyzer()
        result = await analyzer.analyze_composition(sample_image)

        if result["success"]:
            assert "aspect_ratio" in result["data"]
            assert "dimensions" in result["data"]
            assert "brightness" in result["data"]
            assert "contrast" in result["data"]

    def test_scene_type_classification(self):
        """测试场景类型分类"""
        analyzer = SceneAnalyzer()

        assert analyzer._classify_scene_type("indoor room") == "indoor"
        assert analyzer._classify_scene_type("outdoor street") == "outdoor"
        assert analyzer._classify_scene_type("forest mountain") == "nature"
        assert analyzer._classify_scene_type("person portrait") == "portrait"

    def test_color_distribution(self):
        """测试颜色分布分析"""
        analyzer = SceneAnalyzer()

        img_array = np.zeros((100, 100, 3), dtype=np.uint8)
        img_array[:, :, 0] = 255  # 红色

        result = analyzer._analyze_color_distribution(img_array)

        assert "red" in result
        assert "green" in result
        assert "blue" in result
        assert result["dominant_color"] == "red"


class TestVQAProcessor:
    """视觉问答处理器测试"""

    def test_vqa_initialization(self):
        """测试VQA初始化"""
        processor = VQAProcessor()
        assert processor is not None

    @pytest.mark.asyncio
    async def test_vqa_no_models(self, sample_image):
        """测试无可用模型的问答"""
        processor = VQAProcessor()
        processor._blip_available = False
        processor._clip_available = False

        result = await processor.answer_question(sample_image, "What is this?")
        assert result["success"] is False

    @pytest.mark.asyncio
    async def test_vqa_batch_questions(self, sample_image):
        """测试批量问答"""
        processor = VQAProcessor()

        with patch.object(processor, "answer_question") as mock_answer:
            mock_answer.return_value = {
                "success": True,
                "data": {"answer": "test answer"}
            }

            questions = ["What is this?", "What color is it?"]
            result = await processor.batch_answer_questions(sample_image, questions)

            if result["success"]:
                assert result["data"]["total_questions"] == 2

    @pytest.mark.asyncio
    async def test_vqa_question_type_analysis(self):
        """测试问题类型分析"""
        processor = VQAProcessor()

        result = await processor.analyze_question_type("What is in the image?")
        assert result["data"]["question_type"] == "what"

        result = await processor.analyze_question_type("Where is the cat?")
        assert result["data"]["question_type"] == "where"

        result = await processor.analyze_question_type("How many people?")
        assert result["data"]["question_type"] == "count"

    def test_vqa_possible_answers(self):
        """测试可能答案生成"""
        processor = VQAProcessor()

        answers = processor._generate_possible_answers("What color is it?")
        assert "red" in answers
        assert "blue" in answers

        answers = processor._generate_possible_answers("How many?")
        assert "0" in answers or "many" in answers

        answers = processor._generate_possible_answers("Is there a cat?")
        assert "yes" in answers or "no" in answers


class TestSimilaritySearcher:
    """相似度搜索器测试"""

    def test_searcher_initialization(self):
        """测试搜索器初始化"""
        searcher = SimilaritySearcher()
        assert len(searcher._embeddings_cache) == 0

    @pytest.mark.asyncio
    async def test_searcher_no_clip(self, sample_image):
        """测试无CLIP的搜索"""
        searcher = SimilaritySearcher()
        searcher._clip_available = False

        result = await searcher.compute_embedding(sample_image)
        assert result["success"] is False

    @pytest.mark.asyncio
    async def test_searcher_cache_clear(self):
        """测试缓存清除"""
        searcher = SimilaritySearcher()
        searcher._embeddings_cache["test"] = [1, 2, 3]

        assert len(searcher._embeddings_cache) == 1
        searcher.clear_cache()
        assert len(searcher._embeddings_cache) == 0

    @pytest.mark.asyncio
    async def test_searcher_find_similar(self, sample_images):
        """测试查找相似图像"""
        searcher = SimilaritySearcher()

        with patch.object(searcher, "compute_embedding") as mock_embed:
            mock_embed.return_value = {
                "success": True,
                "data": {"embedding": [0.1] * 512}
            }

            result = await searcher.find_similar_images(
                sample_images[0],
                sample_images[1:],
                top_k=1
            )

            if result["success"]:
                assert "similar_images" in result["data"]

    @pytest.mark.asyncio
    async def test_searcher_similarity_matrix(self, sample_images):
        """测试相似度矩阵"""
        searcher = SimilaritySearcher()

        with patch.object(searcher, "compute_embedding") as mock_embed:
            mock_embed.return_value = {
                "success": True,
                "data": {"embedding": [0.1] * 512}
            }

            result = await searcher.compute_similarity_matrix(sample_images)

            if result["success"]:
                assert "similarity_matrix" in result["data"]
                assert result["data"]["matrix_size"] == len(sample_images)

    @pytest.mark.asyncio
    async def test_searcher_cluster_images(self, sample_images):
        """测试图像聚类"""
        searcher = SimilaritySearcher()

        with patch.object(searcher, "compute_similarity_matrix") as mock_matrix:
            mock_matrix.return_value = {
                "success": True,
                "data": {
                    "similarity_matrix": [
                        [1.0, 0.8, 0.2],
                        [0.8, 1.0, 0.3],
                        [0.2, 0.3, 1.0],
                    ]
                }
            }

            result = await searcher.cluster_similar_images(sample_images, threshold=0.7)

            if result["success"]:
                assert "clusters" in result["data"]

    @pytest.mark.asyncio
    async def test_searcher_text_search(self, sample_images):
        """测试文本搜索"""
        searcher = SimilaritySearcher()
        searcher._clip_available = False

        result = await searcher.search_by_text("red object", sample_images)
        assert result["success"] is False


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
