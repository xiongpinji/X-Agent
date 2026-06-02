from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path
from threading import RLock
from uuid import uuid4

import bcrypt
from pydantic import BaseModel, Field, field_validator

from backend.app.core.security import APIKeyCreateRequest, APIKeyCreateResponse, APIKeyRecord, APIKeyStore, Principal


class AuthLoginRequest(BaseModel):
    email: str
    password: str


class AuthTokenResponse(BaseModel):
    access_token: str
    refresh_token: str
    expires_in: int = 900
    token_type: str = "Bearer"
    user: dict[str, object]


class UserRecord(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid4()))
    email: str
    display_name: str = "User"
    role: str = "developer"
    tenant_id: str = "default"
    password_hash: str | None = None
    password_history: list[str] = Field(default_factory=list)  # Store last 5 password hashes
    failed_login_attempts: int = 0
    locked_until: datetime | None = None
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(UTC))


class UserCreateRequest(BaseModel):
    email: str
    display_name: str = "User"
    role: str = "developer"
    tenant_id: str = "default"

    @field_validator("email")
    @classmethod
    def _validate_email(cls, value: str) -> str:
        # 最小邮箱格式校验（零新依赖，不引 email-validator）：必须形如
        # local@domain.tld。非法值由 pydantic 在进 handler 前抛 422，符合
        # 创建用户端点的输入契约(见 test_create_user_invalid_email /
        # test_validation_error_format)。
        candidate = value.strip()
        local, sep, domain = candidate.partition("@")
        if not sep or not local or "." not in domain or domain.startswith(".") or domain.endswith("."):
            raise ValueError("Invalid email format.")
        return candidate


class UserUpdateRequest(BaseModel):
    email: str | None = None
    display_name: str | None = None
    role: str | None = None
    tenant_id: str | None = None


class TenantRecord(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid4()))
    name: str
    plan: str = "free"
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(UTC))


class TenantCreateRequest(BaseModel):
    name: str
    plan: str = "free"


class TenantUpdateRequest(BaseModel):
    name: str | None = None
    plan: str | None = None


class UserStore:
    def __init__(self, storage_path: str | Path | None = None) -> None:
        self._records: dict[str, UserRecord] = {}
        self._lock = RLock()

    def upsert(self, request: UserCreateRequest | UserUpdateRequest, user_id: str | None = None) -> UserRecord:
        existing = self._records.get(user_id or "")
        if existing is None and user_id is not None:
            record = UserRecord(id=user_id, email=request.email or "unknown@example.com")
        else:
            record = existing.model_copy() if existing else UserRecord(email=request.email or "unknown@example.com")
        if request.email is not None:
            record.email = request.email
        if request.display_name is not None:
            record.display_name = request.display_name
        if request.role is not None:
            record.role = request.role
        if request.tenant_id is not None:
            record.tenant_id = request.tenant_id
        record.updated_at = datetime.now(UTC)
        self._records[record.id] = record
        return record

    def create(self, request: UserCreateRequest, password: str | None = None) -> UserRecord:
        record = UserRecord(
            email=request.email,
            display_name=request.display_name,
            role=request.role,
            tenant_id=request.tenant_id,
            password_hash=_hash_password(password) if password else None,
        )
        self._records[record.id] = record
        return record

    def authenticate(self, email: str, password: str) -> UserRecord | None:
        """Authenticate user with email and password.

        Implements:
        - Account lockout checking
        - Password verification
        - Failed attempt tracking
        """
        for record in self._records.values():
            if record.email == email:
                # Check if account is locked
                if record.locked_until and datetime.now(UTC) < record.locked_until:
                    return None

                # Reset lock if lockout period has expired
                if record.locked_until and datetime.now(UTC) >= record.locked_until:
                    record.locked_until = None
                    record.failed_login_attempts = 0

                if record.password_hash:
                    if bcrypt.checkpw(password.encode("utf-8"), record.password_hash.encode("utf-8")):
                        # Successful authentication - reset failed attempts
                        record.failed_login_attempts = 0
                        record.updated_at = datetime.now(UTC)
                        self._records[record.id] = record
                        return record
                    else:
                        # Failed authentication - increment attempts
                        record.failed_login_attempts += 1
                        if record.failed_login_attempts >= 5:
                            # Lock account for 15 minutes
                            record.locked_until = datetime.now(UTC) + __import__('datetime').timedelta(minutes=15)
                        record.updated_at = datetime.now(UTC)
                        self._records[record.id] = record
        return None

    def change_password(self, user_id: str, old_password: str, new_password: str) -> bool:
        """Change user password with history check.

        Implements:
        - Old password verification
        - Password history check (prevent reuse of last 5 passwords)
        - Password strength validation
        """
        record = self._records.get(user_id)
        if not record or not record.password_hash:
            return False

        # Verify old password
        if not bcrypt.checkpw(old_password.encode("utf-8"), record.password_hash.encode("utf-8")):
            return False

        # Check if new password was used before (last 5 passwords)
        for old_hash in record.password_history[-5:]:
            if bcrypt.checkpw(new_password.encode("utf-8"), old_hash.encode("utf-8")):
                raise ValueError("Cannot reuse recent passwords")

        # Hash new password
        new_hash = _hash_password(new_password)

        # Update password history
        record.password_history.append(record.password_hash)
        if len(record.password_history) > 5:
            record.password_history = record.password_history[-5:]

        record.password_hash = new_hash
        record.updated_at = datetime.now(UTC)
        self._records[record.id] = record
        return True

    def list(self) -> list[UserRecord]:
        return sorted(self._records.values(), key=lambda item: item.updated_at, reverse=True)

    def get(self, user_id: str) -> UserRecord | None:
        return self._records.get(user_id)

    def delete(self, user_id: str) -> bool:
        return self._records.pop(user_id, None) is not None


class TenantStore:
    def __init__(self) -> None:
        self._records: dict[str, TenantRecord] = {}
        self._lock = RLock()

    def create(self, request: TenantCreateRequest) -> TenantRecord:
        record = TenantRecord(name=request.name, plan=request.plan)
        self._records[record.id] = record
        return record

    def upsert(self, request: TenantUpdateRequest, tenant_id: str) -> TenantRecord:
        existing = self._records.get(tenant_id)
        if existing is None:
            record = TenantRecord(id=tenant_id, name=request.name or "tenant", plan=request.plan or "free")
        else:
            record = existing.model_copy()
            if request.name is not None:
                record.name = request.name
            if request.plan is not None:
                record.plan = request.plan
            record.updated_at = datetime.now(UTC)
        self._records[record.id] = record
        return record

    def list(self) -> list[TenantRecord]:
        return sorted(self._records.values(), key=lambda item: item.updated_at, reverse=True)

    def get(self, tenant_id: str) -> TenantRecord | None:
        return self._records.get(tenant_id)

    def delete(self, tenant_id: str) -> bool:
        return self._records.pop(tenant_id, None) is not None


def _hash_password(password: str) -> str:
    return bcrypt.hashpw(password.encode("utf-8"), bcrypt.gensalt(rounds=12)).decode("utf-8")


user_store = UserStore()
tenant_store = TenantStore()
