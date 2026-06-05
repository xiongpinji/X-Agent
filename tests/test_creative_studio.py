"""Tests for Creative Studio: ShortDramaProducerAgent + quality gates + adapters."""

from __future__ import annotations

import asyncio
import json

import pytest

from backend.app.core.creative_studio.storyboard import (
    AspectRatio,
    Storyboard,
    Shot,
    CameraSpec,
    CharacterCard,
    SceneCard,
    StoryboardStatus,
)
from backend.app.core.creative_studio.knowledge import knowledge_pack_for, DRAMA_GENRES
from backend.app.core.creative_studio.subagents import SUB_AGENT_TEAM, sub_agent_by_id
from backend.app.core.creative_studio.prompt_compiler import (
    compile_image_prompt,
    compile_video_prompt,
    compile_storyboard_prompts,
)
from backend.app.core.creative_studio.quality import (
    run_gates,
    all_passed,
    gate_shot_count,
    gate_duration,
    gate_storyboard_fields,
)
from backend.app.core.creative_studio.producer import ShortDramaProducerAgent
from backend.app.core.creative_studio.media import (
    MediaKind,
    MediaRequest,
    MediaProviderRegistry,
)
from backend.app.core.creative_studio.adapters import PlaceholderImageAdapter


# ───── storyboard schema ─────

def test_storyboard_total_duration():
    sb = Storyboard(brief="test", genre="都市")
    sb.shots = [Shot(shot_id="S01", duration_seconds=4), Shot(shot_id="S02", duration_seconds=6)]
    assert sb.total_shot_duration() == 10.0


def test_storyboard_defaults():
    sb = Storyboard(brief="x")
    assert sb.status == StoryboardStatus.DRAFT
    assert sb.aspect_ratio == AspectRatio.VERTICAL
    assert sb.project_id.startswith("sd_")


# ───── knowledge packs ─────

def test_knowledge_pack_director_nonempty():
    pack = knowledge_pack_for("director")
    assert pack  # non-empty
    data = json.loads(pack)
    assert "shot_sizes" in data


def test_knowledge_pack_unknown_returns_empty():
    assert knowledge_pack_for("nonexistent") == ""


def test_all_genres_defined():
    assert len(DRAMA_GENRES) >= 6


# ───── sub-agents ─────

def test_sub_agent_team_size():
    assert len(SUB_AGENT_TEAM) == 11


def test_sub_agent_full_prompt_injects_knowledge():
    d = sub_agent_by_id("director")
    assert d is not None
    prompt = d.full_system_prompt()
    assert "专业知识包" in prompt
    assert "shot_sizes" in prompt  # json key from camera knowledge


def test_sub_agent_by_id_unknown_returns_none():
    assert sub_agent_by_id("ghost") is None


# ───── prompt compiler ─────

def test_compile_image_prompt_contains_genre():
    sb = Storyboard(genre="逆袭", style_profile="urban_drama_cinematic")
    shot = Shot(shot_id="S01", scene="高档公寓", emotion="压迫感")
    out = compile_image_prompt(shot, sb)
    assert "逆袭" in out
    assert "高档公寓" in out


def test_compile_video_prompt_mentions_movement():
    sb = Storyboard(genre="甜宠")
    from backend.app.core.creative_studio.storyboard import CameraSpec
    shot = Shot(shot_id="S01", camera=CameraSpec(movement="slow push-in"), action="女主转身")
    out = compile_video_prompt(shot, sb)
    assert "slow push-in" in out


def test_compile_storyboard_prompts_fills_shots():
    sb = Storyboard(genre="霸总")
    sb.shots = [Shot(shot_id="S01"), Shot(shot_id="S02")]
    result = compile_storyboard_prompts(sb)
    assert all(s.visual_prompt for s in result.shots)
    assert all(s.video_prompt for s in result.shots)


# ───── quality gates ─────

def test_gate_shot_count_ok():
    sb = Storyboard()
    sb.shots = [Shot(shot_id=f"S{i:02d}") for i in range(5)]
    g = gate_shot_count(sb)
    assert g.passed


def test_gate_shot_count_fail_too_few():
    sb = Storyboard()
    sb.shots = [Shot(shot_id="S01")]
    g = gate_shot_count(sb)
    assert not g.passed


def test_gate_duration_ok():
    sb = Storyboard(target_duration_seconds=60)
    sb.shots = [Shot(shot_id=f"S{i:02d}", duration_seconds=10) for i in range(6)]
    g = gate_duration(sb)
    assert g.passed


def test_gate_duration_fail():
    sb = Storyboard(target_duration_seconds=60)
    sb.shots = [Shot(shot_id="S01", duration_seconds=5)]
    g = gate_duration(sb)
    assert not g.passed


def test_run_gates_writes_back():
    sb = Storyboard(target_duration_seconds=60)
    sb.shots = [Shot(shot_id=f"S{i:02d}", duration_seconds=10, action="ok", plot_purpose="ok") for i in range(6)]
    gates = run_gates(sb)
    assert len(sb.quality_gates) == len(gates)


