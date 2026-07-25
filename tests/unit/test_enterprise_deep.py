"""Deep coverage tests for enterprise.py and admin_store.py — all branches."""
import pytest
from datetime import UTC, datetime, timedelta
from unittest.mock import MagicMock, patch

from backend.app.core.enterprise import (
    TenantPlan, RoleType, PermissionType, AuditEventType,
    EnterpriseUser, Team, EnterpriseTenant, APIKey, AuditLog,
    AccessPolicy, ComplianceReport,
    EnterpriseUserStore, TeamStore, EnterpriseTenantStore,
    APIKeyStore, AuditLogStore, EnterpriseService,
)
from backend.app.core.admin_store import (
    normalize_sync_database_url, SqlUserStore, SqlTenantStore, _as_utc,
)
from backend.app.core.admin import (
    UserCreateRequest, UserUpdateRequest, UserRecord,
    TenantCreateRequest, TenantUpdateRequest, TenantRecord,
)


# ═══════════════════════════════════════════════════════════════════════════════
# EnterpriseUserStore TESTS
# ═══════════════════════════════════════════════════════════════════════════════

class TestEnterpriseUserStore:
    def test_create_and_get(self):
        store = EnterpriseUserStore()
        user = EnterpriseUser(email="a@b.com", display_name="Alice", tenant_id="t1")
        store.create(user)
        assert store.get(user.id) is not None
        assert store.get("nope") is None

    def test_get_by_email(self):
        store = EnterpriseUserStore()
        user = EnterpriseUser(email="a@b.com", display_name="Alice", tenant_id="t1")
        store.create(user)
        assert store.get_by_email("a@b.com") is not None
        assert store.get_by_email("x@y.com") is None

    def test_list_by_tenant(self):
        store = EnterpriseUserStore()
        store.create(EnterpriseUser(email="a@b.com", display_name="A", tenant_id="t1"))
        store.create(EnterpriseUser(email="c@d.com", display_name="B", tenant_id="t2"))
        assert len(store.list_by_tenant("t1")) == 1
        assert len(store.list_by_tenant("t2")) == 1

    def test_update(self):
        store = EnterpriseUserStore()
        user = EnterpriseUser(email="a@b.com", display_name="Alice", tenant_id="t1")
        store.create(user)
        updated = store.update(user.id, {"display_name": "Bob"})
        assert updated.display_name == "Bob"
        assert store.update("nope", {"display_name": "X"}) is None

    def test_delete(self):
        store = EnterpriseUserStore()
        user = EnterpriseUser(email="a@b.com", display_name="Alice", tenant_id="t1")
        store.create(user)
        assert store.delete(user.id) is True
        assert store.delete(user.id) is False


# ═══════════════════════════════════════════════════════════════════════════════
# TeamStore TESTS
# ═══════════════════════════════════════════════════════════════════════════════

class TestTeamStore:
    def test_create_and_get(self):
        store = TeamStore()
        team = Team(tenant_id="t1", name="Dev Team", owner_id="u1")
        store.create(team)
        assert store.get(team.id) is not None
        assert store.get("nope") is None

    def test_list_by_tenant(self):
        store = TeamStore()
        store.create(Team(tenant_id="t1", name="Team A", owner_id="u1"))
        store.create(Team(tenant_id="t2", name="Team B", owner_id="u2"))
        assert len(store.list_by_tenant("t1")) == 1

    def test_add_member(self):
        store = TeamStore()
        team = Team(tenant_id="t1", name="Dev", owner_id="u1")
        store.create(team)
        assert store.add_member(team.id, "u2") is True
        assert store.add_member(team.id, "u2") is False  # already member
        assert store.add_member("nope", "u2") is False

    def test_remove_member(self):
        store = TeamStore()
        team = Team(tenant_id="t1", name="Dev", owner_id="u1", member_ids=["u2"])
        store.create(team)
        assert store.remove_member(team.id, "u2") is True
        assert store.remove_member(team.id, "u2") is False  # already removed
        assert store.remove_member("nope", "u2") is False


# ═══════════════════════════════════════════════════════════════════════════════
# EnterpriseTenantStore TESTS
# ═══════════════════════════════════════════════════════════════════════════════

