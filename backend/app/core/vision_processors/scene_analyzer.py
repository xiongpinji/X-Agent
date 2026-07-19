"""
场景分析处理器 - 理解和描述图像场景
"""

import logging
from typing import Any, Dict, List, Optional
import time

logger = logging.getLogger(__name__)


class SceneAnalyzer:
    """场景分析器 - 支持多种场景理解方法"""

    def __init__(self):
        self._clip_available = False
        self._blip_available = False
        self._initialize_models()

    def _initialize_models(self) -> None:
        """初始化模型"""
        try:
            import clip
            self._clip_available = True
        except ImportError:
            logger.warning("clip not installed, CLIP scene analysis disabled")

        try:
            from transformers import BlipProcessor, BlipForConditionalGeneration
            self._blip_available = True
        except ImportError:
            logger.warning("transformers not installed, BLIP scene analysis disabled")

    async def analyze_scene(
        self,
        image_path: str,
        **kwargs
    ) -> Dict[str, Any]:
        """分析场景"""
        start_time = time.time()

        try:
            # 尝试使用BLIP进行场景描述
            if self._blip_available:
                return await self._analyze_with_blip(image_path, **kwargs)
            elif self._clip_available:
                return await self._analyze_with_clip(image_path, **kwargs)
            else:
                return {
                    "success": False,
                    "error": "No scene analysis models available",
                }

        except Exception as e:
            logger.error(f"Scene analysis error: {e}")
            return {
                "success": False,
                "error": str(e),
                "latency_ms": (time.time() - start_time) * 1000,
            }

    async def _analyze_with_blip(
        self,
        image_path: str,
        **kwargs
    ) -> Dict[str, Any]:
        """使用BLIP分析场景"""
        if not self._blip_available:
            return {"success": False, "error": "BLIP not installed"}

        try:
            from transformers import BlipProcessor, BlipForConditionalGeneration
            from PIL import Image
            import torch

            processor = BlipProcessor.from_pretrained("Salesforce/blip-image-captioning-base")
            model = BlipForConditionalGeneration.from_pretrained(
                "Salesforce/blip-image-captioning-base"
            )

            image = Image.open(image_path).convert("RGB")
            inputs = processor(image, return_tensors="pt")

            with torch.no_grad():
                out = model.generate(**inputs, max_length=100)

            caption = processor.decode(out[0], skip_special_tokens=True)

            # 生成详细描述
            detailed_inputs = processor(
                image,
                text="a detailed description of this scene:",
                return_tensors="pt"
            )

            with torch.no_grad():
                detailed_out = model.generate(**detailed_inputs, max_length=150)

            detailed_caption = processor.decode(detailed_out[0], skip_special_tokens=True)

            return {
                "success": True,
                "data": {
                    "caption": caption,
                    "detailed_description": detailed_caption,
                    "scene_type": self._classify_scene_type(caption),
                },
            }

        except Exception as e:
            logger.error(f"BLIP scene analysis error: {e}")
            return {"success": False, "error": str(e)}

    async def _analyze_with_clip(
        self,
        image_path: str,
        **kwargs
    ) -> Dict[str, Any]:
        """使用CLIP分析场景"""
        if not self._clip_available:
            return {"success": False, "error": "CLIP not installed"}

        try:
            import clip
            import torch
            from PIL import Image

            device = "cuda" if torch.cuda.is_available() else "cpu"
            model, preprocess = clip.load("ViT-B/32", device=device)

            image = Image.open(image_path).convert("RGB")
            image_input = preprocess(image).unsqueeze(0).to(device)

            # 场景分类标签
            scene_labels = [
                "indoor scene",
                "outdoor scene",
                "nature scene",
                "urban scene",
                "portrait",
                "landscape",
                "still life",
                "abstract",
            ]

            text_inputs = clip.tokenize(scene_labels).to(device)

            with torch.no_grad():
                image_features = model.encode_image(image_input)
                text_features = model.encode_text(text_inputs)
                logits_per_image = image_features @ text_features.T
                probs = logits_per_image.softmax(dim=-1).cpu().numpy()

            scene_scores = {
                label: float(prob)
                for label, prob in zip(scene_labels, probs[0])
            }

            top_scene = max(scene_scores, key=scene_scores.get)

            return {
                "success": True,
                "data": {
                    "scene_classification": scene_scores,
                    "primary_scene": top_scene,
                    "confidence": scene_scores[top_scene],
                },
            }

        except Exception as e:
            logger.error(f"CLIP scene analysis error: {e}")
            return {"success": False, "error": str(e)}

    async def extract_scene_elements(
        self,
        image_path: str,
        **kwargs
    ) -> Dict[str, Any]:
        """提取场景元素"""
        try:
            from PIL import Image
            import clip
            import torch

            device = "cuda" if torch.cuda.is_available() else "cpu"
            model, preprocess = clip.load("ViT-B/32", device=device)

            image = Image.open(image_path).convert("RGB")
            image_input = preprocess(image).unsqueeze(0).to(device)

            # 常见场景元素
            elements = [
                "people",
                "animals",
                "vehicles",
                "buildings",
                "trees",
                "water",
                "sky",
                "food",
                "furniture",
                "text",
            ]

            text_inputs = clip.tokenize(elements).to(device)

            with torch.no_grad():
                image_features = model.encode_image(image_input)
                text_features = model.encode_text(text_inputs)
                logits_per_image = image_features @ text_features.T
                probs = logits_per_image.softmax(dim=-1).cpu().numpy()

            element_scores = {
                element: float(prob)
                for element, prob in zip(elements, probs[0])
            }

            # 过滤高置信度元素
            detected_elements = {
                k: v for k, v in element_scores.items() if v > 0.3
            }

            return {
                "success": True,
                "data": {
                    "detected_elements": detected_elements,
                    "element_count": len(detected_elements),
                },
            }

        except Exception as e:
            logger.error(f"Scene element extraction error: {e}")
            return {"success": False, "error": str(e)}

    async def analyze_composition(
        self,
        image_path: str,
        **kwargs
    ) -> Dict[str, Any]:
        """分析图像构图"""
        try:
            from PIL import Image
            import numpy as np

            image = Image.open(image_path).convert("RGB")
            img_array = np.array(image)

            height, width = img_array.shape[:2]

            # 计算构图特征
            composition = {
                "aspect_ratio": width / height,
                "dimensions": {"width": width, "height": height},
                "rule_of_thirds": self._check_rule_of_thirds(img_array),
                "color_distribution": self._analyze_color_distribution(img_array),
                "brightness": float(np.mean(img_array)),
                "contrast": float(np.std(img_array)),
            }

            return {
                "success": True,
                "data": composition,
            }

        except Exception as e:
            logger.error(f"Composition analysis error: {e}")
            return {"success": False, "error": str(e)}

    @staticmethod
    def _classify_scene_type(caption: str) -> str:
        """根据描述分类场景类型"""
        caption_lower = caption.lower()

        if any(word in caption_lower for word in ["indoor", "room", "inside", "house"]):
            return "indoor"
        elif any(word in caption_lower for word in ["outdoor", "outside", "street", "park"]):
            return "outdoor"
        elif any(word in caption_lower for word in ["nature", "forest", "mountain", "water"]):
            return "nature"
        elif any(word in caption_lower for word in ["person", "people", "man", "woman"]):
            return "portrait"
        else:
            return "general"

    @staticmethod
    def _check_rule_of_thirds(img_array) -> Dict[str, Any]:
        """检查三分法则"""
        height, width = img_array.shape[:2]
        h_third = height // 3
        w_third = width // 3

        return {
            "horizontal_lines": [h_third, 2 * h_third],
            "vertical_lines": [w_third, 2 * w_third],
        }

    @staticmethod
    def _analyze_color_distribution(img_array) -> Dict[str, Any]:
        """分析颜色分布"""
        import numpy as np

        r_mean = float(np.mean(img_array[:, :, 0]))
        g_mean = float(np.mean(img_array[:, :, 1]))
        b_mean = float(np.mean(img_array[:, :, 2]))

        return {
            "red": r_mean,
            "green": g_mean,
            "blue": b_mean,
            "dominant_color": max(
                [("red", r_mean), ("green", g_mean), ("blue", b_mean)],
                key=lambda x: x[1]
            )[0],
        }
