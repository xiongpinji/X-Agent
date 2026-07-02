"""媒体注册表装配 + X-Agent 工具注册。

在模块级注册表 media_registry 中注册默认适配器（优先 gpt-image-2，保底
PlaceholderImage；TTS 用 edge-tts；合成用 ffmpeg）。

同时导出 register_creative_tools 供显式 opt-in 工具注册；默认商业工具面不自动挂入。
"""

from __future__ import annotations

import logging
import os
import tempfile
from pathlib import Path
from typing import Any

from backend.app.core.creative_studio.adapters import (
    EdgeTTSAdapter,
    ExternalVideoAPIAdapter,
    FFmpegAdapter,
    GPTImage2Adapter,
    PlaceholderImageAdapter,
)
from backend.app.core.creative_studio.media import MediaKind, MediaRequest, media_registry
from backend.app.core.creative_studio.producer import ShortDramaProducerAgent
from backend.app.core.creative_studio.storyboard import Storyboard

logger = logging.getLogger(__name__)


def _setup_media_registry() -> None:
    """注册默认媒体适配器（幂等，可重复调用）。"""
    # 图片：gpt-image-2 优先，PlaceholderImage 保底（永远可用）
    if not media_registry.list_for(MediaKind.IMAGE):
        openai_key = os.getenv("OPENAI_API_KEY", "") or os.getenv("XAGENT_OPENAI_API_KEY", "")
        if openai_key:
            media_registry.register(GPTImage2Adapter(api_key=openai_key))
        media_registry.register(PlaceholderImageAdapter())  # 永远保底

    # TTS：edge-tts（无需 API Key）
    if not media_registry.list_for(MediaKind.TTS):
        media_registry.register(EdgeTTSAdapter())

    # 合成：ffmpeg（需系统安装）
    if not media_registry.list_for(MediaKind.RENDER):
        media_registry.register(FFmpegAdapter())

    # 视频：外部模型 API，仅在配置齐全且调用已人工审核后才会出站。
    if not media_registry.list_for(MediaKind.VIDEO):
        media_registry.register(ExternalVideoAPIAdapter())

    logger.info(
        "creative_studio: media registry ready (image=%d video=%d tts=%d render=%d)",
        len(media_registry.list_for(MediaKind.IMAGE)),
        len(media_registry.list_for(MediaKind.VIDEO)),
        len(media_registry.list_for(MediaKind.TTS)),
        len(media_registry.list_for(MediaKind.RENDER)),
    )


_setup_media_registry()


# ──────────────────────────────────────────
# X-Agent 工具 handlers（注入到 ToolRegistry）
# ──────────────────────────────────────────

async def create_short_drama_storyboard(
    brief: str,
    genre: str = "都市",
    platform: str = "douyin",
    duration_seconds: int = 60,
) -> dict[str, Any]:
    """从一句话需求生成故事板。返回故事板 JSON。"""
    from backend.app.core.llm import LLMRouter

    def make_llm_caller():
        try:
            from backend.app.dependencies import build_llm_router
            from backend.app.settings import get_settings
            _s = get_settings()
            router = build_llm_router(
                llm_backend=_s.llm_backend,
                fallback_order=_s.llm_fallback_order,
                openai_api_key=_s.openai_api_key,
                openai_model=_s.openai_model,
                deepseek_api_key=_s.deepseek_api_key,
                deepseek_model=_s.deepseek_model,
                deepseek_base_url=_s.deepseek_base_url or "https://api.deepseek.com/v1",
            )
            async def caller(system_prompt: str, user_prompt: str) -> str:
                resp = await router.chat([
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt},
                ], [])  # tools=[] for plain text generation
                return str(resp.content if hasattr(resp, "content") else (resp or {}).get("content", ""))
            return caller
        except Exception as exc:
            import logging; logging.getLogger(__name__).warning("creative_studio llm unavailable: %s", exc)
            return None

    agent = ShortDramaProducerAgent(llm_caller=make_llm_caller(), max_shots=8)
    sb = await agent.create_storyboard(
        brief=brief, genre=genre, platform=platform,
        target_duration_seconds=duration_seconds,
    )
    return _storyboard_summary(sb)