class TestEnterpriseTenantStore:
    def test_create_and_get(self):
        store = EnterpriseTenantStore()
        tenant = EnterpriseTenant(name="Acme Corp")
        store.create(tenant)
        assert store.get(tenant.id) is not None
        assert store.get("nope") is None

    def test_list_all(self):
        store = EnterpriseTenantStore()
        store.create(EnterpriseTenant(name="A"))
        store.create(EnterpriseTenant(name="B"))
        assert len(store.list_all()) == 2

    def test_update(self):
        store = EnterpriseTenantStore()
        tenant = EnterpriseTenant(name="Acme")
        store.create(tenant)
        updated = store.update(tenant.id, {"name": "Acme Updated", "plan": "enterprise"})
        assert updated.name == "Acme Updated"
        assert store.update("nope", {"name": "X"}) is None


# ═══════════════════════════════════════════════════════════════════════════════
# APIKeyStore TESTS
# ═══════════════════════════════════════════════════════════════════════════════

class TestAPIKeyStore:
    def test_create_and_get(self):
        store = APIKeyStore()
        key = APIKey(tenant_id="t1", user_id="u1", name="My Key", key_hash="hash123")
        store.create(key)
        assert store.get(key.id) is not None
        assert store.get("nope") is None

    def test_list_by_user(self):
        store = APIKeyStore()
        store.create(APIKey(tenant_id="t1", user_id="u1", name="K1", key_hash="h1"))
        store.create(APIKey(tenant_id="t1", user_id="u2", name="K2", key_hash="h2"))
        assert len(store.list_by_user("u1")) == 1

    def test_revoke(self):
        store = APIKeyStore()
        key = APIKey(tenant_id="t1", user_id="u1", name="K1", key_hash="h1")
        store.create(key)
        assert store.revoke(key.id) is True
        assert store.get(key.id).is_active is False
        assert store.revoke("nope") is False


# ═══════════════════════════════════════════════════════════════════════════════
# AuditLogStore TESTS
# ═══════════════════════════════════════════════════════════════════════════════

class TestAuditLogStore:
    def test_log_and_get(self):
        store = AuditLogStore()
        event = AuditLog(
            tenant_id="t1", event_type=AuditEventType.USER_LOGIN,
            resource_type="user", resource_id="u1", action="login",
        )
        store.log(event)
        assert store.get(event.id) is not None
        assert store.get("nope") is None

    def test_list_by_tenant_no_filters(self):
        store = AuditLogStore()
        store.log(AuditLog(tenant_id="t1", event_type=AuditEventType.USER_LOGIN,
                           resource_type="user", resource_id="u1", action="login"))
        store.log(AuditLog(tenant_id="t2", event_type=AuditEventType.USER_LOGOUT,
                           resource_type="user", resource_id="u2", action="logout"))
        assert len(store.list_by_tenant("t1")) == 1

    def test_list_by_tenant_with_date_filter(self):
        store = AuditLogStore()
        store.log(AuditLog(tenant_id="t1", event_type=AuditEventType.USER_LOGIN,
                           resource_type="user", resource_id="u1", action="login"))
        past = datetime(2020, 1, 1, tzinfo=UTC)
        future = datetime(2099, 1, 1, tzinfo=UTC)
        assert len(store.list_by_tenant("t1", start_date=past)) == 1
        assert len(store.list_by_tenant("t1", end_date=past)) == 0
        assert len(store.list_by_tenant("t1", start_date=past, end_date=future)) == 1

    def test_list_by_tenant_with_event_type_filter(self):
        store = AuditLogStore()
        store.log(AuditLog(tenant_id="t1", event_type=AuditEventType.USER_LOGIN,
                           resource_type="user", resource_id="u1", action="login"))
        store.log(AuditLog(tenant_id="t1", event_type=AuditEventType.USER_LOGOUT,
                           resource_type="user", resource_id="u1", action="logout"))
        assert len(store.list_by_tenant("t1", event_type=AuditEventType.USER_LOGIN)) == 1


# ═══════════════════════════════════════════════════════════════════════════════
# EnterpriseService TESTS
# ═══════════════════════════════════════════════════════════════════════════════

