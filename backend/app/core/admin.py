from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path
from threading import RLock
from typing import TYPE_CHECKING
from uuid import uuid4

import bcrypt
from pydantic import BaseModel, Field, field_validator


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


# ---------------------------------------------------------------------------
# P1-03: 存储后端装配(内存 dev 降级 / Postgres 生产)
# ---------------------------------------------------------------------------

_SQL_BACKEND_ALIASES = {"postgres", "postgresql", "sql", "database", "db"}
_FILE_BACKEND_ALIASES = {"file", "json"}


def _resolve_admin_store_config(
    backend: str | None,
    database_url: str | None,
) -> tuple[str, str | None]:
    """解析用户/租户存储后端配置。

    解析顺序: 显式参数 > settings(XAGENT_ADMIN_STORE_BACKEND / XAGENT_DATABASE_URL)
    > 安全默认(memory)。settings 模块不可导入(极端早期导入)时回退 memory;
    但 settings 校验失败(如生产模式 fail-fast 守卫)必须向上抛出——
    绝不静默降级回内存后端(否则会架空 P1-19 的拒绝启动语义)。
    """
    if backend is None or (backend in _SQL_BACKEND_ALIASES and database_url is None):
        try:
            from backend.app.settings import get_settings
        except ImportError:  # settings 模块本身不可导入的极端场景: dev 回退内存
            return (backend or "memory").strip().lower(), database_url

        settings = get_settings()  # ValidationError(含 P1-19 fail-fast)直接上抛
        if backend is None:
            backend = getattr(settings, "admin_store_backend", "memory")
        if database_url is None:
            database_url = settings.database_url
    backend = (backend or "memory").strip().lower()
    return backend, database_url


def create_user_store(
    backend: str | None = None,
    database_url: str | None = None,
) -> UserStore | SqlUserStoreProtocol:
    """按配置创建用户存储。

    - ``memory``: 进程内存后端(仅测试; 重启即丢, 不可多实例共享)
    - ``file``(别名 json): JSON 文件后端(dev/单实例; 重启不丢, 不可多实例共享)
    - ``postgres``(别名 postgresql/sql/database/db): SQL 后端, 状态外置,
      支持多实例共享(P1-03)。需要 ``database_url``(生产为 Postgres DSN)。
    """
    resolved_backend, resolved_url = _resolve_admin_store_config(backend, database_url)
    if resolved_backend == "memory":
        return UserStore()
    if resolved_backend in _FILE_BACKEND_ALIASES:
        from backend.app.core.admin_store_file import FileUserStore
        from backend.app.settings import get_settings

        store_path = get_settings().admin_store_path
        return FileUserStore(store_path)
    if resolved_backend in _SQL_BACKEND_ALIASES:
        if not resolved_url:
            raise ValueError(
                "admin_store_backend=postgres 需要 database_url "
                "(设置 XAGENT_DATABASE_URL 或显式传参)"
            )
        from backend.app.core.admin_store import SqlUserStore

        return SqlUserStore(resolved_url)
    raise ValueError(
        f"未知用户存储后端: {resolved_backend!r}; 合法值: memory, file, postgres"
    )


def create_tenant_store(
    backend: str | None = None,
    database_url: str | None = None,
) -> TenantStore | SqlTenantStoreProtocol:
    """按配置创建租户存储(后端取值与 create_user_store 相同)。"""
    resolved_backend, resolved_url = _resolve_admin_store_config(backend, database_url)
    if resolved_backend == "memory":
        return TenantStore()
    if resolved_backend in _FILE_BACKEND_ALIASES:
        from backend.app.core.admin_store_file import FileTenantStore
        from backend.app.settings import get_settings

        store_path = get_settings().admin_store_path
        return FileTenantStore(store_path)
    if resolved_backend in _SQL_BACKEND_ALIASES:
        if not resolved_url:
            raise ValueError(
                "admin_store_backend=postgres 需要 database_url "
                "(设置 XAGENT_DATABASE_URL 或显式传参)"
            )
        from backend.app.core.admin_store import SqlTenantStore

        return SqlTenantStore(resolved_url)
    raise ValueError(
        f"未知租户存储后端: {resolved_backend!r}; 合法值: memory, file, postgres"
    )


if TYPE_CHECKING:
    from backend.app.core.admin_store import SqlTenantStore as SqlTenantStoreProtocol
    from backend.app.core.admin_store import SqlUserStore as SqlUserStoreProtocol


# 全局存储单例: 按 settings 装配(默认 file; XAGENT_ADMIN_STORE_BACKEND=postgres
# 时切换为 SQL 后端)。生产模式下 settings 守卫(P1-19)会拒绝 memory/file 后端。
user_store = create_user_store()
tenant_store = create_tenant_store()
