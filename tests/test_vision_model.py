"""
视觉模型单元测试
"""

import pytest

# Vision tests require optional ML deps (Pillow/torch/transformers,
# see requirements-vision.txt). Skip cleanly when they are not installed
# instead of failing collection in a core-only environment.
pytest.importorskip("PIL", reason="vision deps not installed (requirements-vision.txt)")
pytest.importorskip("numpy")
import asyncio
from pathlib import Path
from unittest.mock import Mock, patch, AsyncMock
import tempfile
from PIL import Image
import numpy as np

from backend.app.core.vision_model import (
    VisionModelType,
    VisionTask,
    VisionResult,
    GPT4VisionModel,
    ClaudeVisionModel,
    CLIPVisionModel,
    BLIPVisionModel,
    VisionModelFactory,
    VisionModelManager,
)


@pytest.fixture
def sample_image():
    """创建示例图像"""
    # Windows 上 NamedTemporaryFile 在 with 块内持有打开句柄，跨 yield 不退出
    # → teardown 的 unlink 触发 WinError 32（文件被占用）。先退出 with 关句柄，
    # 再用 PIL 按路径写入，teardown 即可安全删除。
    with tempfile.NamedTemporaryFile(suffix=".png", delete=False) as f:
        name = f.name
    img = Image.new("RGB", (100, 100), color="red")
    img.save(name)
    yield name
    Path(name).unlink(missing_ok=True)


@pytest.fixture
def vision_manager():
    """创建视觉模型管理器"""
    return VisionModelManager()


class TestVisionResult:
    """VisionResult测试"""

    def test_vision_result_creation(self):
        """测试VisionResult创建"""
        result = VisionResult(
            task=VisionTask.IMAGE_CLASSIFICATION,
            model=VisionModelType.CLIP,
            success=True,
            data={"test": "data"},
            confidence=0.95,
        )

        assert result.task == VisionTask.IMAGE_CLASSIFICATION
        assert result.model == VisionModelType.CLIP
        assert result.success is True
        assert result.data == {"test": "data"}
        assert result.confidence == 0.95

    def test_vision_result_failure(self):
        """测试VisionResult失败"""
        result = VisionResult(
            task=VisionTask.OCR,
            model=VisionModelType.GPT4V,
            success=False,
            error="Test error",
        )

        assert result.success is False
        assert result.error == "Test error"


class TestGPT4VisionModel:
    """GPT-4V模型测试"""

    @pytest.mark.asyncio
    async def test_gpt4v_initialization(self):
        """测试GPT-4V初始化"""
        model = GPT4VisionModel(api_key="test-key")
        assert model.api_key == "test-key"
        assert model.model == "gpt-4-vision-preview"

    @pytest.mark.asyncio
    async def test_gpt4v_custom_model(self):
        """测试自定义GPT-4V模型"""
        model = GPT4VisionModel(api_key="test-key", model="gpt-4-turbo-vision")
        assert model.model == "gpt-4-turbo-vision"

    def test_gpt4v_prompt_building(self):
        """测试提示词构建"""
        model = GPT4VisionModel(api_key="test-key")

        prompt = model._build_prompt(VisionTask.IMAGE_CLASSIFICATION)
        assert "classify" in prompt.lower()

        prompt = model._build_prompt(VisionTask.OCR)
        assert "text" in prompt.lower()

        prompt = model._build_prompt(VisionTask.VQA, question="What is this?")
        assert "What is this?" in prompt


class TestClaudeVisionModel:
    """Claude Vision模型测试"""

    @pytest.mark.asyncio
    async def test_claude_initialization(self):
        """测试Claude初始化"""
        model = ClaudeVisionModel(api_key="test-key")
        assert model.api_key == "test-key"
        assert model.model == "claude-3-5-sonnet-20241022"

    def test_claude_prompt_building(self):
        """测试提示词构建"""
        model = ClaudeVisionModel(api_key="test-key")

        prompt = model._build_prompt(VisionTask.SCENE_UNDERSTANDING)
        assert "scene" in prompt.lower()


class TestCLIPVisionModel:
    """CLIP模型测试"""

    @pytest.mark.asyncio
    async def test_clip_initialization(self):
        """测试CLIP初始化"""
        model = CLIPVisionModel(model_name="ViT-B/32")
        assert model.model_name == "ViT-B/32"

    @pytest.mark.asyncio
    async def test_clip_custom_model(self):
        """测试自定义CLIP模型"""
        model = CLIPVisionModel(model_name="ViT-L/14")
        assert model.model_name == "ViT-L/14"


class TestBLIPVisionModel:
    """BLIP模型测试"""

    @pytest.mark.asyncio
    async def test_blip_initialization(self):
        """测试BLIP初始化"""
        model = BLIPVisionModel(model_name="blip-image-captioning-base")
        assert model.model_name == "blip-image-captioning-base"


