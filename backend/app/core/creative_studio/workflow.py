"""Creative Studio external-video workflow boundary.

This module keeps Creative Studio orchestration local to the opt-in feature
slice. It builds a deterministic plan first, then only executes video calls
when the caller explicitly enables execution and confirms human review.
"""

from __future__ import annotations

from typing import Any, Awaitable, Callable

from backend.app.core.contracts import RiskLevel
from backend.app.core.creative_studio.adapters import external_video_api_status
from backend.app.core.creative_studio.storyboard import Storyboard

ShotVideoRunner = Callable[..., Awaitable[dict[str, Any]]]


def _workflow_id(storyboard: Storyboard) -> str:
    return f"creative-video-{storyboard.project_id}"


def _shot_limit(max_shots: int) -> int:
    return min(max(max_shots, 0), 8)


def build_external_video_workflow_plan(
    storyboard: Storyboard,
    *,
    human_review_approved: bool = False,
    max_shots: int = 8,
) -> dict[str, Any]:
    """Return a dry-run-safe workflow plan for storyboard video generation."""

    selected_shots = storyboard.shots[: _shot_limit(max_shots)]
    provider_status = {
        **external_video_api_status(),
        "endpoints": {
            "shot_video": "/api/v1/creative-studio/shot-video",
            "video_workflow": "/api/v1/creative-studio/video-workflow",
        },
    }
    approval_status = "approved" if human_review_approved else "needs_approval"
    nodes: list[dict[str, Any]] = [
        {
            "id": "provider_status",
            "type": "preflight",
            "title": "External video provider status",
            "status": "passed" if provider_status.get("configured") else "blocked",
            "requires_human_review": False,
            "provider_api_call_attempted": False,
        },
        {
            "id": "human_review",
            "type": "approval",
            "title": "Human review before external video API call",
            "status": approval_status,
            "requires_human_review": True,
            "provider_api_call_attempted": False,
            "risk_level": RiskLevel.HIGH.value,
        },
    ]
    for shot in selected_shots:
        nodes.append(
            {
                "id": f"shot_video:{shot.shot_id}",
                "type": "shot_video",
                "title": f"Generate video for {shot.shot_id}",
                "status": "pending" if human_review_approved else "blocked",
                "shot_id": shot.shot_id,
                "duration_seconds": shot.duration_seconds,
                "aspect_ratio": storyboard.aspect_ratio.value,
                "requires_human_review": True,
                "provider_api_call_attempted": False,
            }
        )
    nodes.append(
        {
            "id": "compose_handoff",
            "type": "compose_handoff",
            "title": "Hand off generated clips to compose_short_drama",
            "status": "pending" if human_review_approved and selected_shots else "blocked",
            "requires_human_review": False,
            "provider_api_call_attempted": False,
        }
    )
    return {
        "workflow_id": _workflow_id(storyboard),
        "workflow_name": "Creative Studio external video API workflow",
        "workflow_status": "ready" if human_review_approved else "needs_approval",
        "dry_run": True,
        "approval_required": not human_review_approved,
        "risk_level": RiskLevel.HIGH.value,
        "provider_status": provider_status,
        "selected_shot_count": len(selected_shots),
        "nodes": nodes,
        "edges": [
            {"source": "provider_status", "target": "human_review"},
            *[
                {"source": "human_review", "target": f"shot_video:{shot.shot_id}"}
                for shot in selected_shots
            ],
            *[
                {"source": f"shot_video:{shot.shot_id}", "target": "compose_handoff"}
                for shot in selected_shots
            ],
        ],
        "approval": {
            "required": not human_review_approved,
            "subject_type": "network_request",
            "risk_level": RiskLevel.HIGH.value,
            "reason": "external_video_provider_call_requires_human_review",
        },
    }


async def run_external_video_workflow(
    storyboard: Storyboard,
    *,
    execute: bool = False,
    human_review_approved: bool = False,
    max_shots: int = 8,
    shot_video_runner: ShotVideoRunner | None = None,
) -> dict[str, Any]:
    """Run the opt-in external video workflow.

    Without ``execute`` this returns only the plan. Without human review it
    fails closed before invoking any provider runner.
    """

    plan = build_external_video_workflow_plan(
        storyboard,
        human_review_approved=human_review_approved,
        max_shots=max_shots,
    )
    if not execute:
        return {
            **plan,
            "success": True,
            "workflow_status": "dry_run",
            "provider_api_call_attempted": False,
            "results": [],
        }
    if not human_review_approved:
        return {
            **plan,
            "success": False,
            "workflow_status": "needs_approval",
            "error": "human_review_required_before_video_provider_call",
            "provider_api_call_attempted": False,
            "results": [],
        }

    if shot_video_runner is None:
        from backend.app.core.creative_studio.wiring import generate_shot_video

        shot_video_runner = generate_shot_video

    results: list[dict[str, Any]] = []
    attempted = False
    failed = False
    for shot in storyboard.shots[: _shot_limit(max_shots)]:
        result = await shot_video_runner(
            video_prompt=shot.video_prompt,
            output_path=shot.video_path,
            duration_seconds=int(shot.duration_seconds),
            aspect_ratio=storyboard.aspect_ratio.value,
            human_review_approved=True,
        )
        metadata = result.get("metadata", {}) if isinstance(result, dict) else {}
        attempted = attempted or bool(metadata.get("provider_api_call_attempted"))
        failed = failed or not bool(result.get("success"))
        results.append({"shot_id": shot.shot_id, **result})

    return {
        **plan,
        "success": not failed,
        "workflow_status": "failed" if failed else "completed",
        "dry_run": False,
        "approval_required": False,
        "provider_api_call_attempted": attempted,
        "results": results,
    }
