"""
视觉模型API端点
"""

import logging
import tempfile
from pathlib import Path
from typing import Any

from fastapi import APIRouter, File, UploadFile
from pydantic import BaseModel

from backend.app.core.vision_model import (
    VisionModelManager,
    VisionModelType,
    VisionTask,
)
from backend.app.core.vision_processors.object_detector import ObjectDetector
from backend.app.core.vision_processors.ocr_processor import OCRProcessor
from backend.app.core.vision_processors.scene_analyzer import SceneAnalyzer
from backend.app.core.vision_processors.similarity_searcher import SimilaritySearcher
from backend.app.core.vision_processors.vqa_processor import VQAProcessor

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1/vision", tags=["vision"])

# 全局管理器实例
_vision_manager: VisionModelManager | None = None
_ocr_processor: OCRProcessor | None = None
_object_detector: ObjectDetector | None = None
_scene_analyzer: SceneAnalyzer | None = None
_vqa_processor: VQAProcessor | None = None
_similarity_searcher: SimilaritySearcher | None = None


def get_vision_manager() -> VisionModelManager:
    """获取视觉模型管理器"""
    global _vision_manager
    if _vision_manager is None:
        _vision_manager = VisionModelManager()
    return _vision_manager


def get_ocr_processor() -> OCRProcessor:
    """获取OCR处理器"""
    global _ocr_processor
    if _ocr_processor is None:
        _ocr_processor = OCRProcessor()
    return _ocr_processor


def get_object_detector() -> ObjectDetector:
    """获取对象检测器"""
    global _object_detector
    if _object_detector is None:
        _object_detector = ObjectDetector()
    return _object_detector


def get_scene_analyzer() -> SceneAnalyzer:
    """获取场景分析器"""
    global _scene_analyzer
    if _scene_analyzer is None:
        _scene_analyzer = SceneAnalyzer()
    return _scene_analyzer


def get_vqa_processor() -> VQAProcessor:
    """获取VQA处理器"""
    global _vqa_processor
    if _vqa_processor is None:
        _vqa_processor = VQAProcessor()
    return _vqa_processor


def get_similarity_searcher() -> SimilaritySearcher:
    """获取相似度搜索器"""
    global _similarity_searcher
    if _similarity_searcher is None:
        _similarity_searcher = SimilaritySearcher()
    return _similarity_searcher


# 请求/响应模型
class ImageClassificationRequest(BaseModel):
    """图像分类请求"""
    model_type: VisionModelType = VisionModelType.CLAUDE_VISION
    max_tokens: int = 1024


class ObjectDetectionRequest(BaseModel):
    """对象检测请求"""
    confidence_threshold: float = 0.5


class OCRRequest(BaseModel):
    """OCR请求"""
    language: str = "eng"
    engine: str = "tesseract"


class SceneAnalysisRequest(BaseModel):
    """场景分析请求"""
    include_composition: bool = True
    include_elements: bool = True


class VQARequest(BaseModel):
    """视觉问答请求"""
    question: str
    model_type: VisionModelType = VisionModelType.CLAUDE_VISION


class SimilaritySearchRequest(BaseModel):
    """相似度搜索请求"""
    top_k: int = 5
    threshold: float = 0.5


class VisionResponse(BaseModel):
    """视觉处理响应"""
    success: bool
    data: dict[str, Any] | None = None
    error: str | None = None
    latency_ms: float = 0.0


# API端点

@router.post("/classify")
async def classify_image(
    file: UploadFile = File(...),
    request: ImageClassificationRequest = ImageClassificationRequest(),
) -> VisionResponse:
    """分类图像"""
    try:
        # 保存上传的文件
        with tempfile.NamedTemporaryFile(delete=False, suffix=".png") as tmp:
            content = await file.read()
            tmp.write(content)
            tmp_path = tmp.name

        try:
            manager = get_vision_manager()
            result = await manager.process(
                tmp_path,
                VisionTask.IMAGE_CLASSIFICATION,
                request.model_type,
                max_tokens=request.max_tokens,
            )

            return VisionResponse(
                success=result.success,
                data=result.data,
                error=result.error,
                latency_ms=result.latency_ms,
            )

        finally:
            Path(tmp_path).unlink()

    except Exception as e:
        logger.error(f"Image classification error: {e}")
        return VisionResponse(success=False, error=str(e))


