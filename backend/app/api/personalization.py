"""
Personalization API endpoints for X-Agent.

Provides REST API for:
- User preference management
- Recommendation retrieval
- Feedback recording
- Profile management
- A/B testing
"""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, Query

from backend.app.api.errors import api_error
from backend.app.core.contracts import ErrorCode
from backend.app.core.personalization import (
    ABTestManager,
    FeedbackStore,
    FeedbackType,
    ItemCatalog,
    LayoutPreference,
    PreferenceStore,
    PreferenceType,
    RecommendationEngine,
    RecommendationType,
    ShortcutPreference,
    ThemePreference,
    WidgetPreference,
    WorkspacePreference,
)
from backend.app.core.security import Principal
from backend.app.dependencies import enforce_scope, get_current_principal

router = APIRouter(prefix="/api/v1/personalization", tags=["personalization"])
PrincipalDependency = Annotated[Principal, Depends(get_current_principal)]


# Initialize stores
preference_store = PreferenceStore()
feedback_store = FeedbackStore()
item_catalog = ItemCatalog()
recommendation_engine = RecommendationEngine(preference_store, feedback_store, item_catalog)
ab_test_manager = ABTestManager()


@router.get("/preferences")
async def get_preferences(
    principal: PrincipalDependency,
    preference_type: PreferenceType | None = Query(None),
) -> dict[str, object]:
    """Get user preferences.

    Args:
        principal: Current user principal
        preference_type: Optional filter by preference type

    Returns:
        List of user preferences
    """
    user_id = principal.user_id
    prefs = preference_store.get_all_preferences(user_id, preference_type)
    return {
        "data": [
            {
                "id": p.id,
                "type": p.preference_type.value,
                "key": p.key,
                "value": p.value,
                "updated_at": p.updated_at.isoformat(),
            }
            for p in prefs
        ]
    }


@router.put("/preferences")
async def update_preferences(
    request: dict[str, object],
    principal: PrincipalDependency,
) -> dict[str, object]:
    """Update user preferences.

    Args:
        request: Preference update request with type, key, and value
        principal: Current user principal

    Returns:
        Updated preference
    """
    user_id = principal.user_id
    preference_type_str = request.get("type")
    key = request.get("key")
    value = request.get("value", {})

    if not preference_type_str or not key:
        raise api_error(400, ErrorCode.INVALID_REQUEST, "Missing type or key")

    try:
        preference_type = PreferenceType(preference_type_str)
    except ValueError:
        raise api_error(400, ErrorCode.INVALID_REQUEST, f"Invalid preference type: {preference_type_str}")

    pref = preference_store.save_preference(user_id, preference_type, key, value)
    return {
        "id": pref.id,
        "type": pref.preference_type.value,
        "key": pref.key,
        "value": pref.value,
        "updated_at": pref.updated_at.isoformat(),
    }


@router.delete("/preferences/{preference_type}/{key}")
async def delete_preference(
    preference_type: str,
    key: str,
    principal: PrincipalDependency,
) -> dict[str, object]:
    """Delete user preference.

    Args:
        preference_type: Type of preference to delete
        key: Preference key
        principal: Current user principal

    Returns:
        Success status
    """
    user_id = principal.user_id
    try:
        pref_type = PreferenceType(preference_type)
    except ValueError:
        raise api_error(400, ErrorCode.INVALID_REQUEST, f"Invalid preference type: {preference_type}")

    success = preference_store.delete_preference(user_id, pref_type, key)
    if not success:
        raise api_error(404, ErrorCode.RESOURCE_NOT_FOUND, "Preference not found")

    return {"success": True}


@router.get("/profile")
async def get_profile(principal: PrincipalDependency) -> dict[str, object]:
    """Get user profile for personalization.

    Args:
        principal: Current user principal

    Returns:
        User profile with preferences and usage patterns
    """
    user_id = principal.user_id
    profile = preference_store.get_or_create_profile(user_id, principal.role)
    return {
        "user_id": profile.user_id,
        "role": profile.role,
        "skill_level": profile.skill_level,
        "preferences": profile.preferences,
        "usage_patterns": profile.usage_patterns,
        "interests": profile.interests,
        "created_at": profile.created_at.isoformat(),
        "updated_at": profile.updated_at.isoformat(),
    }


@router.put("/profile")
async def update_profile(
    request: dict[str, object],
    principal: PrincipalDependency,
) -> dict[str, object]:
    """Update user profile.

    Args:
        request: Profile update request
        principal: Current user principal

    Returns:
        Updated profile
    """
    user_id = principal.user_id
    profile = preference_store.update_profile(user_id, **request)
    return {
        "user_id": profile.user_id,
        "role": profile.role,
        "skill_level": profile.skill_level,
        "preferences": profile.preferences,
        "usage_patterns": profile.usage_patterns,
        "interests": profile.interests,
        "created_at": profile.created_at.isoformat(),
        "updated_at": profile.updated_at.isoformat(),
    }


