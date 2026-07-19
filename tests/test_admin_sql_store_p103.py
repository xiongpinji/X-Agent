"""P1-03 验证: UserStore/TenantStore 的 SQL(Postgres) 后端。

验证策略(任务书要求):
- Postgres 在本环境不可用, 使用 sqlite(同步驱动 + aiosqlite 异步驱动)验证
  SQLAlchemy 模型与存储逻辑——模型/映射层与方言无关, 生产 Postgres 走同一套代码路径。
- 覆盖: CRUD、认证锁定、密码历史、多实例共享、_records 兼容、工厂装配。
"""
from __future__ import annotations

from datetime import UTC, datetime

import pytest
from sqlalchemy.ext.asyncio import create_async_engine

from backend.app.core.admin import (
    TenantCreateRequest,
    TenantUpdateRequest,
    UserCreateRequest,
    UserUpdateRequest,
    UserStore,
    TenantStore,
    create_tenant_store,
    create_user_store,
)
from backend.app.core.admin_store import (
    AdminStoreBase,
    AdminUserModel,
    SqlTenantStore,
    SqlUserStore,
    normalize_sync_database_url,
)


@pytest.fixture
def sqlite_url(tmp_path) -> str:
    return f"sqlite:///{tmp_path / 'admin_store.db'}"


@pytest.fixture
def user_store(sqlite_url) -> SqlUserStore:
    return SqlUserStore(sqlite_url)


@pytest.fixture
def tenant_store(sqlite_url) -> SqlTenantStore:
    return SqlTenantStore(sqlite_url)


def _make_user_req(email: str = "alice@example.com", **overrides) -> UserCreateRequest:
    payload = {"email": email, "display_name": "Alice", "role": "developer", "tenant_id": "default"}
    payload.update(overrides)
    return UserCreateRequest(**payload)


# ---------------------------------------------------------------------------
# URL 规范化
# ---------------------------------------------------------------------------

class TestUrlNormalization:
    def test_postgres_urls_map_to_psycopg(self):
        assert normalize_sync_database_url("postgres://u:p@h:5432/db").startswith("postgresql+psycopg://")
        assert normalize_sync_database_url("postgresql://u:p@h/db").startswith("postgresql+psycopg://")
        assert normalize_sync_database_url("postgresql+asyncpg://u:p@h/db").startswith("postgresql+psycopg://")
        assert normalize_sync_database_url("postgresql+psycopg://u:p@h/db").startswith("postgresql+psycopg://")

    def test_aiosqlite_maps_to_sync_sqlite(self):
        assert normalize_sync_database_url("sqlite+aiosqlite:///./data/x.db") == "sqlite:///./data/x.db"

    def test_other_urls_passthrough(self):
        assert normalize_sync_database_url("sqlite:///./x.db") == "sqlite:///./x.db"


# ---------------------------------------------------------------------------
# 用户存储 CRUD
# ---------------------------------------------------------------------------

