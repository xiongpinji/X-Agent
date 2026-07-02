"""Tests for Creative Studio: ShortDramaProducerAgent + quality gates + adapters."""

from __future__ import annotations

import asyncio
import json

from fastapi import FastAPI
from fastapi.testclient import TestClient
import pytest

from backend.app.api.errors import XAgentAPIError, xagent_api_error_handler
from backend.app.api.creative_studio import router as creative_studio_router
from backend.app.core.security import Principal, ROLE_SCOPES
from backend.app.dependencies import get_current_principal
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
from backend.app.core.creative_studio.adapters import ExternalVideoAPIAdapter

VIDEO_PROTOCOL_URL = "https://api.xagent-protocol.invalid/v1/video/generate"
"""Static external-HTTPS protocol URL used only with injected post_json fakes."""


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
async def test_registry_falls_back_to_placeholder(tmp_path):
    """gpt-image-2 requires key; placeholder is always last in chain → must succeed."""
    from backend.app.core.creative_studio.media import MediaProviderRegistry
    reg = MediaProviderRegistry()
    reg.register(PlaceholderImageAdapter())
    result = await reg.generate(MediaRequest(kind=MediaKind.IMAGE, prompt="test", output_path=str(tmp_path / "reg_test.png")))
    assert result.success
    assert result.provider == "placeholder-image"


@pytest.mark.asyncio
async def test_registry_no_provider_returns_failure():
    reg = MediaProviderRegistry()
    result = await reg.generate(MediaRequest(kind=MediaKind.IMAGE, prompt="test"))
    assert not result.success
    assert result.error


@pytest.mark.asyncio
async def test_external_video_adapter_blocks_without_human_review():
    calls = []

    async def post_json(url, payload, headers, timeout):
        calls.append(payload)
        return {"video_url": "https://cdn.example/video.mp4"}

    adp = ExternalVideoAPIAdapter(
        api_url=VIDEO_PROTOCOL_URL,
        api_key="test-key",
        post_json=post_json,
    )
    result = await adp.generate(MediaRequest(kind=MediaKind.VIDEO, prompt="slow push in"))

    assert not result.success
    assert result.error == "human_review_required_before_video_provider_call"
    assert result.metadata["provider_api_call_attempted"] is False
    assert calls == []


@pytest.mark.asyncio
async def test_external_video_adapter_posts_approved_request():
    calls = []

    async def post_json(url, payload, headers, timeout):
        calls.append((url, payload, headers, timeout))
        return {"video_url": "https://cdn.example/video.mp4", "job_id": "job-1"}

    adp = ExternalVideoAPIAdapter(
        api_url=VIDEO_PROTOCOL_URL,
        api_key="test-key",
        provider="protocol-video",
        model="video-model",
        timeout_seconds=12,
        post_json=post_json,
    )
    result = await adp.generate(
        MediaRequest(
            kind=MediaKind.VIDEO,
            prompt="slow push in",
            output_path="shot.mp4",
            params={"human_review_approved": True, "duration_seconds": 5, "aspect_ratio": "9:16"},
        )
    )

    assert result.success
    assert result.output_path == "https://cdn.example/video.mp4"
    assert result.provider == "protocol-video"
    assert result.metadata["provider_api_call_attempted"] is True
    assert result.metadata["job_id"] == "job-1"
    url, payload, headers, timeout = calls[0]
    assert url == VIDEO_PROTOCOL_URL
    assert payload["prompt"] == "slow push in"
    assert payload["model"] == "video-model"
    assert "output_path" not in payload
    assert headers["Authorization"] == "Bearer test-key"
    assert timeout == 12


@pytest.mark.asyncio
async def test_external_video_adapter_rejects_missing_output_reference():
    async def post_json(url, payload, headers, timeout):
        return {"status": "ok"}

    adp = ExternalVideoAPIAdapter(
        api_url=VIDEO_PROTOCOL_URL,
        api_key="test-key",
        post_json=post_json,
    )
    result = await adp.generate(
        MediaRequest(
            kind=MediaKind.VIDEO,
            prompt="slow push in",
            params={"human_review_approved": True},
        )
    )

    assert not result.success
    assert result.error == "external_video_api_missing_output_reference"
    assert result.metadata["provider_api_call_attempted"] is True
    assert result.metadata["response_keys"] == ["status"]