@router.get("/recommendations")
async def get_recommendations(
    principal: PrincipalDependency,
    item_type: RecommendationType = Query(RecommendationType.WORKFLOW),
    top_k: int = Query(5, ge=1, le=50),
) -> dict[str, object]:
    """Get personalized recommendations.

    Args:
        principal: Current user principal
        item_type: Type of items to recommend
        top_k: Number of recommendations to return

    Returns:
        List of recommendations with scores and reasons
    """
    user_id = principal.user_id
    recommendations = recommendation_engine.recommend_personalized(user_id, item_type, top_k)
    return {
        "data": [
            {
                "item_id": rec.item_id,
                "item_name": rec.item_name,
                "item_type": rec.item_type.value,
                "score": rec.score,
                "reason": rec.reason,
                "algorithm": rec.algorithm,
                "confidence": rec.confidence,
            }
            for rec in recommendations
        ]
    }


@router.post("/feedback")
async def record_feedback(
    request: dict[str, object],
    principal: PrincipalDependency,
) -> dict[str, object]:
    """Record user feedback for recommendations.

    Args:
        request: Feedback request with item_id, item_type, feedback_type, etc.
        principal: Current user principal

    Returns:
        Recorded feedback
    """
    user_id = principal.user_id
    item_id = request.get("item_id")
    item_type_str = request.get("item_type")
    feedback_type_str = request.get("feedback_type", "implicit")
    rating = request.get("rating")
    dwell_time = request.get("dwell_time")
    action_taken = request.get("action_taken", False)

    if not item_id or not item_type_str:
        raise api_error(400, ErrorCode.INVALID_REQUEST, "Missing item_id or item_type")

    try:
        item_type = RecommendationType(item_type_str)
        feedback_type = FeedbackType(feedback_type_str)
    except ValueError as e:
        raise api_error(400, ErrorCode.INVALID_REQUEST, f"Invalid type: {e}")

    feedback = feedback_store.record_feedback(
        user_id=user_id,
        item_id=item_id,
        item_type=item_type,
        feedback_type=feedback_type,
        rating=rating,
        dwell_time=dwell_time,
        action_taken=action_taken,
    )

    return {
        "id": feedback.id,
        "user_id": feedback.user_id,
        "item_id": feedback.item_id,
        "item_type": feedback.item_type.value,
        "feedback_type": feedback.feedback_type.value,
        "rating": feedback.rating,
        "dwell_time": feedback.dwell_time,
        "action_taken": feedback.action_taken,
        "created_at": feedback.created_at.isoformat(),
    }


@router.get("/theme")
async def get_theme_preference(principal: PrincipalDependency) -> dict[str, object]:
    """Get user theme preference.

    Args:
        principal: Current user principal

    Returns:
        Theme configuration
    """
    user_id = principal.user_id
    pref = preference_store.get_preference(user_id, PreferenceType.THEME, "default")
    if pref:
        return pref.value
    return ThemePreference().model_dump()


@router.put("/theme")
async def update_theme_preference(
    request: dict[str, object],
    principal: PrincipalDependency,
) -> dict[str, object]:
    """Update user theme preference.

    Args:
        request: Theme configuration
        principal: Current user principal

    Returns:
        Updated theme
    """
    user_id = principal.user_id
    theme = ThemePreference(**request)
    pref = preference_store.save_preference(user_id, PreferenceType.THEME, "default", theme.model_dump())
    return pref.value


@router.get("/layout")
async def get_layout_preference(principal: PrincipalDependency) -> dict[str, object]:
    """Get user layout preference.

    Args:
        principal: Current user principal

    Returns:
        Layout configuration
    """
    user_id = principal.user_id
    pref = preference_store.get_preference(user_id, PreferenceType.LAYOUT, "default")
    if pref:
        return pref.value
    return LayoutPreference().model_dump()


@router.put("/layout")
async def update_layout_preference(
    request: dict[str, object],
    principal: PrincipalDependency,
) -> dict[str, object]:
    """Update user layout preference.

    Args:
        request: Layout configuration
        principal: Current user principal

    Returns:
        Updated layout
    """
    user_id = principal.user_id
    layout = LayoutPreference(**request)
    pref = preference_store.save_preference(user_id, PreferenceType.LAYOUT, "default", layout.model_dump())
    return pref.value


