"""
反馈系统新增端点测试: PUT/DELETE/resolve/trends/sentiment-analysis/
category-distribution/search/export, 覆盖 tenant 收敛与 scope 校验。
"""
from __future__ import annotations

import pytest
from httpx import ASGITransport, AsyncClient
from uuid import uuid4

from backend.app.main import app
from backend.app.core.security import Principal
from backend.app.dependencies import get_current_principal

FEEDBACK_SCOPES = ["feedback:read", "feedback:write"]


@pytest.fixture
async def client():
    """带 x-api-key: bootstrap 头的测试客户端(CSRF 豁免, 见 test_feedback_integration)。"""
    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://test",
        headers={"x-api-key": "bootstrap"},
    ) as client:
        yield client
    app.dependency_overrides.pop(get_current_principal, None)


@pytest.fixture
def user_principal():
    return Principal(
        user_id="fb-user-1",
        tenant_id="fb-tenant-1",
        role="user",
        scopes=list(FEEDBACK_SCOPES),
        authenticated=True,
    )


@pytest.fixture
def admin_principal():
    return Principal(
        user_id="fb-admin-1",
        tenant_id="fb-tenant-1",
        role="admin",
        scopes=list(FEEDBACK_SCOPES),
        authenticated=True,
    )


def _use(principal: Principal) -> None:
    app.dependency_overrides[get_current_principal] = lambda: principal


async def _create(client: AsyncClient, **overrides) -> str:
    payload = {
        "feedback_type": "bug",
        "title": "App crashes on startup",
        "description": "The application crashes immediately after launch",
        "severity": "high",
    }
    payload.update(overrides)
    resp = await client.post("/api/v1/feedback/", json=payload)
    assert resp.status_code == 201, resp.text
    return resp.json()["id"]


class TestFeedbackPut:
    @pytest.mark.asyncio
    async def test_put_update_success(self, client, user_principal):
        _use(user_principal)
        fid = await _create(client)

        resp = await client.put(
            f"/api/v1/feedback/{fid}",
            json={"title": "Updated title", "severity": "critical", "status": "in_progress"},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["title"] == "Updated title"
        assert data["severity"] == "critical"
        assert data["status"] == "in_progress"

    @pytest.mark.asyncio
    async def test_put_invalid_enum(self, client, user_principal):
        _use(user_principal)
        fid = await _create(client)

        resp = await client.put(f"/api/v1/feedback/{fid}", json={"severity": "bogus"})
        assert resp.status_code == 400

    @pytest.mark.asyncio
    async def test_put_forbidden_for_other_user(self, client, user_principal):
        _use(user_principal)
        fid = await _create(client)

        other = Principal(
            user_id="fb-user-2",
            tenant_id="fb-tenant-1",
            role="user",
            scopes=list(FEEDBACK_SCOPES),
            authenticated=True,
        )
        _use(other)
        resp = await client.put(f"/api/v1/feedback/{fid}", json={"title": "hijack"})
        assert resp.status_code == 403

    @pytest.mark.asyncio
    async def test_put_cross_tenant_returns_404(self, client, user_principal):
        _use(user_principal)
        fid = await _create(client)

        cross = Principal(
            user_id="fb-user-9",
            tenant_id="fb-tenant-2",
            role="admin",
            scopes=list(FEEDBACK_SCOPES),
            authenticated=True,
        )
        _use(cross)
        resp = await client.put(f"/api/v1/feedback/{fid}", json={"title": "x"})
        assert resp.status_code == 404

    @pytest.mark.asyncio
    async def test_put_requires_write_scope(self, client, user_principal):
        _use(user_principal)
        fid = await _create(client)

        no_scope = Principal(
            user_id="fb-user-1",
            tenant_id="fb-tenant-1",
            role="user",
            scopes=[],
            authenticated=True,
        )
        _use(no_scope)
        resp = await client.put(f"/api/v1/feedback/{fid}", json={"title": "x"})
        assert resp.status_code == 403


class TestFeedbackDelete:
    @pytest.mark.asyncio
    async def test_delete_success(self, client, user_principal):
        _use(user_principal)
        fid = await _create(client)

        resp = await client.delete(f"/api/v1/feedback/{fid}")
        assert resp.status_code == 204

        get_resp = await client.get(f"/api/v1/feedback/{fid}")
        assert get_resp.status_code == 404

    @pytest.mark.asyncio
    async def test_delete_not_found(self, client, user_principal):
        _use(user_principal)
        resp = await client.delete(f"/api/v1/feedback/{uuid4()}")
        assert resp.status_code == 404

    @pytest.mark.asyncio
    async def test_delete_forbidden_for_other_user(self, client, user_principal):
        _use(user_principal)
        fid = await _create(client)

        other = Principal(
            user_id="fb-user-2",
            tenant_id="fb-tenant-1",
            role="user",
            scopes=list(FEEDBACK_SCOPES),
            authenticated=True,
        )
        _use(other)
        resp = await client.delete(f"/api/v1/feedback/{fid}")
        assert resp.status_code == 403


class TestFeedbackResolve:
    @pytest.mark.asyncio
    async def test_resolve_success(self, client, user_principal):
        _use(user_principal)
        fid = await _create(client)

        resp = await client.post(f"/api/v1/feedback/{fid}/resolve")
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "resolved"
        assert data["resolved_at"] is not None

    @pytest.mark.asyncio
    async def test_resolve_cross_tenant_404(self, client, user_principal):
        _use(user_principal)
        fid = await _create(client)

        cross = Principal(
            user_id="fb-admin-9",
            tenant_id="fb-tenant-2",
            role="admin",
            scopes=list(FEEDBACK_SCOPES),
            authenticated=True,
        )
        _use(cross)
        resp = await client.post(f"/api/v1/feedback/{fid}/resolve")
        assert resp.status_code == 404


class TestFeedbackTrends:
    @pytest.mark.asyncio
    async def test_trends_returns_daily_points(self, client, user_principal):
        _use(user_principal)
        await _create(client)

        resp = await client.get("/api/v1/feedback/trends?days=7")
        assert resp.status_code == 200
        data = resp.json()
        assert data["period_days"] == 7
        assert isinstance(data["data_points"], list)
        total = sum(p["count"] for p in data["data_points"])
        assert total >= 1

    @pytest.mark.asyncio
    async def test_trends_resolved_counted(self, client, user_principal):
        _use(user_principal)
        fid = await _create(client)
        await client.post(f"/api/v1/feedback/{fid}/resolve")

        resp = await client.get("/api/v1/feedback/trends")
        assert resp.status_code == 200
        resolved_total = sum(p["resolved"] for p in resp.json()["data_points"])
        assert resolved_total >= 1

    @pytest.mark.asyncio
    async def test_trends_tenant_isolated(self, client, user_principal):
        _use(user_principal)
        await _create(client)

        other_tenant = Principal(
            user_id="fb-user-9",
            tenant_id="fb-tenant-2",
            role="user",
            scopes=list(FEEDBACK_SCOPES),
            authenticated=True,
        )
        _use(other_tenant)
        resp = await client.get("/api/v1/feedback/trends")
        assert resp.status_code == 200
        assert resp.json()["data_points"] == []

    @pytest.mark.asyncio
    async def test_trends_requires_read_scope(self, client):
        no_scope = Principal(
            user_id="fb-user-1",
            tenant_id="fb-tenant-1",
            role="user",
            scopes=[],
            authenticated=True,
        )
        _use(no_scope)
        resp = await client.get("/api/v1/feedback/trends")
        assert resp.status_code == 403


class TestFeedbackSentimentAndCategory:
    @pytest.mark.asyncio
    async def test_sentiment_analysis(self, client, user_principal):
        _use(user_principal)
        await _create(client, title="This is terrible and broken", description="I hate this bug")

        resp = await client.get("/api/v1/feedback/sentiment-analysis")
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] >= 1
        assert set(data["distribution"]) == {"positive", "neutral", "negative", "unanalyzed"}
        assert data["distribution"]["negative"] >= 1

    @pytest.mark.asyncio
    async def test_category_distribution(self, client, user_principal):
        _use(user_principal)
        await _create(client)

        resp = await client.get("/api/v1/feedback/category-distribution")
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] >= 1
        assert isinstance(data["distribution"], dict)
        assert sum(data["distribution"].values()) == data["total"]


