from __future__ import annotations

import asyncio
import importlib
import threading

import pytest
from sqlalchemy import event, update
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


@pytest.mark.asyncio
async def test_concurrent_appends_keep_session_counters_and_messages_consistent(tmp_path) -> None:
    store_module = _store_module()
    database_url = f"sqlite:///{(tmp_path / 'concurrent-chat-history.db').as_posix()}"
    store = store_module.SqlChatHistoryStore(database_url, create_schema=True)
    chat_session = await store.create_session(
        tenant_id="tenant-a",
        user_id="user-a",
        title="",
        agent_id="support-agent",
    )
    read_barrier = threading.Barrier(2)

    def synchronize_owned_session_reads(
        _connection,
        _cursor,
        statement,
        _parameters,
        _context,
        _executemany,
    ) -> None:
        normalized = " ".join(statement.lower().split())
        if normalized.startswith("select") and "from chat_sessions" in normalized:
            read_barrier.wait(timeout=5)

    event.listen(store.engine, "before_cursor_execute", synchronize_owned_session_reads)
    try:
        results = await asyncio.gather(
            store.append_message(
                tenant_id="tenant-a",
                user_id="user-a",
                session_id=chat_session.id,
                role="user",
                content="first concurrent message",
            ),
            store.append_message(
                tenant_id="tenant-a",
                user_id="user-a",
                session_id=chat_session.id,
                role="user",
                content="second concurrent message",
            ),
            return_exceptions=True,
        )
    finally:
        event.remove(store.engine, "before_cursor_execute", synchronize_owned_session_reads)

    restored = await store.get_session(
        tenant_id="tenant-a",
        user_id="user-a",
        session_id=chat_session.id,
    )
    await store.dispose()

    assert not [result for result in results if isinstance(result, BaseException)]
    assert restored is not None
    assert restored.message_count == 2
    assert len(restored.messages) == 2
    assert restored.title in {"first concurrent message", "second concurrent message"}
    assert restored.updated_at == max(message.timestamp for message in restored.messages)


@pytest.mark.asyncio
async def test_append_never_moves_session_updated_at_backwards(tmp_path) -> None:
    store_module = _store_module()
    database_url = f"sqlite:///{(tmp_path / 'monotonic-chat-history.db').as_posix()}"
    store = store_module.SqlChatHistoryStore(database_url, create_schema=True)
    chat_session = await store.create_session(
        tenant_id="tenant-a",
        user_id="user-a",
        title="",
        agent_id="support-agent",
    )
    future_timestamp = chat_session.updated_at + 3600

    def set_future_timestamp() -> None:
        with store.engine.begin() as connection:
            connection.execute(
                update(store_module.ChatSessionModel)
                .where(
                    store_module.ChatSessionModel.id == chat_session.id,
                    store_module.ChatSessionModel.tenant_id == "tenant-a",
                    store_module.ChatSessionModel.user_id == "user-a",
                )
                .values(updated_at=future_timestamp)
            )

    await asyncio.to_thread(set_future_timestamp)
    await store.append_message(
        tenant_id="tenant-a",
        user_id="user-a",
        session_id=chat_session.id,
        role="assistant",
        content="older event",
    )
    restored = await store.get_session(
        tenant_id="tenant-a",
        user_id="user-a",
        session_id=chat_session.id,
    )
    await store.dispose()

    assert restored is not None
    assert restored.updated_at == future_timestamp
