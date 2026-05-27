"""Plugin Lifecycle Management and Audit System"""

from __future__ import annotations

import logging
from datetime import UTC, datetime
from pathlib import Path
from threading import RLock
from typing import Any
from uuid import uuid4

from plugin_schema import PluginSchema, PluginStatus, PluginAuditRecord

logger = logging.getLogger(__name__)


class PluginLifecycleManager:
    """Manage plugin installation, enabling, disabling, and removal"""

    def __init__(self):
        self._lifecycle_state: dict[str, dict[str, Any]] = {}
        self._lock = RLock()

    def initialize_lifecycle(self, plugin_id: str, plugin: PluginSchema) -> None:
        """Initialize lifecycle tracking for plugin"""
        with self._lock:
            self._lifecycle_state[plugin_id] = {
                "plugin_id": plugin_id,
                "name": plugin.name,
                "version": plugin.version,
                "status": plugin.status,
                "installed_at": None,
                "enabled_at": None,
                "disabled_at": None,
                "uninstalled_at": None,
                "last_action": None,
                "action_history": [],
            }

    def record_install(self, plugin_id: str) -> None:
        """Record plugin installation"""
        with self._lock:
            if plugin_id in self._lifecycle_state:
                now = datetime.now(UTC)
                self._lifecycle_state[plugin_id]["installed_at"] = now
                self._lifecycle_state[plugin_id]["last_action"] = "install"
                self._lifecycle_state[plugin_id]["action_history"].append(
                    {"action": "install", "timestamp": now}
                )

    def record_enable(self, plugin_id: str) -> None:
        """Record plugin enabling"""
        with self._lock:
            if plugin_id in self._lifecycle_state:
                now = datetime.now(UTC)
                self._lifecycle_state[plugin_id]["enabled_at"] = now
                self._lifecycle_state[plugin_id]["last_action"] = "enable"
                self._lifecycle_state[plugin_id]["action_history"].append(
                    {"action": "enable", "timestamp": now}
                )

    def record_disable(self, plugin_id: str) -> None:
        """Record plugin disabling"""
        with self._lock:
            if plugin_id in self._lifecycle_state:
                now = datetime.now(UTC)
                self._lifecycle_state[plugin_id]["disabled_at"] = now
                self._lifecycle_state[plugin_id]["last_action"] = "disable"
                self._lifecycle_state[plugin_id]["action_history"].append(
                    {"action": "disable", "timestamp": now}
                )

    def record_uninstall(self, plugin_id: str) -> None:
        """Record plugin uninstallation"""
        with self._lock:
            if plugin_id in self._lifecycle_state:
                now = datetime.now(UTC)
                self._lifecycle_state[plugin_id]["uninstalled_at"] = now
                self._lifecycle_state[plugin_id]["last_action"] = "uninstall"
                self._lifecycle_state[plugin_id]["action_history"].append(
                    {"action": "uninstall", "timestamp": now}
                )

    def record_upgrade(self, plugin_id: str, new_version: str) -> None:
        """Record plugin upgrade"""
        with self._lock:
            if plugin_id in self._lifecycle_state:
                now = datetime.now(UTC)
                self._lifecycle_state[plugin_id]["version"] = new_version
                self._lifecycle_state[plugin_id]["last_action"] = "upgrade"
                self._lifecycle_state[plugin_id]["action_history"].append(
                    {"action": "upgrade", "new_version": new_version, "timestamp": now}
                )

    def get_lifecycle_state(self, plugin_id: str) -> dict[str, Any] | None:
        """Get lifecycle state for plugin"""
        return self._lifecycle_state.get(plugin_id)

    def get_action_history(self, plugin_id: str) -> list[dict[str, Any]]:
        """Get action history for plugin"""
        state = self._lifecycle_state.get(plugin_id)
        return state["action_history"] if state else []


