from __future__ import annotations

import json
from datetime import UTC, datetime
from hashlib import sha256
from hmac import new as hmac_new
from pathlib import Path
from threading import RLock
from typing import Any
from uuid import uuid4

from pydantic import BaseModel, Field

from backend.app.core.config import get_settings


class AuditLogRecord(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid4()))
    tenant_id: str = "default"
    actor_id: str = "anonymous"
    action: str
    resource_type: str
    resource_id: str | None = None
    outcome: str = "success"
    trace_id: str | None = None
    run_id: str | None = None
    workflow_id: str | None = None
    details: dict[str, Any] = Field(default_factory=dict)
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    prev_hash: str | None = None
    hash: str | None = None
    signature: str | None = None
    snapshot: dict[str, Any] = Field(default_factory=dict)


class AuditChainVerification(BaseModel):
    valid: bool
    checked: int
    signed: int = 0
    signature_valid: bool = True
    broken_at: str | None = None
    reason: str | None = None


class AuditStore:
    def __init__(
        self,
        storage_path: str | Path | None = None,
        hmac_secret: str | None = None,
    ) -> None:
        self._records: list[AuditLogRecord] = []
        self._lock = RLock()
        self._storage_path = Path(storage_path) if storage_path else None
        self._hmac_secret = hmac_secret

        # Production fail-fast: HMAC secret is required in production
        settings = get_settings()
        if settings.is_production() and not self._hmac_secret:
            raise RuntimeError(
                "Audit HMAC secret is required in production. "
                "Set XAGENT_AUDIT_HMAC_SECRET environment variable."
            )

        if self._storage_path:
            self._load_from_disk()

    def record(
        self,
        *,
        action: str,
        resource_type: str,
        tenant_id: str = "default",
        actor_id: str = "anonymous",
        resource_id: str | None = None,
        outcome: str = "success",
        trace_id: str | None = None,
        run_id: str | None = None,
        workflow_id: str | None = None,
        details: dict[str, Any] | None = None,
    ) -> AuditLogRecord:
        previous_hash = self._records[-1].hash if self._records else None
        record = AuditLogRecord(
            tenant_id=tenant_id,
            actor_id=actor_id,
            action=action,
            resource_type=resource_type,
            resource_id=resource_id,
            outcome=outcome,
            trace_id=trace_id,
            run_id=run_id,
            workflow_id=workflow_id,
            details=details or {},
            prev_hash=previous_hash,
            snapshot={
                "trace_id": trace_id,
                "run_id": run_id,
                "workflow_id": workflow_id,
                "action": action,
                "resource_type": resource_type,
                "resource_id": resource_id,
                "outcome": outcome,
            },
        )
        record.hash = self._hash_record(record)
        record.signature = self._signature_record(record)
        with self._lock:
            self._records.append(record)
            self._append_to_disk(record)
        return record

    def list(
        self,
        *,
        limit: int = 50,
        offset: int = 0,
        tenant_id: str | None = None,
        actor_id: str | None = None,
        action: str | None = None,
        resource_type: str | None = None,
        outcome: str | None = None,
    ) -> list[AuditLogRecord]:
        """List audit records with filtering and pagination.

        Args:
            limit: Maximum number of records to return
            offset: Number of records to skip
            tenant_id: Filter by tenant
            actor_id: Filter by actor
            action: Filter by action
            resource_type: Filter by resource type
            outcome: Filter by outcome

        Returns:
            List of matching audit records
        """
        records = [
            record
            for record in self._records
            if (tenant_id is None or record.tenant_id == tenant_id)
            and (actor_id is None or record.actor_id == actor_id)
            and (action is None or record.action == action)
            and (resource_type is None or record.resource_type == resource_type)
            and (outcome is None or record.outcome == outcome)
        ]
        records.sort(key=lambda record: record.created_at, reverse=True)
        return records[offset : offset + limit]

    def count(self) -> int:
        return len(self._records)

    def verify_chain(self) -> AuditChainVerification:
        previous_hash: str | None = None
        signed = 0
        for index, record in enumerate(self._records):
            if record.prev_hash != previous_hash:
                return AuditChainVerification(
                    valid=False,
                    checked=index,
                    signed=signed,
                    broken_at=record.id,
                    reason="Previous hash mismatch.",
                )
            expected_hash = self._hash_record(record)
            if record.hash != expected_hash:
                return AuditChainVerification(
                    valid=False,
                    checked=index,
                    signed=signed,
                    broken_at=record.id,
                    reason="Record hash mismatch.",
                )
            if record.signature is not None:
                signed += 1

            # When HMAC is enabled, enforce that ALL records must have valid signatures
            if self._hmac_secret is not None:
                if record.signature is None:
                    return AuditChainVerification(
                        valid=False,
                        checked=index,
                        signed=signed,
                        signature_valid=False,
                        broken_at=record.id,
                        reason="Record missing required signature (HMAC enabled).",
                    )
                expected_signature = self._signature_record(record)
                if record.signature != expected_signature:
                    return AuditChainVerification(
                        valid=False,
                        checked=index,
                        signed=signed,
                        signature_valid=False,
                        broken_at=record.id,
                        reason="Record signature mismatch.",
                    )
            previous_hash = record.hash
        return AuditChainVerification(valid=True, checked=len(self._records), signed=signed)

    def _load_from_disk(self) -> None:
        if self._storage_path is None or not self._storage_path.exists():
            return
        bad_lines = 0
        with self._storage_path.open("r", encoding="utf-8") as handle:
            for line in handle:
                line = line.strip()
                if not line:
                    continue
                try:
                    self._records.append(
                        AuditLogRecord.model_validate(json.loads(line))
                    )
                except (json.JSONDecodeError, ValueError) as exc:
                    bad_lines += 1
                    import logging
                    logging.getLogger(__name__).warning(
                        "Skipping corrupt audit line in %s: %s",
                        self._storage_path, exc,
                    )
        if bad_lines:
            import logging
            logging.getLogger(__name__).warning(
                "Audit store loaded with %d corrupt line(s) skipped.", bad_lines
            )

    def _append_to_disk(self, record: AuditLogRecord) -> None:
        if self._storage_path is None:
            return
        self._storage_path.parent.mkdir(parents=True, exist_ok=True)
        with self._storage_path.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(record.model_dump(mode="json"), ensure_ascii=False) + "\n")

    @staticmethod
    def _hash_record(record: AuditLogRecord) -> str:
        payload = record.model_dump(mode="json", exclude={"hash", "signature"})
        serialized = json.dumps(payload, sort_keys=True, ensure_ascii=False, separators=(",", ":"))
        return sha256(serialized.encode("utf-8")).hexdigest()

    def _signature_record(self, record: AuditLogRecord) -> str | None:
        if self._hmac_secret is None:
            return None
        digest = record.hash or self._hash_record(record)
        return hmac_new(
            self._hmac_secret.encode("utf-8"),
            digest.encode("utf-8"),
            sha256,
        ).hexdigest()

    def export_csv(
        self,
        *,
        tenant_id: str | None = None,
        actor_id: str | None = None,
        action: str | None = None,
        resource_type: str | None = None,
        outcome: str | None = None,
    ) -> str:
        """Export audit logs as CSV format.

        Args:
            tenant_id: Filter by tenant
            actor_id: Filter by actor
            action: Filter by action
            resource_type: Filter by resource type
            outcome: Filter by outcome

        Returns:
            CSV formatted string
        """
        import csv
        from io import StringIO

        records = self.list(
            limit=10000,
            tenant_id=tenant_id,
            actor_id=actor_id,
            action=action,
            resource_type=resource_type,
            outcome=outcome,
        )

        output = StringIO()
        writer = csv.DictWriter(
            output,
            fieldnames=[
                "id",
                "created_at",
                "tenant_id",
                "actor_id",
                "action",
                "resource_type",
                "resource_id",
                "outcome",
                "trace_id",
                "run_id",
                "workflow_id",
            ],
        )
        writer.writeheader()
        for record in records:
            writer.writerow({
                "id": record.id,
                "created_at": record.created_at.isoformat(),
                "tenant_id": record.tenant_id,
                "actor_id": record.actor_id,
                "action": record.action,
                "resource_type": record.resource_type,
                "resource_id": record.resource_id,
                "outcome": record.outcome,
                "trace_id": record.trace_id,
                "run_id": record.run_id,
                "workflow_id": record.workflow_id,
            })
        return output.getvalue()

    def export_json(
        self,
        *,
        tenant_id: str | None = None,
        actor_id: str | None = None,
        action: str | None = None,
        resource_type: str | None = None,
        outcome: str | None = None,
    ) -> list[dict[str, Any]]:
        """Export audit logs as JSON format.

        Args:
            tenant_id: Filter by tenant
            actor_id: Filter by actor
            action: Filter by action
            resource_type: Filter by resource type
            outcome: Filter by outcome

        Returns:
            List of audit records as dictionaries
        """
        records = self.list(
            limit=10000,
            tenant_id=tenant_id,
            actor_id=actor_id,
            action=action,
            resource_type=resource_type,
            outcome=outcome,
        )
        return [record.model_dump(mode="json") for record in records]
