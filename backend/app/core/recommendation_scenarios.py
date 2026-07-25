"""
Advanced Recommendation Scenarios and Cross-Device Sync

Provides:
- Workflow recommendations based on history
- Tool recommendations based on task type
- Template recommendations based on project type
- Plugin recommendations based on functionality
- Skill recommendations based on user role
- Cross-device preference synchronization
"""

from __future__ import annotations

from datetime import UTC, datetime
from enum import StrEnum
from threading import RLock
from typing import Any
from uuid import uuid4

from pydantic import BaseModel, Field

from backend.app.core.personalization import (
    FeedbackStore,
    PreferenceStore,
    RecommendationEngine,
    RecommendationType,
)


class TaskType(StrEnum):
    """Types of tasks."""
    DATA_PROCESSING = "data_processing"
    WEB_SCRAPING = "web_scraping"
    API_INTEGRATION = "api_integration"
    AUTOMATION = "automation"
    ANALYSIS = "analysis"
    REPORTING = "reporting"


class ProjectType(StrEnum):
    """Types of projects."""
    DATA_SCIENCE = "data_science"
    WEB_DEVELOPMENT = "web_development"
    DEVOPS = "devops"
    MOBILE_APP = "mobile_app"
    ENTERPRISE = "enterprise"


class Device(BaseModel):
    """User device for sync."""
    device_id: str
    device_name: str
    device_type: str  # desktop, mobile, tablet
    os: str  # windows, macos, linux, ios, android
    last_sync: datetime = Field(default_factory=lambda: datetime.now(UTC))
    is_primary: bool = False


class SyncRecord(BaseModel):
    """Sync record for cross-device synchronization."""
    id: str = Field(default_factory=lambda: str(uuid4()))
    user_id: str
    device_id: str
    preference_type: str
    data: dict[str, Any]
    version: int = 1
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(UTC))


class WorkflowRecommender:
    """Recommend workflows based on user history."""

    def __init__(self, recommendation_engine: RecommendationEngine, feedback_store: FeedbackStore) -> None:
        self.recommendation_engine = recommendation_engine
        self.feedback_store = feedback_store
        self._lock = RLock()

    def recommend_by_history(self, user_id: str, top_k: int = 5) -> list[dict[str, Any]]:
        """Recommend workflows based on user history."""
        with self._lock:
            # Get user's recent workflows
            recent_feedback = self.feedback_store.get_recent_feedback(user_id, days=30)
            workflow_feedback = [f for f in recent_feedback if f.item_type == RecommendationType.WORKFLOW]

            if not workflow_feedback:
                # Cold start: recommend popular workflows
                return self._recommend_popular_workflows(top_k)

            # Get recommendations
            recommendations = self.recommendation_engine.recommend_personalized(
                user_id, RecommendationType.WORKFLOW, top_k
            )

            return [
                {
                    "workflow_id": rec.item_id,
                    "name": rec.item_name,
                    "score": rec.score,
                    "reason": rec.reason,
                    "confidence": rec.confidence,
                }
                for rec in recommendations
            ]

    def recommend_by_task_type(self, user_id: str, task_type: TaskType, top_k: int = 5) -> list[dict[str, Any]]:
        """Recommend workflows for specific task type."""
        with self._lock:
            # Map task type to tags
            task_tags = {
                TaskType.DATA_PROCESSING: ["data", "processing", "etl"],
                TaskType.WEB_SCRAPING: ["web", "scraping", "crawling"],
                TaskType.API_INTEGRATION: ["api", "integration", "rest"],
                TaskType.AUTOMATION: ["automation", "workflow", "scheduled"],
                TaskType.ANALYSIS: ["analysis", "analytics", "reporting"],
                TaskType.REPORTING: ["reporting", "dashboard", "visualization"],
            }

            tags = task_tags.get(task_type, [])

            # Get workflows with matching tags
            workflows = []
            for item in self.recommendation_engine.catalog.get_items_by_type(RecommendationType.WORKFLOW):
                if any(tag in item.tags for tag in tags):
                    workflows.append(item)

            # Score and sort
            scored = []
            for workflow in workflows:
                score = sum(1 for tag in tags if tag in workflow.tags) / len(tags) if tags else 0
                score += workflow.popularity_score * 0.2
                scored.append((workflow, score))

            sorted_workflows = sorted(scored, key=lambda x: x[1], reverse=True)[:top_k]

            return [
                {
                    "workflow_id": workflow.id,
                    "name": workflow.name,
                    "score": score,
                    "reason": f"Recommended for {task_type.value}",
                    "tags": workflow.tags,
                }
                for workflow, score in sorted_workflows
            ]

    def _recommend_popular_workflows(self, top_k: int = 5) -> list[dict[str, Any]]:
        """Recommend popular workflows."""
        workflows = self.recommendation_engine.catalog.get_items_by_type(RecommendationType.WORKFLOW)
        sorted_workflows = sorted(workflows, key=lambda x: x.popularity_score, reverse=True)[:top_k]

        return [
            {
                "workflow_id": workflow.id,
                "name": workflow.name,
                "score": workflow.popularity_score,
                "reason": "Popular with other users",
            }
            for workflow in sorted_workflows
        ]