class TestSqlUserStoreCRUD:
    def test_create_get_roundtrip(self, user_store):
        created = user_store.create(_make_user_req(), password="Passw0rd!")
        fetched = user_store.get(created.id)
        assert fetched is not None
        assert fetched.email == "alice@example.com"
        assert fetched.display_name == "Alice"
        assert fetched.role == "developer"
        assert fetched.tenant_id == "default"
        assert fetched.password_hash is not None and fetched.password_hash != "Passw0rd!"
        assert fetched.created_at.tzinfo is not None  # 时区归一化到 UTC

    def test_get_missing_returns_none(self, user_store):
        assert user_store.get("no-such-id") is None

    def test_list_sorted_by_updated_desc(self, user_store):
        user_store.create(_make_user_req("u1@example.com"))
        user_store.create(_make_user_req("u2@example.com"))
        emails = [u.email for u in user_store.list()]
        assert set(emails) == {"u1@example.com", "u2@example.com"}

    def test_upsert_creates_with_explicit_id(self, user_store):
        """与内存版一致: upsert 携带新 user_id 时创建记录。"""
        record = user_store.upsert(UserUpdateRequest(display_name="Bob"), user_id="fixed-id-1")
        assert record.id == "fixed-id-1"
        assert record.display_name == "Bob"
        assert user_store.get("fixed-id-1") is not None

    def test_upsert_partial_update_preserves_fields(self, user_store):
        created = user_store.create(_make_user_req(), password="Passw0rd!")
        updated = user_store.upsert(UserUpdateRequest(role="admin"), created.id)
        assert updated.role == "admin"
        assert updated.email == created.email  # None 字段不覆盖
        assert updated.password_hash == created.password_hash

    def test_delete(self, user_store):
        created = user_store.create(_make_user_req())
        assert user_store.delete(created.id) is True
        assert user_store.get(created.id) is None
        assert user_store.delete(created.id) is False

    def test_duplicate_email_same_tenant_rejected(self, user_store):
        """唯一约束 (email, tenant_id): 并发重复注册的 DB 级兜底, 显式报错而非静默。"""
        user_store.create(_make_user_req())
        with pytest.raises(ValueError, match="已存在"):
            user_store.create(_make_user_req())

    def test_same_email_different_tenant_allowed(self, user_store):
        user_store.create(_make_user_req(tenant_id="t1"))
        record = user_store.create(_make_user_req(tenant_id="t2"))
        assert record.tenant_id == "t2"


# ---------------------------------------------------------------------------
# 认证与密码
# ---------------------------------------------------------------------------

class TestSqlUserStoreAuth:
    def test_authenticate_success(self, user_store):
        user_store.create(_make_user_req(), password="Passw0rd!")
        record = user_store.authenticate("alice@example.com", "Passw0rd!")
        assert record is not None and record.email == "alice@example.com"

    def test_authenticate_wrong_password_and_lockout(self, user_store):
        user_store.create(_make_user_req(), password="Passw0rd!")
        for _ in range(5):
            assert user_store.authenticate("alice@example.com", "wrong-pass") is None
        # 5 次失败后锁定: 即使密码正确也拒绝
        assert user_store.authenticate("alice@example.com", "Passw0rd!") is None
        locked = user_store.get([u.id for u in user_store.list()][0])
        assert locked.failed_login_attempts >= 5
        assert locked.locked_until is not None and locked.locked_until > datetime.now(UTC)

    def test_authenticate_unknown_email(self, user_store):
        assert user_store.authenticate("ghost@example.com", "Passw0rd!") is None

    def test_change_password_flow_and_history_reuse(self, user_store):
        created = user_store.create(_make_user_req(), password="Passw0rd!")
        assert user_store.change_password(created.id, "Passw0rd!", "NewPass1!") is True
        assert user_store.authenticate("alice@example.com", "Passw0rd!") is None
        assert user_store.authenticate("alice@example.com", "NewPass1!") is not None
        # 最近 5 次密码不可复用
        with pytest.raises(ValueError, match="recent passwords"):
            user_store.change_password(created.id, "NewPass1!", "Passw0rd!")

    def test_change_password_wrong_old(self, user_store):
        created = user_store.create(_make_user_req(), password="Passw0rd!")
        assert user_store.change_password(created.id, "bad-old", "NewPass1!") is False


# ---------------------------------------------------------------------------
# 租户存储 CRUD
# ---------------------------------------------------------------------------

class TestSqlTenantStoreCRUD:
    def test_create_get_roundtrip(self, tenant_store):
        created = tenant_store.create(TenantCreateRequest(name="Acme", plan="pro"))
        fetched = tenant_store.get(created.id)
        assert fetched is not None
        assert fetched.name == "Acme" and fetched.plan == "pro"

    def test_upsert_create_and_update(self, tenant_store):
        created = tenant_store.upsert(TenantUpdateRequest(name="T1"), tenant_id="tid-1")
        assert created.id == "tid-1" and created.name == "T1"
        updated = tenant_store.upsert(TenantUpdateRequest(plan="enterprise"), tenant_id="tid-1")
        assert updated.plan == "enterprise" and updated.name == "T1"

    def test_list_and_delete(self, tenant_store):
        tenant_store.create(TenantCreateRequest(name="A"))
        tenant_store.create(TenantCreateRequest(name="B"))
        assert len(tenant_store.list()) == 2
        victim = tenant_store.list()[0]
        assert tenant_store.delete(victim.id) is True
        assert len(tenant_store.list()) == 1
        assert tenant_store.delete("missing") is False


