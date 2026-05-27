"""Workflow Versioning and Version Management

Implements version control for workflows:
- Version tracking
- Version comparison
- Version rollback
- Canary/blue-green deployment
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime
from enum import StrEnum
from typing import Any
from uuid import uuid4


class VersionStatus(StrEnum):
    DRAFT = "draft"
    PUBLISHED = "published"
    DEPRECATED = "deprecated"
    ARCHIVED = "archived"


class DeploymentStrategy(StrEnum):
    IMMEDIATE = "immediate"
    CANARY = "canary"
    BLUE_GREEN = "blue_green"
    ROLLING = "rolling"


@dataclass
class WorkflowVersion:
    """Represents a workflow version"""
    id: str = field(default_factory=lambda: str(uuid4()))
    workflow_id: str = ""
    version_number: str = "1.0.0"
    status: VersionStatus = VersionStatus.DRAFT
    nodes: list[dict[str, Any]] = field(default_factory=list)
    edges: list[dict[str, Any]] = field(default_factory=list)
    changelog: str = ""
    author: str = ""
    created_at: datetime = field(default_factory=lambda: datetime.now(UTC))
    published_at: datetime | None = None
    deployment_strategy: DeploymentStrategy = DeploymentStrategy.IMMEDIATE
    canary_percentage: int = 10  # For canary deployments
    metadata: dict[str, Any] = field(default_factory=dict)
    tags: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary"""
        return {
            "id": self.id,
            "workflow_id": self.workflow_id,
            "version_number": self.version_number,
            "status": self.status,
            "node_count": len(self.nodes),
            "edge_count": len(self.edges),
            "changelog": self.changelog,
            "author": self.author,
            "created_at": self.created_at.isoformat(),
            "published_at": self.published_at.isoformat() if self.published_at else None,
            "deployment_strategy": self.deployment_strategy,
            "canary_percentage": self.canary_percentage,
            "tags": self.tags,
        }