@router.get("/shortcuts")
async def get_shortcuts_preference(principal: PrincipalDependency) -> dict[str, object]:
    """Get user keyboard shortcuts preference.

    Args:
        principal: Current user principal

    Returns:
        Shortcuts configuration
    """
    user_id = principal.user_id
    pref = preference_store.get_preference(user_id, PreferenceType.SHORTCUTS, "default")
    if pref:
        return pref.value
    return ShortcutPreference().model_dump()


@router.put("/shortcuts")
async def update_shortcuts_preference(
    request: dict[str, object],
    principal: PrincipalDependency,
) -> dict[str, object]:
    """Update user keyboard shortcuts preference.

    Args:
        request: Shortcuts configuration
        principal: Current user principal

    Returns:
        Updated shortcuts
    """
    user_id = principal.user_id
    shortcuts = ShortcutPreference(**request)
    pref = preference_store.save_preference(user_id, PreferenceType.SHORTCUTS, "default", shortcuts.model_dump())
    return pref.value


@router.get("/widgets")
async def get_widgets_preference(principal: PrincipalDependency) -> dict[str, object]:
    """Get user dashboard widgets preference.

    Args:
        principal: Current user principal

    Returns:
        Widgets configuration
    """
    user_id = principal.user_id
    pref = preference_store.get_preference(user_id, PreferenceType.WIDGETS, "default")
    if pref:
        return pref.value
    return WidgetPreference().model_dump()


@router.put("/widgets")
async def update_widgets_preference(
    request: dict[str, object],
    principal: PrincipalDependency,
) -> dict[str, object]:
    """Update user dashboard widgets preference.

    Args:
        request: Widgets configuration
        principal: Current user principal

    Returns:
        Updated widgets
    """
    user_id = principal.user_id
    widgets = WidgetPreference(**request)
    pref = preference_store.save_preference(user_id, PreferenceType.WIDGETS, "default", widgets.model_dump())
    return pref.value


@router.get("/workspace/{workspace_id}")
async def get_workspace_preference(
    workspace_id: str,
    principal: PrincipalDependency,
) -> dict[str, object]:
    """Get workspace state preference.

    Args:
        workspace_id: Workspace ID
        principal: Current user principal

    Returns:
        Workspace state
    """
    user_id = principal.user_id
    pref = preference_store.get_preference(user_id, PreferenceType.WORKSPACE, workspace_id)
    if pref:
        return pref.value
    return WorkspacePreference(workspace_id=workspace_id).model_dump()


@router.put("/workspace/{workspace_id}")
async def update_workspace_preference(
    workspace_id: str,
    request: dict[str, object],
    principal: PrincipalDependency,
) -> dict[str, object]:
    """Update workspace state preference.

    Args:
        workspace_id: Workspace ID
        request: Workspace state
        principal: Current user principal

    Returns:
        Updated workspace state
    """
    user_id = principal.user_id
    workspace = WorkspacePreference(workspace_id=workspace_id, **request)
    pref = preference_store.save_preference(user_id, PreferenceType.WORKSPACE, workspace_id, workspace.model_dump())
    return pref.value


@router.post("/ab-test")
async def create_ab_test(
    request: dict[str, object],
    principal: PrincipalDependency,
) -> dict[str, object]:
    """Create A/B test for recommendations.

    Args:
        request: A/B test configuration with test_id and variants
        principal: Current user principal

    Returns:
        Assigned variant and recommendations
    """
    user_id = principal.user_id
    test_id = request.get("test_id")
    variants = request.get("variants", {})

    if not test_id or not variants:
        raise api_error(400, ErrorCode.INVALID_REQUEST, "Missing test_id or variants")

    variant = ab_test_manager.create_test(test_id, variants, user_id)
    return {
        "test_id": test_id,
        "user_id": user_id,
        "variant": variant,
        "recommendations": variants[variant],
    }


@router.post("/ab-test/{test_id}/conversion")
async def record_ab_test_conversion(
    test_id: str,
    principal: PrincipalDependency,
) -> dict[str, object]:
    """Record conversion for A/B test.

    Args:
        test_id: A/B test ID
        principal: Current user principal

    Returns:
        Success status
    """
    user_id = principal.user_id
    ab_test_manager.record_conversion(test_id, user_id)
    return {"success": True}


@router.get("/ab-test/{test_id}/results")
async def get_ab_test_results(
    test_id: str,
    principal: PrincipalDependency,
) -> dict[str, object]:
    """Get A/B test results.

    Args:
        test_id: A/B test ID
        principal: Current user principal

    Returns:
        Test results with conversion rates
    """
    enforce_scope(principal, "analytics:read")
    results = ab_test_manager.get_test_results(test_id)
    return results