@router.post("/detect-objects")
async def detect_objects(
    file: UploadFile = File(...),
    request: ObjectDetectionRequest = ObjectDetectionRequest(),
) -> VisionResponse:
    """检测对象"""
    try:
        with tempfile.NamedTemporaryFile(delete=False, suffix=".png") as tmp:
            content = await file.read()
            tmp.write(content)
            tmp_path = tmp.name

        try:
            detector = get_object_detector()
            result = await detector.detect_objects(
                tmp_path,
                confidence_threshold=request.confidence_threshold,
            )

            return VisionResponse(
                success=result.get("success", False),
                data=result.get("data"),
                error=result.get("error"),
            )

        finally:
            Path(tmp_path).unlink()

    except Exception as e:
        logger.error(f"Object detection error: {e}")
        return VisionResponse(success=False, error=str(e))


@router.post("/ocr")
async def extract_text(
    file: UploadFile = File(...),
    request: OCRRequest = OCRRequest(),
) -> VisionResponse:
    """提取文本"""
    try:
        with tempfile.NamedTemporaryFile(delete=False, suffix=".png") as tmp:
            content = await file.read()
            tmp.write(content)
            tmp_path = tmp.name

        try:
            processor = get_ocr_processor()
            result = await processor.extract_text(
                tmp_path,
                language=request.language,
            )

            return VisionResponse(
                success=result.get("success", False),
                data=result.get("data"),
                error=result.get("error"),
            )

        finally:
            Path(tmp_path).unlink()

    except Exception as e:
        logger.error(f"OCR error: {e}")
        return VisionResponse(success=False, error=str(e))


@router.post("/analyze-scene")
async def analyze_scene(
    file: UploadFile = File(...),
    request: SceneAnalysisRequest = SceneAnalysisRequest(),
) -> VisionResponse:
    """分析场景"""
    try:
        with tempfile.NamedTemporaryFile(delete=False, suffix=".png") as tmp:
            content = await file.read()
            tmp.write(content)
            tmp_path = tmp.name

        try:
            analyzer = get_scene_analyzer()
            result = await analyzer.analyze_scene(tmp_path)

            # 添加额外分析
            if request.include_composition:
                composition = await analyzer.analyze_composition(tmp_path)
                if composition.get("success"):
                    result["data"]["composition"] = composition["data"]

            if request.include_elements:
                elements = await analyzer.extract_scene_elements(tmp_path)
                if elements.get("success"):
                    result["data"]["elements"] = elements["data"]

            return VisionResponse(
                success=result.get("success", False),
                data=result.get("data"),
                error=result.get("error"),
            )

        finally:
            Path(tmp_path).unlink()

    except Exception as e:
        logger.error(f"Scene analysis error: {e}")
        return VisionResponse(success=False, error=str(e))


@router.post("/vqa")
async def visual_question_answering(
    file: UploadFile = File(...),
    request: VQARequest = VQARequest(),
) -> VisionResponse:
    """视觉问答"""
    try:
        with tempfile.NamedTemporaryFile(delete=False, suffix=".png") as tmp:
            content = await file.read()
            tmp.write(content)
            tmp_path = tmp.name

        try:
            processor = get_vqa_processor()
            result = await processor.answer_question(
                tmp_path,
                request.question,
            )

            return VisionResponse(
                success=result.get("success", False),
                data=result.get("data"),
                error=result.get("error"),
            )

        finally:
            Path(tmp_path).unlink()

    except Exception as e:
        logger.error(f"VQA error: {e}")
        return VisionResponse(success=False, error=str(e))


@router.post("/similarity/compute")
async def compute_embedding(
    file: UploadFile = File(...),
) -> VisionResponse:
    """计算图像嵌入"""
    try:
        with tempfile.NamedTemporaryFile(delete=False, suffix=".png") as tmp:
            content = await file.read()
            tmp.write(content)
            tmp_path = tmp.name

        try:
            searcher = get_similarity_searcher()
            result = await searcher.compute_embedding(tmp_path)

            return VisionResponse(
                success=result.get("success", False),
                data=result.get("data"),
                error=result.get("error"),
            )

        finally:
            Path(tmp_path).unlink()

    except Exception as e:
        logger.error(f"Embedding computation error: {e}")
        return VisionResponse(success=False, error=str(e))


@router.get("/models")
async def list_available_models() -> dict[str, Any]:
    """列出可用模型"""
    return {
        "models": [
            {
                "type": model_type.value,
                "name": model_type.name,
                "description": f"{model_type.value} vision model",
            }
            for model_type in VisionModelType
        ],
        "tasks": [
            {
                "type": task.value,
                "name": task.name,
                "description": f"{task.value} task",
            }
            for task in VisionTask
        ],
    }


@router.get("/health")
async def health_check() -> dict[str, str]:
    """健康检查"""
    return {"status": "healthy", "service": "vision-models"}