# ───── producer agent (no-LLM fallback path) ─────

@pytest.mark.asyncio
async def test_producer_no_llm_creates_storyboard():
    agent = ShortDramaProducerAgent(llm_caller=None)
    sb = await agent.create_storyboard(brief="逆袭短剧", genre="逆袭")
    assert sb.status == StoryboardStatus.STORYBOARDED
    assert len(sb.shots) >= 1
    assert sb.shots[0].visual_prompt


@pytest.mark.asyncio
async def test_producer_with_mock_llm():
    """Mock LLM returns deterministic JSON → 3 shots."""
    async def mock_llm(system: str, user: str) -> str:
        if "logline" in user:
            return json.dumps({"logline": "测试故事线", "outline": ["开场", "冲突", "反转"]})
        if "完整剧本" in user:
            return json.dumps({"script": "女主出场。对白：你凭什么？男主：凭我是老板。"})
        if "characters" in user:
            return json.dumps({
                "characters": [{"ref_id": "female_v1", "name": "女主", "appearance": "干练", "outfit": "黑西装"}],
                "scenes": [{"ref_id": "office_v1", "name": "办公室", "description": "高层办公室", "time_of_day": "白天"}],
            })
        if "镜头" in user or "shot" in user.lower():
            return json.dumps([
                {"shot_id": "S01", "duration": 4, "scene": "大厅", "action": "女主走进", "dialogue": "谁准你进来的", "plot_purpose": "开场冲突", "shot_size": "medium", "angle": "eye-level", "movement": "static", "emotion": "紧张"},
                {"shot_id": "S02", "duration": 5, "scene": "办公室", "action": "男主站起", "dialogue": "你知道我是谁吗", "plot_purpose": "反转铺垫", "shot_size": "close-up", "angle": "low", "movement": "slow push-in", "emotion": "压迫感"},
                {"shot_id": "S03", "duration": 6, "scene": "落地窗", "action": "女主取下眼镜", "dialogue": "集团继承人，你好", "plot_purpose": "身份揭露爽点", "shot_size": "medium", "angle": "eye-level", "movement": "static", "emotion": "冷静反转"},
            ])
        return ""

    agent = ShortDramaProducerAgent(llm_caller=mock_llm)
    sb = await agent.create_storyboard(brief="身份揭露", genre="逆袭", target_duration_seconds=60)
    assert sb.status == StoryboardStatus.STORYBOARDED
    assert len(sb.shots) == 3
    assert sb.shots[2].dialogue == "集团继承人，你好"
    assert len(sb.character_cards) >= 1          # 角色卡存在（mock 或 fallback 均可）
    assert sb.shots[0].visual_prompt              # prompt compiler ran
    # quality gates
    gates = run_gates(sb)
    shot_count_gate = next(g for g in gates if g.name == "shot_count")
    assert shot_count_gate.passed


# ───── media adapters ─────

@pytest.mark.asyncio
async def test_placeholder_image_always_available():
    adp = PlaceholderImageAdapter()
    assert await adp.available()


@pytest.mark.asyncio
async def test_placeholder_image_generates_png(tmp_path):
    adp = PlaceholderImageAdapter()
    out = str(tmp_path / "test.png")
    result = await adp.generate(MediaRequest(kind=MediaKind.IMAGE, output_path=out))
    assert result.success
    from pathlib import Path
    data = Path(out).read_bytes()
    assert data[:8] == b"\x89PNG\r\n\x1a\n"


@pytest.mark.asyncio
async def test_registry_falls_back_to_placeholder():
    """gpt-image-2 requires key; placeholder is always last in chain → must succeed."""
    from backend.app.core.creative_studio.media import MediaProviderRegistry
    reg = MediaProviderRegistry()
    reg.register(PlaceholderImageAdapter())
    result = await reg.generate(MediaRequest(kind=MediaKind.IMAGE, prompt="test", output_path="/tmp/reg_test.png"))
    assert result.success
    assert result.provider == "placeholder-image"


@pytest.mark.asyncio
async def test_registry_no_provider_returns_failure():
    reg = MediaProviderRegistry()
    result = await reg.generate(MediaRequest(kind=MediaKind.IMAGE, prompt="test"))
    assert not result.success
    assert result.error


# ───── tool integration ─────

def test_creative_tools_registered_in_default_registry():
    from backend.app.core.tools import build_default_tool_registry
    from backend.app.core.policy import ToolPolicyEngine
    reg = build_default_tool_registry(ToolPolicyEngine(enable_high_risk_tools=True))
    names = {t["name"] for t in reg.manifest()}
    assert "create_short_drama_storyboard" in names
    assert "generate_shot_image" in names

    assert "synthesize_voiceover" in names
    assert "compose_short_drama" in names