class TestEnterpriseService:
    def test_check_permission_super_admin(self):
        svc = EnterpriseService()
        user = EnterpriseUser(email="admin@x.com", display_name="Admin",
                              tenant_id="t1", role=RoleType.SUPER_ADMIN)
        assert svc.check_permission(user, PermissionType.TENANT_DELETE) is True

    def test_check_permission_explicit(self):
        svc = EnterpriseService()
        user = EnterpriseUser(email="dev@x.com", display_name="Dev",
                              tenant_id="t1", role=RoleType.DEVELOPER,
                              permissions=[PermissionType.AGENT_READ])
        assert svc.check_permission(user, PermissionType.AGENT_READ) is True
        assert svc.check_permission(user, PermissionType.TENANT_DELETE) is False

    def test_check_resource_access_super_admin(self):
        svc = EnterpriseService()
        user = EnterpriseUser(email="admin@x.com", display_name="Admin",
                              tenant_id="t1", role=RoleType.SUPER_ADMIN)
        assert svc.check_resource_access(user, "agent", "a1", "execute") is True

    def test_check_resource_access_tenant_admin(self):
        svc = EnterpriseService()
        user = EnterpriseUser(email="ta@x.com", display_name="TA",
                              tenant_id="t1", role=RoleType.TENANT_ADMIN)
        assert svc.check_resource_access(user, "agent", "a1", "execute") is True

    def test_check_resource_access_developer(self):
        svc = EnterpriseService()
        user = EnterpriseUser(email="dev@x.com", display_name="Dev",
                              tenant_id="t1", role=RoleType.DEVELOPER)
        assert svc.check_resource_access(user, "agent", "a1", "execute") is False

    def test_log_event(self):
        svc = EnterpriseService()
        event = svc.log_event(
            tenant_id="t1", event_type=AuditEventType.AGENT_EXECUTED,
            resource_type="agent", resource_id="a1", action="execute",
            actor_id="u1", actor_email="dev@x.com",
            changes={"status": "completed"}, ip_address="1.2.3.4",
        )
        assert event.id is not None
        assert event.tenant_id == "t1"

    def test_log_event_with_error(self):
        svc = EnterpriseService()
        event = svc.log_event(
            tenant_id="t1", event_type=AuditEventType.SECURITY_EVENT,
            resource_type="user", resource_id="u1", action="login",
            status="failure", error_message="Invalid password",
        )
        assert event.status == "failure"
        assert event.error_message == "Invalid password"

    def test_generate_compliance_report(self):
        svc = EnterpriseService()
        svc.log_event(tenant_id="t1", event_type=AuditEventType.USER_LOGIN,
                      resource_type="user", resource_id="u1", action="login")
        svc.log_event(tenant_id="t1", event_type=AuditEventType.SECURITY_EVENT,
                      resource_type="user", resource_id="u1", action="failed_login")
        report = svc.generate_compliance_report(
            tenant_id="t1", report_type="soc2",
            period_start=datetime(2020, 1, 1, tzinfo=UTC),
            period_end=datetime(2099, 1, 1, tzinfo=UTC),
        )
        assert report.total_events == 2
        assert report.security_events == 1
        assert report.report_type == "soc2"


# ═══════════════════════════════════════════════════════════════════════════════
# admin_store: normalize_sync_database_url TESTS
# ═══════════════════════════════════════════════════════════════════════════════

class TestNormalizeSyncDatabaseUrl:
    def test_postgres_prefix(self):
        assert normalize_sync_database_url("postgres://user:pass@host/db") == \
            "postgresql+psycopg://user:pass@host/db"

    def test_postgresql_asyncpg_prefix(self):
        assert normalize_sync_database_url("postgresql+asyncpg://user:pass@host/db") == \
            "postgresql+psycopg://user:pass@host/db"

    def test_postgresql_prefix(self):
        assert normalize_sync_database_url("postgresql://user:pass@host/db") == \
            "postgresql+psycopg://user:pass@host/db"

    def test_sqlite_aiosqlite_prefix(self):
        assert normalize_sync_database_url("sqlite+aiosqlite:///path.db") == \
            "sqlite:///path.db"

    def test_already_sync(self):
        url = "postgresql+psycopg://user:pass@host/db"
        assert normalize_sync_database_url(url) == url

    def test_whitespace_stripped(self):
        assert normalize_sync_database_url("  postgres://x  ") == \
            "postgresql+psycopg://x"


# ═══════════════════════════════════════════════════════════════════════════════
# admin_store: _as_utc TESTS
# ═══════════════════════════════════════════════════════════════════════════════

class TestAsUtc:
    def test_none(self):
        assert _as_utc(None) is None

    def test_naive_datetime(self):
        dt = datetime(2024, 6, 15, 10, 0)
        result = _as_utc(dt)
        assert result.tzinfo is not None

    def test_aware_datetime(self):
        dt = datetime(2024, 6, 15, 10, 0, tzinfo=UTC)
        result = _as_utc(dt)
        assert result == dt


