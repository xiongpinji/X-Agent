"""媒体能力抽象层 (图片 / 视频 / TTS / 合成)。

现有 llm_providers 只覆盖文本模型。短剧成片还需要图片、视频、配音、剪辑
能力。这里定义统一的 MediaProvider 抽象，让具体实现 (gpt-image / edge-tts /
ffmpeg 等开源或商业适配器) 可插拔注册，工作流只依赖抽象。

设计原则：
- adapter 模式：切换供应商只改 adapter，不改工作流
- 双路径保底：视频不可用时，图片运镜模板仍能出片
- 不在产物里写入任何模型密钥
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from enum import Enum
from typing import Any


class MediaKind(str, Enum):
    """媒体能力类别，对应多模型路由的 model_class。"""

    IMAGE = "image_generation"
    VIDEO = "video_generation"
    TTS = "tts"
    RENDER = "render_engine"


@dataclass
class MediaRequest:
    """媒体生成请求。"""

    kind: MediaKind
    prompt: str = ""
    output_path: str = ""
    params: dict[str, Any] = field(default_factory=dict)


@dataclass
class MediaResult:
    """媒体生成结果。不含任何密钥。"""

    success: bool
    kind: MediaKind
    output_path: str = ""
    provider: str = ""
    cost_usd: float = 0.0
    latency_ms: float = 0.0
    error: str | None = None
    metadata: dict[str, Any] = field(default_factory=dict)


class MediaProvider(ABC):
    """媒体供应商抽象基类。"""

    #: 供应商唯一名（如 "gpt-image", "edge-tts", "ffmpeg"）
    name: str = "base"
    #: 能力类别
    kind: MediaKind = MediaKind.IMAGE
    #: 是否需要密钥/联网（保底路径不需要）
    requires_network: bool = True

    @abstractmethod
    async def generate(self, request: MediaRequest) -> MediaResult:
        """执行媒体生成。具体实现负责调用模型/工具。"""
        raise NotImplementedError

    async def available(self) -> bool:
        """供应商是否可用（密钥/依赖/二进制就绪）。默认可用。"""
        return True


class MediaProviderRegistry:
    """媒体供应商注册表，支持按能力类别选择 + 保底回退。"""

    def __init__(self) -> None:
        self._providers: dict[MediaKind, list[MediaProvider]] = {}

    def register(self, provider: MediaProvider) -> None:
        """注册供应商。先注册的优先级更高。"""
        self._providers.setdefault(provider.kind, []).append(provider)

    def list_for(self, kind: MediaKind) -> list[MediaProvider]:
        return list(self._providers.get(kind, []))

    async def select(self, kind: MediaKind) -> MediaProvider | None:
        """选择该类别下第一个可用的供应商。"""
        for provider in self._providers.get(kind, []):
            try:
                if await provider.available():
                    return provider
            except Exception:
                continue
        return None

    async def generate(self, request: MediaRequest) -> MediaResult:
        """选择可用供应商并生成；全部不可用时返回失败结果。"""
        provider = await self.select(request.kind)
        if provider is None:
            return MediaResult(
                success=False,
                kind=request.kind,
                error=f"no available provider for {request.kind.value}",
            )
        return await provider.generate(request)


# 进程级默认注册表（adapter 在 wiring 中注册）
media_registry = MediaProviderRegistry()