async def generate_shot_image(
    visual_prompt: str,
    output_path: str = "",
    size: str = "1024x1792",
) -> dict[str, Any]:
    """为单个镜头生成关键帧图片（gpt-image-2 优先，保底占位图）。"""
    out = output_path or str(Path(tempfile.mkdtemp()) / "shot.png")
    result = await media_registry.generate(
        MediaRequest(kind=MediaKind.IMAGE, prompt=visual_prompt,
                     output_path=out, params={"size": size})
    )
    return {"success": result.success, "output_path": result.output_path,
            "provider": result.provider, "error": result.error}


async def generate_shot_video(
    video_prompt: str,
    output_path: str = "",
    duration_seconds: int = 5,
    aspect_ratio: str = "9:16",
    human_review_approved: bool = False,
) -> dict[str, Any]:
    """为单个镜头调用外部视频模型 API；未人工审核时不会出站调用。"""
    if not human_review_approved:
        return {
            "success": False,
            "output_path": "",
            "provider": "external-video-api",
            "error": "human_review_required_before_video_provider_call",
            "metadata": {"provider_api_call_attempted": False},
        }
    result = await media_registry.generate(
        MediaRequest(
            kind=MediaKind.VIDEO,
            prompt=video_prompt,
            output_path=output_path,
            params={
                "duration_seconds": duration_seconds,
                "aspect_ratio": aspect_ratio,
                "human_review_approved": human_review_approved,
            },
        )
    )
    return {
        "success": result.success,
        "output_path": result.output_path,
        "provider": result.provider,
        "error": result.error,
        "metadata": result.metadata,
    }


async def synthesize_voiceover(
    text: str,
    output_path: str = "",
    voice: str = "zh-CN-XiaoxiaoNeural",
) -> dict[str, Any]:
    """用 edge-tts 把台词合成为语音文件（无 API Key，免费）。"""
    out = output_path or str(Path(tempfile.mkdtemp()) / "voice.mp3")
    srt = str(Path(out).with_suffix(".srt"))
    result = await media_registry.generate(
        MediaRequest(kind=MediaKind.TTS, prompt=text, output_path=out,
                     params={"text": text, "voice": voice, "srt_path": srt})
    )
    return {"success": result.success, "audio_path": result.output_path,
            "srt_path": srt, "provider": result.provider, "error": result.error}


async def compose_short_drama(
    storyboard_json: dict,
    output_path: str = "",
) -> dict[str, Any]:
    """用 ffmpeg 把镜头图片+配音+字幕合成 final.mp4。"""
    try:
        sb = Storyboard.model_validate(storyboard_json)
    except Exception as e:
        return {"success": False, "error": f"invalid storyboard: {e}"}

    out = output_path or str(Path(tempfile.mkdtemp()) / f"{sb.project_id}_final.mp4")
    image_paths = [s.image_path for s in sb.shots if s.image_path]
    audio_path = sb.deliverables.get("voiceover", "")
    srt_path = sb.deliverables.get("subtitles", "")
    durations = [s.duration_seconds for s in sb.shots]

    result = await media_registry.generate(
        MediaRequest(kind=MediaKind.RENDER, output_path=out, params={
            "image_paths": image_paths, "audio_path": audio_path,
            "srt_path": srt_path, "durations": durations,
        })
    )
    return {"success": result.success, "output_path": result.output_path,
            "provider": result.provider, "error": result.error}