# ═══════════════════════════════════════════════════════════════════════════════
# SqlUserStore TESTS (sqlite in-memory)
# ═══════════════════════════════════════════════════════════════════════════════

class TestSqlUserStore:
    def _make_store(self):
        return SqlUserStore("sqlite:///:memory:")

    def test_create_and_get(self):
        store = self._make_store()
        req = UserCreateRequest(email="a@b.com", display_name="Alice", role="developer", tenant_id="t1")
        record = store.create(req)
        assert record.id is not None
        assert store.get(record.id) is not None
        assert store.get("nope") is None

    def test_create_with_password(self):
        store = self._make_store()
        req = UserCreateRequest(email="a@b.com", display_name="Alice", role="developer", tenant_id="t1")
        record = store.create(req, password="secret123")
        assert record.password_hash is not None

    def test_authenticate_success(self):
        store = self._make_store()
        req = UserCreateRequest(email="a@b.com", display_name="Alice", role="developer", tenant_id="t1")
        store.create(req, password="secret123")
        result = store.authenticate("a@b.com", "secret123")
        assert result is not None
        assert result.email == "a@b.com"

    def test_authenticate_wrong_password(self):
        store = self._make_store()
        req = UserCreateRequest(email="a@b.com", display_name="Alice", role="developer", tenant_id="t1")
        store.create(req, password="secret123")
        result = store.authenticate("a@b.com", "wrong")
        assert result is None

    def test_authenticate_nonexistent_user(self):
        store = self._make_store()
        assert store.authenticate("nobody@x.com", "pass") is None

    def test_authenticate_no_password_hash(self):
        store = self._make_store()
        req = UserCreateRequest(email="a@b.com", display_name="Alice", role="developer", tenant_id="t1")
        store.create(req)  # no password
        assert store.authenticate("a@b.com", "any") is None

    def test_authenticate_lockout(self):
        store = self._make_store()
        req = UserCreateRequest(email="a@b.com", display_name="Alice", role="developer", tenant_id="t1")
        store.create(req, password="secret123")
        # 5 failed attempts -> lockout
        for _ in range(5):
            store.authenticate("a@b.com", "wrong")
        # Now locked
        assert store.authenticate("a@b.com", "secret123") is None

    def test_change_password(self):
        store = self._make_store()
        req = UserCreateRequest(email="a@b.com", display_name="Alice", role="developer", tenant_id="t1")
        record = store.create(req, password="old_pass")
        assert store.change_password(record.id, "old_pass", "new_pass") is True
        assert store.authenticate("a@b.com", "new_pass") is not None

    def test_change_password_wrong_old(self):
        store = self._make_store()
        req = UserCreateRequest(email="a@b.com", display_name="Alice", role="developer", tenant_id="t1")
        record = store.create(req, password="old_pass")
        assert store.change_password(record.id, "wrong", "new_pass") is False

    def test_change_password_no_hash(self):
        store = self._make_store()
        req = UserCreateRequest(email="a@b.com", display_name="Alice", role="developer", tenant_id="t1")
        record = store.create(req)
        assert store.change_password(record.id, "old", "new") is False

    def test_change_password_reuse_rejected(self):
        store = self._make_store()
        req = UserCreateRequest(email="a@b.com", display_name="Alice", role="developer", tenant_id="t1")
        record = store.create(req, password="pass1")
        store.change_password(record.id, "pass1", "pass2")
        with pytest.raises(ValueError, match="Cannot reuse"):
            store.change_password(record.id, "pass2", "pass1")

    def test_list(self):
        store = self._make_store()
        store.create(UserCreateRequest(email="a@b.com", display_name="A", role="dev", tenant_id="t1"))
        store.create(UserCreateRequest(email="c@d.com", display_name="B", role="dev", tenant_id="t1"))
        assert len(store.list()) == 2

    def test_delete(self):
        store = self._make_store()
        record = store.create(UserCreateRequest(email="a@b.com", display_name="A", role="dev", tenant_id="t1"))
        assert store.delete(record.id) is True
        assert store.delete(record.id) is False

    def test_upsert_create(self):
        store = self._make_store()
        req = UserCreateRequest(email="new@x.com", display_name="New", role="dev", tenant_id="t1")
        record = store.upsert(req)
        assert record.email == "new@x.com"

    def test_upsert_update(self):
        store = self._make_store()
        record = store.create(UserCreateRequest(email="a@b.com", display_name="A", role="dev", tenant_id="t1"))
        update = UserUpdateRequest(display_name="Updated")
        updated = store.upsert(update, user_id=record.id)
        assert updated.display_name == "Updated"

    def test_upsert_nonexistent_id(self):
        store = self._make_store()
        update = UserUpdateRequest(email="x@y.com")
        record = store.upsert(update, user_id="nonexistent-id")
        assert record.id == "nonexistent-id"

    def test_records_mapping(self):
        store = self._make_store()
        record = store.create(UserCreateRequest(email="a@b.com", display_name="A", role="dev", tenant_id="t1"))
        records = store._records
        assert len(records) == 1
        assert records[record.id].email == "a@b.com"
        with pytest.raises(KeyError):
            _ = records["nope"]
        del records[record.id]
        assert len(records) == 0

    def test_records_mapping_clear(self):
        store = self._make_store()
        store.create(UserCreateRequest(email="a@b.com", display_name="A", role="dev", tenant_id="t1"))
        store._records.clear()
        assert store.count() == 0

    def test_records_mapping_setitem(self):
        store = self._make_store()
        record = store.create(UserCreateRequest(email="a@b.com", display_name="A", role="dev", tenant_id="t1"))
        record.display_name = "Changed"
        store._records[record.id] = record
        assert store.get(record.id).display_name == "Changed"

    def test_records_mapping_setitem_type_error(self):
        store = self._make_store()
        with pytest.raises(TypeError):
            store._records["x"] = "not a record"

    def test_records_mapping_delitem_keyerror(self):
        store = self._make_store()
        with pytest.raises(KeyError):
            del store._records["nope"]

    def test_count(self):
        store = self._make_store()
        assert store.count() == 0
        store.create(UserCreateRequest(email="a@b.com", display_name="A", role="dev", tenant_id="t1"))
        assert store.count() == 1