class ToolRecommender:
    """Recommend tools based on task type."""

    def __init__(self, recommendation_engine: RecommendationEngine) -> None:
        self.recommendation_engine = recommendation_engine
        self._lock = RLock()

    def recommend_by_task_type(self, user_id: str, task_type: TaskType, top_k: int = 5) -> list[dict[str, Any]]:
        """Recommend tools for specific task type."""
        with self._lock:
            # Map task type to tool categories
            task_tools = {
                TaskType.DATA_PROCESSING: ["data", "processing", "transformation"],
                TaskType.WEB_SCRAPING: ["web", "scraping", "http"],
                TaskType.API_INTEGRATION: ["api", "rest", "graphql"],
                TaskType.AUTOMATION: ["automation", "scheduling", "workflow"],
                TaskType.ANALYSIS: ["analysis", "statistics", "ml"],
                TaskType.REPORTING: ["reporting", "visualization", "export"],
            }

            tags = task_tools.get(task_type, [])

            # Get tools with matching tags
            tools = []
            for item in self.recommendation_engine.catalog.get_items_by_type(RecommendationType.TOOL):
                if any(tag in item.tags for tag in tags):
                    tools.append(item)

            # Score and sort
            scored = []
            for tool in tools:
                score = sum(1 for tag in tags if tag in tool.tags) / len(tags) if tags else 0
                score += tool.quality_score * 0.3
                scored.append((tool, score))

            sorted_tools = sorted(scored, key=lambda x: x[1], reverse=True)[:top_k]

            return [
                {
                    "tool_id": tool.id,
                    "name": tool.name,
                    "score": score,
                    "reason": f"Recommended for {task_type.value}",
                    "category": tool.category,
                }
                for tool, score in sorted_tools
            ]


