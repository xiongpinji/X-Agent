"""X-Agent Creative Studio — 短剧成片工作流内核。

围绕"故事板优先"(storyboard-first)原则组织：用户一句话需求经由
ShortDramaProducerAgent 拆解为结构化故事板，所有下游能力
(图片/视频/TTS/字幕/剪辑) 从同一份故事板读取字段，而不是各自重新
理解需求。

公开导出：
- 数据契约：Storyboard / Shot / CharacterCard / SceneCard 等
- 制作人：ShortDramaProducerAgent
- 子代理：SubAgentRole 与团队定义
- 媒体能力抽象：MediaProvider / MediaProviderRegistry
"""

from __future__ import annotations

from backend.app.core.creative_studio.knowledge import (
    CAMERA_KNOWLEDGE,
    DRAMA_GENRES,
    EDIT_KNOWLEDGE,
    LIGHTING_KNOWLEDGE,
    SCREENWRITING_KNOWLEDGE,
    knowledge_pack_for,
)
from backend.app.core.creative_studio.storyboard import (
    AspectRatio,
    AudioPlan,
    CameraSpec,
    CharacterCard,
    EditPlan,
    LightingSpec,
    QualityGate,
    SceneCard,
    Shot,
    ShotContinuity,
    Storyboard,
    StoryboardStatus,
    SubtitleTrack,
)
from backend.app.core.creative_studio.subagents import (
    SUB_AGENT_TEAM,
    SubAgentRole,
    sub_agent_by_id,
)

__all__ = [
    "CAMERA_KNOWLEDGE",
    # knowledge packs
    "DRAMA_GENRES",
    "EDIT_KNOWLEDGE",
    "LIGHTING_KNOWLEDGE",
    "SCREENWRITING_KNOWLEDGE",
    # sub agents
    "SUB_AGENT_TEAM",
    "AspectRatio",
    "AudioPlan",
    "CameraSpec",
    "CharacterCard",
    "EditPlan",
    "LightingSpec",
    "QualityGate",
    "SceneCard",
    "Shot",
    "ShotContinuity",
    # storyboard schema
    "Storyboard",
    "StoryboardStatus",
    "SubAgentRole",
    "SubtitleTrack",
    "knowledge_pack_for",
    "sub_agent_by_id",
]
