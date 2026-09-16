"""``PATCH /api/v1/feedback/{id}`` 的请求体契约。

缺陷（静默忽略）：端点只从 query string 读 ``status``（``?status=...``），请求体被
整体丢弃。按 REST 惯例发 ``PATCH`` + ``{"status": "resolved"}`` 的客户端会拿到 200
与**未改变**的记录 —— 静默成功。前端编辑态提交的 ``{status, priority}``（priority
映射后端 severity）同样被丢掉，用户改完严重程度点保存会看到「保存成功」而值不变。

用例刻意用 ``GET`` 复核落库结果，而不是信 ``PATCH`` 自己的响应体：同一个 handler
既能返回真实值也能返回伪造值，只看响应会放过「改了但没存」。
"""

from __future__ import annotations

from datetime import UTC, datetime

import pytest
from fastapi.testclient import TestClient

from backend.app.main import app

ENDPOINT = "/api/v1/feedback"


def _instant(value: str) -> datetime:
    """把响应里的时间戳统一成 UTC 瞬时。

    同一时刻在响应里的写法不固定：写路径（刚 setattr 过 tz-aware datetime）给出
    ``...+00:00``，而回读路径从 DB 列取回的是 naive datetime，``isoformat()`` 之后就
    没有偏移了。这是**已知遗留**（见交付文档），不属于本用例的契约范围 —— 这里只
    比较瞬时，避免把「时间戳格式」误当成「时间被重写」。
    """
    parsed = datetime.fromisoformat(value)
    return parsed.replace(tzinfo=UTC) if parsed.tzinfo is None else parsed.astimezone(UTC)


def _client() -> TestClient:
    """带 body 的请求必须带 API key：CSRF 中间件只对 header 认证的请求豁免，
    否则 PATCH 会先被 403 拦掉，测不到真正的契约。"""
    return TestClient(app, headers={"x-api-key": "bootstrap"})


@pytest.fixture()
def feedback_id() -> str:
    created = _client().post(
        f"{ENDPOINT}/",
        json={
            "feedback_type": "bug",
            "title": "PATCH 请求体契约",
            "description": "用于验证 PATCH 是否真的读请求体。",
            "severity": "low",
        },
    )
    assert created.status_code == 201, created.text
    return created.json()["id"]


def _status(client: TestClient, feedback_id: str) -> str:
    response = client.get(f"{ENDPOINT}/{feedback_id}")
    assert response.status_code == 200
    return response.json()["status"]


def _severity(client: TestClient, feedback_id: str) -> str:
    response = client.get(f"{ENDPOINT}/{feedback_id}")
    assert response.status_code == 200
    return response.json()["severity"]


class TestRequestBodyIsHonored:
    def test_body_status_is_persisted(self, feedback_id: str) -> None:
        client = _client()
        patched = client.patch(f"{ENDPOINT}/{feedback_id}", json={"status": "in_progress"})
        assert patched.status_code == 200, patched.text
        assert _status(client, feedback_id) == "in_progress"

    def test_body_severity_is_persisted(self, feedback_id: str) -> None:
        """前端把 priority 映射成 severity；此前它被静默丢弃。"""
        client = _client()
        patched = client.patch(f"{ENDPOINT}/{feedback_id}", json={"severity": "critical"})
        assert patched.status_code == 200, patched.text
        assert _severity(client, feedback_id) == "critical"

    def test_query_status_still_works(self, feedback_id: str) -> None:
        """query 形态要保持可用（既有 / 未知客户端）。"""
        client = _client()
        patched = client.patch(f"{ENDPOINT}/{feedback_id}", params={"status": "acknowledged"})
        assert patched.status_code == 200, patched.text
        assert _status(client, feedback_id) == "acknowledged"

    def test_resolved_at_is_set_once(self, feedback_id: str) -> None:
        client = _client()
        first = client.patch(f"{ENDPOINT}/{feedback_id}", json={"status": "resolved"})
        assert first.status_code == 200, first.text
        resolved_at = first.json()["resolved_at"]
        assert resolved_at is not None

        # 再次 PATCH resolved 不得把首次解决时间抹成当前时间
        second = client.patch(f"{ENDPOINT}/{feedback_id}", json={"status": "resolved"})
        assert second.status_code == 200
        assert second.json()["resolved_at"] is not None
        assert _instant(second.json()["resolved_at"]) == _instant(resolved_at)


class TestSilentlyIgnoredInputIsNowRejected:
    def test_conflicting_status_is_rejected(self, feedback_id: str) -> None:
        client = _client()
        response = client.patch(
            f"{ENDPOINT}/{feedback_id}",
            params={"status": "closed"},
            json={"status": "resolved"},
        )
        assert response.status_code == 400
        # 不得替调用方任选一个写下去
        assert _status(client, feedback_id) == "new"

    def test_no_update_fields_is_rejected(self, feedback_id: str) -> None:
        """200 + 什么都没做 = 把调用方的 bug 变成静默成功。"""
        client = _client()
        assert client.patch(f"{ENDPOINT}/{feedback_id}").status_code == 400
        assert client.patch(f"{ENDPOINT}/{feedback_id}", json={}).status_code == 400
        assert _status(client, feedback_id) == "new"

    def test_unknown_body_field_is_rejected(self, feedback_id: str) -> None:
        """此前未知字段被丢掉后照样返回 200。"""
        client = _client()
        response = client.patch(
            f"{ENDPOINT}/{feedback_id}",
            json={"status": "resolved", "resolution_note": "夹带"},
        )
        assert response.status_code == 422

    def test_invalid_body_status_is_rejected(self, feedback_id: str) -> None:
        client = _client()
        response = client.patch(f"{ENDPOINT}/{feedback_id}", json={"status": "nonsense"})
        assert response.status_code == 400
        assert _status(client, feedback_id) == "new"

    def test_invalid_body_severity_is_rejected(self, feedback_id: str) -> None:
        client = _client()
        response = client.patch(f"{ENDPOINT}/{feedback_id}", json={"severity": "catastrophic"})
        assert response.status_code == 400
        assert _severity(client, feedback_id) == "low"


class TestPatchRequiresWriteScope:
    def test_unauthenticated_patch_is_401_not_403(self) -> None:
        """PATCH 此前**没有** enforce_scope（PUT / DELETE / resolve 都有）。

        影响：未鉴权主体能一路走到「这条反馈不是你的」判断，拿到的是 403
        「无权访问」，而不是 401「先登录」；并且鉴权发生在资源查找**之后**，
        可以把「存在与否」当作旁路信号。现在与兄弟端点对齐。

        这里刻意用一个不存在的 id：401 必须发生在 404 之前。
        """
        client = TestClient(app)
        csrf = client.post("/api/v1/csrf-token")
        assert csrf.status_code == 200, csrf.text

        response = client.patch(
            f"{ENDPOINT}/does-not-exist",
            json={"status": "resolved"},
            headers={"X-CSRF-Token": csrf.json()["csrf_token"]},
        )
        assert response.status_code == 401, response.text
