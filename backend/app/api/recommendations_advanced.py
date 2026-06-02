"""
Advanced Recommendation Scenarios API endpoints.

Provides REST API for:
- Workflow recommendations
- Tool recommendations
- Template recommendations
- Plugin recommendations
- Skill recommendations
- Cross-device synchronization
"""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, Query

from backend.app.api.errors import api_error
from backend.app.core.contracts import ErrorCode
from backend.app.core.recommendation_scenarios import (
    Device,
    ProjectType,
    TaskType,
    initialize_recommenders,
    plugin_recommender,
    skill_recommender,
    sync_manager,
    template_recommender,
    tool_recommender,
    workflow_recommender,
)
from backend.app.core.security import Principal
from backend.app.dependencies import get_current_principal

router = APIRouter(prefix="/api/v1/recommendations", tags=["recommendations"])
PrincipalDependency = Annotated[Principal, Depends(get_current_principal)]


@router.get("/workflows")
async def get_workflow_recommendations(
    principal: PrincipalDependency,
    top_k: int = Query(5, ge=1, le=50),
) -> dict[str, object]:
    """Get workflow recommendations based on user history.

    Args:
        principal: Current user principal
        top_k: Number of recommendations to return

    Returns:
        List of recommended workflows
    """
    if not workflow_recommender:
        raise api_error(500, ErrorCode.INTERNAL_ERROR, "Recommendation engine not initialized")

    user_id = principal.user_id
    recommendations = workflow_recommender.recommend_by_history(user_id, top_k)
    return {"data": recommendations}


@router.get("/workflows/by-task")
async def get_workflow_recommendations_by_task(
    principal: PrincipalDependency,
    task_type: TaskType = Query(TaskType.AUTOMATION),
    top_k: int = Query(5, ge=1, le=50),
) -> dict[str, object]:
    """Get workflow recommendations for specific task type.

    Args:
        principal: Current user principal
        task_type: Type of task
        top_k: Number of recommendations to return

    Returns:
        List of recommended workflows for the task
    """
    if not workflow_recommender:
        raise api_error(500, ErrorCode.INTERNAL_ERROR, "Recommendation engine not initialized")

    user_id = principal.user_id
    recommendations = workflow_recommender.recommend_by_task_type(user_id, task_type, top_k)
    return {"data": recommendations}


@router.get("/tools/by-task")
async def get_tool_recommendations_by_task(
    principal: PrincipalDependency,
    task_type: TaskType = Query(TaskType.DATA_PROCESSING),
    top_k: int = Query(5, ge=1, le=50),
) -> dict[str, object]:
    """Get tool recommendations for specific task type.

    Args:
        principal: Current user principal
        task_type: Type of task
        top_k: Number of recommendations to return

    Returns:
        List of recommended tools for the task
    """
    if not tool_recommender:
        raise api_error(500, ErrorCode.INTERNAL_ERROR, "Recommendation engine not initialized")

    user_id = principal.user_id
    recommendations = tool_recommender.recommend_by_task_type(user_id, task_type, top_k)
    return {"data": recommendations}


@router.get("/templates/by-project")
async def get_template_recommendations_by_project(
    principal: PrincipalDependency,
    project_type: ProjectType = Query(ProjectType.DATA_SCIENCE),
    top_k: int = Query(5, ge=1, le=50),
) -> dict[str, object]:
    """Get template recommendations for specific project type.

    Args:
        principal: Current user principal
        project_type: Type of project
        top_k: Number of recommendations to return

    Returns:
        List of recommended templates for the project
    """
    if not template_recommender:
        raise api_error(500, ErrorCode.INTERNAL_ERROR, "Recommendation engine not initialized")

    user_id = principal.user_id
    recommendations = template_recommender.recommend_by_project_type(user_id, project_type, top_k)
    return {"data": recommendations}


@router.get("/plugins/by-features")
async def get_plugin_recommendations_by_features(
    principal: PrincipalDependency,
    features: list[str] = Query([]),
    top_k: int = Query(5, ge=1, le=50),
) -> dict[str, object]:
    """Get plugin recommendations based on required features.

    Args:
        principal: Current user principal
        features: List of required features
        top_k: Number of recommendations to return

    Returns:
        List of recommended plugins
    """
    if not plugin_recommender:
        raise api_error(500, ErrorCode.INTERNAL_ERROR, "Recommendation engine not initialized")

    if not features:
        raise api_error(400, ErrorCode.INVALID_REQUEST, "At least one feature is required")

    user_id = principal.user_id
    recommendations = plugin_recommender.recommend_by_functionality(user_id, features, top_k)
    return {"data": recommendations}


@router.get("/skills/by-role")
async def get_skill_recommendations_by_role(
    principal: PrincipalDependency,
    role: str = Query("developer"),
    top_k: int = Query(5, ge=1, le=50),
) -> dict[str, object]:
    """Get skill recommendations for specific role.

    Args:
        principal: Current user principal
        role: User role
        top_k: Number of recommendations to return

    Returns:
        List of recommended skills for the role
    """
    if not skill_recommender:
        raise api_error(500, ErrorCode.INTERNAL_ERROR, "Recommendation engine not initialized")

    user_id = principal.user_id
    recommendations = skill_recommender.recommend_by_role(user_id, role, top_k)
    return {"data": recommendations}


