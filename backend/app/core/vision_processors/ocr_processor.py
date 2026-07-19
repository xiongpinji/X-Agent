"""
OCR处理器 - 文字识别和提取
"""

import logging
from typing import Any, Dict, List, Optional
from dataclasses import dataclass
import time

logger = logging.getLogger(__name__)


@dataclass
class TextRegion:
    """文本区域"""
    text: str
    confidence: float
    bbox: tuple  # (x1, y1, x2, y2)
    language: Optional[str] = None


class OCRProcessor:
    """OCR处理器 - 支持多种OCR引擎"""

    def __init__(self, engine: str = "tesseract"):
        self.engine = engine
        self._tesseract_available = False
        self._paddleocr_available = False
        self._initialize_engines()

    def _initialize_engines(self) -> None:
        """初始化OCR引擎"""
        try:
            import pytesseract
            self._tesseract_available = True
        except ImportError:
            logger.warning("pytesseract not installed, Tesseract OCR disabled")

        try:
            from paddleocr import PaddleOCR
            self._paddleocr_available = True
        except ImportError:
            logger.warning("paddleocr not installed, PaddleOCR disabled")

    async def extract_text(
        self,
        image_path: str,
        language: str = "eng",
        **kwargs
    ) -> Dict[str, Any]:
        """提取文本"""
        start_time = time.time()

        try:
            if self.engine == "tesseract":
                return await self._extract_with_tesseract(image_path, language, **kwargs)
            elif self.engine == "paddleocr":
                return await self._extract_with_paddleocr(image_path, **kwargs)
            else:
                return {
                    "success": False,
                    "error": f"Unknown OCR engine: {self.engine}",
                }

        except Exception as e:
            logger.error(f"OCR extraction error: {e}")
            return {
                "success": False,
                "error": str(e),
                "latency_ms": (time.time() - start_time) * 1000,
            }

    async def _extract_with_tesseract(
        self,
        image_path: str,
        language: str,
        **kwargs
    ) -> Dict[str, Any]:
        """使用Tesseract提取文本"""
        if not self._tesseract_available:
            return {"success": False, "error": "Tesseract not installed"}

        try:
            import pytesseract
            from PIL import Image

            image = Image.open(image_path)
            text = pytesseract.image_to_string(image, lang=language)
            data = pytesseract.image_to_data(image, lang=language, output_type="dict")

            regions = []
            for i in range(len(data["text"])):
                if data["text"][i].strip():
                    regions.append(
                        TextRegion(
                            text=data["text"][i],
                            confidence=int(data["conf"][i]) / 100.0,
                            bbox=(
                                data["left"][i],
                                data["top"][i],
                                data["left"][i] + data["width"][i],
                                data["top"][i] + data["height"][i],
                            ),
                            language=language,
                        )
                    )

            return {
                "success": True,
                "data": {
                    "full_text": text,
                    "regions": [
                        {
                            "text": r.text,
                            "confidence": r.confidence,
                            "bbox": r.bbox,
                            "language": r.language,
                        }
                        for r in regions
                    ],
                    "region_count": len(regions),
                },
            }

        except Exception as e:
            logger.error(f"Tesseract OCR error: {e}")
            return {"success": False, "error": str(e)}

    async def _extract_with_paddleocr(
        self,
        image_path: str,
        **kwargs
    ) -> Dict[str, Any]:
        """使用PaddleOCR提取文本"""
        if not self._paddleocr_available:
            return {"success": False, "error": "PaddleOCR not installed"}

        try:
            from paddleocr import PaddleOCR

            ocr = PaddleOCR(use_angle_cls=True, lang="ch")
            result = ocr.ocr(image_path, cls=True)

            full_text = ""
            regions = []

            for line in result:
                for word_info in line:
                    bbox, (text, confidence) = word_info
                    full_text += text + " "
                    regions.append(
                        {
                            "text": text,
                            "confidence": float(confidence),
                            "bbox": [
                                [float(p[0]), float(p[1])] for p in bbox
                            ],
                        }
                    )

            return {
                "success": True,
                "data": {
                    "full_text": full_text.strip(),
                    "regions": regions,
                    "region_count": len(regions),
                },
            }

        except Exception as e:
            logger.error(f"PaddleOCR error: {e}")
            return {"success": False, "error": str(e)}

    async def extract_text_with_layout(
        self,
        image_path: str,
        **kwargs
    ) -> Dict[str, Any]:
        """提取保留布局的文本"""
        try:
            import pytesseract
            from PIL import Image

            image = Image.open(image_path)
            text = pytesseract.image_to_pdf_or_hocr(
                image, extension="hocr", lang="eng"
            )

            return {
                "success": True,
                "data": {
                    "hocr": text.decode("utf-8") if isinstance(text, bytes) else text,
                },
            }

        except Exception as e:
            logger.error(f"Layout extraction error: {e}")
            return {"success": False, "error": str(e)}

    async def extract_handwriting(
        self,
        image_path: str,
        **kwargs
    ) -> Dict[str, Any]:
        """提取手写文本"""
        try:
            from PIL import Image
            import pytesseract

            image = Image.open(image_path)
            # 使用特殊配置处理手写文本
            config = "--psm 6 --oem 1"
            text = pytesseract.image_to_string(image, config=config)

            return {
                "success": True,
                "data": {
                    "handwritten_text": text,
                },
            }

        except Exception as e:
            logger.error(f"Handwriting extraction error: {e}")
            return {"success": False, "error": str(e)}
