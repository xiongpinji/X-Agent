"""JSON 文件持久化的用户/租户存储后端。

设计说明
========
- 为 ``backend.app.core.admin`` 中的内存版 ``UserStore``/``TenantStore``
  提供 **调用契约完全一致** 的 JSON 文件后端。
- 适用于开发/单实例部署: 数据持久化到本地 JSON 文件, 重启不丢失。
- 生产多实例部署仍应使用 postgres 后端(P1-19 守卫会拒绝 file 后端)。
- 写入策略: 每次写操作后原子写入整个 JSON 文件(先写临时文件再 rename),
  保证不会出现半写状态。
"""
from __future__ import annotations

import json
import logging
import tempfile
from datetime import UTC, datetime
from pathlib import Path
from threading import RLock
from typing import TYPE_CHECKING

import bcrypt

if TYPE_CHECKING:
    from backend.app.core.admin import (
        TenantCreateRequest,
        TenantRecord,
        TenantUpdateRequest,
        UserCreateRequest,
        UserRecord,
        UserUpdateRequest,
    )

logger = logging.getLogger(__name__)


def _import_admin_models():
    """Lazy import to avoid circular dependency with admin.py module-level singletons."""
    from backend.app.core.admin import (
        TenantRecord,
        UserRecord,
        _hash_password,
    )
    return UserRecord, TenantRecord, _hash_password


class FileUserStore:
    """JSON 文件持久化的用户存储, 接口与内存版 UserStore 一致。"""

    def __init__(self, storage_path: str | Path) -> None:
        self._storage_path = Path(storage_path)
        self._records: dict[str, UserRecord] = {}
        self._lock = RLock()
        # Cache model classes (admin.py is fully loaded by the time we're instantiated)
        self._UserRecord, _, self._hash_password = _import_admin_models()
        self._load_from_disk()

    # ------------------------------------------------------------------
    # 持久化
    # ------------------------------------------------------------------

    def _load_from_disk(self) -> None:
        if not self._storage_path.exists():
            return
        try:
            with self._storage_path.open("r", encoding="utf-8") as fh:
                payload = json.load(fh)
            users = payload.get("users", [])
            for item in users:
                record = self._UserRecord.model_validate(item)
                self._records[record.id] = record
            logger.info("FileUserStore: loaded %d users from %s", len(self._records), self._storage_path)
        except (json.JSONDecodeError, OSError) as exc:
            logger.warning("FileUserStore: failed to load %s: %s", self._storage_path, exc)

    def _persist(self) -> None:
        self._storage_path.parent.mkdir(parents=True, exist_ok=True)
        payload = {
            "users": [record.model_dump(mode="json") for record in self._records.values()],
        }
        # 原子写入: 先写临时文件再 rename, 避免半写
        fd, tmp_name = tempfile.mkstemp(
            dir=str(self._storage_path.parent),
            suffix=".tmp",
        )
        try:
            with open(fd, "w", encoding="utf-8") as fh:
                json.dump(payload, fh, ensure_ascii=False, indent=2)
            Path(tmp_name).replace(self._storage_path)
        except BaseException:
            # 清理临时文件
            try:
                Path(tmp_name).unlink(missing_ok=True)
            except OSError:
                pass
            raise

    # ------------------------------------------------------------------
    # 公开接口(与 UserStore 一致)
    # ------------------------------------------------------------------

    def upsert(self, request: UserCreateRequest | UserUpdateRequest, user_id: str | None = None) -> UserRecord:
        UserRecord = self._UserRecord
        with self._lock:
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
            self._persist()
            return record

    def create(self, request: UserCreateRequest, password: str | None = None) -> UserRecord:
        UserRecord = self._UserRecord
        with self._lock:
            record = UserRecord(
                email=request.email,
                display_name=request.display_name,
                role=request.role,
                tenant_id=request.tenant_id,
                password_hash=self._hash_password(password) if password else None,
            )
            self._records[record.id] = record
            self._persist()
            return record

    def authenticate(self, email: str, password: str) -> UserRecord | None:
        with self._lock:
            for record in self._records.values():
                if record.email == email:
                    if record.locked_until and datetime.now(UTC) < record.locked_until:
                        return None
                    if record.locked_until and datetime.now(UTC) >= record.locked_until:
                        record.locked_until = None
                        record.failed_login_attempts = 0
                    if record.password_hash:
                        if bcrypt.checkpw(password.encode("utf-8"), record.password_hash.encode("utf-8")):
                            record.failed_login_attempts = 0
                            record.updated_at = datetime.now(UTC)
                            self._records[record.id] = record
                            self._persist()
                            return record
                        else:
                            record.failed_login_attempts += 1
                            if record.failed_login_attempts >= 5:
                                from datetime import timedelta
                                record.locked_until = datetime.now(UTC) + timedelta(minutes=15)
                            record.updated_at = datetime.now(UTC)
                            self._records[record.id] = record
                            self._persist()
            return None

    def change_password(self, user_id: str, old_password: str, new_password: str) -> bool:
        with self._lock:
            record = self._records.get(user_id)
            if not record or not record.password_hash:
                return False
            if not bcrypt.checkpw(old_password.encode("utf-8"), record.password_hash.encode("utf-8")):
                return False
            for old_hash in record.password_history[-5:]:
                if bcrypt.checkpw(new_password.encode("utf-8"), old_hash.encode("utf-8")):
                    raise ValueError("Cannot reuse recent passwords")
            new_hash = self._hash_password(new_password)
            record.password_history.append(record.password_hash)
            if len(record.password_history) > 5:
                record.password_history = record.password_history[-5:]
            record.password_hash = new_hash
            record.updated_at = datetime.now(UTC)
            self._records[record.id] = record
            self._persist()
            return True

    def list(self) -> list[UserRecord]:
        with self._lock:
            return sorted(self._records.values(), key=lambda item: item.updated_at, reverse=True)

    def get(self, user_id: str) -> UserRecord | None:
        with self._lock:
            return self._records.get(user_id)

    def delete(self, user_id: str) -> bool:
        with self._lock:
            result = self._records.pop(user_id, None) is not None
            if result:
                self._persist()
            return result


