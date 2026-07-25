"""P1-03: 用户/租户管理存储的 SQL(Postgres) 后端。

设计说明
========
- 本模块为 ``backend.app.core.admin`` 中的内存版 ``UserStore``/``TenantStore``
  提供 **调用契约完全一致** 的 SQL 后端。API 层(api/users.py、api/tenants.py、
  api/auth.py、dependencies.py)以 **同步** 方式调用存储, 因此这里使用
  同步 SQLAlchemy 2.0(而非 backend/app/models/user_store.py 的 async 实现)。
- 生产部署使用 Postgres + psycopg v3 驱动(requirements.txt 已含
  ``psycopg[binary]``); sqlite 仅用于 dev/测试降级。生产模式下 sqlite 会被
  ``backend.app.settings`` 的 fail-fast 守卫拒绝(P1-19)。
- 状态外置到数据库后, 多个应用实例共享同一份用户/租户数据(多实例共享),
  不再出现"重启即丢 / HPA 多副本数据分裂"。
- 表结构权威 DDL 见 ``backend/migrations/admin_user_tenant_schema.sql``;
  ``create_all`` 幂等, 开发/测试环境建表便捷, 生产以迁移 SQL 为准。

兼容说明
========
- ``_records`` 属性以 ``MutableMapping`` 视图暴露, 兼容既有的两处直接访问:
  ``tests/conftest.py`` 的 ``user_store._records.clear()`` 与
  ``api/auth.py`` 密码重置的 ``user_store._records[user.id] = user``
  (写穿透到数据库, 不产生静默丢失)。
"""
from __future__ import annotations

import json
import logging
from collections.abc import Iterator, MutableMapping
from datetime import UTC, datetime, timedelta

import bcrypt
from sqlalchemy import (
    DateTime,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
    create_engine,
    delete,
    func,
    select,
)
from sqlalchemy.engine import Engine
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import DeclarativeBase, Mapped, Session, mapped_column, sessionmaker
from sqlalchemy.pool import StaticPool

from backend.app.core.admin import (
    TenantCreateRequest,
    TenantRecord,
    TenantUpdateRequest,
    UserCreateRequest,
    UserRecord,
    UserUpdateRequest,
    _hash_password,
)

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# URL 规范化
# ---------------------------------------------------------------------------

def normalize_sync_database_url(database_url: str) -> str:
    """把配置中的 database_url 规范化为 **同步** SQLAlchemy URL。

    - ``postgres://`` / ``postgresql://`` / ``postgresql+asyncpg://``
      → ``postgresql+psycopg://`` (psycopg v3 同步驱动)
    - ``sqlite+aiosqlite:///`` → ``sqlite:///`` (同步 sqlite 驱动)
    - 其他原样返回(已是指定同步驱动的 URL, 如 ``postgresql+psycopg://``)。
    """
    url = database_url.strip()
    lowered = url.lower()
    if lowered.startswith("postgres://"):
        return "postgresql+psycopg://" + url[len("postgres://"):]
    if lowered.startswith("postgresql+asyncpg://"):
        return "postgresql+psycopg://" + url[len("postgresql+asyncpg://"):]
    if lowered.startswith("postgresql://"):
        return "postgresql+psycopg://" + url[len("postgresql://"):]
    if lowered.startswith("sqlite+aiosqlite://"):
        return "sqlite://" + url[len("sqlite+aiosqlite://"):]
    return url


# ---------------------------------------------------------------------------
# SQLAlchemy 模型(独立 metadata, 与 models/__init__.py 的 async 体系解耦)
# ---------------------------------------------------------------------------

class AdminStoreBase(DeclarativeBase):
    """用户/租户管理存储的 SQLAlchemy 基类。"""


class AdminUserModel(AdminStoreBase):
    """用户表(admin_users)——映射 admin.UserRecord 的全部字段。"""

    __tablename__ = "admin_users"

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    email: Mapped[str] = mapped_column(String(255), nullable=False)
    display_name: Mapped[str] = mapped_column(String(255), nullable=False, default="User")
    role: Mapped[str] = mapped_column(String(50), nullable=False, default="developer")
    tenant_id: Mapped[str] = mapped_column(String(36), nullable=False, default="default")
    password_hash: Mapped[str | None] = mapped_column(String(255), nullable=True)
    password_history_json: Mapped[str] = mapped_column(Text, nullable=False, default="[]")
    failed_login_attempts: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    locked_until: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=lambda: datetime.now(UTC)
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(UTC),
        onupdate=lambda: datetime.now(UTC),
    )

    __table_args__ = (
        UniqueConstraint("email", "tenant_id", name="uq_admin_users_email_tenant"),
        Index("idx_admin_users_email", "email"),
        Index("idx_admin_users_tenant_id", "tenant_id"),
        Index("idx_admin_users_updated_at", "updated_at"),
    )


