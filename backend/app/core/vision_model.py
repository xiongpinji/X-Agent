"""
视觉模型集成 - 支持GPT-4V、Claude Vision和本地视觉模型
"""

import base64
import logging
from abc import ABC, abstractmethod
from enum import Enum
from pathlib import Path
from typing import Any, Dict, List, Optional, Protocol, Union
from dataclasses import dataclass
import asyncio
import time

logger = logging.getLogger(__name__)


class VisionModelType(str, Enum):
    """视觉模型类型"""
    GPT4V = "gpt4v"
    CLAUDE_VISION = "claude_vision"
    CLIP = "clip"
    BLIP = "blip"


class VisionTask(str, Enum):
    """视觉任务类型"""
    IMAGE_CLASSIFICATION = "image_classification"
    OBJECT_DETECTION = "object_detection"
    OCR = "ocr"
    SCENE_UNDERSTANDING = "scene_understanding"
    VQA = "visual_question_answering"
    IMAGE_SIMILARITY = "image_similarity"


@dataclass
class VisionResult:
    """视觉处理结果"""
    task: VisionTask
    model: VisionModelType
    success: bool
    data: Optional[Dict[str, Any]] = None
    error: Optional[str] = None
    latency_ms: float = 0.0
    confidence: Optional[float] = None


class VisionModel(ABC):
    """视觉模型基类"""

    @abstractmethod
    async def process(
        self,
        image_path: str,
        task: VisionTask,
        **kwargs
    ) -> VisionResult:
        """处理图像"""
        pass

    @abstractmethod
    async def batch_process(
        self,
        image_paths: List[str],
        task: VisionTask,
        **kwargs
    ) -> List[VisionResult]:
        """批量处理图像"""
        pass

    @staticmethod
    def _load_image_as_base64(image_path: str) -> str:
        """加载图像为base64"""
        path = Path(image_path)
        if not path.exists():
            raise FileNotFoundError(f"Image not found: {image_path}")

        with open(path, "rb") as f:
            return base64.standard_b64encode(f.read()).decode("utf-8")

    @staticmethod
    def _get_image_media_type(image_path: str) -> str:
        """获取图像媒体类型"""
        suffix = Path(image_path).suffix.lower()
        media_types = {
            ".jpg": "image/jpeg",
            ".jpeg": "image/jpeg",
            ".png": "image/png",
            ".gif": "image/gif",
            ".webp": "image/webp",
        }
        return media_types.get(suffix, "image/jpeg")


class GPT4VisionModel(VisionModel):
    """GPT-4V视觉模型"""

    def __init__(self, api_key: str, model: str = "gpt-4-vision-preview"):
        self.api_key = api_key
        self.model = model
        self._client = None

    async def _get_client(self):
        """获取OpenAI客户端"""
        if self._client is None:
            try:
                from openai import AsyncOpenAI
            except ImportError as exc:
                raise RuntimeError("openai package is not installed") from exc
            self._client = AsyncOpenAI(api_key=self.api_key)
        return self._client

    async def process(
        self,
        image_path: str,
        task: VisionTask,
        **kwargs
    ) -> VisionResult:
        """处理图像"""
        start_time = time.time()
        try:
            client = await self._get_client()
            image_base64 = self._load_image_as_base64(image_path)
            media_type = self._get_image_media_type(image_path)

            # 构建提示词
            prompt = self._build_prompt(task, **kwargs)

            # 调用GPT-4V
            response = await client.chat.completions.create(
                model=self.model,
                messages=[
                    {
                        "role": "user",
                        "content": [
                            {"type": "text", "text": prompt},
                            {
                                "type": "image_url",
                                "image_url": {
                                    "url": f"data:{media_type};base64,{image_base64}"
                                },
                            },
                        ],
                    }
                ],
                max_tokens=kwargs.get("max_tokens", 1024),
            )

            result_text = response.choices[0].message.content
            latency_ms = (time.time() - start_time) * 1000

            return VisionResult(
                task=task,
                model=VisionModelType.GPT4V,
                success=True,
                data={"result": result_text},
                latency_ms=latency_ms,
                confidence=0.95,
            )

        except Exception as e:
            latency_ms = (time.time() - start_time) * 1000
            logger.error(f"GPT-4V processing error: {e}")
            return VisionResult(
                task=task,
                model=VisionModelType.GPT4V,
                success=False,
                error=str(e),
                latency_ms=latency_ms,
            )

    async def batch_process(
        self,
        image_paths: List[str],
        task: VisionTask,
        **kwargs
    ) -> List[VisionResult]:
        """批量处理图像"""
        tasks = [self.process(path, task, **kwargs) for path in image_paths]
        return await asyncio.gather(*tasks)

    def _build_prompt(self, task: VisionTask, **kwargs) -> str:
        """构建任务提示词"""
        prompts = {
            VisionTask.IMAGE_CLASSIFICATION: "Classify this image and provide the main categories with confidence scores.",
            VisionTask.OBJECT_DETECTION: "Detect all objects in this image and provide their locations and labels.",
            VisionTask.OCR: "Extract all text from this image and preserve the layout.",
            VisionTask.SCENE_UNDERSTANDING: "Describe the scene in this image in detail, including objects, activities, and context.",
            VisionTask.VQA: kwargs.get("question", "What is in this image?"),
            VisionTask.IMAGE_SIMILARITY: "Analyze the visual features of this image for similarity comparison.",
        }
        return prompts.get(task, "Analyze this image.")


