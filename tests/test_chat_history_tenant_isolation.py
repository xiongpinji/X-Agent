from __future__ import annotations

import importlib
from collections.abc import Iterator
from dataclasses import dataclass

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from backend.app.api import chat_history
from backend.app.core.security import ROLE_SCOPES, Principal
from backend.app.dependencies import get_current_principal


def _store_module():
    try:
        return importlib.import_module("backend.app.core.chat_history_store")
    except ModuleNotFoundError:
        pytest.fail("persistent chat history store is not implemented")


def _principal(tenant_id: str, user_id: str) -> Principal:
    return Principal(
        tenant_id=tenant_id,
        user_id=user_id,
        role="user",
        scopes=list(ROLE_SCOPES["user"]),
        authenticated=True,
    )


@dataclass
class ApiContext:
    client: TestClient
    principal: dict[str, Principal]


@pytest.fixture
def api_context(tmp_path) -> Iterator[ApiContext]:
    store_module = _store_module()
    database_url = f"sqlite:///{(tmp_path / 'chat-history-api.db').as_posix()}"
    store = store_module.SqlChatHistoryStore(database_url, create_schema=True)
    principal = {"current": _principal("tenant-a", "user-a")}

    app = FastAPI()
    app.include_router(chat_history.router)
    app.dependency_overrides[get_current_principal] = lambda: principal["current"]
    app.dependency_overrides[chat_history.get_chat_history_store] = lambda: store

    with TestClient(app, raise_server_exceptions=False) as client:
        yield ApiContext(client=client, principal=principal)

    import asyncio

    asyncio.run(store.dispose())


def _create_session(context: ApiContext, title: str) -> str:
    response = context.client.post(
        "/api/v1/chat/history",
        json={"title": title, "agent_id": "support-agent"},
    )
    assert response.status_code == 200
    return response.json()["id"]


def test_list_is_scoped_by_both_tenant_and_user(api_context: ApiContext) -> None:
    owner_session = _create_session(api_context, "Owner session")

    api_context.principal["current"] = _principal("tenant-a", "user-b")
    other_user_session = _create_session(api_context, "Other user session")
    other_user_list = api_context.client.get("/api/v1/chat/history")

    api_context.principal["current"] = _principal("tenant-b", "user-a")
    other_tenant_session = _create_session(api_context, "Other tenant session")
    other_tenant_list = api_context.client.get("/api/v1/chat/history")

    api_context.principal["current"] = _principal("tenant-a", "user-a")
    owner_list = api_context.client.get("/api/v1/chat/history")

    assert other_user_list.status_code == 200
    assert [item["id"] for item in other_user_list.json()["sessions"]] == [other_user_session]
    assert other_tenant_list.status_code == 200
    assert [item["id"] for item in other_tenant_list.json()["sessions"]] == [other_tenant_session]
    assert owner_list.status_code == 200
    assert [item["id"] for item in owner_list.json()["sessions"]] == [owner_session]


@pytest.mark.parametrize(
    ("intruder_tenant", "intruder_user"),
    [("tenant-a", "user-b"), ("tenant-b", "user-a")],
)
def test_get_append_and_delete_hide_foreign_sessions(
    api_context: ApiContext,
    intruder_tenant: str,
    intruder_user: str,
) -> None:
    owner_session = _create_session(api_context, "Owner session")
    api_context.principal["current"] = _principal(intruder_tenant, intruder_user)

    get_response = api_context.client.get(f"/api/v1/chat/history/{owner_session}")
    append_response = api_context.client.post(
        f"/api/v1/chat/history/{owner_session}/messages",
        json={"role": "user", "content": "take over"},
    )
    delete_response = api_context.client.delete(f"/api/v1/chat/history/{owner_session}")

    assert get_response.status_code == 404
    assert append_response.status_code == 404
    assert delete_response.status_code == 404

    api_context.principal["current"] = _principal("tenant-a", "user-a")
    assert api_context.client.get(f"/api/v1/chat/history/{owner_session}").status_code == 200


def test_append_to_unknown_session_returns_404_without_creating_it(api_context: ApiContext) -> None:
    append_response = api_context.client.post(
        "/api/v1/chat/history/attacker-chosen-id/messages",
        json={"role": "user", "content": "take over"},
    )
    list_response = api_context.client.get("/api/v1/chat/history")

    assert append_response.status_code == 404
    assert list_response.status_code == 200
    assert list_response.json() == {"sessions": [], "total": 0}


