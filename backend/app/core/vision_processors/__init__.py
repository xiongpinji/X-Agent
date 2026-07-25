"""
视觉处理器模块 - 提供各种视觉任务的处理器
"""

from .object_detector import ObjectDetector
from .ocr_processor import OCRProcessor
from .scene_analyzer import SceneAnalyzer
from .similarity_searcher import SimilaritySearcher
from .vqa_processor import VQAProcessor

__all__ = [
    "OCRProcessor",
    "ObjectDetector",
    "SceneAnalyzer",
    "SimilaritySearcher",
    "VQAProcessor",
]
