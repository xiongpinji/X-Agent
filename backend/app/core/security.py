from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path
from secrets import token_urlsafe
from threading import RLock
from uuid import uuid4

import bcrypt
from pydantic import BaseModel, Field

ROLE_SCOPES: dict[str, list[str]] = {
    "admin": [
        "agent:run",
        "agent:read",
        "tools:*",
        "memory:read",
        "memory:write",
        "workflow:create",
        "workflow:manage",
        "workflow:run",
        "workflow:control",
        "audit:read",
        "security:manage",
        "sandbox:run",
        "sandbox:read",
    ],
    "developer": [
        "agent:run",
        "agent:read",
        "tools:read",
        "memory:read",
        "memory:write",
        "workflow:create",
        "workflow:run",
        "audit:read",
        "sandbox:run",
    ],
    "user": [
        "agent:run",
        "tools:read",
        "memory:read",
        "memory:write",
        "workflow:run",
    ],
    "viewer": ["memory:read", "audit:read"],
    "anonymous": [],  # SECURITY: Anonymous users have NO permissions
}


class Principal(BaseModel):
    tenant_id: str = "default"
    user_id: str = "anonymous"
    agent_id: str = "default-agent"
    request_id: str = Field(default_factory=lambda: str(uuid4()))
    trace_id: str = Field(default_factory=lambda: str(uuid4()))
    permission_scope: list[str] = Field(default_factory=list)
    role: str = "anonymous"
    scopes: list[str] = Field(default_factory=list)
    api_key_id: str | None = None
    authenticated: bool = False


class APIKeyRecord(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid4()))
    name: str
    key_prefix: str
    key_hash: str
    tenant_id: str = "default"
    user_id: str = "anonymous"
    role: str = "developer"
    scopes: list[str] = Field(default_factory=list)
    revoked: bool = False
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    revoked_at: datetime | None = None
    expires_at: datetime | None = None  # SECURITY: API Key过期时间（90天）
    last_used_at: datetime | None = None  # 最后使用时间


class APIKeyCreateRequest(BaseModel):
    name: str
    tenant_id: str = "default"
    user_id: str = "anonymous"
    role: str = "developer"
    scopes: list[str] = Field(default_factory=list)


class APIKeyCreateResponse(BaseModel):
    key: str
    record: APIKeyRecord


class RBACPolicy:
    def scopes_for_role(self, role: str) -> list[str]:
        return list(ROLE_SCOPES.get(role, []))

    def resolve_scopes(self, principal: Principal, requested_scopes: list[str]) -> list[str]:
        """Resolve scopes for principal.

        SECURITY: Unauthenticated principals get no scopes.
        """
        if not principal.authenticated:
            return []  # SECURITY: Anonymous users get NO scopes
        if self.has_scope(principal, "tools:*"):
            return requested_scopes
        return [scope for scope in requested_scopes if self.has_scope(principal, scope)]

    def has_scope(self, principal: Principal, scope: str) -> bool:
        """Check if principal has required scope.

        SECURITY: Unauthenticated principals have no scopes.
        """
        if not principal.authenticated:
            return False  # SECURITY: Reject unauthenticated access
        return scope in principal.scopes or self._wildcard_scope(scope) in principal.scopes

    @staticmethod
    def _wildcard_scope(scope: str) -> str:
        namespace = scope.split(":", 1)[0]
        return f"{namespace}:*"


class APIKeyStore:
    def __init__(self, storage_path: str | Path | None = None) -> None:
        self._records: dict[str, APIKeyRecord] = {}
        self._hash_index: dict[str, list[str]] = {}  # prefix -> [record_id, ...]
        self._lock = RLock()
        self._storage_path = Path(storage_path) if storage_path else None
        if self._storage_path:
            self._load_from_disk()

    def create(self, request: APIKeyCreateRequest) -> APIKeyCreateResponse:
        raw_key = f"xag_{token_urlsafe(32)}"
        role_scopes = ROLE_SCOPES.get(request.role, [])
        scopes = request.scopes or role_scopes
        # SECURITY: API Key自动设置90天过期时间
        expires_at = datetime.now(UTC) + __import__('datetime').timedelta(days=90)
        record = APIKeyRecord(
            name=request.name,
            key_prefix=raw_key[:12],
            key_hash=self._hash_key(raw_key),
            tenant_id=request.tenant_id,
            user_id=request.user_id,
            role=request.role,
            scopes=list(scopes),
            expires_at=expires_at,
        )
        with self._lock:
            self._records[record.id] = record
            self._hash_index.setdefault(record.key_prefix, []).append(record.id)
            self._persist()
        return APIKeyCreateResponse(key=raw_key, record=record)

    def authenticate(self, raw_key: str) -> Principal | None:
        prefix = raw_key[:12]
        candidates = self._hash_index.get(prefix, [])
        for record_id in candidates:
            record = self._records.get(record_id)
            if record is None or record.revoked:
                continue
            # SECURITY: 检查API Key是否过期
            if record.expires_at and datetime.now(UTC) > record.expires_at:
                continue
            if bcrypt.checkpw(raw_key.encode("utf-8"), record.key_hash.encode("utf-8")):
                # 更新最后使用时间
                record.last_used_at = datetime.now(UTC)
                self._records[record_id] = record
                return Principal(
                    tenant_id=record.tenant_id,
                    user_id=record.user_id,
                    role=record.role,
                    scopes=record.scopes,
                    api_key_id=record.id,
                    authenticated=True,
                )
        return None

    def list(self) -> list[APIKeyRecord]:
        records = list(self._records.values())
        records.sort(key=lambda record: record.created_at, reverse=True)
        return records

    def revoke(self, key_id: str) -> APIKeyRecord | None:
        with self._lock:
            record = self._records.get(key_id)
            if record is None:
                return None
            updated = record.model_copy(
                update={"revoked": True, "revoked_at": datetime.now(UTC)}
            )
            self._records[key_id] = updated
            prefix_list = self._hash_index.get(updated.key_prefix, [])
            if key_id in prefix_list:
                prefix_list.remove(key_id)
                if not prefix_list:
                    del self._hash_index[updated.key_prefix]
            self._persist()
            return updated

    def count(self) -> int:
        return len(self._records)

    def active_count(self) -> int:
        return sum(1 for record in self._records.values() if not record.revoked)

    def _load_from_disk(self) -> None:
        if self._storage_path is None or not self._storage_path.exists():
            return
        with self._storage_path.open("r", encoding="utf-8") as handle:
            payload = json.load(handle)
        for item in payload:
            record = APIKeyRecord.model_validate(item)
            self._records[record.id] = record
            self._hash_index.setdefault(record.key_prefix, []).append(record.id)

    def _persist(self) -> None:
        if self._storage_path is None:
            return
        self._storage_path.parent.mkdir(parents=True, exist_ok=True)
        payload = [record.model_dump(mode="json") for record in self.list()]
        self._storage_path.write_text(
            json.dumps(payload, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )

    @staticmethod
    def _hash_key(raw_key: str) -> str:
        return bcrypt.hashpw(raw_key.encode("utf-8"), bcrypt.gensalt(rounds=12)).decode("utf-8")


def anonymous_principal() -> Principal:
    return Principal(scopes=[])
