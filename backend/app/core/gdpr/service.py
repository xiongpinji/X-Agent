"""P2-03: 数据主体权利服务 (Data Subject Rights Service).

实现 GDPR Art.17 (删除权) 和 Art.20 (数据可携带权):
- 级联删除: 清理用户在各 store 中的所有数据
- 数据导出: 打包用户所有数据为 JSON
- 删除确认: 生成删除证明 (用于合规审计)
"""

from __future__ import annotations

import json
import logging
import uuid
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)


@dataclass
class DeletionResult:
    """删除操作结果."""

    request_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    user_id: str = ""
    tenant_id: str = ""
    deleted_counts: dict[str, int] = field(default_factory=dict)
    errors: list[str] = field(default_factory=list)
    completed_at: str = field(default_factory=lambda: datetime.now(UTC).isoformat())
    success: bool = True

    @property
    def total_deleted(self) -> int:
        return sum(self.deleted_counts.values())


@dataclass
class ExportResult:
    """数据导出结果."""

    request_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    user_id: str = ""
    tenant_id: str = ""
    data: dict[str, Any] = field(default_factory=dict)
    exported_at: str = field(default_factory=lambda: datetime.now(UTC).isoformat())
    record_counts: dict[str, int] = field(default_factory=dict)

    @property
    def total_records(self) -> int:
        return sum(self.record_counts.values())

    def to_json(self, indent: int = 2) -> str:
        """序列化为 JSON."""
        return json.dumps({
            "request_id": self.request_id,
            "user_id": self.user_id,
            "tenant_id": self.tenant_id,
            "exported_at": self.exported_at,
            "record_counts": self.record_counts,
            "data": self.data,
        }, ensure_ascii=False, indent=indent, default=str)


