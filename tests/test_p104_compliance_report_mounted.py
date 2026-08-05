"""P1-04：合规报告端点挂载到主审计路由的回归测试。

背景：/reports/compliance 原仅在未挂载的 audit_enhanced.py（同名前缀路由
与已挂载 audit.py 冲突，整挂会阴影 + 超 G3 预算）。本次按预算安全方式
将该端点移植进已挂载的 audit.py（/api/v1/audit-logs），增强审计存储
provider 同步迁入 dependencies（两文件共享单例）。
"""

from __future__ import annotations

from starlette.testclient import TestClient

from backend.app.main import app

_HEADERS = {"X-API-Key": "bootstrap"}


def test_compliance_report_mounted_on_main_audit_router() -> None:
    with TestClient(app) as client:
        resp = client.get("/api/v1/audit-logs/reports/compliance", headers=_HEADERS)

    assert resp.status_code == 200
    data = resp.json()["data"]
    assert data["report_type"] == "SOC2"
    assert "period_start" in data and "period_end" in data
    assert "total_operations" in data


def test_compliance_report_params_and_auth() -> None:
    with TestClient(app) as client:
        custom = client.get(
            "/api/v1/audit-logs/reports/compliance",
            params={"report_type": "ISO27001", "days": 7},
            headers=_HEADERS,
        )
        unauthenticated = client.get("/api/v1/audit-logs/reports/compliance")

    assert custom.status_code == 200
    assert custom.json()["data"]["report_type"] == "ISO27001"
    assert unauthenticated.status_code in (401, 403)


def test_enhanced_store_is_shared_singleton() -> None:
    """audit.py 与 audit_enhanced.py 必须使用同一增强存储实例。"""
    from backend.app.api import audit_enhanced
    from backend.app.dependencies import get_enhanced_audit_store

    assert audit_enhanced.get_enhanced_audit_store is get_enhanced_audit_store
    assert get_enhanced_audit_store() is get_enhanced_audit_store()
