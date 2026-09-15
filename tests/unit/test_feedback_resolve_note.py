"""反馈「解决说明」resolution_note 单测 —— 2026-09-15 遗留项②。

背景（为什么这不是"加个字段"这么简单）
=====================================
前端 ``services/feedback.ts::resolveFeedback(id, response)`` 一直在发这个值，但后端
没有任何字段承接：``PATCH /{id}`` 只读 ``status`` 查询参数，``POST /{id}/resolve``
不收请求体，``FeedbackUpdateRequest`` 也没有对应字段。FastAPI 对**未知查询参数不报错**，
于是它被静默丢弃 —— 功能看起来"能用"（HTTP 200），实际什么也没存。

⚠️ 最容易漏的一点：``FeedbackResponse`` 此前有 **5 处**手抄构造
（_to_response / create_feedback / get_feedback / update_feedback / replace_feedback
/ list_feedback 的列表推导）。给响应模型加字段时漏掉任何一处，该端点就会静默不返回
新字段。本文件为此单独锁定"每条返回路径都带这个字段"。

隔离
====
- 强制 ``XAGENT_FEEDBACK_STORE_BACKEND=file``：auto 在有 Postgres 的环境会走 Postgres，
  断言就测不到本实现。
- 存储重定向到 tmp_path，不碰仓库 ``data/``。
- ``tests/conftest.py`` 导入期已幂等注册全部路由，故直接 ``TestClient(app)``，
  不进上下文（不跑 lifespan）。
"""
from __future__ import annotations

import json

import pytest
from fastapi.testclient import TestClient

import backend.app.api.feedback as feedback_api
from backend.app.core.feedback_store_file import FeedbackStoreFile
from backend.app.main import app
from backend.app.settings import get_settings

BASE = "/api/v1/feedback"
CREATE_BODY = {
    "feedback_type": "bug",
    "title": "Login button does nothing",
    "description": "Clicking login has no effect on the homepage.",
    "severity": "high",
}


@pytest.fixture()
def client(tmp_path, monkeypatch):
    monkeypatch.setenv("XAGENT_FEEDBACK_STORE_PATH", str(tmp_path / "feedback_store.json"))
    monkeypatch.setenv("XAGENT_FEEDBACK_STORE_BACKEND", "file")
    # 工厂把实例缓存在模块全局；不清就会沿用上一个用例（乃至仓库 data/）的路径。
    monkeypatch.setattr(feedback_api, "_feedback_store", None)
    monkeypatch.setattr(feedback_api, "_feedback_store_backend", None)
    yield TestClient(app)  # 不进上下文 → 不跑 lifespan


@pytest.fixture()
def headers():
    # bootstrap key → admin，带 feedback:write 全 scope。
    return {"x-api-key": get_settings().bootstrap_api_key or "xagent-dev-key-2024"}


def _create(client: TestClient, headers: dict) -> dict:
    resp = client.post(f"{BASE}/", json=CREATE_BODY, headers=headers)
    assert resp.status_code == 201, resp.text
    return resp.json()


class TestResponsePathsCarryTheField:
    """给 FeedbackResponse 加字段时，5 处构造点必须同步 —— 逐条锁死。

    ⚠️ 断言必须查**值**，不能查"键是否存在"。Pydantic 会把已声明、带默认值的字段
    一并序列化成 null，于是构造点漏传该字段时 ``"x" in body`` 依然成立。

    本类第一版就是那么写的（4 条 `"resolution_note" in body`），变异验证把
    ``_to_response`` 里的传参拿掉之后 —— 4 条**全绿**，什么都没测到。现在改成：
    先把说明写进去，再逐条路径确认取回来的**就是那句话**。
    """

    NOTE = "carried through every response path"

    @pytest.fixture()
    def noted(self, client, headers) -> str:
        fid = _create(client, headers)["id"]
        resp = client.post(
            f"{BASE}/{fid}/resolve",
            json={"resolution_note": self.NOTE},
            headers=headers,
        )
        assert resp.status_code == 200, resp.text
        return fid

    def test_resolve_response_carries_the_note(self, client, headers, noted):
        """不带请求体的重新解决：说明应原样保留并被响应带回。"""
        resp = client.post(f"{BASE}/{noted}/resolve", headers=headers)
        assert resp.json()["resolution_note"] == self.NOTE

    def test_get_detail_carries_the_note(self, client, headers, noted):
        """最要命的一处：前端读单条走这里，漏了就等于说明永远读不回来。"""
        body = client.get(f"{BASE}/{noted}", headers=headers).json()
        assert body["resolution_note"] == self.NOTE

    def test_patch_carries_the_note(self, client, headers, noted):
        body = client.patch(
            f"{BASE}/{noted}", params={"status": "in_progress"}, headers=headers
        ).json()
        assert body["resolution_note"] == self.NOTE

    def test_put_carries_the_note(self, client, headers, noted):
        """PUT 只写它拿到的字段，未提及的说明不该被清掉。"""
        body = client.put(
            f"{BASE}/{noted}", json={"title": "retitled"}, headers=headers
        ).json()
        assert body["resolution_note"] == self.NOTE

    def test_create_response_declares_the_field(self, client, headers):
        """新建记录必然没有说明，这里只能锁"响应模型声明了该字段"。

        这是本类唯一一条 schema 级断言，强度低于上面的值断言 —— 单独标明以免误读。
        """
        body = _create(client, headers)
        assert "resolution_note" in body
        assert body["resolution_note"] is None