class DataSubjectRightsService:
    """GDPR 数据主体权利服务.

    协调各 store 实现级联删除和数据导出。
    设计为 best-effort: 单个 store 失败不阻断整体流程,
    但会记录错误并在结果中体现。
    """

    def __init__(self, data_dir: Path | None = None):
        self._data_dir = data_dir or Path("data")
        self._deletion_log: list[DeletionResult] = []

    # ─── 删除权 (Art. 17) ─────────────────────────────────────────────────────

    def erase_user_data(self, user_id: str, tenant_id: str = "") -> DeletionResult:
        """级联删除用户所有数据.

        覆盖:
        - Memory items
        - Run records
        - Checkpoints
        - Tool execution records
        - Sessions
        - Approvals
        - Collaboration data
        - Audit logs (匿名化, 不完全删除 — 合规保留)
        """
        result = DeletionResult(user_id=user_id, tenant_id=tenant_id)
        logger.info("GDPR erasure started: user=%s tenant=%s", user_id, tenant_id)

        # 1. Memory items
        self._erase_memories(user_id, tenant_id, result)

        # 2. Run records
        self._erase_runs(user_id, result)

        # 3. Checkpoints
        self._erase_checkpoints(user_id, result)

        # 4. Tool execution records
        self._erase_tool_executions(user_id, result)

        # 5. Sessions (memory store 中的 session)
        self._erase_sessions(user_id, result)

        # 6. Approvals
        self._erase_approvals(user_id, result)

        # 7. Collaboration data
        self._erase_collaboration(user_id, result)

        # 8. Audit logs — 匿名化而非删除 (法律保留义务)
        self._anonymize_audit_logs(user_id, result)

        result.success = len(result.errors) == 0
        self._deletion_log.append(result)

        # 持久化删除证明
        self._persist_deletion_proof(result)

        logger.info(
            "GDPR erasure completed: user=%s total_deleted=%d errors=%d",
            user_id, result.total_deleted, len(result.errors),
        )
        return result

    # ─── 导出权 (Art. 20) ─────────────────────────────────────────────────────

    def export_user_data(self, user_id: str, tenant_id: str = "") -> ExportResult:
        """导出用户所有数据 (数据可携带权)."""
        result = ExportResult(user_id=user_id, tenant_id=tenant_id)
        logger.info("GDPR export started: user=%s tenant=%s", user_id, tenant_id)

        # 1. Memory items
        self._export_memories(user_id, tenant_id, result)

        # 2. Run records
        self._export_runs(user_id, result)

        # 3. Checkpoints
        self._export_checkpoints(user_id, result)

        # 4. Tool execution records
        self._export_tool_executions(user_id, result)

        # 5. Sessions
        self._export_sessions(user_id, result)

        logger.info(
            "GDPR export completed: user=%s total_records=%d",
            user_id, result.total_records,
        )
        return result

    # ─── 删除证明 ─────────────────────────────────────────────────────────────

    def get_deletion_proof(self, request_id: str) -> DeletionResult | None:
        """获取删除证明."""
        for r in self._deletion_log:
            if r.request_id == request_id:
                return r
        return None

    def list_deletion_requests(self, user_id: str | None = None) -> list[DeletionResult]:
        """列出删除请求记录."""
        if user_id:
            return [r for r in self._deletion_log if r.user_id == user_id]
        return list(self._deletion_log)

    # ─── 内部: 各 store 删除实现 ──────────────────────────────────────────────

    def _erase_memories(self, user_id: str, tenant_id: str, result: DeletionResult) -> None:
        """删除用户 memory items."""
        try:
            from backend.app.core.memory.store import MemoryStore
            store = MemoryStore()
            # MemoryStore 按 tenant_id 过滤, 再按 user_id 过滤
            items = [
                item for item in store._items
                if item.metadata.get("user_id") == user_id
                or (tenant_id and item.tenant_id == tenant_id and item.metadata.get("user_id") == user_id)
            ]
            count = 0
            for item in items:
                store._items.remove(item)
                count += 1
            result.deleted_counts["memories"] = count
        except Exception as e:
            result.errors.append(f"memories: {e}")
            logger.warning("GDPR erase memories failed: %s", e)

    def _erase_runs(self, user_id: str, result: DeletionResult) -> None:
        """删除用户 run records."""
        try:
            from backend.app.core.runs import get_run_store
            store = get_run_store()
            to_delete = [r for r in store._records.values() if r.user_id == user_id]
            for r in to_delete:
                del store._records[r.run_id]
            result.deleted_counts["runs"] = len(to_delete)
        except Exception as e:
            result.errors.append(f"runs: {e}")

    def _erase_checkpoints(self, user_id: str, result: DeletionResult) -> None:
        """删除用户 checkpoints."""
        try:
            from backend.app.core.checkpoint.store import get_checkpoint_store
            store = get_checkpoint_store()
            to_delete = [
                trace_id for trace_id, cps in store._checkpoints.items()
                if any(cp.user_id == user_id for cp in cps)
            ]
            count = 0
            for trace_id in to_delete:
                count += len(store._checkpoints[trace_id])
                del store._checkpoints[trace_id]
            result.deleted_counts["checkpoints"] = count
        except Exception as e:
            result.errors.append(f"checkpoints: {e}")

    def _erase_tool_executions(self, user_id: str, result: DeletionResult) -> None:
        """删除用户 tool execution records."""
        try:
            from backend.app.core.tools import ToolExecutionStore
            store = ToolExecutionStore()
            to_delete = [
                eid for eid, r in store._records.items()
                if r.user_id == user_id
            ]
            for eid in to_delete:
                del store._records[eid]
            result.deleted_counts["tool_executions"] = len(to_delete)
        except Exception as e:
            result.errors.append(f"tool_executions: {e}")

    def _erase_sessions(self, user_id: str, result: DeletionResult) -> None:
        """删除用户 sessions."""
        try:
            from backend.app.core.memory.store import MemoryStore
            store = MemoryStore()
            to_delete = [
                sid for sid, s in store._sessions.items()
                if s.user_id == user_id
            ]
            for sid in to_delete:
                del store._sessions[sid]
            result.deleted_counts["sessions"] = len(to_delete)
        except Exception as e:
            result.errors.append(f"sessions: {e}")

    def _erase_approvals(self, user_id: str, result: DeletionResult) -> None:
        """删除用户 approvals."""
        try:
            from backend.app.core.approvals import ApprovalStore
            store = ApprovalStore()
            to_delete = [
                aid for aid, a in store._records.items()
                if getattr(a, "user_id", "") == user_id
                or getattr(a, "requested_by", "") == user_id
            ]
            for aid in to_delete:
                del store._records[aid]
            result.deleted_counts["approvals"] = len(to_delete)
        except Exception as e:
            result.errors.append(f"approvals: {e}")

    def _erase_collaboration(self, user_id: str, result: DeletionResult) -> None:
        """删除用户协作数据."""
        try:
            from backend.app.core.collaboration.store import CollaborationStore
            store = CollaborationStore()
            # 协作 store 按 user_id 过滤
            count = 0
            if hasattr(store, "_messages"):
                to_delete = [
                    mid for mid, m in store._messages.items()
                    if getattr(m, "user_id", "") == user_id
                    or getattr(m, "sender_id", "") == user_id
                ]
                for mid in to_delete:
                    del store._messages[mid]
                    count += 1
            result.deleted_counts["collaboration"] = count
        except Exception as e:
            result.errors.append(f"collaboration: {e}")

    def _anonymize_audit_logs(self, user_id: str, result: DeletionResult) -> None:
        """匿名化审计日志 (法律保留, 不完全删除)."""
        try:
            from backend.app.core.audit import get_audit_store
            store = get_audit_store()
            count = 0
            for entry in store._entries:
                if getattr(entry, "user_id", "") == user_id:
                    entry.user_id = "[ANONYMIZED]"
                    if hasattr(entry, "metadata"):
                        entry.metadata.pop("user_email", None)
                        entry.metadata.pop("user_name", None)
                    count += 1
            result.deleted_counts["audit_anonymized"] = count
        except Exception as e:
            result.errors.append(f"audit_anonymize: {e}")

    # ─── 内部: 各 store 导出实现 ──────────────────────────────────────────────

    def _export_memories(self, user_id: str, tenant_id: str, result: ExportResult) -> None:
        """导出用户 memory items."""
        try:
            from backend.app.core.memory.store import MemoryStore
            store = MemoryStore()
            items = [
                {
                    "id": item.id,
                    "content": item.content,
                    "layer": item.layer,
                    "importance": item.importance,
                    "tags": item.tags,
                    "created_at": str(getattr(item, "created_at", "")),
                }
                for item in store._items
                if item.metadata.get("user_id") == user_id
            ]
            result.data["memories"] = items
            result.record_counts["memories"] = len(items)
        except Exception as e:
            logger.warning("GDPR export memories failed: %s", e)

    def _export_runs(self, user_id: str, result: ExportResult) -> None:
        """导出用户 run records."""
        try:
            from backend.app.core.runs import get_run_store
            store = get_run_store()
            runs = [
                r.model_dump(mode="json")
                for r in store._records.values()
                if r.user_id == user_id
            ]
            result.data["runs"] = runs
            result.record_counts["runs"] = len(runs)
        except Exception as e:
            logger.warning("GDPR export runs failed: %s", e)

    def _export_checkpoints(self, user_id: str, result: ExportResult) -> None:
        """导出用户 checkpoints."""
        try:
            from backend.app.core.checkpoint.store import get_checkpoint_store
            store = get_checkpoint_store()
            checkpoints = []
            for cps in store._checkpoints.values():
                for cp in cps:
                    if cp.user_id == user_id:
                        checkpoints.append(cp.to_dict())
            result.data["checkpoints"] = checkpoints
            result.record_counts["checkpoints"] = len(checkpoints)
        except Exception as e:
            logger.warning("GDPR export checkpoints failed: %s", e)

    def _export_tool_executions(self, user_id: str, result: ExportResult) -> None:
        """导出用户 tool execution records."""
        try:
            from backend.app.core.tools import ToolExecutionStore
            store = ToolExecutionStore()
            records = [
                r.model_dump(mode="json")
                for r in store._records.values()
                if r.user_id == user_id
            ]
            result.data["tool_executions"] = records
            result.record_counts["tool_executions"] = len(records)
        except Exception as e:
            logger.warning("GDPR export tool_executions failed: %s", e)

    def _export_sessions(self, user_id: str, result: ExportResult) -> None:
        """导出用户 sessions."""
        try:
            from backend.app.core.memory.store import MemoryStore
            store = MemoryStore()
            sessions = [
                {
                    "session_id": s.session_id,
                    "title": s.title,
                    "tags": s.tags,
                    "created_at": str(getattr(s, "created_at", "")),
                }
                for s in store._sessions.values()
                if s.user_id == user_id
            ]
            result.data["sessions"] = sessions
            result.record_counts["sessions"] = len(sessions)
        except Exception as e:
            logger.warning("GDPR export sessions failed: %s", e)

    # ─── 持久化删除证明 ───────────────────────────────────────────────────────

    def _persist_deletion_proof(self, result: DeletionResult) -> None:
        """持久化删除证明到磁盘 (合规审计用)."""
        try:
            proof_dir = self._data_dir / "gdpr"
            proof_dir.mkdir(parents=True, exist_ok=True)
            proof_file = proof_dir / f"deletion_{result.request_id}.json"
            proof_file.write_text(json.dumps({
                "request_id": result.request_id,
                "user_id": result.user_id,
                "tenant_id": result.tenant_id,
                "deleted_counts": result.deleted_counts,
                "errors": result.errors,
                "completed_at": result.completed_at,
                "success": result.success,
            }, ensure_ascii=False, indent=2), encoding="utf-8")
        except Exception as e:
            logger.warning("Failed to persist deletion proof: %s", e)

