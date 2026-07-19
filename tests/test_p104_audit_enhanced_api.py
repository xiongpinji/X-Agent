"""P1-04: audit_enhanced 端点 TestClient 直测(自建 app, 不依赖 main.py)。

覆盖:
- 8+ 个带 tenant_id 端点的强制租户收敛(同 api/audit.py
  _enforce_audit_tenant_scope 语义): 非 admin 传他人租户 → 403;
  未传 → 收敛本租户; admin 可跨租户。
- /logs/{log_id}: 跨租户 → 403; 不存在 → 404(修复原 200+error 假成功)。
- 合规报告端点(SOC2)可用且租户收敛。
- /export/pdf 输出真实 PDF(reportlab)。
- 未认证 → 401; 缺 scope → 403。
"""

from __future__ import annotations

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from backend.app.api.audit_enhanced import (
    get_enhanced_audit_store,
    router,
)
from backend.app.api.errors import XAgentAPIError, xagent_api_error_handler
from backend.app.core.audit_enhanced import AuditStore as EnhancedAuditStore
from backend.app.core.security import Principal
from backend.app.dependencies import get_current_principal


def _build_store() -> EnhancedAuditStore:
    store = EnhancedAuditStore(hmac_secret="test-secret")
    # tenant t1: 3 条(含 1 次失败登录, 供合规报告统计)
    store.record(action="login", resource_type="session", tenant_id="t1", actor_id="u1", outcome="success")
    store.record(action="login", resource_type="session", tenant_id="t1", actor_id="u1", outcome="failure")
    store.record(action="read", resource_type="doc", tenant_id="t1", actor_id="u1", outcome="success")
    # tenant t2: 2 条
    store.record(action="login", resource_type="session", tenant_id="t2", actor_id="u2", outcome="success")
    store.record(action="delete", resource_type="doc", tenant_id="t2", actor_id="u2", outcome="success")
    return store


_store = _build_store()

_viewer = Principal(
    tenant_id="t1", user_id="u1", role="viewer",
    scopes=["audit:read"], authenticated=True,
)
_admin = Principal(
    tenant_id="default", user_id="root", role="admin",
    scopes=["audit:read"], authenticated=True,
)
_anonymous = Principal(authenticated=False)

_current: dict[str, Principal] = {"principal": _viewer}


def _principal_override() -> Principal:
    return _current["principal"]


def _store_override() -> EnhancedAuditStore:
    return _store


app = FastAPI()
app.add_exception_handler(XAgentAPIError, xagent_api_error_handler)
app.include_router(router)
app.dependency_overrides[get_enhanced_audit_store] = _store_override
app.dependency_overrides[get_current_principal] = _principal_override

client = TestClient(app)
BASE = "/api/v1/audit"


@pytest.fixture(autouse=True)
def _reset_principal():
    _current["principal"] = _viewer
    yield
    _current["principal"] = _viewer


def _use(principal: Principal) -> None:
    _current["principal"] = principal


# ---------------------------------------------------------------------------
# /logs
# ---------------------------------------------------------------------------


def test_logs_default_converges_to_own_tenant() -> None:
    resp = client.get(f"{BASE}/logs")
    assert resp.status_code == 200
    data = resp.json()["data"]
    assert len(data) == 3
    assert {r["tenant_id"] for r in data} == {"t1"}


def test_logs_foreign_tenant_forbidden() -> None:
    resp = client.get(f"{BASE}/logs", params={"tenant_id": "t2"})
    assert resp.status_code == 403
    assert resp.json()["code"] == "authorization_failed"


def test_logs_own_tenant_explicit_ok() -> None:
    resp = client.get(f"{BASE}/logs", params={"tenant_id": "t1"})
    assert resp.status_code == 200
    assert len(resp.json()["data"]) == 3


def test_logs_admin_cross_tenant() -> None:
    _use(_admin)
    resp = client.get(f"{BASE}/logs")
    assert resp.status_code == 200
    assert len(resp.json()["data"]) == 5  # admin 不传 tenant → 跨租户全量

    resp = client.get(f"{BASE}/logs", params={"tenant_id": "t2"})
    assert resp.status_code == 200
    assert {r["tenant_id"] for r in resp.json()["data"]} == {"t2"}


# ---------------------------------------------------------------------------
# /logs/{log_id}
# ---------------------------------------------------------------------------


def test_get_log_own_tenant_ok() -> None:
    record = _store.list(tenant_id="t1", limit=1)[0]
    resp = client.get(f"{BASE}/logs/{record.id}")
    assert resp.status_code == 200
    assert resp.json()["data"]["id"] == record.id


def test_get_log_foreign_tenant_forbidden() -> None:
    record = _store.list(tenant_id="t2", limit=1)[0]
    resp = client.get(f"{BASE}/logs/{record.id}")
    assert resp.status_code == 403


def test_get_log_admin_cross_tenant_ok() -> None:
    _use(_admin)
    record = _store.list(tenant_id="t2", limit=1)[0]
    resp = client.get(f"{BASE}/logs/{record.id}")
    assert resp.status_code == 200


def test_get_log_missing_returns_404() -> None:
    resp = client.get(f"{BASE}/logs/does-not-exist")
    assert resp.status_code == 404
    assert resp.json()["code"] == "resource_not_found"


# ---------------------------------------------------------------------------
# /search
# ---------------------------------------------------------------------------