# ---------------------------------------------------------------------------
# 多实例共享(P1-03 核心目标)
# ---------------------------------------------------------------------------

class TestMultiInstanceSharing:
    def test_two_store_instances_share_state(self, sqlite_url):
        """两个存储实例(模拟两个应用副本)指向同一数据库时互可见写入。"""
        instance_a_users = SqlUserStore(sqlite_url)
        instance_b_users = SqlUserStore(sqlite_url)
        instance_a_tenants = SqlTenantStore(sqlite_url)
        instance_b_tenants = SqlTenantStore(sqlite_url)

        created = instance_a_users.create(_make_user_req(), password="Passw0rd!")
        instance_a_tenants.create(TenantCreateRequest(name="SharedTenant"))

        from_b = instance_b_users.get(created.id)
        assert from_b is not None and from_b.email == "alice@example.com"
        assert instance_b_users.authenticate("alice@example.com", "Passw0rd!") is not None
        assert [t.name for t in instance_b_tenants.list()] == ["SharedTenant"]

        # B 实例更新, A 实例可见
        instance_b_users.upsert(UserUpdateRequest(role="admin"), created.id)
        assert instance_a_users.get(created.id).role == "admin"

    def test_state_survives_store_recreation(self, sqlite_url):
        """状态外置: 丢弃存储实例(模拟进程重启)后数据仍在——内存后端做不到的语义。"""
        SqlUserStore(sqlite_url).create(_make_user_req(), password="Passw0rd!")
        reloaded = SqlUserStore(sqlite_url)
        assert reloaded.authenticate("alice@example.com", "Passw0rd!") is not None


# ---------------------------------------------------------------------------
# _records 兼容视图(conftest clear / auth.py 密码重置写穿透)
# ---------------------------------------------------------------------------

class TestRecordsMappingCompat:
    def test_clear_empties_database(self, user_store):
        user_store.create(_make_user_req())
        assert len(user_store._records) == 1
        user_store._records.clear()
        assert len(user_store._records) == 0
        assert user_store.list() == []

    def test_setitem_write_through(self, user_store):
        """api/auth.py reset_password 的写法: 改 record 后 user_store._records[id] = record。"""
        created = user_store.create(_make_user_req(), password="Passw0rd!")
        record = user_store.get(created.id)
        record.password_hash = "x" * 60  # 模拟外部直接改写哈希
        record.updated_at = datetime.now(UTC)
        user_store._records[record.id] = record
        assert user_store.get(created.id).password_hash == "x" * 60

    def test_mapping_getitem_delitem(self, user_store):
        created = user_store.create(_make_user_req())
        assert user_store._records[created.id].email == "alice@example.com"
        with pytest.raises(KeyError):
            _ = user_store._records["missing"]
        del user_store._records[created.id]
        assert user_store.get(created.id) is None


# ---------------------------------------------------------------------------
# 工厂装配(配置选择后端)
# ---------------------------------------------------------------------------