class AdminTenantModel(AdminStoreBase):
    """租户表(admin_tenants)——映射 admin.TenantRecord 的全部字段。"""

    __tablename__ = "admin_tenants"

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    plan: Mapped[str] = mapped_column(String(50), nullable=False, default="free")
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=lambda: datetime.now(UTC)
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(UTC),
        onupdate=lambda: datetime.now(UTC),
    )

    __table_args__ = (
        Index("idx_admin_tenants_updated_at", "updated_at"),
    )


# ---------------------------------------------------------------------------
# 公共辅助
# ---------------------------------------------------------------------------

def _as_utc(value: datetime | None) -> datetime | None:
    """把数据库读出的 datetime 规范化为带 UTC 时区。

    sqlite 无原生时区支持, SQLAlchemy 读出为 naive datetime(按 UTC 写入);
    Postgres TIMESTAMPTZ 读出为 aware datetime。统一归一到 aware UTC,
    保证与内存后端一致的 Python 侧比较语义(如 locked_until 锁定判断)。
    """
    if value is None:
        return None
    if value.tzinfo is None:
        return value.replace(tzinfo=UTC)
    return value.astimezone(UTC)


class _EngineFactory:
    """同步引擎/会话工厂。每个存储实例持有自己的引擎(测试友好, 多实例可指向同一库)。"""

    def __init__(self, database_url: str, *, echo: bool = False, create_schema: bool = True) -> None:
        self.sync_url = normalize_sync_database_url(database_url)
        engine_kwargs: dict[str, object] = {"echo": echo, "future": True}
        if self.sync_url.startswith("sqlite"):
            # sqlite 文件/内存库: 允许多线程(TestClient 线程池)共享连接
            engine_kwargs["connect_args"] = {"check_same_thread": False}
            if ":memory:" in self.sync_url:
                engine_kwargs["poolclass"] = StaticPool
        else:
            # Postgres 等外部库: 连接池 + 探活, 支持多实例共享
            engine_kwargs.update(
                pool_size=5,
                max_overflow=10,
                pool_recycle=1800,
                pool_pre_ping=True,
            )
        self.engine: Engine = create_engine(self.sync_url, **engine_kwargs)
        self.session_factory = sessionmaker(bind=self.engine, expire_on_commit=False)
        if create_schema:
            # 幂等建表(IF NOT EXISTS 语义); 生产权威 DDL 为 migrations SQL
            AdminStoreBase.metadata.create_all(self.engine)

    def session(self) -> Session:
        return self.session_factory()


def _user_model_to_record(model: AdminUserModel) -> UserRecord:
    try:
        history = json.loads(model.password_history_json or "[]")
        if not isinstance(history, list):
            history = []
    except (TypeError, ValueError):
        history = []
    return UserRecord(
        id=model.id,
        email=model.email,
        display_name=model.display_name,
        role=model.role,
        tenant_id=model.tenant_id,
        password_hash=model.password_hash,
        password_history=history,
        failed_login_attempts=model.failed_login_attempts or 0,
        locked_until=_as_utc(model.locked_until),
        created_at=_as_utc(model.created_at) or datetime.now(UTC),
        updated_at=_as_utc(model.updated_at) or datetime.now(UTC),
    )


def _tenant_model_to_record(model: AdminTenantModel) -> TenantRecord:
    return TenantRecord(
        id=model.id,
        name=model.name,
        plan=model.plan,
        created_at=_as_utc(model.created_at) or datetime.now(UTC),
        updated_at=_as_utc(model.updated_at) or datetime.now(UTC),
    )


# ---------------------------------------------------------------------------
# 用户存储 SQL 后端
# ---------------------------------------------------------------------------