def _storyboard_summary(sb: Storyboard) -> dict[str, Any]:
    """返回故事板的可序列化摘要（不含密钥）。"""
    return {
        "project_id": sb.project_id,
        "status": sb.status.value,
        "title": sb.title,
        "genre": sb.genre,
        "brief": sb.brief,
        "logline": sb.logline,
        "outline": sb.outline,
        "target_duration_seconds": sb.target_duration_seconds,
        "shot_count": len(sb.shots),
        "total_shot_duration": sb.total_shot_duration(),
        "character_count": len(sb.character_cards),
        "scene_count": len(sb.scene_cards),
        "quality_gates": [
            {"name": g.name, "passed": g.passed, "detail": g.detail}
            for g in sb.quality_gates
        ],
        "shots": [
            {
                "shot_id": s.shot_id,
                "duration": s.duration_seconds,
                "scene": s.scene,
                "plot_purpose": s.plot_purpose,
                "dialogue": s.dialogue,
                "emotion": s.emotion,
                "camera": {"shot_size": s.camera.shot_size, "movement": s.camera.movement},
            }
            for s in sb.shots
        ],
    }


def register_creative_tools(registry) -> None:
    """注册 Creative Studio 工具到 ToolRegistry。调用方需显式 opt-in。"""
    from backend.app.core.contracts import RiskLevel

    registry.register(
        "create_short_drama_storyboard",
        "从一句话需求生成短剧故事板（含镜头/台词/角色/场景/质量门）。",
        create_short_drama_storyboard,
        risk_level=RiskLevel.MEDIUM,
        parameters_schema={
            "type": "object",
            "properties": {
                "brief": {"type": "string", "description": "一句话需求"},
                "genre": {"type": "string", "description": "类型，如：都市/逆袭/霸总/甜宠"},
                "platform": {"type": "string", "description": "目标平台，如：douyin"},
                "duration_seconds": {"type": "integer", "description": "目标时长（秒），默认 60"},
            },
            "required": ["brief"],
        },
    )
    registry.register(
        "generate_shot_image",
        "为故事板单个镜头生成关键帧图片（gpt-image-2，保底占位图）。",
        generate_shot_image,
        risk_level=RiskLevel.MEDIUM,
        parameters_schema={
            "type": "object",
            "properties": {
                "visual_prompt": {"type": "string", "description": "Prompt Compiler 输出的图片提示词"},
                "output_path": {"type": "string", "description": "输出文件路径"},
                "size": {"type": "string", "description": "图片尺寸，默认 1024x1792（竖屏）"},
            },
            "required": ["visual_prompt"],
        },
    )
    registry.register(
        "generate_shot_video",
        "为故事板单个镜头调用外部视频模型 API 生成视频；必须先完成真人审核。",
        generate_shot_video,
        risk_level=RiskLevel.HIGH,
        required_scope="workflow:control",
        parameters_schema={
            "type": "object",
            "properties": {
                "video_prompt": {"type": "string", "description": "Prompt Compiler 输出的视频提示词"},
                "output_path": {"type": "string", "description": "输出文件路径或远端交付目标"},
                "duration_seconds": {"type": "integer", "description": "镜头时长（秒），默认 5"},
                "aspect_ratio": {"type": "string", "description": "画幅比例，默认 9:16"},
                "human_review_approved": {"type": "boolean", "description": "是否已完成真人审核"},
            },
            "required": ["video_prompt", "human_review_approved"],
        },
    )
    registry.register(
        "synthesize_voiceover",
        "用 edge-tts 把台词合成配音文件，无 API Key（Microsoft Edge TTS）。",
        synthesize_voiceover,
        risk_level=RiskLevel.LOW,
        parameters_schema={
            "type": "object",
            "properties": {
                "text": {"type": "string", "description": "配音文本"},
                "output_path": {"type": "string", "description": "输出路径"},
                "voice": {"type": "string", "description": "音色名，默认 zh-CN-XiaoxiaoNeural"},
            },
            "required": ["text"],
        },
    )
    registry.register(
        "compose_short_drama",
        "用 ffmpeg 把镜头图片+配音+字幕合成 final.mp4。",
        compose_short_drama,
        risk_level=RiskLevel.HIGH,
        parameters_schema={
            "type": "object",
            "properties": {
                "storyboard_json": {"type": "object", "description": "故事板 JSON（来自 create_short_drama_storyboard）"},
                "output_path": {"type": "string", "description": "输出 mp4 路径"},
            },
            "required": ["storyboard_json"],
        },
    )
    logger.info("creative_studio: 5 tools registered (storyboard/image/video/tts/compose)")
