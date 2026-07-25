"""故事板数据契约 (storyboard-first)。

故事板是整个短剧工作流的核心契约：编剧、分镜、摄影灯光、图片生成、
视频生成、TTS、字幕、剪辑都从这里读取结构化字段。所有模型 adapter 只
负责把这些字段编译成各自的 prompt，而不重新理解用户需求。
"""

from __future__ import annotations

from datetime import UTC, datetime
from enum import StrEnum
from uuid import uuid4

from pydantic import BaseModel, Field


def _utcnow() -> datetime:
    return datetime.now(UTC)


class StoryboardStatus(StrEnum):
    """故事板生命周期状态。"""

    DRAFT = "draft"  # 刚由制作人生成大纲
    SCRIPTED = "scripted"  # 剧本与台词已就绪
    STORYBOARDED = "storyboarded"  # 镜头级故事板已完成
    ASSETS_READY = "assets_ready"  # 图片/视频/配音素材已生成
    COMPOSED = "composed"  # 已合成 final.mp4
    FAILED = "failed"


class AspectRatio(StrEnum):
    """画面比例。短剧默认竖屏 9:16。"""

    VERTICAL = "9:16"
    HORIZONTAL = "16:9"
    SQUARE = "1:1"


class CameraSpec(BaseModel):
    """镜头语言：景别 / 机位 / 运镜 / 焦段 / 焦点 / 构图。"""

    shot_size: str = "medium"  # 远景/全景/中景/中近景/近景/特写/大特写
    angle: str = "eye-level"  # 平视/俯拍/仰拍/鸟瞰/低机位/高机位
    movement: str = "static"  # 推/拉/摇/移/跟/环绕/升降/横移/手持
    lens: str = "50mm"
    focus: str = "deep focus"
    composition: str = "rule of thirds"


class LightingSpec(BaseModel):
    """光线与影调。"""

    style: str = "natural"  # 悬疑低调光/甜宠柔光/豪门冷暖对比 等
    key_light: str = "soft frontal"
    fill_light: str = "minimal"
    back_light: str = "subtle rim"
    contrast: str = "medium"
    color_temperature: str = "neutral"
    mood: str = "neutral"


class ShotContinuity(BaseModel):
    """连续性约束：跨镜头保持角色/场景/风格一致。"""

    character_ref: str = ""  # 角色参考 id，如 female_lead_v1
    scene_ref: str = ""  # 场景参考 id
    style_ref: str = ""  # 风格参考 id


class Shot(BaseModel):
    """单个镜头。故事板的最小可验证单元。"""

    shot_id: str
    duration_seconds: float = 4.0
    scene: str = ""
    characters: list[str] = Field(default_factory=list)
    plot_purpose: str = ""
    camera: CameraSpec = Field(default_factory=CameraSpec)
    lighting: LightingSpec = Field(default_factory=LightingSpec)
    action: str = ""
    dialogue: str = ""
    subtitle: str = ""
    emotion: str = ""
    # 由 Prompt Compiler 从上面字段编译产出
    visual_prompt: str = ""
    video_prompt: str = ""
    negative_prompt: str = (
        "deformed face, inconsistent outfit, extra fingers, low quality, watermark"
    )
    continuity: ShotContinuity = Field(default_factory=ShotContinuity)
    # 生成产物路径（素材阶段回填）
    image_path: str = ""
    video_path: str = ""
    audio_path: str = ""


class CharacterCard(BaseModel):
    """角色卡：保证跨镜头角色一致性。"""

    ref_id: str  # female_lead_v1
    name: str = ""
    role: str = ""  # 女主/男主/配角
    appearance: str = ""  # 外貌、年龄、气质
    outfit: str = ""  # 固定服装
    personality: str = ""
    reference_image: str = ""


class SceneCard(BaseModel):
    """场景卡：保证跨镜头场景一致性。"""

    ref_id: str  # luxury_apartment_v1
    name: str = ""
    description: str = ""
    time_of_day: str = ""  # 清晨/正午/黄昏/夜晚
    atmosphere: str = ""
    reference_image: str = ""


class SubtitleTrack(BaseModel):
    """字幕轨：与台词一致，最终导出 SRT。"""

    shot_id: str
    start_seconds: float = 0.0
    end_seconds: float = 0.0
    text: str = ""


class AudioPlan(BaseModel):
    """音频计划：配音 + BGM。"""

    voiceover_provider: str = "edge-tts"
    voice: str = "zh-CN-XiaoxiaoNeural"
    bgm_style: str = ""
    bgm_path: str = ""


class EditPlan(BaseModel):
    """剪辑计划：转场、卡点、节奏。"""

    transitions: list[str] = Field(default_factory=lambda: ["cut"])
    hook_seconds: float = 3.0  # 前 3 秒钩子
    bgm_volume: float = 0.3
    subtitle_burn_in: bool = True
    engine: str = "ffmpeg"  # ffmpeg / remotion


class QualityGate(BaseModel):
    """质量门检查结果。"""

    name: str
    passed: bool = False
    detail: str = ""


class Storyboard(BaseModel):
    """完整故事板：短剧工作流的核心契约对象。"""

    project_id: str = Field(default_factory=lambda: f"sd_{uuid4().hex[:12]}")
    title: str = ""
    genre: str = ""  # 霸总/甜宠/复仇/逆袭/都市/古风 等
    platform: str = "douyin"
    target_duration_seconds: int = 60
    aspect_ratio: AspectRatio = AspectRatio.VERTICAL
    style_profile: str = "urban_drama_cinematic"

    # 一句话原始需求与派生大纲
    brief: str = ""
    logline: str = ""
    outline: list[str] = Field(default_factory=list)
    script: str = ""

    character_cards: list[CharacterCard] = Field(default_factory=list)
    scene_cards: list[SceneCard] = Field(default_factory=list)
    shots: list[Shot] = Field(default_factory=list)
    subtitle_tracks: list[SubtitleTrack] = Field(default_factory=list)
    audio_plan: AudioPlan = Field(default_factory=AudioPlan)
    edit_plan: EditPlan = Field(default_factory=EditPlan)
    quality_gates: list[QualityGate] = Field(default_factory=list)

    status: StoryboardStatus = StoryboardStatus.DRAFT
    # 成品交付包路径
    deliverables: dict[str, str] = Field(default_factory=dict)
    # 成本与错误记录（不写入任何模型密钥）
    cost_records: list[dict] = Field(default_factory=list)
    error_records: list[dict] = Field(default_factory=list)

    created_at: datetime = Field(default_factory=_utcnow)
    updated_at: datetime = Field(default_factory=_utcnow)

    def total_shot_duration(self) -> float:
        """所有镜头时长之和。"""
        return round(sum(shot.duration_seconds for shot in self.shots), 2)

    def touch(self) -> None:
        """更新修改时间。"""
        self.updated_at = _utcnow()