class SqlUserStore:
    """UserStore 的 SQL(Postgres) 后端, 与内存版接口一致(同步调用)。"""

    backend_name = "sql"

    def __init__(self, database_url: str, *, echo: bool = False, create_schema: bool = True) -> None:
        self._factory = _EngineFactory(database_url, echo=echo, create_schema=create_schema)

    # ---- 内部持久化原语 ----

    def _persist_record(self, record: UserRecord) -> UserRecord:
        """按 id 插入或更新整条用户记录(供 create/upsert/_records 写穿透复用)。"""
        with self._factory.session() as session:
            model = session.get(AdminUserModel, record.id)
            if model is None:
                model = AdminUserModel(id=record.id, email=record.email)
                session.add(model)
            model.email = record.email
            model.display_name = record.display_name
            model.role = record.role
            model.tenant_id = record.tenant_id
            model.password_hash = record.password_hash
            model.password_history_json = json.dumps(record.password_history or [])
            model.failed_login_attempts = record.failed_login_attempts
            model.locked_until = record.locked_until
            model.created_at = record.created_at
            model.updated_at = record.updated_at
            try:
                session.commit()
            except IntegrityError as exc:
                session.rollback()
                raise ValueError(
                    f"用户保存失败: email={record.email} 在租户 {record.tenant_id} 下已存在"
                ) from exc
        return record

    def _load_model(self, session: Session, user_id: str) -> AdminUserModel | None:
        return session.get(AdminUserModel, user_id)

    def count(self) -> int:
        with self._factory.session() as session:
            return int(session.scalar(select(func.count()).select_from(AdminUserModel)) or 0)

    def _delete_all(self) -> None:
        """清空全部用户(兼容 conftest 的 _records.clear() 语义, 仅用于测试/重置)。"""
        with self._factory.session() as session:
            session.execute(delete(AdminUserModel))
            session.commit()

    # ---- 与内存版一致的公开接口 ----

    def upsert(self, request: UserCreateRequest | UserUpdateRequest, user_id: str | None = None) -> UserRecord:
        existing = self.get(user_id) if user_id else None
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
        return self._persist_record(record)

    def create(self, request: UserCreateRequest, password: str | None = None) -> UserRecord:
        record = UserRecord(
            email=request.email,
            display_name=request.display_name,
            role=request.role,
            tenant_id=request.tenant_id,
            password_hash=_hash_password(password) if password else None,
        )
        return self._persist_record(record)

    def authenticate(self, email: str, password: str) -> UserRecord | None:
        """邮箱+密码认证, 语义与内存版一致(锁定检查/失败计数/15 分钟锁定)。

        读会话只做查询并立即关闭(避免 sqlite 下读事务与后续写事务争锁);
        状态变更通过独立会话持久化。
        """
        with self._factory.session() as session:
            # 内存版按插入序取第一个 email 匹配者; 这里按 created_at 升序对齐该语义
            stmt = (
                select(AdminUserModel)
                .where(AdminUserModel.email == email)
                .order_by(AdminUserModel.created_at.asc())
                .limit(1)
            )
            model = session.scalar(stmt)
            record = _user_model_to_record(model) if model is not None else None

        if record is None:
            return None

        now = datetime.now(UTC)
        if record.locked_until and now < record.locked_until:
            return None

        lock_reset = False
        if record.locked_until and now >= record.locked_until:
            record.locked_until = None
            record.failed_login_attempts = 0
            lock_reset = True

        if not record.password_hash:
            if lock_reset:
                record.updated_at = now
                self._persist_record(record)
            return None

        if bcrypt.checkpw(password.encode("utf-8"), record.password_hash.encode("utf-8")):
            record.failed_login_attempts = 0
            record.updated_at = now
            self._persist_record(record)
            return record

        record.failed_login_attempts += 1
        if record.failed_login_attempts >= 5:
            record.locked_until = now + timedelta(minutes=15)
        record.updated_at = now
        self._persist_record(record)
        return None

    def change_password(self, user_id: str, old_password: str, new_password: str) -> bool:
        """修改密码(校验旧密码 + 最近 5 次历史防复用), 语义与内存版一致。"""
        record = self.get(user_id)
        if not record or not record.password_hash:
            return False
        if not bcrypt.checkpw(old_password.encode("utf-8"), record.password_hash.encode("utf-8")):
            return False
        for old_hash in record.password_history[-5:]:
            if bcrypt.checkpw(new_password.encode("utf-8"), old_hash.encode("utf-8")):
                raise ValueError("Cannot reuse recent passwords")
        new_hash = _hash_password(new_password)
        record.password_history.append(record.password_hash)
        if len(record.password_history) > 5:
            record.password_history = record.password_history[-5:]
        record.password_hash = new_hash
        record.updated_at = datetime.now(UTC)
        self._persist_record(record)
        return True

    def list(self) -> list[UserRecord]:
        with self._factory.session() as session:
            stmt = select(AdminUserModel).order_by(AdminUserModel.updated_at.desc())
            return [_user_model_to_record(m) for m in session.scalars(stmt).all()]

    def get(self, user_id: str) -> UserRecord | None:
        with self._factory.session() as session:
            model = self._load_model(session, user_id)
            return _user_model_to_record(model) if model is not None else None

    def delete(self, user_id: str) -> bool:
        with self._factory.session() as session:
            model = self._load_model(session, user_id)
            if model is None:
                return False
            session.delete(model)
            session.commit()
            return True

    @property
    def _records(self) -> MutableMapping[str, UserRecord]:
        """兼容视图: 直写 _records 会写穿透到数据库(见模块 docstring)。"""
        return _UserRecordsMapping(self)