class TestVisionModelFactory:
    """VisionModelFactory测试"""

    def test_factory_create_gpt4v(self):
        """测试创建GPT-4V模型"""
        model = VisionModelFactory.create(
            VisionModelType.GPT4V,
            api_key="test-key"
        )
        assert isinstance(model, GPT4VisionModel)

    def test_factory_create_claude(self):
        """测试创建Claude模型"""
        model = VisionModelFactory.create(
            VisionModelType.CLAUDE_VISION,
            api_key="test-key"
        )
        assert isinstance(model, ClaudeVisionModel)

    def test_factory_create_clip(self):
        """测试创建CLIP模型"""
        model = VisionModelFactory.create(VisionModelType.CLIP)
        assert isinstance(model, CLIPVisionModel)

    def test_factory_create_blip(self):
        """测试创建BLIP模型"""
        model = VisionModelFactory.create(VisionModelType.BLIP)
        assert isinstance(model, BLIPVisionModel)

    def test_factory_missing_api_key(self):
        """测试缺少API密钥"""
        with pytest.raises(ValueError):
            VisionModelFactory.create(VisionModelType.GPT4V)

    def test_factory_unknown_model(self):
        """测试未知模型"""
        with pytest.raises(ValueError):
            VisionModelFactory.create("unknown_model")

    def test_factory_singleton(self):
        """测试单例模式"""
        model1 = VisionModelFactory.get_or_create(VisionModelType.CLIP)
        model2 = VisionModelFactory.get_or_create(VisionModelType.CLIP)
        assert model1 is model2


class TestVisionModelManager:
    """VisionModelManager测试"""

    def test_manager_initialization(self):
        """测试管理器初始化"""
        manager = VisionModelManager()
        assert manager.default_model == VisionModelType.CLAUDE_VISION
        assert len(manager.models) == 0

    def test_manager_register_model(self):
        """测试注册模型"""
        manager = VisionModelManager()
        model = CLIPVisionModel()

        manager.register_model(VisionModelType.CLIP, model)
        assert VisionModelType.CLIP in manager.models
        assert manager.models[VisionModelType.CLIP] is model

    def test_manager_get_model(self):
        """测试获取模型"""
        manager = VisionModelManager()
        model = CLIPVisionModel()
        manager.register_model(VisionModelType.CLIP, model)

        retrieved = manager.get_model(VisionModelType.CLIP)
        assert retrieved is model

    def test_manager_get_default_model(self):
        """测试获取默认模型"""
        manager = VisionModelManager()
        model = ClaudeVisionModel(api_key="test-key")
        manager.register_model(VisionModelType.CLAUDE_VISION, model)

        retrieved = manager.get_model()
        assert retrieved is model

    def test_manager_get_unregistered_model(self):
        """测试获取未注册的模型"""
        manager = VisionModelManager()

        with pytest.raises(ValueError):
            manager.get_model(VisionModelType.CLIP)

    @pytest.mark.asyncio
    async def test_manager_process(self, sample_image):
        """测试处理图像"""
        manager = VisionModelManager()
        model = Mock()
        model.process = AsyncMock(return_value=VisionResult(
            task=VisionTask.IMAGE_CLASSIFICATION,
            model=VisionModelType.CLIP,
            success=True,
            data={"test": "data"},
        ))

        manager.register_model(VisionModelType.CLIP, model)
        result = await manager.process(
            sample_image,
            VisionTask.IMAGE_CLASSIFICATION,
            VisionModelType.CLIP
        )

        assert result.success is True
        model.process.assert_called_once()

    @pytest.mark.asyncio
    async def test_manager_batch_process(self, sample_image):
        """测试批量处理"""
        manager = VisionModelManager()
        model = Mock()
        model.batch_process = AsyncMock(return_value=[
            VisionResult(
                task=VisionTask.IMAGE_CLASSIFICATION,
                model=VisionModelType.CLIP,
                success=True,
                data={"test": "data"},
            )
        ])

        manager.register_model(VisionModelType.CLIP, model)
        results = await manager.batch_process(
            [sample_image],
            VisionTask.IMAGE_CLASSIFICATION,
            VisionModelType.CLIP
        )

        assert len(results) == 1
        assert results[0].success is True


class TestVisionModelIntegration:
    """集成测试"""

    def test_vision_task_enum(self):
        """测试VisionTask枚举"""
        assert VisionTask.IMAGE_CLASSIFICATION.value == "image_classification"
        assert VisionTask.OBJECT_DETECTION.value == "object_detection"
        assert VisionTask.OCR.value == "ocr"
        assert VisionTask.SCENE_UNDERSTANDING.value == "scene_understanding"
        assert VisionTask.VQA.value == "visual_question_answering"
        assert VisionTask.IMAGE_SIMILARITY.value == "image_similarity"

    def test_vision_model_type_enum(self):
        """测试VisionModelType枚举"""
        assert VisionModelType.GPT4V.value == "gpt4v"
        assert VisionModelType.CLAUDE_VISION.value == "claude_vision"
        assert VisionModelType.CLIP.value == "clip"
        assert VisionModelType.BLIP.value == "blip"

    def test_base64_encoding(self, sample_image):
        """测试Base64编码"""
        from backend.app.core.vision_model import VisionModel

        base64_str = VisionModel._load_image_as_base64(sample_image)
        assert isinstance(base64_str, str)
        assert len(base64_str) > 0

    def test_media_type_detection(self):
        """测试媒体类型检测"""
        from backend.app.core.vision_model import VisionModel

        assert VisionModel._get_image_media_type("test.jpg") == "image/jpeg"
        assert VisionModel._get_image_media_type("test.png") == "image/png"
        assert VisionModel._get_image_media_type("test.gif") == "image/gif"
        assert VisionModel._get_image_media_type("test.webp") == "image/webp"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