class ClaudeVisionModel(VisionModel):
    """Claude Vision视觉模型"""

    def __init__(self, api_key: str, model: str = "claude-3-5-sonnet-20241022"):
        self.api_key = api_key
        self.model = model
        self._client = None

    async def _get_client(self):
        """获取Anthropic客户端"""
        if self._client is None:
            try:
                from anthropic import AsyncAnthropic
            except ImportError as exc:
                raise RuntimeError("anthropic package is not installed") from exc
            self._client = AsyncAnthropic(api_key=self.api_key)
        return self._client

    async def process(
        self,
        image_path: str,
        task: VisionTask,
        **kwargs
    ) -> VisionResult:
        """处理图像"""
        start_time = time.time()
        try:
            client = await self._get_client()
            image_base64 = self._load_image_as_base64(image_path)
            media_type = self._get_image_media_type(image_path)

            # 构建提示词
            prompt = self._build_prompt(task, **kwargs)

            # 调用Claude Vision
            response = await client.messages.create(
                model=self.model,
                max_tokens=kwargs.get("max_tokens", 1024),
                messages=[
                    {
                        "role": "user",
                        "content": [
                            {
                                "type": "image",
                                "source": {
                                    "type": "base64",
                                    "media_type": media_type,
                                    "data": image_base64,
                                },
                            },
                            {"type": "text", "text": prompt},
                        ],
                    }
                ],
            )

            result_text = response.content[0].text
            latency_ms = (time.time() - start_time) * 1000

            return VisionResult(
                task=task,
                model=VisionModelType.CLAUDE_VISION,
                success=True,
                data={"result": result_text},
                latency_ms=latency_ms,
                confidence=0.95,
            )

        except Exception as e:
            latency_ms = (time.time() - start_time) * 1000
            logger.error(f"Claude Vision processing error: {e}")
            return VisionResult(
                task=task,
                model=VisionModelType.CLAUDE_VISION,
                success=False,
                error=str(e),
                latency_ms=latency_ms,
            )

    async def batch_process(
        self,
        image_paths: List[str],
        task: VisionTask,
        **kwargs
    ) -> List[VisionResult]:
        """批量处理图像"""
        tasks = [self.process(path, task, **kwargs) for path in image_paths]
        return await asyncio.gather(*tasks)

    def _build_prompt(self, task: VisionTask, **kwargs) -> str:
        """构建任务提示词"""
        prompts = {
            VisionTask.IMAGE_CLASSIFICATION: "Classify this image and provide the main categories with confidence scores.",
            VisionTask.OBJECT_DETECTION: "Detect all objects in this image and provide their locations and labels.",
            VisionTask.OCR: "Extract all text from this image and preserve the layout.",
            VisionTask.SCENE_UNDERSTANDING: "Describe the scene in this image in detail, including objects, activities, and context.",
            VisionTask.VQA: kwargs.get("question", "What is in this image?"),
            VisionTask.IMAGE_SIMILARITY: "Analyze the visual features of this image for similarity comparison.",
        }
        return prompts.get(task, "Analyze this image.")