@router.post("/devices/register")
async def register_device(
    request: dict[str, object],
    principal: PrincipalDependency,
) -> dict[str, object]:
    """Register a device for cross-device sync.

    Args:
        request: Device information
        principal: Current user principal

    Returns:
        Registered device information
    """
    if not sync_manager:
        raise api_error(500, ErrorCode.INTERNAL_ERROR, "Sync manager not initialized")

    user_id = principal.user_id
    device_id = request.get("device_id")
    device_name = request.get("device_name", "Unknown Device")
    device_type = request.get("device_type", "desktop")
    os = request.get("os", "unknown")

    if not device_id:
        raise api_error(400, ErrorCode.INVALID_REQUEST, "device_id is required")

    device = Device(
        device_id=device_id,
        device_name=device_name,
        device_type=device_type,
        os=os,
    )

    sync_manager.register_device(user_id, device)

    return {
        "device_id": device.device_id,
        "device_name": device.device_name,
        "device_type": device.device_type,
        "os": device.os,
        "registered_at": device.last_sync.isoformat(),
    }


@router.get("/devices")
async def get_devices(principal: PrincipalDependency) -> dict[str, object]:
    """Get all registered devices for user.

    Args:
        principal: Current user principal

    Returns:
        List of registered devices
    """
    if not sync_manager:
        raise api_error(500, ErrorCode.INTERNAL_ERROR, "Sync manager not initialized")

    user_id = principal.user_id
    devices = sync_manager.get_devices(user_id)

    return {
        "data": [
            {
                "device_id": d.device_id,
                "device_name": d.device_name,
                "device_type": d.device_type,
                "os": d.os,
                "last_sync": d.last_sync.isoformat(),
                "is_primary": d.is_primary,
            }
            for d in devices
        ]
    }


@router.post("/sync/pull")
async def pull_preferences(
    request: dict[str, object],
    principal: PrincipalDependency,
) -> dict[str, object]:
    """Pull preferences from server to device.

    Args:
        request: Device ID
        principal: Current user principal

    Returns:
        Synced preferences
    """
    if not sync_manager:
        raise api_error(500, ErrorCode.INTERNAL_ERROR, "Sync manager not initialized")

    user_id = principal.user_id
    device_id = request.get("device_id")

    if not device_id:
        raise api_error(400, ErrorCode.INVALID_REQUEST, "device_id is required")

    preferences = sync_manager.sync_preferences(user_id, device_id)

    return {
        "device_id": device_id,
        "preferences": preferences,
        "synced_at": __import__("datetime").datetime.now(__import__("datetime").UTC).isoformat(),
    }


@router.post("/sync/push")
async def push_preferences(
    request: dict[str, object],
    principal: PrincipalDependency,
) -> dict[str, object]:
    """Push preferences from device to server.

    Args:
        request: Device ID and preferences
        principal: Current user principal

    Returns:
        Sync status
    """
    if not sync_manager:
        raise api_error(500, ErrorCode.INTERNAL_ERROR, "Sync manager not initialized")

    user_id = principal.user_id
    device_id = request.get("device_id")
    preferences = request.get("preferences", {})

    if not device_id:
        raise api_error(400, ErrorCode.INVALID_REQUEST, "device_id is required")

    sync_manager.push_preferences(user_id, device_id, preferences)

    return {
        "device_id": device_id,
        "synced_at": __import__("datetime").datetime.now(__import__("datetime").UTC).isoformat(),
        "status": "success",
    }


@router.get("/sync/status")
async def get_sync_status(principal: PrincipalDependency) -> dict[str, object]:
    """Get sync status for all devices.

    Args:
        principal: Current user principal

    Returns:
        Sync status for each device
    """
    if not sync_manager:
        raise api_error(500, ErrorCode.INTERNAL_ERROR, "Sync manager not initialized")

    user_id = principal.user_id
    status = sync_manager.get_sync_status(user_id)

    return {"devices": status}


@router.post("/sync/resolve-conflicts")
async def resolve_sync_conflicts(
    request: dict[str, object],
    principal: PrincipalDependency,
) -> dict[str, object]:
    """Resolve conflicts between devices.

    Args:
        request: List of conflicts
        principal: Current user principal

    Returns:
        Resolved preferences
    """
    if not sync_manager:
        raise api_error(500, ErrorCode.INTERNAL_ERROR, "Sync manager not initialized")

    user_id = principal.user_id
    conflicts = request.get("conflicts", [])

    if not conflicts:
        raise api_error(400, ErrorCode.INVALID_REQUEST, "conflicts list is required")

    resolved = sync_manager.resolve_conflicts(user_id, conflicts)

    return {
        "resolved": resolved,
        "resolved_at": __import__("datetime").datetime.now(__import__("datetime").UTC).isoformat(),
    }