@pytest.mark.asyncio
async def test_external_video_adapter_reports_missing_config_without_call():
    calls = []

    async def post_json(url, payload, headers, timeout):
        calls.append(payload)
        return {"video_url": "https://cdn.example/video.mp4"}

    adp = ExternalVideoAPIAdapter(api_url="", api_key="", post_json=post_json)
    result = await adp.generate(
        MediaRequest(
            kind=MediaKind.VIDEO,
            prompt="slow push in",
            params={"human_review_approved": True},
        )
    )

    assert not result.success
    assert result.error == "external_video_api_not_configured"
    assert result.metadata["provider_api_call_attempted"] is False
    assert calls == []


@pytest.mark.asyncio
async def test_generate_shot_video_requires_review_before_external_call():
    from backend.app.core.creative_studio.wiring import generate_shot_video

    result = await generate_shot_video(video_prompt="camera move", human_review_approved=False)

    assert not result["success"]
    assert result["error"] == "human_review_required_before_video_provider_call"
    assert result["metadata"]["provider_api_call_attempted"] is False


def _principal(role: str = "admin") -> Principal:
    return Principal(
        tenant_id="tenant-1",
        user_id="user-1",
        role=role,
        authenticated=True,
        api_key_id="test-key",
        permission_scope=list(ROLE_SCOPES[role]),
        scopes=list(ROLE_SCOPES[role]),
    )


def _principal_with_scopes(scopes: list[str], role: str = "user") -> Principal:
    return Principal(
        tenant_id="tenant-1",
        user_id="user-1",
        role=role,
        authenticated=True,
        api_key_id="test-key",
        permission_scope=scopes,
        scopes=scopes,
    )


def test_creative_studio_shot_video_endpoint_blocks_without_review():
    app = FastAPI()
    app.include_router(creative_studio_router)
    app.dependency_overrides[get_current_principal] = lambda: _principal()
    try:
        client = TestClient(app)
        response = client.post(
            "/api/v1/creative-studio/shot-video",
            json={"video_prompt": "slow push in", "human_review_approved": False},
        )
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 200
    data = response.json()
    assert not data["success"]
    assert data["error"] == "human_review_required_before_video_provider_call"
    assert data["metadata"]["provider_api_call_attempted"] is False


def test_creative_studio_shot_video_endpoint_requires_control_scope_for_reviewed_execution():
    app = FastAPI()
    app.include_router(creative_studio_router)
    app.add_exception_handler(XAgentAPIError, xagent_api_error_handler)
    app.dependency_overrides[get_current_principal] = lambda: _principal_with_scopes(["workflow:run"])
    try:
        client = TestClient(app)
        response = client.post(
            "/api/v1/creative-studio/shot-video",
            json={"video_prompt": "slow push in", "human_review_approved": True},
        )
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 403
    assert "workflow:control" in response.text


def test_external_video_api_status_reports_redacted_missing_config(monkeypatch):
    from backend.app.core.creative_studio.adapters import external_video_api_status

    monkeypatch.delenv("XAGENT_CREATIVE_VIDEO_API_URL", raising=False)
    monkeypatch.delenv("XAGENT_CREATIVE_VIDEO_API_KEY", raising=False)
    monkeypatch.delenv("XAGENT_CREATIVE_VIDEO_PROVIDER", raising=False)
    monkeypatch.delenv("XAGENT_CREATIVE_VIDEO_MODEL", raising=False)

    status = external_video_api_status()

    assert status["provider"] == "external-video-api"
    assert status["model"] == ""
    assert status["configured"] is False
    assert status["api_url_configured"] is False
    assert status["api_key_configured"] is False
    assert status["api_key_fingerprint"] == ""
    assert status["requires_human_review"] is True
    assert status["provider_api_call_attempted"] is False


