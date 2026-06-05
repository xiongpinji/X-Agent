"""Creative Studio API — 短剧成片工作流端点。"""

from __future__ import annotations

from typing import Annotated, Any

from fastapi import APIRouter, Depends
from pydantic import BaseModel

from backend.app.api.auth import PrincipalDependency
from backend.app.core.security import Principal
from backend.app.dependencies import get_current_principal

router = APIRouter(prefix="/api/v1/creative-studio", tags=["creative-studio"])
PrincipalDep = Annotated[Principal, Depends(get_current_principal)]


class StoryboardRequest(BaseModel):
    brief: str
    genre: str = "都市"
    platform: str = "douyin"
    duration_seconds: int = 60


class ShotImageRequest(BaseModel):
    visual_prompt: str
    output_path: str = ""
    size: str = "1024x1792"


class VoiceoverRequest(BaseModel):
    text: str
    output_path: str = ""
    voice: str = "zh-CN-XiaoxiaoNeural"


class ComposeRequest(BaseModel):
    storyboard_json: dict[str, Any]
    output_path: str = ""


@router.post("/storyboard")
async def create_storyboard(body: StoryboardRequest, principal: PrincipalDep) -> dict[str, Any]:
    """从一句话需求生成完整故事板。"""
    from backend.app.core.creative_studio.wiring import create_short_drama_storyboard
    return await create_short_drama_storyboard(
        brief=body.brief,
        genre=body.genre,
        platform=body.platform,
        duration_seconds=body.duration_seconds,
    )


@router.post("/shot-image")
async def generate_shot_image(body: ShotImageRequest, principal: PrincipalDep) -> dict[str, Any]:
    """为单个镜头生成关键帧图片（gpt-image-2 优先，保底占位图）。"""
    from backend.app.core.creative_studio.wiring import generate_shot_image as _gen
    return await _gen(
        visual_prompt=body.visual_prompt,
        output_path=body.output_path,
        size=body.size,
    )


@router.post("/voiceover")
async def synthesize_voiceover(body: VoiceoverRequest, principal: PrincipalDep) -> dict[str, Any]:
    """用 edge-tts 合成配音（免费，无 API Key）。"""
    from backend.app.core.creative_studio.wiring import synthesize_voiceover as _tts
    return await _tts(text=body.text, output_path=body.output_path, voice=body.voice)


@router.post("/compose")
async def compose_drama(body: ComposeRequest, principal: PrincipalDep) -> dict[str, Any]:
    """用 ffmpeg 合成 final.mp4（镜头图片 + 配音 + 字幕）。"""
    from backend.app.core.creative_studio.wiring import compose_short_drama as _cmp
    return await _cmp(storyboard_json=body.storyboard_json, output_path=body.output_path)
