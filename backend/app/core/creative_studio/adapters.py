"""开源/商业媒体供应商适配器。

每个适配器按 MediaProvider 抽象挂入 MediaProviderRegistry，
工作流只依赖 media.py 里的抽象，切换供应商不改流水线。

TTS     — edge-tts (免费, 无 API Key, 中文晓晓/云扬等)
图片    — gpt-image-2 via openai SDK (需 OPENAI_API_KEY)
图片保底— 纯色占位图 (无需任何依赖，永远可用)
合成    — ffmpeg subprocess (需系统安装 ffmpeg)
"""

from __future__ import annotations

import asyncio
import inspect
import logging
import os
import shutil
import subprocess
from pathlib import Path
from typing import Any, Callable

from backend.app.core.creative_studio.media import (
    MediaKind,
    MediaProvider,
    MediaRequest,
    MediaResult,
)

logger = logging.getLogger(__name__)

PostJson = Callable[[str, dict[str, Any], dict[str, str], float], Any]


def external_video_api_status() -> dict[str, Any]:
    """Return redacted external video provider configuration status."""
    api_url = os.getenv("XAGENT_CREATIVE_VIDEO_API_URL", "")
    api_key = os.getenv("XAGENT_CREATIVE_VIDEO_API_KEY", "")
    provider = os.getenv("XAGENT_CREATIVE_VIDEO_PROVIDER", ExternalVideoAPIAdapter.name)
    model = os.getenv("XAGENT_CREATIVE_VIDEO_MODEL", "")
    configured = bool(api_url and api_key)
    return {
        "provider": provider,
        "model": model,
        "configured": configured,
        "api_url_configured": bool(api_url),
        "api_key_configured": bool(api_key),
        "api_key_fingerprint": _fingerprint_secret(api_key),
        "requires_human_review": True,
        "provider_api_call_attempted": False,
    }


def _fingerprint_secret(value: str) -> str:
    if not value:
        return ""
    import hashlib

    return hashlib.sha256(value.encode("utf-8")).hexdigest()[:12]


# ──────────────────────────────────────────
# TTS adapter: edge-tts (open-source, no API key)
# pip install edge-tts
# ──────────────────────────────────────────
class EdgeTTSAdapter(MediaProvider):
    """edge-tts：Microsoft Edge 在线 TTS，中文晓晓声，无 API Key。"""

    name = "edge-tts"
    kind = MediaKind.TTS
    requires_network = True

    def __init__(self, voice: str = "zh-CN-XiaoxiaoNeural") -> None:
        self.voice = voice

    async def available(self) -> bool:
        try:
            import edge_tts  # noqa: F401
            return True
        except ImportError:
            return False

    async def generate(self, request: MediaRequest) -> MediaResult:
        import time
        t0 = time.perf_counter()
        try:
            import edge_tts
            text = request.params.get("text") or request.prompt
            voice = request.params.get("voice", self.voice)
            output = request.output_path or "/tmp/tts_out.mp3"
            communicate = edge_tts.Communicate(text, voice)
            await communicate.save(output)
            # 同时导出 SRT 如果请求
            srt_path = request.params.get("srt_path", "")
            if srt_path:
                sub = edge_tts.SubMaker()
                async for chunk in communicate.stream():
                    if chunk["type"] == "WordBoundary":
                        sub.create_sub((chunk["offset"], chunk["duration"]), chunk["text"])
                Path(srt_path).write_text(sub.generate_subs(), encoding="utf-8")
            return MediaResult(
                success=True, kind=MediaKind.TTS,
                output_path=output, provider=self.name,
                latency_ms=(time.perf_counter() - t0) * 1000,
            )
        except Exception as exc:
            logger.warning("edge-tts failed: %s", exc)
            return MediaResult(success=False, kind=MediaKind.TTS, error=str(exc), provider=self.name)


# ──────────────────────────────────────────
# 图片 adapter: gpt-image-2 (openai SDK)
# 需 OPENAI_API_KEY 环境变量
# ──────────────────────────────────────────
class GPTImage2Adapter(MediaProvider):
    """gpt-image-2：OpenAI 图片生成，1024×1792 竖屏。"""

    name = "gpt-image-2"
    kind = MediaKind.IMAGE
    requires_network = True

    def __init__(self, api_key: str | None = None, model: str = "gpt-image-alpha") -> None:
        import os
        self.api_key = api_key or os.getenv("OPENAI_API_KEY", "")
        self.model = model

    async def available(self) -> bool:
        try:
            import openai  # noqa: F401
            return bool(self.api_key)
        except ImportError:
            return False

    async def generate(self, request: MediaRequest) -> MediaResult:
        import time, base64
        t0 = time.perf_counter()
        try:
            from openai import AsyncOpenAI
            client = AsyncOpenAI(api_key=self.api_key)
            size = request.params.get("size", "1024x1792")  # 竖屏 9:16
            quality = request.params.get("quality", "standard")
            resp = await client.images.generate(
                model=self.model,
                prompt=request.prompt,
                size=size,
                quality=quality,
                response_format="b64_json",
                n=1,
            )
            img_data = base64.b64decode(resp.data[0].b64_json)
            out = request.output_path or "/tmp/image_out.png"
            Path(out).write_bytes(img_data)
            return MediaResult(
                success=True, kind=MediaKind.IMAGE,
                output_path=out, provider=self.name,
                latency_ms=(time.perf_counter() - t0) * 1000,
            )
        except Exception as exc:
            logger.warning("gpt-image-2 failed: %s", exc)
            return MediaResult(success=False, kind=MediaKind.IMAGE, error=str(exc), provider=self.name)