def test_external_video_api_status_redacts_configured_secret(monkeypatch):
    from backend.app.core.creative_studio.adapters import external_video_api_status

    monkeypatch.setenv("XAGENT_CREATIVE_VIDEO_API_URL", VIDEO_PROTOCOL_URL)
    monkeypatch.setenv("XAGENT_CREATIVE_VIDEO_API_KEY", "secret-video-key")
    monkeypatch.setenv("XAGENT_CREATIVE_VIDEO_PROVIDER", "protocol-video")
    monkeypatch.setenv("XAGENT_CREATIVE_VIDEO_MODEL", "video-model")

    status = external_video_api_status()

    assert status["provider"] == "protocol-video"
    assert status["model"] == "video-model"
    assert status["configured"] is True
    assert status["api_url_configured"] is True
    assert status["api_key_configured"] is True
    assert status["api_key_fingerprint"]
    assert "secret-video-key" not in json.dumps(status)
    assert VIDEO_PROTOCOL_URL not in json.dumps(status)


def test_creative_studio_video_provider_status_endpoint(monkeypatch):
    monkeypatch.setenv("XAGENT_CREATIVE_VIDEO_API_URL", VIDEO_PROTOCOL_URL)
    monkeypatch.setenv("XAGENT_CREATIVE_VIDEO_API_KEY", "secret-video-key")
    monkeypatch.setenv("XAGENT_CREATIVE_VIDEO_PROVIDER", "protocol-video")
    monkeypatch.setenv("XAGENT_CREATIVE_VIDEO_MODEL", "video-model")

    app = FastAPI()
    app.include_router(creative_studio_router)
    app.dependency_overrides[get_current_principal] = lambda: _principal()
    try:
        client = TestClient(app)
        response = client.get("/api/v1/creative-studio/video-provider-status")
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 200
    data = response.json()
    assert data["configured"] is True
    assert data["provider"] == "protocol-video"
    assert data["model"] == "video-model"
    assert data["endpoints"]["shot_video"] == "/api/v1/creative-studio/shot-video"
    assert "secret-video-key" not in response.text
    assert VIDEO_PROTOCOL_URL not in response.text


def test_external_video_workflow_plan_requires_review():
    from backend.app.core.creative_studio.workflow import build_external_video_workflow_plan

    sb = Storyboard(brief="外部视频工作流", genre="都市")
    sb.shots = [
        Shot(shot_id="S01", duration_seconds=4, video_prompt="slow push"),
        Shot(shot_id="S02", duration_seconds=5, video_prompt="pan right"),
    ]

    plan = build_external_video_workflow_plan(sb, human_review_approved=False)

    assert plan["workflow_status"] == "needs_approval"
    assert plan["dry_run"] is True
    assert plan["approval_required"] is True
    assert plan["risk_level"] == "high"
    assert plan["provider_status"]["provider_api_call_attempted"] is False
    by_id = {node["id"]: node for node in plan["nodes"]}
    assert by_id["human_review"]["status"] == "needs_approval"
    assert by_id["shot_video:S01"]["status"] == "blocked"
    assert all(node["provider_api_call_attempted"] is False for node in plan["nodes"])


def test_external_video_workflow_plan_clamps_max_shots():
    from backend.app.core.creative_studio.workflow import build_external_video_workflow_plan

    sb = Storyboard(brief="外部视频工作流", genre="都市")
    sb.shots = [Shot(shot_id=f"S{i:02d}", duration_seconds=4, video_prompt="slow push") for i in range(12)]

    plan = build_external_video_workflow_plan(sb, human_review_approved=True, max_shots=99)

    assert plan["selected_shot_count"] == 8
    shot_nodes = [node for node in plan["nodes"] if node["type"] == "shot_video"]
    assert len(shot_nodes) == 8


@pytest.mark.asyncio
async def test_external_video_workflow_dry_run_does_not_call_runner():
    from backend.app.core.creative_studio.workflow import run_external_video_workflow

    calls = []
    sb = Storyboard(brief="外部视频工作流", genre="都市")
    sb.shots = [Shot(shot_id="S01", duration_seconds=4, video_prompt="slow push")]

    async def runner(**kwargs):
        calls.append(kwargs)
        return {"success": True, "metadata": {"provider_api_call_attempted": True}}

    result = await run_external_video_workflow(
        sb,
        execute=False,
        human_review_approved=True,
        shot_video_runner=runner,
    )

    assert result["success"] is True
    assert result["workflow_status"] == "dry_run"
    assert result["provider_api_call_attempted"] is False
    assert result["results"] == []
    assert calls == []