def test_clear_only_removes_current_principals_sessions(api_context: ApiContext) -> None:
    owner_session = _create_session(api_context, "Owner session")

    api_context.principal["current"] = _principal("tenant-a", "user-b")
    other_user_session = _create_session(api_context, "Other user session")

    api_context.principal["current"] = _principal("tenant-b", "user-a")
    other_tenant_session = _create_session(api_context, "Other tenant session")

    api_context.principal["current"] = _principal("tenant-a", "user-a")
    clear_response = api_context.client.delete("/api/v1/chat/history")

    assert clear_response.status_code == 200
    assert clear_response.json() == {"status": "cleared", "deleted_count": 1}
    assert api_context.client.get(f"/api/v1/chat/history/{owner_session}").status_code == 404

    api_context.principal["current"] = _principal("tenant-a", "user-b")
    assert api_context.client.get(f"/api/v1/chat/history/{other_user_session}").status_code == 200

    api_context.principal["current"] = _principal("tenant-b", "user-a")
    assert api_context.client.get(f"/api/v1/chat/history/{other_tenant_session}").status_code == 200


@pytest.mark.parametrize(
    "payload",
    [
        {"role": "tool", "content": "invalid role"},
        {"role": 123, "content": "invalid role type"},
        {"role": "user", "content": 123},
        {"role": "user", "content": ""},
        {"role": "user", "content": "x" * 100_001},
        {"role": "user", "content": "invalid metadata", "metadata": []},
        {"role": "user"},
    ],
)
def test_invalid_message_payload_returns_422_without_writing(
    api_context: ApiContext,
    payload: dict,
) -> None:
    session_id = _create_session(api_context, "Validation session")

    response = api_context.client.post(
        f"/api/v1/chat/history/{session_id}/messages",
        json=payload,
    )
    session_response = api_context.client.get(f"/api/v1/chat/history/{session_id}")
    list_response = api_context.client.get("/api/v1/chat/history")

    assert response.status_code == 422
    assert "traceback" not in response.text.lower()
    assert "validationerror" not in response.text.lower()
    assert session_response.status_code == 200
    assert session_response.json()["messages"] == []
    assert list_response.json()["sessions"][0]["message_count"] == 0


@pytest.mark.parametrize(
    "payload",
    [
        {"title": 123, "agent_id": "support-agent"},
        {"title": "x" * 256, "agent_id": "support-agent"},
        {"title": "valid", "agent_id": 123},
        {"title": "valid", "agent_id": ""},
        {"title": "valid", "agent_id": "x" * 65},
    ],
)
def test_invalid_create_payload_returns_422_without_writing(
    api_context: ApiContext,
    payload: dict,
) -> None:
    response = api_context.client.post("/api/v1/chat/history", json=payload)
    list_response = api_context.client.get("/api/v1/chat/history")

    assert response.status_code == 422
    assert "traceback" not in response.text.lower()
    assert "validationerror" not in response.text.lower()
    assert list_response.status_code == 200
    assert list_response.json() == {"sessions": [], "total": 0}


@pytest.mark.parametrize("raw_body", ["null", "[]", '"not-an-object"'])
def test_create_requires_a_json_object_body_without_writing(
    api_context: ApiContext,
    raw_body: str,
) -> None:
    response = api_context.client.post(
        "/api/v1/chat/history",
        content=raw_body,
        headers={"content-type": "application/json"},
    )
    list_response = api_context.client.get("/api/v1/chat/history")

    assert response.status_code == 422
    assert list_response.status_code == 200
    assert list_response.json() == {"sessions": [], "total": 0}


def test_create_requires_a_request_body_without_writing(api_context: ApiContext) -> None:
    response = api_context.client.post("/api/v1/chat/history")
    list_response = api_context.client.get("/api/v1/chat/history")

    assert response.status_code == 422
    assert list_response.status_code == 200
    assert list_response.json() == {"sessions": [], "total": 0}


def test_create_accepts_an_empty_json_object(api_context: ApiContext) -> None:
    response = api_context.client.post("/api/v1/chat/history", json={})
    list_response = api_context.client.get("/api/v1/chat/history")

    assert response.status_code == 200
    assert response.json()["title"] == ""
    assert list_response.status_code == 200
    assert list_response.json()["total"] == 1
