"""Creative Studio API — 短剧成片工作流端点。"""

from __future__ import annotations

from typing import Annotated, Any

from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field

from backend.app.api.auth import PrincipalDependency
from backend.app.core.security import Principal
from backend.app.dependencies import enforce_scope, get_current_principal

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


class ShotVideoRequest(BaseModel):
    video_prompt: str
    output_path: str = ""
    duration_seconds: int = 5
    aspect_ratio: str = "9:16"
    human_review_approved: bool = False


class VideoWorkflowRequest(BaseModel):
    storyboard_json: dict[str, Any]
    execute: bool = False
    human_review_approved: bool = False
    max_shots: int = Field(default=8, ge=0, le=8)


class VoiceoverRequest(BaseModel):
    text: str
    output_path: str = ""
    voice: str = "zh-CN-XiaoxiaoNeural"


class ComposeRequest(BaseModel):
    storyboard_json: dict[str, Any]
    output_path: str = ""


def _creative_studio_endpoint(path: str) -> str:
    return f"/api/v1/creative-studio/{path}"


def _creative_video_provider_status() -> dict[str, Any]:
    from backend.app.core.creative_studio.adapters import external_video_api_status

    return {
        **external_video_api_status(),
        "endpoints": {
            "shot_video": _creative_studio_endpoint("shot-video"),
            "video_workflow": _creative_studio_endpoint("video-workflow"),
        },
    }


def _invalid_video_workflow_response(error: str) -> dict[str, Any]:
    return {
        "success": False,
        "workflow_id": "",
        "workflow_name": "Creative Studio external video API workflow",
        "workflow_status": "invalid",
        "dry_run": True,
        "approval_required": True,
        "risk_level": "high",
        "provider_api_call_attempted": False,
        "provider_status": _creative_video_provider_status(),
        "selected_shot_count": 0,
        "nodes": [],
        "edges": [],
        "approval": {
            "required": True,
            "subject_type": "network_request",
            "risk_level": "high",
            "reason": "external_video_provider_call_requires_human_review",
        },
        "results": [],
        "error": error,
    }


def _enforce_creative_video_execution_scope(principal: Principal, approved: bool) -> None:
    if approved:
        enforce_scope(principal, "workflow:control")


@router.get("/video-provider-status")
async def get_video_provider_status(principal: PrincipalDep) -> dict[str, Any]:
    """返回外部视频模型 API 配置状态；不返回密钥明文。"""
    return _creative_video_provider_status()


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


@router.post("/shot-video")
async def generate_shot_video(body: ShotVideoRequest, principal: PrincipalDep) -> dict[str, Any]:
    """为单个镜头调用外部视频模型 API；未人工审核时阻断 provider 调用。"""
    from backend.app.core.creative_studio.wiring import generate_shot_video as _gen
    _enforce_creative_video_execution_scope(principal, body.human_review_approved)
    return await _gen(
        video_prompt=body.video_prompt,
        output_path=body.output_path,
        duration_seconds=body.duration_seconds,
        aspect_ratio=body.aspect_ratio,
        human_review_approved=body.human_review_approved,
    )


@router.post("/video-workflow")
async def run_video_workflow(body: VideoWorkflowRequest, principal: PrincipalDep) -> dict[str, Any]:
    """计划或执行外部视频模型 API 工作流；默认仅 dry-run。"""
    from backend.app.core.creative_studio.storyboard import Storyboard
    from backend.app.core.creative_studio.workflow import run_external_video_workflow
    _enforce_creative_video_execution_scope(principal, body.execute and body.human_review_approved)

    try:
        storyboard = Storyboard.model_validate(body.storyboard_json)
    except Exception as exc:
        return _invalid_video_workflow_response(f"invalid storyboard: {exc}")
    return await run_external_video_workflow(
        storyboard,
        execute=body.execute,
        human_review_approved=body.human_review_approved,
        max_shots=body.max_shots,
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