@pytest.mark.asyncio
async def test_external_video_workflow_blocks_execution_without_review():
    from backend.app.core.creative_studio.workflow import run_external_video_workflow

    calls = []
    sb = Storyboard(brief="外部视频工作流", genre="都市")
    sb.shots = [Shot(shot_id="S01", duration_seconds=4, video_prompt="slow push")]

    async def runner(**kwargs):
        calls.append(kwargs)
        return {"success": True, "metadata": {"provider_api_call_attempted": True}}

    result = await run_external_video_workflow(
        sb,
        execute=True,
        human_review_approved=False,
        shot_video_runner=runner,
    )

    assert result["success"] is False
    assert result["workflow_status"] == "needs_approval"
    assert result["error"] == "human_review_required_before_video_provider_call"
    assert result["provider_api_call_attempted"] is False
    assert calls == []


@pytest.mark.asyncio
async def test_external_video_workflow_executes_after_review():
    from backend.app.core.creative_studio.workflow import run_external_video_workflow

    calls = []
    sb = Storyboard(brief="外部视频工作流", genre="都市")
    sb.shots = [Shot(shot_id="S01", duration_seconds=4, video_prompt="slow push")]

    async def runner(**kwargs):
        calls.append(kwargs)
        return {
            "success": True,
            "output_path": "https://cdn.example/S01.mp4",
            "provider": "protocol-video",
            "error": None,
            "metadata": {"provider_api_call_attempted": True, "job_id": "job-S01"},
        }

    result = await run_external_video_workflow(
        sb,
        execute=True,
        human_review_approved=True,
        shot_video_runner=runner,
    )

    assert result["success"] is True
    assert result["workflow_status"] == "completed"
    assert result["dry_run"] is False
    assert result["provider_api_call_attempted"] is True
    assert result["results"][0]["shot_id"] == "S01"
    assert calls[0]["human_review_approved"] is True
    assert calls[0]["video_prompt"] == "slow push"


@pytest.mark.asyncio
async def test_external_video_workflow_execution_caps_max_shots():
    from backend.app.core.creative_studio.workflow import run_external_video_workflow

    calls = []
    sb = Storyboard(brief="外部视频工作流", genre="都市")
    sb.shots = [Shot(shot_id=f"S{i:02d}", duration_seconds=4, video_prompt="slow push") for i in range(12)]

    async def runner(**kwargs):
        calls.append(kwargs)
        return {
            "success": True,
            "output_path": "https://cdn.example/shot.mp4",
            "provider": "protocol-video",
            "error": None,
            "metadata": {"provider_api_call_attempted": True},
        }

    result = await run_external_video_workflow(
        sb,
        execute=True,
        human_review_approved=True,
        max_shots=99,
        shot_video_runner=runner,
    )

    assert result["selected_shot_count"] == 8
    assert len(result["results"]) == 8
    assert len(calls) == 8


def test_creative_studio_video_workflow_endpoint_dry_run():
    sb = Storyboard(brief="外部视频工作流", genre="都市")
    sb.shots = [Shot(shot_id="S01", duration_seconds=4, video_prompt="slow push")]

    app = FastAPI()
    app.include_router(creative_studio_router)
    app.dependency_overrides[get_current_principal] = lambda: _principal()
    try:
        client = TestClient(app)
        response = client.post(
            "/api/v1/creative-studio/video-workflow",
            json={"storyboard_json": sb.model_dump(mode="json"), "execute": False},
        )
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 200
    data = response.json()
    assert data["success"] is True
    assert data["workflow_status"] == "dry_run"
    assert data["provider_api_call_attempted"] is False
    assert data["nodes"][0]["id"] == "provider_status"


def test_creative_studio_video_workflow_endpoint_invalid_contract_shape():
    app = FastAPI()
    app.include_router(creative_studio_router)
    app.dependency_overrides[get_current_principal] = lambda: _principal()
    try:
        client = TestClient(app)
        response = client.post(
            "/api/v1/creative-studio/video-workflow",
            json={"storyboard_json": {"shots": "not-a-list"}, "execute": False},
        )
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 200
    data = response.json()
    assert data["success"] is False
    assert data["workflow_status"] == "invalid"
    assert data["dry_run"] is True
    assert data["provider_api_call_attempted"] is False
    assert data["nodes"] == []
    assert data["results"] == []