class PluginAuditSystem:
    """Comprehensive audit system for plugin operations"""

    def __init__(self, storage_path: str | Path | None = None):
        self.storage_path = Path(storage_path) if storage_path else Path("./audit")
        self.storage_path.mkdir(parents=True, exist_ok=True)
        self._audit_records: list[PluginAuditRecord] = []
        self._lock = RLock()
        self._load_audit_log()

    def _load_audit_log(self) -> None:
        """Load audit log from storage"""
        audit_file = self.storage_path / "audit.json"
        if audit_file.exists():
            import json

            try:
                with open(audit_file) as f:
                    data = json.load(f)
                    for record_data in data.get("records", []):
                        record = PluginAuditRecord(**record_data)
                        self._audit_records.append(record)
                logger.info(f"Loaded {len(self._audit_records)} audit records")
            except Exception as e:
                logger.error(f"Failed to load audit log: {e}")

    def _save_audit_log(self) -> None:
        """Save audit log to storage"""
        import json

        audit_file = self.storage_path / "audit.json"
        try:
            with open(audit_file, "w") as f:
                data = {
                    "records": [
                        json.loads(r.model_dump_json()) for r in self._audit_records
                    ]
                }
                json.dump(data, f, indent=2, default=str)
        except Exception as e:
            logger.error(f"Failed to save audit log: {e}")

    def record_action(
        self,
        plugin_id: str,
        action: str,
        actor_id: str = "system",
        outcome: str = "success",
        details: dict[str, Any] | None = None,
    ) -> PluginAuditRecord:
        """Record plugin action in audit log"""
        record = PluginAuditRecord(
            plugin_id=plugin_id,
            action=action,
            actor_id=actor_id,
            outcome=outcome,
            details=details or {},
        )
        with self._lock:
            self._audit_records.append(record)
            self._save_audit_log()
        logger.info(
            f"Audit recorded: {action} on {plugin_id} by {actor_id} - {outcome}"
        )
        return record

    def record_install(
        self, plugin_id: str, actor_id: str = "system", details: dict[str, Any] | None = None
    ) -> PluginAuditRecord:
        """Record plugin installation"""
        return self.record_action(
            plugin_id, "install", actor_id, "success", details or {}
        )

    def record_uninstall(
        self, plugin_id: str, actor_id: str = "system", details: dict[str, Any] | None = None
    ) -> PluginAuditRecord:
        """Record plugin uninstallation"""
        return self.record_action(
            plugin_id, "uninstall", actor_id, "success", details or {}
        )

    def record_enable(
        self, plugin_id: str, actor_id: str = "system", details: dict[str, Any] | None = None
    ) -> PluginAuditRecord:
        """Record plugin enabling"""
        return self.record_action(
            plugin_id, "enable", actor_id, "success", details or {}
        )

    def record_disable(
        self, plugin_id: str, actor_id: str = "system", details: dict[str, Any] | None = None
    ) -> PluginAuditRecord:
        """Record plugin disabling"""
        return self.record_action(
            plugin_id, "disable", actor_id, "success", details or {}
        )

    def record_execution(
        self,
        plugin_id: str,
        action: str,
        success: bool = True,
        error: str | None = None,
        details: dict[str, Any] | None = None,
    ) -> PluginAuditRecord:
        """Record plugin execution"""
        outcome = "success" if success else "failure"
        audit_details = details or {}
        if error:
            audit_details["error"] = error
        return self.record_action(
            plugin_id, f"execute:{action}", "system", outcome, audit_details
        )

    def record_permission_change(
        self,
        plugin_id: str,
        permissions: list[str],
        actor_id: str = "system",
    ) -> PluginAuditRecord:
        """Record permission changes"""
        return self.record_action(
            plugin_id,
            "permission_change",
            actor_id,
            "success",
            {"permissions": permissions},
        )

    def get_audit_records(
        self, plugin_id: str | None = None, action: str | None = None
    ) -> list[PluginAuditRecord]:
        """Get audit records with optional filtering"""
        records = self._audit_records

        if plugin_id:
            records = [r for r in records if r.plugin_id == plugin_id]

        if action:
            records = [r for r in records if r.action == action]

        return list(reversed(records))

    def get_plugin_audit_trail(self, plugin_id: str) -> list[PluginAuditRecord]:
        """Get complete audit trail for a plugin"""
        return self.get_audit_records(plugin_id=plugin_id)

    def verify_audit_integrity(self) -> tuple[bool, list[str]]:
        """Verify audit log integrity"""
        issues = []

        if not self._audit_records:
            return True, []

        # Check chronological order
        for i in range(1, len(self._audit_records)):
            if (
                self._audit_records[i].created_at
                < self._audit_records[i - 1].created_at
            ):
                issues.append(f"Chronological order violation at record {i}")

        # Check for suspicious patterns
        plugin_actions = {}
        for record in self._audit_records:
            if record.plugin_id not in plugin_actions:
                plugin_actions[record.plugin_id] = []
            plugin_actions[record.plugin_id].append(record.action)

        # Flag rapid enable/disable cycles
        for plugin_id, actions in plugin_actions.items():
            enable_disable_count = sum(
                1 for a in actions if a in ["enable", "disable"]
            )
            if enable_disable_count > 20:
                issues.append(
                    f"Suspicious enable/disable cycles for plugin {plugin_id}"
                )

        return len(issues) == 0, issues

    def export_audit_report(self, plugin_id: str | None = None) -> dict[str, Any]:
        """Export audit report"""
        records = self.get_audit_records(plugin_id=plugin_id)
        integrity_valid, integrity_issues = self.verify_audit_integrity()

        return {
            "export_time": datetime.now(UTC).isoformat(),
            "plugin_id": plugin_id,
            "total_records": len(records),
            "records": [json.loads(r.model_dump_json()) for r in records],
            "integrity": {
                "valid": integrity_valid,
                "issues": integrity_issues,
            },
        }


# Global instances
lifecycle_manager = PluginLifecycleManager()
audit_system = PluginAuditSystem()

import json
