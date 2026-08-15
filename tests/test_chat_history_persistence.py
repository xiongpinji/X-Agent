from __future__ import annotations

import importlib

import pytest
from sqlalchemy.exc import OperationalError


def _store_module():
    try:
        return importlib.import_module("backend.app.core.chat_history_store")
    except ModuleNotFoundError:
        pytest.fail("persistent chat history store is not implemented")


@pytest.mark.asyncio
async def test_file_sqlite_history_survives_store_recreation(tmp_path) -> None:
    store_module = _store_module()
    database_url = f"sqlite:///{(tmp_path / 'chat-history.db').as_posix()}"

    first_store = store_module.SqlChatHistoryStore(database_url, create_schema=True)
    session = await first_store.create_session(
        tenant_id="tenant-a",
        user_id="user-a",
        title="Persistent conversation",
        agent_id="support-agent",
    )
    message = await first_store.append_message(
        tenant_id="tenant-a",
        user_id="user-a",
        session_id=session.id,
        role="user",
        content="Keep this after restart",
        metadata={"source": "persistence-test"},
    )
    await first_store.dispose()

    second_store = store_module.SqlChatHistoryStore(database_url, create_schema=True)
    restored = await second_store.get_session(
        tenant_id="tenant-a",
        user_id="user-a",
        session_id=session.id,
    )
    await second_store.dispose()

    assert restored is not None
    assert restored.id == session.id
    assert restored.title == "Persistent conversation"
    assert restored.agent_id == "support-agent"
    assert restored.message_count == 1
    assert [record.model_dump() for record in restored.messages] == [
        {
            "id": message.id,
            "role": "user",
            "content": "Keep this after restart",
            "timestamp": message.timestamp,
            "metadata": {"source": "persistence-test"},
        }
    ]


@pytest.mark.asyncio
async def test_create_schema_false_fails_closed_when_migration_is_missing(tmp_path) -> None:
    store_module = _store_module()
    database_url = f"sqlite:///{(tmp_path / 'missing-schema.db').as_posix()}"
    store = store_module.SqlChatHistoryStore(database_url, create_schema=False)

    with pytest.raises(OperationalError):
        await store.list_sessions(tenant_id="tenant-a", user_id="user-a", limit=50)

    await store.dispose()