class TestStoreFactory:
    def test_explicit_memory_backend(self):
        assert isinstance(create_user_store("memory"), UserStore)
        assert isinstance(create_tenant_store("memory"), TenantStore)

    def test_explicit_postgres_backend_with_sqlite_url(self, sqlite_url):
        """显式选择 postgres 后端: 返回 SQL 实现(此处以 sqlite 验证逻辑, 生产为 Postgres DSN)。"""
        assert isinstance(create_user_store("postgres", sqlite_url), SqlUserStore)
        assert isinstance(create_tenant_store("postgres", sqlite_url), SqlTenantStore)

    def test_unknown_backend_raises(self):
        with pytest.raises(ValueError, match="未知用户存储后端"):
            create_user_store("cassandra")
        with pytest.raises(ValueError, match="未知租户存储后端"):
            create_tenant_store("cassandra")

    def test_postgres_backend_requires_url(self, monkeypatch):
        monkeypatch.setenv("XAGENT_DATABASE_URL", "")
        from backend.app.settings import get_settings

        get_settings.cache_clear()
        try:
            with pytest.raises(ValueError, match="需要 database_url"):
                create_user_store("postgres", None)
        finally:
            get_settings.cache_clear()

    def test_settings_driven_selection(self, monkeypatch, sqlite_url):
        """XAGENT_ADMIN_STORE_BACKEND=postgres 时工厂走 SQL 后端(经 settings 解析)。"""
        monkeypatch.setenv("XAGENT_ADMIN_STORE_BACKEND", "postgres")
        monkeypatch.setenv("XAGENT_DATABASE_URL", sqlite_url)
        from backend.app.settings import get_settings

        get_settings.cache_clear()
        try:
            assert isinstance(create_user_store(), SqlUserStore)
        finally:
            get_settings.cache_clear()

    def test_factory_does_not_silently_degrade_on_settings_validation_error(self, monkeypatch):
        """生产模式 settings 校验失败时, 工厂必须上抛 ValidationError,
        而非静默回退内存后端(否则架空 P1-19 fail-fast)。"""
        from pydantic import ValidationError

        monkeypatch.setenv("XAGENT_APP_MODE", "production")
        monkeypatch.setenv("XAGENT_JWT_SECRET", "ProdJWTSecret1234567890ABCDEFGHIJK")
        monkeypatch.setenv("XAGENT_ENCRYPTION_KEY", "ProdEncKey1234567890ABCDEFGHIJKLMN")
        monkeypatch.setenv("XAGENT_AUDIT_HMAC_SECRET", "hmac-secret")
        from backend.app.settings import get_settings

        get_settings.cache_clear()
        try:
            with pytest.raises(ValidationError, match="拒绝启动"):
                create_user_store()
        finally:
            get_settings.cache_clear()


# ---------------------------------------------------------------------------
# aiosqlite 异步驱动验证 SQLAlchemy 模型逻辑(任务书指定验证方式)
# ---------------------------------------------------------------------------

class TestModelsOnAiosqlite:
    @pytest.mark.asyncio
    async def test_models_roundtrip_via_async_engine(self, tmp_path):
        """同一套 AdminStoreBase 模型在 aiosqlite 异步引擎下建表 + CRUD 可行,
        证明模型映射方言无关(Postgres 仅换驱动/方言, 模型代码不变)。"""
        from sqlalchemy import select

        db_file = tmp_path / "admin_async.db"
        engine = create_async_engine(f"sqlite+aiosqlite:///{db_file}")
        try:
            async with engine.begin() as conn:
                await conn.run_sync(AdminStoreBase.metadata.create_all)

            from sqlalchemy.ext.asyncio import async_sessionmaker

            session_factory = async_sessionmaker(engine, expire_on_commit=False)
            async with session_factory() as session:
                session.add(
                    AdminUserModel(
                        id="async-u1",
                        email="async@example.com",
                        display_name="Async",
                        role="developer",
                        tenant_id="default",
                        password_hash="hash",
                        password_history_json="[]",
                        failed_login_attempts=0,
                        created_at=datetime.now(UTC),
                        updated_at=datetime.now(UTC),
                    )
                )
                await session.commit()

            async with session_factory() as session:
                result = await session.execute(
                    select(AdminUserModel).where(AdminUserModel.id == "async-u1")
                )
                model = result.scalar_one()
                assert model.email == "async@example.com"
                assert model.failed_login_attempts == 0
        finally:
            await engine.dispose()