def test_search_default_converges_to_own_tenant() -> None:
    resp = client.post(f"{BASE}/search", json={"limit": 50})
    assert resp.status_code == 200
    body = resp.json()
    assert body["pagination"]["total"] == 3
    assert {r["tenant_id"] for r in body["data"]} == {"t1"}


def test_search_foreign_tenant_forbidden() -> None:
    resp = client.post(f"{BASE}/search", json={"tenant_id": "t2"})
    assert resp.status_code == 403


def test_search_admin_cross_tenant() -> None:
    _use(_admin)
    resp = client.post(f"{BASE}/search", json={"tenant_id": "t2"})
    assert resp.status_code == 200
    assert resp.json()["pagination"]["total"] == 2


def test_search_has_snapshot_filter() -> None:
    """覆盖 core.audit_enhanced.search 的 has_snapshot 分支(曾 NameError)。"""
    resp = client.post(f"{BASE}/search", json={"has_snapshot": True})
    assert resp.status_code == 200
    assert resp.json()["pagination"]["total"] == 0

    resp = client.post(f"{BASE}/search", json={"has_snapshot": False})
    assert resp.status_code == 200
    assert resp.json()["pagination"]["total"] == 3


# ---------------------------------------------------------------------------
# /analytics /reports/compliance /summary
# ---------------------------------------------------------------------------


def test_analytics_tenant_scoped() -> None:
    resp = client.get(f"{BASE}/analytics")
    assert resp.status_code == 200
    assert resp.json()["data"]["total_records"] == 3

    resp = client.get(f"{BASE}/analytics", params={"tenant_id": "t2"})
    assert resp.status_code == 403


def test_compliance_report_soc2_usable_and_tenant_scoped() -> None:
    resp = client.get(f"{BASE}/reports/compliance", params={"report_type": "SOC2"})
    assert resp.status_code == 200
    report = resp.json()["data"]
    assert report["report_type"] == "SOC2"
    assert report["total_operations"] == 3      # 仅 t1
    assert report["login_attempts"] == 2        # t1 的两次登录
    assert report["failed_logins"] == 1
    assert report["signature"]

    # admin 跨租户
    _use(_admin)
    resp = client.get(f"{BASE}/reports/compliance", params={"report_type": "SOC2"})
    assert resp.json()["data"]["total_operations"] == 5

    # 非 admin 指定他人租户 → 403
    _use(_viewer)
    resp = client.get(f"{BASE}/reports/compliance", params={"tenant_id": "t2"})
    assert resp.status_code == 403


def test_summary_tenant_scoped() -> None:
    resp = client.get(f"{BASE}/summary")
    assert resp.status_code == 200
    body = resp.json()
    primary = body["linked_summaries"]["primary"]["data"]
    assert primary["count"] == 3
    assert primary["by_action"]["login"] == 2

    resp = client.get(f"{BASE}/summary", params={"tenant_id": "t2"})
    assert resp.status_code == 403


# ---------------------------------------------------------------------------
# /export/*
# ---------------------------------------------------------------------------


def test_export_csv_tenant_scoped() -> None:
    resp = client.get(f"{BASE}/export/csv")
    assert resp.status_code == 200
    lines = [line for line in resp.text.splitlines() if line]
    assert len(lines) == 1 + 3  # header + 3 t1 记录
    assert "t2" not in resp.text

    resp = client.get(f"{BASE}/export/csv", params={"tenant_id": "t2"})
    assert resp.status_code == 403


def test_export_json_tenant_scoped() -> None:
    resp = client.get(f"{BASE}/export/json")
    assert resp.status_code == 200
    body = resp.json()
    assert body["count"] == 3
    assert {r["tenant_id"] for r in body["data"]} == {"t1"}


def test_export_xml_tenant_scoped() -> None:
    resp = client.get(f"{BASE}/export/xml")
    assert resp.status_code == 200
    assert resp.headers["content-type"].startswith("application/xml")
    assert 'tenant_id="t1"' in resp.text
    assert 'tenant_id="t2"' not in resp.text


def test_export_pdf_real_pdf_and_tenant_scoped() -> None:
    pytest.importorskip("reportlab")
    resp = client.post(f"{BASE}/export/pdf", params={"report_type": "SOC2"})
    assert resp.status_code == 200
    assert resp.headers["content-type"] == "application/pdf"
    assert resp.content.startswith(b"%PDF"), "应输出真实 PDF 而非占位文本"
    assert len(resp.content) > 500

    resp = client.post(f"{BASE}/export/pdf", params={"tenant_id": "t2"})
    assert resp.status_code == 403


# ---------------------------------------------------------------------------
# /verify 与认证/鉴权
# ---------------------------------------------------------------------------


def test_verify_chain_valid() -> None:
    resp = client.get(f"{BASE}/verify")
    assert resp.status_code == 200
    body = resp.json()
    assert body["valid"] is True
    assert body["checked"] == 5


def test_unauthenticated_rejected() -> None:
    _use(_anonymous)
    resp = client.get(f"{BASE}/logs")
    assert resp.status_code == 401


def test_missing_scope_forbidden() -> None:
    _use(Principal(tenant_id="t1", user_id="u9", role="user", scopes=[], authenticated=True))
    resp = client.get(f"{BASE}/logs")
    assert resp.status_code == 403
