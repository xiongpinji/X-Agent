"""ShortDramaProducerAgent — 短剧制作人智能体。

职责：接收一句话需求 → 识别短剧任务 → 调度子代理团队 → 维护故事板状态
→ 调用多模型路由 → 控制成本/超时/重试 → 聚合成品交付包。

设计：制作人不直接调用模型 SDK，而是通过注入的 llm_caller（默认走项目
LLMRouter）以不同子代理的 system prompt 调用文本模型；媒体生成走注入的
MediaProviderRegistry。这样既复用现有路由/记忆/审计，又保持子代理分工。

LLM 不可用或解析失败时，每一步都有确定性回退，保证流程不中断（出保底成片）。
"""

from __future__ import annotations

import json
import logging
from typing import Any, Awaitable, Callable

from backend.app.core.creative_studio.media import MediaProviderRegistry, media_registry
from backend.app.core.creative_studio.prompt_compiler import compile_storyboard_prompts
from backend.app.core.creative_studio.quality import STORYBOARD_GATES, run_gates
from backend.app.core.creative_studio.storyboard import (
    AspectRatio,
    CameraSpec,
    CharacterCard,
    LightingSpec,
    SceneCard,
    Shot,
    ShotContinuity,
    Storyboard,
    StoryboardStatus,
    SubtitleTrack,
)
from backend.app.core.creative_studio.subagents import sub_agent_by_id

logger = logging.getLogger(__name__)

# llm_caller(system_prompt, user_prompt) -> str
LLMCaller = Callable[[str, str], Awaitable[str]]


def _safe_json(text: str) -> Any:
    """尽力从模型输出中解析 JSON，失败返回 None。"""
    text = (text or "").strip()
    if not text:
        return None
    # 去掉 ```json fenced block
    if text.startswith("```"):
        text = text.strip("`")
        if text.lower().startswith("json"):
            text = text[4:]
    # 截取第一个 { 或 [ 到最后一个 } 或 ]
    for open_c, close_c in (("[", "]"), ("{", "}")):
        i, j = text.find(open_c), text.rfind(close_c)
        if i != -1 and j != -1 and j > i:
            try:
                return json.loads(text[i : j + 1])
            except Exception:
                continue
    return None