class TemplateRecommender:
    """Recommend templates based on project type."""

    def __init__(self, recommendation_engine: RecommendationEngine) -> None:
        self.recommendation_engine = recommendation_engine
        self._lock = RLock()

    def recommend_by_project_type(self, user_id: str, project_type: ProjectType, top_k: int = 5) -> list[dict[str, Any]]:
        """Recommend templates for specific project type."""
        with self._lock:
            # Map project type to template categories
            project_templates = {
                ProjectType.DATA_SCIENCE: ["data", "ml", "analysis", "jupyter"],
                ProjectType.WEB_DEVELOPMENT: ["web", "frontend", "backend", "api"],
                ProjectType.DEVOPS: ["devops", "infrastructure", "deployment", "ci-cd"],
                ProjectType.MOBILE_APP: ["mobile", "ios", "android", "react-native"],
                ProjectType.ENTERPRISE: ["enterprise", "scalable", "security", "monitoring"],
            }

            tags = project_templates.get(project_type, [])

            # Get templates with matching tags
            templates = []
            for item in self.recommendation_engine.catalog.get_items_by_type(RecommendationType.TEMPLATE):
                if any(tag in item.tags for tag in tags):
                    templates.append(item)

            # Score and sort
            scored = []
            for template in templates:
                score = sum(1 for tag in tags if tag in template.tags) / len(tags) if tags else 0
                score += template.popularity_score * 0.2
                scored.append((template, score))

            sorted_templates = sorted(scored, key=lambda x: x[1], reverse=True)[:top_k]

            return [
                {
                    "template_id": template.id,
                    "name": template.name,
                    "score": score,
                    "reason": f"Recommended for {project_type.value}",
                    "category": template.category,
                }
                for template, score in sorted_templates
            ]


class PluginRecommender:
    """Recommend plugins based on functionality needs."""

    def __init__(self, recommendation_engine: RecommendationEngine) -> None:
        self.recommendation_engine = recommendation_engine
        self._lock = RLock()

    def recommend_by_functionality(self, user_id: str, required_features: list[str], top_k: int = 5) -> list[dict[str, Any]]:
        """Recommend plugins based on required features."""
        with self._lock:
            # Get plugins with matching features
            plugins = []
            for item in self.recommendation_engine.catalog.get_items_by_type(RecommendationType.PLUGIN):
                if any(feature in item.tags for feature in required_features):
                    plugins.append(item)

            # Score and sort
            scored = []
            for plugin in plugins:
                score = sum(1 for feature in required_features if feature in plugin.tags) / len(required_features) if required_features else 0
                score += plugin.quality_score * 0.3
                scored.append((plugin, score))

            sorted_plugins = sorted(scored, key=lambda x: x[1], reverse=True)[:top_k]

            return [
                {
                    "plugin_id": plugin.id,
                    "name": plugin.name,
                    "score": score,
                    "reason": "Provides required features",
                    "features": [tag for tag in plugin.tags if tag in required_features],
                }
                for plugin, score in sorted_plugins
            ]


class SkillRecommender:
    """Recommend skills based on user role."""

    def __init__(self, recommendation_engine: RecommendationEngine) -> None:
        self.recommendation_engine = recommendation_engine
        self._lock = RLock()

    def recommend_by_role(self, user_id: str, role: str, top_k: int = 5) -> list[dict[str, Any]]:
        """Recommend skills for specific role."""
        with self._lock:
            # Map role to skill categories
            role_skills = {
                "developer": ["programming", "coding", "debugging", "testing"],
                "analyst": ["analysis", "statistics", "reporting", "visualization"],
                "manager": ["management", "planning", "communication", "leadership"],
                "admin": ["administration", "security", "monitoring", "maintenance"],
            }

            tags = role_skills.get(role, [])

            # Get skills with matching tags
            skills = []
            for item in self.recommendation_engine.catalog.get_items_by_type(RecommendationType.SKILL):
                if any(tag in item.tags for tag in tags):
                    skills.append(item)

            # Score and sort
            scored = []
            for skill in skills:
                score = sum(1 for tag in tags if tag in skill.tags) / len(tags) if tags else 0
                score += skill.popularity_score * 0.2
                scored.append((skill, score))

            sorted_skills = sorted(scored, key=lambda x: x[1], reverse=True)[:top_k]

            return [
                {
                    "skill_id": skill.id,
                    "name": skill.name,
                    "score": score,
                    "reason": f"Recommended for {role}",
                    "category": skill.category,
                }
                for skill, score in sorted_skills
            ]