# ──────────────────────────────────────────
# 视频 adapter: external HTTP JSON API
# 不绑定具体本地模型/ComfyUI。由环境变量配置外部模型 API。
# ──────────────────────────────────────────
class ExternalVideoAPIAdapter(MediaProvider):
    """外部视频模型 API：HTTP JSON 适配器，调用前必须已人工审核。"""

    name = "external-video-api"
    kind = MediaKind.VIDEO
    requires_network = True

    def __init__(
        self,
        api_url: str | None = None,
        api_key: str | None = None,
        provider: str | None = None,
        model: str | None = None,
        timeout_seconds: float = 60.0,
        post_json: PostJson | None = None,
    ) -> None:
        self.api_url = api_url if api_url is not None else os.getenv("XAGENT_CREATIVE_VIDEO_API_URL", "")
        self.api_key = api_key if api_key is not None else os.getenv("XAGENT_CREATIVE_VIDEO_API_KEY", "")
        self.provider = provider if provider is not None else os.getenv("XAGENT_CREATIVE_VIDEO_PROVIDER", self.name)
        self.model = model if model is not None else os.getenv("XAGENT_CREATIVE_VIDEO_MODEL", "")
        self.timeout_seconds = timeout_seconds
        self._post_json = post_json

    async def available(self) -> bool:
        return True

    async def generate(self, request: MediaRequest) -> MediaResult:
        import time

        if not request.params.get("human_review_approved", False):
            return MediaResult(
                success=False,
                kind=MediaKind.VIDEO,
                provider=self.provider,
                error="human_review_required_before_video_provider_call",
                metadata={"provider_api_call_attempted": False},
            )
        if not self.api_url or not self.api_key:
            return MediaResult(
                success=False,
                kind=MediaKind.VIDEO,
                provider=self.provider,
                error="external_video_api_not_configured",
                metadata={"provider_api_call_attempted": False},
            )

        t0 = time.perf_counter()
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }
        payload = {
            "prompt": request.prompt,
            "model": request.params.get("model") or self.model,
            "duration_seconds": request.params.get("duration_seconds"),
            "aspect_ratio": request.params.get("aspect_ratio", "9:16"),
            "provider": self.provider,
            "metadata": request.params.get("metadata", {}),
        }
        try:
            data = await self._post(payload, headers)
            output_url = _first_present(
                data,
                ("video_url", "output_url", "url", "download_url", "output"),
            )
            job_id = _first_present(data, ("job_id", "id", "request_id"))
            response_keys = sorted(str(key) for key in data.keys())
            if not output_url and not job_id:
                return MediaResult(
                    success=False,
                    kind=MediaKind.VIDEO,
                    provider=self.provider,
                    error="external_video_api_missing_output_reference",
                    latency_ms=(time.perf_counter() - t0) * 1000,
                    metadata={
                        "provider_api_call_attempted": True,
                        "response_keys": response_keys,
                    },
                )
            return MediaResult(
                success=True,
                kind=MediaKind.VIDEO,
                output_path=str(output_url or request.output_path or ""),
                provider=self.provider,
                latency_ms=(time.perf_counter() - t0) * 1000,
                metadata={
                    "provider_api_call_attempted": True,
                    "job_id": job_id,
                    "response_keys": response_keys,
                },
            )
        except Exception as exc:
            logger.warning("external video api failed: %s", type(exc).__name__)
            return MediaResult(
                success=False,
                kind=MediaKind.VIDEO,
                provider=self.provider,
                error="external_video_api_request_failed",
                latency_ms=(time.perf_counter() - t0) * 1000,
                metadata={"provider_api_call_attempted": True},
            )

    async def _post(self, payload: dict[str, Any], headers: dict[str, str]) -> dict[str, Any]:
        if self._post_json is not None:
            value = self._post_json(self.api_url, payload, headers, self.timeout_seconds)
            if inspect.isawaitable(value):
                value = await value
            return dict(value or {})

        def _request() -> dict[str, Any]:
            import json
            import urllib.request

            body = json.dumps(payload).encode("utf-8")
            req = urllib.request.Request(self.api_url, data=body, headers=headers, method="POST")
            with urllib.request.urlopen(req, timeout=self.timeout_seconds) as resp:
                return json.loads(resp.read().decode("utf-8"))

        return await asyncio.to_thread(_request)