class TestResolveWithNote:

    def test_resolve_stores_the_note(self, client, headers):
        fid = _create(client, headers)["id"]

        resp = client.post(
            f"{BASE}/{fid}/resolve",
            json={"resolution_note": "Fixed in #482."},
            headers=headers,
        )

        assert resp.status_code == 200, resp.text
        body = resp.json()
        assert body["resolution_note"] == "Fixed in #482."
        assert body["status"] == "resolved"
        assert body["resolved_at"] is not None

    def test_note_is_readable_again_via_get_detail(self, client, headers):
        """端到端：存进去、重新拉回来。写路径对但读路径漏字段 = 用户看不到。"""
        fid = _create(client, headers)["id"]
        client.post(
            f"{BASE}/{fid}/resolve",
            json={"resolution_note": "已定位为回归，已回滚。"},
            headers=headers,
        )

        body = client.get(f"{BASE}/{fid}", headers=headers).json()

        assert body["resolution_note"] == "已定位为回归，已回滚。"

    def test_note_is_readable_from_the_list(self, client, headers):
        fid = _create(client, headers)["id"]
        client.post(
            f"{BASE}/{fid}/resolve",
            json={"resolution_note": "listed note"},
            headers=headers,
        )

        items = client.get(f"{BASE}/", headers=headers).json()["items"]

        assert [i for i in items if i["id"] == fid][0]["resolution_note"] == "listed note"

    def test_a_later_resolve_replaces_the_note(self, client, headers):
        fid = _create(client, headers)["id"]
        client.post(f"{BASE}/{fid}/resolve", json={"resolution_note": "v1"}, headers=headers)
        client.post(f"{BASE}/{fid}/resolve", json={"resolution_note": "v2"}, headers=headers)

        body = client.get(f"{BASE}/{fid}", headers=headers).json()

        assert body["resolution_note"] == "v2"


class TestResolveWithoutNote:

    @pytest.mark.parametrize("kwargs", [{}, {"json": {}}, {"json": {"resolution_note": None}}])
    def test_no_note_given_leaves_the_record_untouched(self, client, headers, kwargs):
        fid = _create(client, headers)["id"]

        resp = client.post(f"{BASE}/{fid}/resolve", headers=headers, **kwargs)

        assert resp.status_code == 200, resp.text
        assert resp.json()["resolution_note"] is None
        assert resp.json()["status"] == "resolved"

    def test_re_resolving_without_a_note_does_not_erase_the_old_one(self, client, headers):
        """不带说明 ≠ 要求删除说明。抹掉它属于"调用方没说的事" 。"""
        fid = _create(client, headers)["id"]
        client.post(
            f"{BASE}/{fid}/resolve",
            json={"resolution_note": "keep me"},
            headers=headers,
        )

        client.post(f"{BASE}/{fid}/resolve", headers=headers)

        body = client.get(f"{BASE}/{fid}", headers=headers).json()
        assert body["resolution_note"] == "keep me"


class TestStorePersistence:

    @pytest.mark.asyncio
    async def test_legacy_json_without_the_key_still_loads(self, tmp_path):
        """2026-09-15 之前落盘的数据没有这个键。旧库必须仍然能加载。"""
        path = tmp_path / "feedback_store.json"
        path.write_text(
            json.dumps(
                {
                    "feedback": {
                        "old-1": {
                            "id": "old-1",
                            "user_id": "u",
                            "tenant_id": "t",
                            "feedback_type": "bug",
                            "title": "legacy",
                            "description": "written before the field existed",
                            "severity": "low",
                            "status": "resolved",
                            "created_at": "2026-01-01T00:00:00+00:00",
                            "updated_at": "2026-01-01T00:00:00+00:00",
                            "resolved_at": "2026-01-02T00:00:00+00:00",
                        }
                    },
                    "analysis": {},
                },
                ensure_ascii=False,
            ),
            encoding="utf-8",
        )

        record = await FeedbackStoreFile(path).get_feedback_by_id("old-1")

        assert record is not None
        assert record.resolution_note is None

    @pytest.mark.asyncio
    async def test_note_survives_a_fresh_store_instance(self, tmp_path):
        """新实例 = 真的从磁盘读，不是复用内存里的对象。"""
        path = tmp_path / "feedback_store.json"
        store = FeedbackStoreFile(path)
        await store.create_feedback(
            feedback_id="f1",
            user_id="u",
            tenant_id="t",
            feedback_type="bug",
            title="title",
            description="description",
            severity="low",
        )
        await store.update_feedback("f1", status="resolved", resolution_note="已修复")

        reloaded = await FeedbackStoreFile(path).get_feedback_by_id("f1")

        assert reloaded is not None
        assert reloaded.resolution_note == "已修复"

    @pytest.mark.asyncio
    async def test_unknown_kwargs_are_silently_ignored_by_the_store(self, tmp_path):
        """前提实证：store.update_feedback 用 hasattr 过滤。

        这条不是"期望行为"，而是把依赖的前提钉住 —— 正因为未知键被静默忽略，
        ``resolution_note`` 必须真的存在于 FeedbackModel 上，否则整条链路会
        安静地什么都不做（HTTP 仍是 200）。
        """
        path = tmp_path / "feedback_store.json"
        store = FeedbackStoreFile(path)
        await store.create_feedback(
            feedback_id="f2",
            user_id="u",
            tenant_id="t",
            feedback_type="bug",
            title="title",
            description="description",
            severity="low",
        )

        await store.update_feedback("f2", definitely_not_a_field="x")

        reloaded = await FeedbackStoreFile(path).get_feedback_by_id("f2")
        assert reloaded is not None
        assert not hasattr(reloaded, "definitely_not_a_field")