class FileTenantStore:
    """JSON 文件持久化的租户存储, 接口与内存版 TenantStore 一致。"""

    def __init__(self, storage_path: str | Path) -> None:
        self._storage_path = Path(storage_path)
        self._records: dict[str, TenantRecord] = {}
        self._lock = RLock()
        # Cache model class
        _, self._TenantRecord, _ = _import_admin_models()
        self._load_from_disk()

    # ------------------------------------------------------------------
    # 持久化
    # ------------------------------------------------------------------

    def _load_from_disk(self) -> None:
        if not self._storage_path.exists():
            return
        try:
            with self._storage_path.open("r", encoding="utf-8") as fh:
                payload = json.load(fh)
            tenants = payload.get("tenants", [])
            for item in tenants:
                record = self._TenantRecord.model_validate(item)
                self._records[record.id] = record
            logger.info("FileTenantStore: loaded %d tenants from %s", len(self._records), self._storage_path)
        except (json.JSONDecodeError, OSError) as exc:
            logger.warning("FileTenantStore: failed to load %s: %s", self._storage_path, exc)

    def _persist(self) -> None:
        self._storage_path.parent.mkdir(parents=True, exist_ok=True)
        payload = {
            "tenants": [record.model_dump(mode="json") for record in self._records.values()],
        }
        fd, tmp_name = tempfile.mkstemp(
            dir=str(self._storage_path.parent),
            suffix=".tmp",
        )
        try:
            with open(fd, "w", encoding="utf-8") as fh:
                json.dump(payload, fh, ensure_ascii=False, indent=2)
            Path(tmp_name).replace(self._storage_path)
        except BaseException:
            try:
                Path(tmp_name).unlink(missing_ok=True)
            except OSError:
                pass
            raise

    # ------------------------------------------------------------------
    # 公开接口(与 TenantStore 一致)
    # ------------------------------------------------------------------

    def create(self, request: TenantCreateRequest) -> TenantRecord:
        TenantRecord = self._TenantRecord
        with self._lock:
            record = TenantRecord(name=request.name, plan=request.plan)
            self._records[record.id] = record
            self._persist()
            return record

    def upsert(self, request: TenantUpdateRequest, tenant_id: str) -> TenantRecord:
        TenantRecord = self._TenantRecord
        with self._lock:
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
            self._persist()
            return record

    def list(self) -> list[TenantRecord]:
        with self._lock:
            return sorted(self._records.values(), key=lambda item: item.updated_at, reverse=True)

    def get(self, tenant_id: str) -> TenantRecord | None:
        with self._lock:
            return self._records.get(tenant_id)

    def delete(self, tenant_id: str) -> bool:
        with self._lock:
            result = self._records.pop(tenant_id, None) is not None
            if result:
                self._persist()
            return result