@dataclass
class VersionDiff:
    """Represents differences between versions"""
    from_version: str
    to_version: str
    nodes_added: list[dict[str, Any]] = field(default_factory=list)
    nodes_removed: list[dict[str, Any]] = field(default_factory=list)
    nodes_modified: list[dict[str, Any]] = field(default_factory=list)
    edges_added: list[dict[str, Any]] = field(default_factory=list)
    edges_removed: list[dict[str, Any]] = field(default_factory=list)
    edges_modified: list[dict[str, Any]] = field(default_factory=list)
    breaking_changes: list[str] = field(default_factory=list)
    compatibility_score: float = 1.0

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary"""
        return {
            "from_version": self.from_version,
            "to_version": self.to_version,
            "nodes_added": len(self.nodes_added),
            "nodes_removed": len(self.nodes_removed),
            "nodes_modified": len(self.nodes_modified),
            "edges_added": len(self.edges_added),
            "edges_removed": len(self.edges_removed),
            "edges_modified": len(self.edges_modified),
            "breaking_changes": self.breaking_changes,
            "compatibility_score": self.compatibility_score,
        }


class VersionComparator:
    """Compares workflow versions"""

    @staticmethod
    def compare(
        from_version: WorkflowVersion,
        to_version: WorkflowVersion,
    ) -> VersionDiff:
        """Compare two versions"""
        diff = VersionDiff(
            from_version=from_version.version_number,
            to_version=to_version.version_number,
        )

        # Compare nodes
        from_nodes = {n["id"]: n for n in from_version.nodes}
        to_nodes = {n["id"]: n for n in to_version.nodes}

        # Find added nodes
        for node_id, node in to_nodes.items():
            if node_id not in from_nodes:
                diff.nodes_added.append(node)

        # Find removed nodes
        for node_id, node in from_nodes.items():
            if node_id not in to_nodes:
                diff.nodes_removed.append(node)

        # Find modified nodes
        for node_id, node in to_nodes.items():
            if node_id in from_nodes and from_nodes[node_id] != node:
                diff.nodes_modified.append({
                    "id": node_id,
                    "from": from_nodes[node_id],
                    "to": node,
                })

        # Compare edges
        from_edges = {(e["source"], e["target"]): e for e in from_version.edges}
        to_edges = {(e["source"], e["target"]): e for e in to_version.edges}

        # Find added edges
        for edge_key, edge in to_edges.items():
            if edge_key not in from_edges:
                diff.edges_added.append(edge)

        # Find removed edges
        for edge_key, edge in from_edges.items():
            if edge_key not in to_edges:
                diff.edges_removed.append(edge)

        # Find modified edges
        for edge_key, edge in to_edges.items():
            if edge_key in from_edges and from_edges[edge_key] != edge:
                diff.edges_modified.append({
                    "from": from_edges[edge_key],
                    "to": edge,
                })

        # Detect breaking changes
        diff.breaking_changes = VersionComparator._detect_breaking_changes(diff)

        # Calculate compatibility score
        diff.compatibility_score = VersionComparator._calculate_compatibility(diff)

        return diff

    @staticmethod
    def _detect_breaking_changes(diff: VersionDiff) -> list[str]:
        """Detect breaking changes"""
        breaking = []

        # Removed nodes are breaking
        if diff.nodes_removed:
            breaking.append(f"Removed {len(diff.nodes_removed)} nodes")

        # Removed edges are breaking
        if diff.edges_removed:
            breaking.append(f"Removed {len(diff.edges_removed)} edges")

        # Type changes are breaking
        for modified in diff.nodes_modified:
            if modified["from"].get("type") != modified["to"].get("type"):
                breaking.append(f"Node {modified['id']} type changed")

        return breaking

    @staticmethod
    def _calculate_compatibility(diff: VersionDiff) -> float:
        """Calculate compatibility score (0-1)"""
        if not diff.breaking_changes:
            return 1.0

        # Penalize for breaking changes
        penalty = len(diff.breaking_changes) * 0.2
        return max(0.0, 1.0 - penalty)


class VersionManager:
    """Manages workflow versions"""

    def __init__(self):
        self.versions: dict[str, list[WorkflowVersion]] = {}  # workflow_id -> versions
        self.current_versions: dict[str, str] = {}  # workflow_id -> current_version_id
        self.deployment_history: list[dict[str, Any]] = []

    def create_version(
        self,
        workflow_id: str,
        nodes: list[dict[str, Any]],
        edges: list[dict[str, Any]],
        changelog: str = "",
        author: str = "",
    ) -> WorkflowVersion:
        """Create a new version"""
        # Get next version number
        existing_versions = self.versions.get(workflow_id, [])
        version_number = self._next_version_number(existing_versions)

        version = WorkflowVersion(
            workflow_id=workflow_id,
            version_number=version_number,
            nodes=nodes,
            edges=edges,
            changelog=changelog,
            author=author,
            status=VersionStatus.DRAFT,
        )

        if workflow_id not in self.versions:
            self.versions[workflow_id] = []
        self.versions[workflow_id].append(version)

        return version

    def publish_version(
        self,
        workflow_id: str,
        version_id: str,
        deployment_strategy: DeploymentStrategy = DeploymentStrategy.IMMEDIATE,
        canary_percentage: int = 10,
    ) -> WorkflowVersion | None:
        """Publish a version"""
        version = self.get_version(workflow_id, version_id)
        if version is None:
            return None

        version.status = VersionStatus.PUBLISHED
        version.published_at = datetime.now(UTC)
        version.deployment_strategy = deployment_strategy
        version.canary_percentage = canary_percentage

        self.current_versions[workflow_id] = version_id

        self.deployment_history.append({
            "workflow_id": workflow_id,
            "version_id": version_id,
            "version_number": version.version_number,
            "strategy": deployment_strategy,
            "timestamp": datetime.now(UTC).isoformat(),
        })

        return version

    def get_version(self, workflow_id: str, version_id: str) -> WorkflowVersion | None:
        """Get specific version"""
        versions = self.versions.get(workflow_id, [])
        for version in versions:
            if version.id == version_id:
                return version
        return None

    def get_current_version(self, workflow_id: str) -> WorkflowVersion | None:
        """Get current published version"""
        version_id = self.current_versions.get(workflow_id)
        if version_id:
            return self.get_version(workflow_id, version_id)
        return None

    def list_versions(
        self,
        workflow_id: str,
        status: VersionStatus | None = None,
    ) -> list[WorkflowVersion]:
        """List versions for workflow"""
        versions = self.versions.get(workflow_id, [])
        if status:
            versions = [v for v in versions if v.status == status]
        return sorted(versions, key=lambda v: v.created_at, reverse=True)

    def rollback(self, workflow_id: str, version_id: str) -> WorkflowVersion | None:
        """Rollback to previous version"""
        version = self.get_version(workflow_id, version_id)
        if version is None or version.status != VersionStatus.PUBLISHED:
            return None

        # Create new version from rollback
        new_version = self.create_version(
            workflow_id,
            version.nodes,
            version.edges,
            changelog=f"Rollback to version {version.version_number}",
            author="system",
        )

        return self.publish_version(workflow_id, new_version.id)

    def compare_versions(
        self,
        workflow_id: str,
        from_version_id: str,
        to_version_id: str,
    ) -> VersionDiff | None:
        """Compare two versions"""
        from_version = self.get_version(workflow_id, from_version_id)
        to_version = self.get_version(workflow_id, to_version_id)

        if from_version is None or to_version is None:
            return None

        return VersionComparator.compare(from_version, to_version)

    def deprecate_version(self, workflow_id: str, version_id: str) -> WorkflowVersion | None:
        """Mark version as deprecated"""
        version = self.get_version(workflow_id, version_id)
        if version is None:
            return None

        version.status = VersionStatus.DEPRECATED
        return version

    def archive_version(self, workflow_id: str, version_id: str) -> WorkflowVersion | None:
        """Archive version"""
        version = self.get_version(workflow_id, version_id)
        if version is None:
            return None

        version.status = VersionStatus.ARCHIVED
        return version

    def get_deployment_history(
        self,
        workflow_id: str | None = None,
        limit: int = 50,
    ) -> list[dict[str, Any]]:
        """Get deployment history"""
        history = self.deployment_history
        if workflow_id:
            history = [h for h in history if h["workflow_id"] == workflow_id]
        return history[-limit:]

    @staticmethod
    def _next_version_number(existing_versions: list[WorkflowVersion]) -> str:
        """Calculate next version number"""
        if not existing_versions:
            return "1.0.0"

        latest = max(existing_versions, key=lambda v: v.created_at)
        parts = latest.version_number.split(".")
        parts[2] = str(int(parts[2]) + 1)
        return ".".join(parts)

    def get_version_stats(self, workflow_id: str) -> dict[str, Any]:
        """Get version statistics"""
        versions = self.versions.get(workflow_id, [])
        return {
            "total_versions": len(versions),
            "published_versions": len([v for v in versions if v.status == VersionStatus.PUBLISHED]),
            "draft_versions": len([v for v in versions if v.status == VersionStatus.DRAFT]),
            "deprecated_versions": len([v for v in versions if v.status == VersionStatus.DEPRECATED]),
            "archived_versions": len([v for v in versions if v.status == VersionStatus.ARCHIVED]),
            "current_version": self.current_versions.get(workflow_id),
        }