class CrossDeviceSyncManager:
    """Manage cross-device preference synchronization."""

    def __init__(self, preference_store: PreferenceStore) -> None:
        self.preference_store = preference_store
        self._devices: dict[str, list[Device]] = {}
        self._sync_records: dict[str, SyncRecord] = {}
        self._lock = RLock()

    def register_device(self, user_id: str, device: Device) -> None:
        """Register a device for a user."""
        with self._lock:
            if user_id not in self._devices:
                self._devices[user_id] = []
            self._devices[user_id].append(device)

    def get_devices(self, user_id: str) -> list[Device]:
        """Get all devices for a user."""
        with self._lock:
            return self._devices.get(user_id, [])

    def sync_preferences(self, user_id: str, device_id: str) -> dict[str, Any]:
        """Sync preferences to a device."""
        with self._lock:
            prefs = self.preference_store.get_all_preferences(user_id)
            sync_data = {}

            for pref in prefs:
                sync_data[f"{pref.preference_type}:{pref.key}"] = pref.value

            # Create sync record
            sync_record = SyncRecord(
                user_id=user_id,
                device_id=device_id,
                preference_type="all",
                data=sync_data,
            )
            self._sync_records[sync_record.id] = sync_record

            # Update device last sync
            devices = self._devices.get(user_id, [])
            for device in devices:
                if device.device_id == device_id:
                    device.last_sync = datetime.now(UTC)

            return sync_data

    def push_preferences(self, user_id: str, device_id: str, preferences: dict[str, Any]) -> None:
        """Push preferences from a device to server."""
        with self._lock:
            for key, value in preferences.items():
                if ":" in key:
                    pref_type_str, pref_key = key.split(":", 1)
                    try:
                        from backend.app.core.personalization import PreferenceType

                        pref_type = PreferenceType(pref_type_str)
                        self.preference_store.save_preference(user_id, pref_type, pref_key, value)
                    except ValueError:
                        pass

            # Create sync record
            sync_record = SyncRecord(
                user_id=user_id,
                device_id=device_id,
                preference_type="all",
                data=preferences,
            )
            self._sync_records[sync_record.id] = sync_record

    def get_sync_status(self, user_id: str) -> dict[str, Any]:
        """Get sync status for all devices."""
        with self._lock:
            devices = self._devices.get(user_id, [])
            status = {}

            for device in devices:
                status[device.device_id] = {
                    "device_name": device.device_name,
                    "device_type": device.device_type,
                    "os": device.os,
                    "last_sync": device.last_sync.isoformat(),
                    "is_primary": device.is_primary,
                }

            return status

    def resolve_conflicts(self, user_id: str, conflicts: list[dict[str, Any]]) -> dict[str, Any]:
        """Resolve sync conflicts between devices."""
        with self._lock:
            resolved = {}

            for conflict in conflicts:
                key = conflict["key"]
                values = conflict["values"]  # dict of device_id -> value

                # Use most recent value
                most_recent = max(values.items(), key=lambda x: x[1].get("timestamp", 0))
                resolved[key] = most_recent[1]["value"]

            return resolved


# Global instances
workflow_recommender: WorkflowRecommender | None = None
tool_recommender: ToolRecommender | None = None
template_recommender: TemplateRecommender | None = None
plugin_recommender: PluginRecommender | None = None
skill_recommender: SkillRecommender | None = None
sync_manager: CrossDeviceSyncManager | None = None


def initialize_recommenders(
    recommendation_engine: RecommendationEngine,
    feedback_store: FeedbackStore,
    preference_store: PreferenceStore,
) -> None:
    """Initialize all recommenders."""
    global workflow_recommender, tool_recommender, template_recommender, plugin_recommender, skill_recommender, sync_manager

    workflow_recommender = WorkflowRecommender(recommendation_engine, feedback_store)
    tool_recommender = ToolRecommender(recommendation_engine)
    template_recommender = TemplateRecommender(recommendation_engine)
    plugin_recommender = PluginRecommender(recommendation_engine)
    skill_recommender = SkillRecommender(recommendation_engine)
    sync_manager = CrossDeviceSyncManager(preference_store)