class ShortDramaProducerAgent:
    """短剧制作人，编排故事板优先的成片流水线。"""

    def __init__(
        self,
        llm_caller: LLMCaller | None = None,
        media: MediaProviderRegistry | None = None,
        max_shots: int = 8,
    ) -> None:
        self._llm = llm_caller
        self._media = media or media_registry
        self._max_shots = max_shots

    async def _ask(self, sub_agent_id: str, user_prompt: str) -> str:
        """以某子代理身份调用文本模型；无 llm_caller 时返回空串触发回退。"""
        role = sub_agent_by_id(sub_agent_id)
        if role is None or self._llm is None:
            return ""
        try:
            return await self._llm(role.full_system_prompt(), user_prompt)
        except Exception as exc:  # noqa: BLE001
            logger.warning("sub-agent %s call failed: %s", sub_agent_id, exc)
            return ""

    async def _plan(self, sb: Storyboard) -> None:
        """选题策划：大纲与爆款结构。"""
        resp = await self._ask(
            "planner",
            f"类型:{sb.genre} 平台:{sb.platform} 时长:{sb.target_duration_seconds}s\n"
            f"需求:{sb.brief}\n"
            "输出JSON: {\"logline\":\"...\",\"outline\":[\"...\",\"...\"]}",
        )
        data = _safe_json(resp)
        if isinstance(data, dict):
            sb.logline = str(data.get("logline", "")).strip() or sb.brief
            outline = data.get("outline", [])
            sb.outline = [str(x) for x in outline if x] if outline else [sb.brief]
        else:
            sb.logline = sb.brief
            sb.outline = [sb.brief]

    async def _write_script(self, sb: Storyboard) -> None:
        """编剧：台词与剧情节拍。"""
        outline_txt = "\n".join(f"{i+1}. {s}" for i, s in enumerate(sb.outline))
        resp = await self._ask(
            "screenwriter",
            f"类型:{sb.genre} 大纲:\n{outline_txt}\n"
            "输出JSON: {\"script\":\"完整剧本文本，含台词\"}",
        )
        data = _safe_json(resp)
        if isinstance(data, dict) and data.get("script"):
            sb.script = str(data["script"])
        elif resp:
            sb.script = resp
        else:
            sb.script = "\n".join(sb.outline)

    async def _build_cards(self, sb: Storyboard, num_characters: int) -> None:
        """美术指导：角色卡 + 场景卡。"""
        resp = await self._ask(
            "art",
            f"类型:{sb.genre} 角色数:{num_characters} 剧本摘要:{sb.script[:400]}\n"
            "输出JSON: {\"characters\":[{\"ref_id\":\"...\",\"name\":\"...\",\"appearance\":\"...\",\"outfit\":\"...\"}],"
            "\"scenes\":[{\"ref_id\":\"...\",\"name\":\"...\",\"description\":\"...\",\"time_of_day\":\"...\"}]}",
        )
        data = _safe_json(resp)
        if isinstance(data, dict):
            for c in data.get("characters", []):
                sb.character_cards.append(
                    CharacterCard(
                        ref_id=str(c.get("ref_id", f"char_{len(sb.character_cards)}")),
                        name=str(c.get("name", "")),
                        appearance=str(c.get("appearance", "")),
                        outfit=str(c.get("outfit", "")),
                    )
                )
            for s in data.get("scenes", []):
                sb.scene_cards.append(
                    SceneCard(
                        ref_id=str(s.get("ref_id", f"scene_{len(sb.scene_cards)}")),
                        name=str(s.get("name", "")),
                        description=str(s.get("description", "")),
                        time_of_day=str(s.get("time_of_day", "")),
                    )
                )
        # 保底：至少有一张角色卡和场景卡
        if not sb.character_cards:
            sb.character_cards = [CharacterCard(ref_id="lead_v1", name="主角")]
        if not sb.scene_cards:
            sb.scene_cards = [SceneCard(ref_id="scene_main_v1", name="主场景")]

    async def _build_shots(self, sb: Storyboard) -> None:
        """分镜导演 + 摄影灯光：镜头级故事板。"""
        char_ref = sb.character_cards[0].ref_id if sb.character_cards else "lead_v1"
        scene_ref = sb.scene_cards[0].ref_id if sb.scene_cards else "scene_main_v1"
        target_per_shot = sb.target_duration_seconds / max(self._max_shots, 3)

        resp = await self._ask(
            "director",
            f"类型:{sb.genre} 目标时长:{sb.target_duration_seconds}s 最多{self._max_shots}个镜头\n"
            f"剧本:{sb.script[:600]}\n"
            "输出JSON数组，每个镜头: {\"shot_id\":\"S01\",\"duration\":4,"
            "\"scene\":\"...\",\"action\":\"...\",\"dialogue\":\"...\","
            "\"plot_purpose\":\"...\",\"shot_size\":\"medium\",\"angle\":\"eye-level\","
            "\"movement\":\"static\",\"emotion\":\"...\"}",
        )
        shots_data = _safe_json(resp)
        if isinstance(shots_data, list):
            for i, item in enumerate(shots_data[: self._max_shots]):
                if not isinstance(item, dict):
                    continue
                sb.shots.append(
                    Shot(
                        shot_id=str(item.get("shot_id", f"S{i+1:02d}")),
                        duration_seconds=float(item.get("duration", target_per_shot)),
                        scene=str(item.get("scene", "")),
                        action=str(item.get("action", "")),
                        dialogue=str(item.get("dialogue", "")),
                        subtitle=str(item.get("dialogue", "")),
                        plot_purpose=str(item.get("plot_purpose", "")),
                        emotion=str(item.get("emotion", "")),
                        camera=CameraSpec(
                            shot_size=str(item.get("shot_size", "medium")),
                            angle=str(item.get("angle", "eye-level")),
                            movement=str(item.get("movement", "static")),
                        ),
                        lighting=LightingSpec(
                            style="low-key cinematic" if "悬疑" in sb.genre or "复仇" in sb.genre else "soft cinematic",
                            mood=str(item.get("emotion", "")),
                        ),
                        continuity=ShotContinuity(character_ref=char_ref, scene_ref=scene_ref),
                    )
                )

        # 保底：用大纲节拍生成最少 3 个镜头
        if not sb.shots:
            beats = (sb.outline or [sb.brief])[: self._max_shots]
            dur = sb.target_duration_seconds / max(len(beats), 3)
            for i, beat in enumerate(beats):
                sb.shots.append(
                    Shot(
                        shot_id=f"S{i+1:02d}",
                        duration_seconds=round(dur, 1),
                        scene="主场景",
                        action=beat,
                        dialogue="",
                        plot_purpose=beat,
                        camera=CameraSpec(),
                        lighting=LightingSpec(),
                        continuity=ShotContinuity(character_ref=char_ref, scene_ref=scene_ref),
                    )
                )

    def _build_subtitles(self, sb: Storyboard) -> None:
        """从镜头台词生成字幕轨（时间轴估算）。"""
        cursor = 0.0
        for shot in sb.shots:
            if shot.dialogue:
                sb.subtitle_tracks.append(
                    SubtitleTrack(
                        shot_id=shot.shot_id,
                        start_seconds=cursor,
                        end_seconds=cursor + shot.duration_seconds,
                        text=shot.dialogue,
                    )
                )
            cursor += shot.duration_seconds

    def to_workflow_task(self, sb: Storyboard) -> dict:
        """导出为 X-Agent 工作流任务格式，供 API 接收和持久化。"""
        return {
            "task": f"短剧成片: {sb.title or sb.brief[:40]}",
            "extra_context": {
                "creative_studio": True,
                "storyboard_id": sb.project_id,
                "genre": sb.genre,
                "platform": sb.platform,
                "target_duration": sb.target_duration_seconds,
                "shot_count": len(sb.shots),
            },
        }
    async def create_storyboard(
        self,
        brief: str,
        genre: str = "都市",
        platform: str = "douyin",
        target_duration_seconds: int = 60,
        characters: int = 2,
    ) -> Storyboard:
        """从一句话需求生成完整故事板（drafт → storyboarded）。"""
        sb = Storyboard(
            brief=brief,
            genre=genre,
            platform=platform,
            target_duration_seconds=target_duration_seconds,
            aspect_ratio=AspectRatio.VERTICAL,
        )

        await self._plan(sb)
        await self._write_script(sb)
        await self._build_cards(sb, characters)
        await self._build_shots(sb)
        self._build_subtitles(sb)

        compile_storyboard_prompts(sb)
        run_gates(sb, STORYBOARD_GATES)
        sb.status = StoryboardStatus.STORYBOARDED
        sb.touch()
        return sb