class CLIPVisionModel(VisionModel):
    """CLIP本地视觉模型"""

    def __init__(self, model_name: str = "ViT-B/32"):
        self.model_name = model_name
        self._model = None
        self._processor = None
        self._device = None

    async def _initialize(self):
        """初始化模型"""
        if self._model is None:
            try:
                import clip
                import torch
            except ImportError as exc:
                raise RuntimeError("clip and torch packages are not installed") from exc

            self._device = "cuda" if torch.cuda.is_available() else "cpu"
            self._model, self._processor = clip.load(self.model_name, device=self._device)

    async def process(
        self,
        image_path: str,
        task: VisionTask,
        **kwargs
    ) -> VisionResult:
        """处理图像"""
        start_time = time.time()
        try:
            await self._initialize()

            from PIL import Image
            import clip
            import torch

            image = Image.open(image_path).convert("RGB")
            image_input = self._processor(image).unsqueeze(0).to(self._device)

            if task == VisionTask.IMAGE_CLASSIFICATION:
                labels = kwargs.get("labels", ["object", "scene", "text"])
                text_inputs = clip.tokenize(labels).to(self._device)

                with torch.no_grad():
                    image_features = self._model.encode_image(image_input)
                    text_features = self._model.encode_text(text_inputs)
                    logits_per_image = image_features @ text_features.T
                    probs = logits_per_image.softmax(dim=-1).cpu().numpy()

                results = {
                    label: float(prob)
                    for label, prob in zip(labels, probs[0])
                }
                latency_ms = (time.time() - start_time) * 1000

                return VisionResult(
                    task=task,
                    model=VisionModelType.CLIP,
                    success=True,
                    data={"classifications": results},
                    latency_ms=latency_ms,
                    confidence=float(max(probs[0])),
                )

            elif task == VisionTask.IMAGE_SIMILARITY:
                with torch.no_grad():
                    image_features = self._model.encode_image(image_input)
                    image_features /= image_features.norm(dim=-1, keepdim=True)

                latency_ms = (time.time() - start_time) * 1000
                return VisionResult(
                    task=task,
                    model=VisionModelType.CLIP,
                    success=True,
                    data={"embedding": image_features.cpu().numpy().tolist()},
                    latency_ms=latency_ms,
                )

            else:
                return VisionResult(
                    task=task,
                    model=VisionModelType.CLIP,
                    success=False,
                    error=f"Task {task} not supported by CLIP",
                    latency_ms=(time.time() - start_time) * 1000,
                )

        except Exception as e:
            latency_ms = (time.time() - start_time) * 1000
            logger.error(f"CLIP processing error: {e}")
            return VisionResult(
                task=task,
                model=VisionModelType.CLIP,
                success=False,
                error=str(e),
                latency_ms=latency_ms,
            )

    async def batch_process(
        self,
        image_paths: List[str],
        task: VisionTask,
        **kwargs
    ) -> List[VisionResult]:
        """批量处理图像"""
        tasks = [self.process(path, task, **kwargs) for path in image_paths]
        return await asyncio.gather(*tasks)


class BLIPVisionModel(VisionModel):
    """BLIP本地视觉模型"""

    def __init__(self, model_name: str = "blip-image-captioning-base"):
        self.model_name = model_name
        self._model = None
        self._processor = None
        self._device = None

    async def _initialize(self):
        """初始化模型"""
        if self._model is None:
            try:
                from transformers import BlipProcessor, BlipForConditionalGeneration
                import torch
            except ImportError as exc:
                raise RuntimeError("transformers and torch packages are not installed") from exc

            self._device = "cuda" if torch.cuda.is_available() else "cpu"
            self._processor = BlipProcessor.from_pretrained(f"Salesforce/{self.model_name}")
            self._model = BlipForConditionalGeneration.from_pretrained(
                f"Salesforce/{self.model_name}"
            ).to(self._device)

    async def process(
        self,
        image_path: str,
        task: VisionTask,
        **kwargs
    ) -> VisionResult:
        """处理图像"""
        start_time = time.time()
        try:
            await self._initialize()

            from PIL import Image
            import torch

            image = Image.open(image_path).convert("RGB")

            if task == VisionTask.SCENE_UNDERSTANDING:
                inputs = self._processor(image, return_tensors="pt").to(self._device)
                with torch.no_grad():
                    out = self._model.generate(**inputs, max_length=100)
                caption = self._processor.decode(out[0], skip_special_tokens=True)

                latency_ms = (time.time() - start_time) * 1000
                return VisionResult(
                    task=task,
                    model=VisionModelType.BLIP,
                    success=True,
                    data={"caption": caption},
                    latency_ms=latency_ms,
                    confidence=0.85,
                )

            elif task == VisionTask.VQA:
                question = kwargs.get("question", "What is in this image?")
                inputs = self._processor(image, question, return_tensors="pt").to(self._device)
                with torch.no_grad():
                    out = self._model.generate(**inputs, max_length=50)
                answer = self._processor.decode(out[0], skip_special_tokens=True)

                latency_ms = (time.time() - start_time) * 1000
                return VisionResult(
                    task=task,
                    model=VisionModelType.BLIP,
                    success=True,
                    data={"answer": answer},
                    latency_ms=latency_ms,
                    confidence=0.85,
                )

            else:
                return VisionResult(
                    task=task,
                    model=VisionModelType.BLIP,
                    success=False,
                    error=f"Task {task} not supported by BLIP",
                    latency_ms=(time.time() - start_time) * 1000,
                )

        except Exception as e:
            latency_ms = (time.time() - start_time) * 1000
            logger.error(f"BLIP processing error: {e}")
            return VisionResult(
                task=task,
                model=VisionModelType.BLIP,
                success=False,
                error=str(e),
                latency_ms=latency_ms,
            )

    async def batch_process(
        self,
        image_paths: List[str],
        task: VisionTask,
        **kwargs
    ) -> List[VisionResult]:
        """批量处理图像"""
        tasks = [self.process(path, task, **kwargs) for path in image_paths]
        return await asyncio.gather(*tasks)