class TestFeedbackSearch:
    @pytest.mark.asyncio
    async def test_search_keyword_match(self, client, user_principal):
        _use(user_principal)
        await _create(client, title="UniqueZebra crash report")

        resp = await client.get("/api/v1/feedback/search?q=UniqueZebra")
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] >= 1
        assert any("UniqueZebra" in item["title"] for item in data["items"])

    @pytest.mark.asyncio
    async def test_search_no_match(self, client, user_principal):
        _use(user_principal)
        await _create(client)

        resp = await client.get("/api/v1/feedback/search?q=NoSuchKeywordXYZ")
        assert resp.status_code == 200
        assert resp.json()["total"] == 0

    @pytest.mark.asyncio
    async def test_search_tenant_isolated(self, client, user_principal):
        _use(user_principal)
        await _create(client, title="TenantScopedZebra bug")

        other_tenant = Principal(
            user_id="fb-user-9",
            tenant_id="fb-tenant-2",
            role="user",
            scopes=list(FEEDBACK_SCOPES),
            authenticated=True,
        )
        _use(other_tenant)
        resp = await client.get("/api/v1/feedback/search?q=TenantScopedZebra")
        assert resp.status_code == 200
        assert resp.json()["total"] == 0


class TestFeedbackExport:
    @pytest.mark.asyncio
    async def test_export_csv(self, client, user_principal):
        _use(user_principal)
        await _create(client, title="CsvExportZebra")

        resp = await client.get("/api/v1/feedback/export?format=csv")
        assert resp.status_code == 200
        assert "text/csv" in resp.headers["content-type"]
        assert "attachment" in resp.headers["content-disposition"]
        body = resp.text
        assert "id,user_id,feedback_type,title" in body
        assert "CsvExportZebra" in body

    @pytest.mark.asyncio
    async def test_export_json(self, client, user_principal):
        _use(user_principal)
        await _create(client, title="JsonExportZebra")

        resp = await client.get("/api/v1/feedback/export?format=json")
        assert resp.status_code == 200
        assert "application/json" in resp.headers["content-type"]
        records = resp.json()
        assert isinstance(records, list)
        assert any(r["title"] == "JsonExportZebra" for r in records)

    @pytest.mark.asyncio
    async def test_export_invalid_format(self, client, user_principal):
        _use(user_principal)
        resp = await client.get("/api/v1/feedback/export?format=xml")
        assert resp.status_code == 422