class _UserRecordsMapping(MutableMapping[str, UserRecord]):
    """``SqlUserStore._records`` 的 DB  backed MutableMapping 视图。"""

    def __init__(self, store: SqlUserStore) -> None:
        self._store = store

    def __getitem__(self, key: str) -> UserRecord:
        record = self._store.get(key)
        if record is None:
            raise KeyError(key)
        return record

    def __setitem__(self, key: str, value: UserRecord) -> None:
        if not isinstance(value, UserRecord):
            raise TypeError("_records 仅接受 UserRecord 值")
        self._store._persist_record(value)

    def __delitem__(self, key: str) -> None:
        if not self._store.delete(key):
            raise KeyError(key)

    def __iter__(self) -> Iterator[str]:
        return (record.id for record in self._store.list())

    def __len__(self) -> int:
        return self._store.count()

    def clear(self) -> None:
        self._store._delete_all()


# ---------------------------------------------------------------------------
# 租户存储 SQL 后端
# ---------------------------------------------------------------------------

class SqlTenantStore:
    """TenantStore 的 SQL(Postgres) 后端, 与内存版接口一致(同步调用)。"""

    backend_name = "sql"

    def __init__(self, database_url: str, *, echo: bool = False, create_schema: bool = True) -> None:
        self._factory = _EngineFactory(database_url, echo=echo, create_schema=create_schema)

    def _persist_record(self, record: TenantRecord) -> TenantRecord:
        with self._factory.session() as session:
            model = session.get(AdminTenantModel, record.id)
            if model is None:
                model = AdminTenantModel(id=record.id, name=record.name)
                session.add(model)
            model.name = record.name
            model.plan = record.plan
            model.created_at = record.created_at
            model.updated_at = record.updated_at
            session.commit()
        return record

    def count(self) -> int:
        with self._factory.session() as session:
            return int(session.scalar(select(func.count()).select_from(AdminTenantModel)) or 0)

    def _delete_all(self) -> None:
        with self._factory.session() as session:
            session.execute(delete(AdminTenantModel))
            session.commit()

    # ---- 与内存版一致的公开接口 ----

    def create(self, request: TenantCreateRequest) -> TenantRecord:
        record = TenantRecord(name=request.name, plan=request.plan)
        return self._persist_record(record)

    def upsert(self, request: TenantUpdateRequest, tenant_id: str) -> TenantRecord:
        existing = self.get(tenant_id)
        if existing is None:
            record = TenantRecord(id=tenant_id, name=request.name or "tenant", plan=request.plan or "free")
        else:
            record = existing.model_copy()
            if request.name is not None:
                record.name = request.name
            if request.plan is not None:
                record.plan = request.plan
            record.updated_at = datetime.now(UTC)
        return self._persist_record(record)

    def list(self) -> list[TenantRecord]:
        with self._factory.session() as session:
            stmt = select(AdminTenantModel).order_by(AdminTenantModel.updated_at.desc())
            return [_tenant_model_to_record(m) for m in session.scalars(stmt).all()]

    def get(self, tenant_id: str) -> TenantRecord | None:
        with self._factory.session() as session:
            model = session.get(AdminTenantModel, tenant_id)
            return _tenant_model_to_record(model) if model is not None else None

    def delete(self, tenant_id: str) -> bool:
        with self._factory.session() as session:
            model = session.get(AdminTenantModel, tenant_id)
            if model is None:
                return False
            session.delete(model)
            session.commit()
            return True

    @property
    def _records(self) -> MutableMapping[str, TenantRecord]:
        return _TenantRecordsMapping(self)


class _TenantRecordsMapping(MutableMapping[str, TenantRecord]):
    """``SqlTenantStore._records`` 的 DB backed MutableMapping 视图。"""

    def __init__(self, store: SqlTenantStore) -> None:
        self._store = store

    def __getitem__(self, key: str) -> TenantRecord:
        record = self._store.get(key)
        if record is None:
            raise KeyError(key)
        return record

    def __setitem__(self, key: str, value: TenantRecord) -> None:
        if not isinstance(value, TenantRecord):
            raise TypeError("_records 仅接受 TenantRecord 值")
        self._store._persist_record(value)

    def __delitem__(self, key: str) -> None:
        if not self._store.delete(key):
            raise KeyError(key)

    def __iter__(self) -> Iterator[str]:
        return (record.id for record in self._store.list())

    def __len__(self) -> int:
        return self._store.count()

    def clear(self) -> None:
        self._store._delete_all()