# ═══════════════════════════════════════════════════════════════════════════════
# SqlTenantStore TESTS (sqlite in-memory)
# ═══════════════════════════════════════════════════════════════════════════════

class TestSqlTenantStore:
    def _make_store(self):
        return SqlTenantStore("sqlite:///:memory:")

    def test_create_and_get(self):
        store = self._make_store()
        req = TenantCreateRequest(name="Acme", plan="enterprise")
        record = store.create(req)
        assert record.id is not None
        assert store.get(record.id) is not None
        assert store.get("nope") is None

    def test_upsert_create(self):
        store = self._make_store()
        req = TenantUpdateRequest(name="New Tenant", plan="starter")
        record = store.upsert(req, tenant_id="new-id")
        assert record.name == "New Tenant"

    def test_upsert_update(self):
        store = self._make_store()
        created = store.create(TenantCreateRequest(name="Acme", plan="free"))
        update = TenantUpdateRequest(name="Acme Corp", plan="enterprise")
        updated = store.upsert(update, tenant_id=created.id)
        assert updated.name == "Acme Corp"
        assert updated.plan == "enterprise"

    def test_list(self):
        store = self._make_store()
        store.create(TenantCreateRequest(name="A", plan="free"))
        store.create(TenantCreateRequest(name="B", plan="starter"))
        assert len(store.list()) == 2

    def test_delete(self):
        store = self._make_store()
        record = store.create(TenantCreateRequest(name="A", plan="free"))
        assert store.delete(record.id) is True
        assert store.delete(record.id) is False

    def test_count(self):
        store = self._make_store()
        assert store.count() == 0
        store.create(TenantCreateRequest(name="A", plan="free"))
        assert store.count() == 1

    def test_records_mapping(self):
        store = self._make_store()
        record = store.create(TenantCreateRequest(name="A", plan="free"))
        records = store._records
        assert len(records) == 1
        assert records[record.id].name == "A"
        with pytest.raises(KeyError):
            _ = records["nope"]
        del records[record.id]
        assert len(records) == 0

    def test_records_mapping_clear(self):
        store = self._make_store()
        store.create(TenantCreateRequest(name="A", plan="free"))
        store._records.clear()
        assert store.count() == 0

    def test_records_mapping_setitem(self):
        store = self._make_store()
        record = store.create(TenantCreateRequest(name="A", plan="free"))
        record.name = "Changed"
        store._records[record.id] = record
        assert store.get(record.id).name == "Changed"

    def test_records_mapping_setitem_type_error(self):
        store = self._make_store()
        with pytest.raises(TypeError):
            store._records["x"] = "not a record"

    def test_records_mapping_delitem_keyerror(self):
        store = self._make_store()
        with pytest.raises(KeyError):
            del store._records["nope"]