def test_creative_studio_video_workflow_requires_control_scope_for_execution():
    sb = Storyboard(brief="外部视频工作流", genre="都市")
    sb.shots = [Shot(shot_id="S01", duration_seconds=4, video_prompt="slow push")]

    app = FastAPI()
    app.include_router(creative_studio_router)
    app.add_exception_handler(XAgentAPIError, xagent_api_error_handler)
    app.dependency_overrides[get_current_principal] = lambda: _principal_with_scopes(["workflow:run"])
    try:
        client = TestClient(app)
        response = client.post(
            "/api/v1/creative-studio/video-workflow",
            json={
                "storyboard_json": sb.model_dump(mode="json"),
                "execute": True,
                "human_review_approved": True,
            },
        )
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 403
    assert "workflow:control" in response.text


# ───── tool integration ─────

def test_creative_tools_register_into_explicit_registry():
    from backend.app.core.policy import ToolPolicyEngine
    from backend.app.core.tools import ToolRegistry
    from backend.app.core.creative_studio.wiring import register_creative_tools

    reg = ToolRegistry(ToolPolicyEngine(enable_high_risk_tools=True))
    register_creative_tools(reg)
    names = {t["name"] for t in reg.manifest()}
    assert "create_short_drama_storyboard" in names
    assert "generate_shot_image" in names
    assert "generate_shot_video" in names
    assert "synthesize_voiceover" in names
    assert "compose_short_drama" in names
    by_name = {t["name"]: t for t in reg.manifest()}
    assert by_name["generate_shot_video"]["risk_level"] == "high"
    assert by_name["generate_shot_video"]["required_scope"] == "workflow:control"


@pytest.mark.asyncio
async def test_creative_video_tool_requires_workflow_control_scope():
    from backend.app.core.contracts import RunContext
    from backend.app.core.policy import ToolPolicyEngine
    from backend.app.core.tools import ToolRegistry
    from backend.app.core.creative_studio.wiring import register_creative_tools

    reg = ToolRegistry(ToolPolicyEngine(enable_high_risk_tools=True))
    register_creative_tools(reg)
    result = await reg.execute(
        RunContext(permission_scope=["tools:read"]),
        "generate_shot_video",
        {"video_prompt": "slow push", "human_review_approved": True},
    )

    assert result.success is False
    assert "workflow:control" in result.error


@pytest.mark.asyncio
async def test_creative_video_tool_allows_workflow_control_scope():
    from backend.app.core.contracts import RunContext
    from backend.app.core.policy import ToolPolicyEngine
    from backend.app.core.tools import ToolRegistry
    from backend.app.core.creative_studio.wiring import register_creative_tools

    reg = ToolRegistry(ToolPolicyEngine(enable_high_risk_tools=True))
    register_creative_tools(reg)
    result = await reg.execute(
        RunContext(permission_scope=["tools:read", "workflow:control"]),
        "generate_shot_video",
        {"video_prompt": "slow push", "human_review_approved": False},
    )

    assert result.success is True
    assert result.output["success"] is False
    assert result.output["error"] == "human_review_required_before_video_provider_call"


@pytest.mark.asyncio
async def test_external_video_adapter_logs_sanitized_provider_exception(caplog):
    async def post_json(url, payload, headers, timeout):
        raise RuntimeError(f"boom {VIDEO_PROTOCOL_URL} Bearer secret-video-key")

    adp = ExternalVideoAPIAdapter(
        api_url=VIDEO_PROTOCOL_URL,
        api_key="secret-video-key",
        post_json=post_json,
    )

    with caplog.at_level("WARNING"):
        result = await adp.generate(
            MediaRequest(
                kind=MediaKind.VIDEO,
                prompt="slow push in",
                params={"human_review_approved": True},
            )
        )

    assert not result.success
    assert result.error == "external_video_api_request_failed"
    assert VIDEO_PROTOCOL_URL not in caplog.text
    assert "secret-video-key" not in caplog.text


def test_creative_tools_not_in_default_registry():
    from backend.app.core.policy import ToolPolicyEngine
    from backend.app.core.tools import build_default_tool_registry

    reg = build_default_tool_registry(ToolPolicyEngine(enable_high_risk_tools=True))
    names = {t["name"] for t in reg.manifest()}

    assert "create_short_drama_storyboard" not in names
    assert "generate_shot_image" not in names
    assert "generate_shot_video" not in names