class VisionModelFactory:
    """视觉模型工厂"""

    _models: Dict[VisionModelType, VisionModel] = {}

    @classmethod
    def create(
        cls,
        model_type: VisionModelType,
        **kwargs
    ) -> VisionModel:
        """创建视觉模型"""
        if model_type == VisionModelType.GPT4V:
            api_key = kwargs.get("api_key")
            if not api_key:
                raise ValueError("api_key is required for GPT-4V")
            return GPT4VisionModel(api_key, kwargs.get("model", "gpt-4-vision-preview"))

        elif model_type == VisionModelType.CLAUDE_VISION:
            api_key = kwargs.get("api_key")
            if not api_key:
                raise ValueError("api_key is required for Claude Vision")
            return ClaudeVisionModel(api_key, kwargs.get("model", "claude-3-5-sonnet-20241022"))

        elif model_type == VisionModelType.CLIP:
            return CLIPVisionModel(kwargs.get("model_name", "ViT-B/32"))

        elif model_type == VisionModelType.BLIP:
            return BLIPVisionModel(kwargs.get("model_name", "blip-image-captioning-base"))

        else:
            raise ValueError(f"Unknown model type: {model_type}")

    @classmethod
    def get_or_create(
        cls,
        model_type: VisionModelType,
        **kwargs
    ) -> VisionModel:
        """获取或创建模型（单例）"""
        if model_type not in cls._models:
            cls._models[model_type] = cls.create(model_type, **kwargs)
        return cls._models[model_type]


class VisionModelManager:
    """视觉模型管理器"""

    def __init__(self):
        self.models: Dict[VisionModelType, VisionModel] = {}
        self.default_model = VisionModelType.CLAUDE_VISION

    def register_model(
        self,
        model_type: VisionModelType,
        model: VisionModel
    ) -> None:
        """注册模型"""
        self.models[model_type] = model
        logger.info(f"Registered vision model: {model_type}")

    def get_model(self, model_type: Optional[VisionModelType] = None) -> VisionModel:
        """获取模型"""
        model_type = model_type or self.default_model
        if model_type not in self.models:
            raise ValueError(f"Model {model_type} not registered")
        return self.models[model_type]

    async def process(
        self,
        image_path: str,
        task: VisionTask,
        model_type: Optional[VisionModelType] = None,
        **kwargs
    ) -> VisionResult:
        """处理图像"""
        model = self.get_model(model_type)
        return await model.process(image_path, task, **kwargs)

    async def batch_process(
        self,
        image_paths: List[str],
        task: VisionTask,
        model_type: Optional[VisionModelType] = None,
        **kwargs
    ) -> List[VisionResult]:
        """批量处理图像"""
        model = self.get_model(model_type)
        return await model.batch_process(image_paths, task, **kwargs)

    async def compare_models(
        self,
        image_path: str,
        task: VisionTask,
        model_types: Optional[List[VisionModelType]] = None,
        **kwargs
    ) -> Dict[VisionModelType, VisionResult]:
        """比较多个模型的结果"""
        model_types = model_types or list(self.models.keys())
        results = {}

        for model_type in model_types:
            try:
                result = await self.process(image_path, task, model_type, **kwargs)
                results[model_type] = result
            except Exception as e:
                logger.error(f"Error processing with {model_type}: {e}")
                results[model_type] = VisionResult(
                    task=task,
                    model=model_type,
                    success=False,
                    error=str(e),
                )

        return results