def _first_present(data: dict[str, Any], keys: tuple[str, ...]) -> Any:
    for key in keys:
        value = data.get(key)
        if value:
            return value
    return None


# ──────────────────────────────────────────
# 图片保底 adapter: 纯色占位图（无需任何依赖）
# ──────────────────────────────────────────
class PlaceholderImageAdapter(MediaProvider):
    """保底图片：无模型依赖，用 Python stdlib 生成纯色 PNG 占位图。"""

    name = "placeholder-image"
    kind = MediaKind.IMAGE
    requires_network = False

    async def available(self) -> bool:
        return True

    async def generate(self, request: MediaRequest) -> MediaResult:
        out = request.output_path or "/tmp/placeholder.png"
        try:
            _write_placeholder_png(out)
            return MediaResult(success=True, kind=MediaKind.IMAGE, output_path=out, provider=self.name)
        except Exception as exc:
            return MediaResult(success=False, kind=MediaKind.IMAGE, error=str(exc), provider=self.name)


def _write_placeholder_png(path: str) -> None:
    """写入最小 1×1 红色 PNG（纯 stdlib，无 Pillow）。"""
    import struct, zlib
    def chunk(tag, data):
        return (struct.pack(">I", len(data)) + tag + data
                + struct.pack(">I", zlib.crc32(tag + data) & 0xFFFFFFFF))
    w, h = 200, 356  # 近似 9:16
    idat_raw = b"".join(b"\x00" + b"\xD6\x2B\x2B" * w for _ in range(h))
    png = (
        b"\x89PNG\r\n\x1a\n"
        + chunk(b"IHDR", struct.pack(">IIBBBBB", w, h, 8, 2, 0, 0, 0))
        + chunk(b"IDAT", zlib.compress(idat_raw))
        + chunk(b"IEND", b"")
    )
    Path(path).write_bytes(png)


# ──────────────────────────────────────────
# 合成 adapter: ffmpeg subprocess (保底路径)
# 需系统安装 ffmpeg
# ──────────────────────────────────────────
class FFmpegAdapter(MediaProvider):
    """FFmpeg：图片序列 + 配音 + 字幕 → final.mp4（保底路径）。"""

    name = "ffmpeg"
    kind = MediaKind.RENDER
    requires_network = False

    async def available(self) -> bool:
        return shutil.which("ffmpeg") is not None

    async def generate(self, request: MediaRequest) -> MediaResult:
        import time
        t0 = time.perf_counter()
        try:
            out = request.output_path or "/tmp/final.mp4"
            image_paths: list[str] = request.params.get("image_paths", [])
            audio_path: str = request.params.get("audio_path", "")
            srt_path: str = request.params.get("srt_path", "")
            durations: list[float] = request.params.get("durations", [])

            if not image_paths:
                return MediaResult(success=False, kind=MediaKind.RENDER,
                                   error="no image_paths", provider=self.name)

            # 写 concat demuxer 文件
            concat_txt = Path("/tmp/concat_list.txt")
            lines = []
            for i, img in enumerate(image_paths):
                dur = durations[i] if i < len(durations) else 4.0
                lines.append(f"file '{img}'\nduration {dur}")
            concat_txt.write_text("\n".join(lines), encoding="utf-8")

            cmd = [
                "ffmpeg", "-y",
                "-f", "concat", "-safe", "0", "-i", str(concat_txt),
                "-vf", f"scale=1080:1920:force_original_aspect_ratio=decrease,pad=1080:1920:-1:-1",
                "-c:v", "libx264", "-pix_fmt", "yuv420p", "-r", "25",
            ]
            if audio_path and Path(audio_path).exists():
                cmd += ["-i", audio_path, "-c:a", "aac", "-shortest"]
            if srt_path and Path(srt_path).exists():
                cmd += ["-vf", f"subtitles={srt_path}"]
            cmd.append(out)

            proc = await asyncio.create_subprocess_exec(
                *cmd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
            _, stderr = await proc.communicate()
            if proc.returncode != 0:
                return MediaResult(success=False, kind=MediaKind.RENDER,
                                   error=stderr.decode(errors="ignore")[-500:], provider=self.name)
            return MediaResult(
                success=True, kind=MediaKind.RENDER,
                output_path=out, provider=self.name,
                latency_ms=(time.perf_counter() - t0) * 1000,
            )
        except Exception as exc:
            logger.warning("ffmpeg adapter failed: %s", exc)
            return MediaResult(success=False, kind=MediaKind.RENDER, error=str(exc), provider=self.name)
