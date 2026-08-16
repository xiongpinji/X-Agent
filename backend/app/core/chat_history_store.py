"""Persistent, tenant-isolated chat history storage."""

from __future__ import annotations

import asyncio
import time
import uuid
from functools import lru_cache
from pathlib import Path
from typing import Any, Protocol

from pydantic import BaseModel, Field
from sqlalchemy import (
    JSON,
    Float,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    case,
    create_engine,
    delete,
    event,
    func,
    select,
    update,
)
from sqlalchemy.engine import Engine
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, sessionmaker

from backend.app.core.database_urls import normalize_sync_database_url
from backend.app.settings import PROJECT_ROOT, Settings, get_settings


class ChatMessageRecord(BaseModel):
    id: str = Field(default_factory=lambda: f"msg-{uuid.uuid4().hex[:12]}")
    role: str
    content: str
    timestamp: float = Field(default_factory=time.time)
    metadata: dict[str, Any] = Field(default_factory=dict)


class ChatSession(BaseModel):
    id: str = Field(default_factory=lambda: f"session-{uuid.uuid4().hex[:12]}")
    title: str = ""
    agent_id: str = "default"
    user_id: str = ""
    created_at: float = Field(default_factory=time.time)
    updated_at: float = Field(default_factory=time.time)
    message_count: int = 0
    messages: list[ChatMessageRecord] = Field(default_factory=list)


class ChatHistoryStore(Protocol):
    async def create_session(
        self,
        *,
        tenant_id: str,
        user_id: str,
        title: str = "",
        agent_id: str = "default",
    ) -> ChatSession: ...

    async def list_sessions(
        self,
        *,
        tenant_id: str,
        user_id: str,
        limit: int,
    ) -> tuple[list[ChatSession], int]: ...

    async def get_session(
        self,
        *,
        tenant_id: str,
        user_id: str,
        session_id: str,
    ) -> ChatSession | None: ...

    async def append_message(
        self,
        *,
        tenant_id: str,
        user_id: str,
        session_id: str,
        role: str,
        content: str,
        metadata: dict[str, Any] | None = None,
    ) -> ChatMessageRecord | None: ...

    async def delete_session(
        self,
        *,
        tenant_id: str,
        user_id: str,
        session_id: str,
    ) -> bool: ...

    async def clear_sessions(self, *, tenant_id: str, user_id: str) -> int: ...


class ChatHistoryBase(DeclarativeBase):
    pass


class ChatSessionModel(ChatHistoryBase):
    __tablename__ = "chat_sessions"
    __table_args__ = (
        Index("idx_chat_sessions_principal_updated", "tenant_id", "user_id", "updated_at"),
    )

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    tenant_id: Mapped[str] = mapped_column(String(64), nullable=False)
    user_id: Mapped[str] = mapped_column(String(64), nullable=False)
    title: Mapped[str] = mapped_column(String(255), nullable=False, default="")
    agent_id: Mapped[str] = mapped_column(String(64), nullable=False, default="default")
    created_at: Mapped[float] = mapped_column(Float, nullable=False)
    updated_at: Mapped[float] = mapped_column(Float, nullable=False)
    message_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)


class ChatMessageModel(ChatHistoryBase):
    __tablename__ = "chat_messages"
    __table_args__ = (
        Index(
            "idx_chat_messages_principal_session_time",
            "tenant_id",
            "user_id",
            "session_id",
            "timestamp",
        ),
    )

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    session_id: Mapped[str] = mapped_column(
        String(64),
        ForeignKey("chat_sessions.id", ondelete="CASCADE"),
        nullable=False,
    )
    tenant_id: Mapped[str] = mapped_column(String(64), nullable=False)
    user_id: Mapped[str] = mapped_column(String(64), nullable=False)
    role: Mapped[str] = mapped_column(String(20), nullable=False)
    content: Mapped[str] = mapped_column(Text, nullable=False)
    timestamp: Mapped[float] = mapped_column(Float, nullable=False)
    metadata_payload: Mapped[dict[str, Any]] = mapped_column(
        "metadata",
        JSON,
        nullable=False,
        default=dict,
    )


def _session_record(model: ChatSessionModel, messages: list[ChatMessageRecord] | None = None) -> ChatSession:
    return ChatSession(
        id=model.id,
        title=model.title,
        agent_id=model.agent_id,
        user_id=model.user_id,
        created_at=model.created_at,
        updated_at=model.updated_at,
        message_count=model.message_count,
        messages=messages or [],
    )


def _message_record(model: ChatMessageModel) -> ChatMessageRecord:
    return ChatMessageRecord(
        id=model.id,
        role=model.role,
        content=model.content,
        timestamp=model.timestamp,
        metadata=dict(model.metadata_payload or {}),
    )


class SqlChatHistoryStore:
    """SQLAlchemy store whose public database operations are all asynchronous."""

    def __init__(self, database_url: str, *, create_schema: bool) -> None:
        self.sync_url = normalize_sync_database_url(database_url)
        if self.sync_url.startswith("sqlite") and ":memory:" in self.sync_url:
            raise ValueError("chat history requires persistent storage; in-memory SQLite is not supported")

        engine_kwargs: dict[str, Any] = {"future": True}
        if self.sync_url.startswith("sqlite"):
            engine_kwargs["connect_args"] = {"check_same_thread": False}
        else:
            engine_kwargs.update(
                pool_size=5,
                max_overflow=10,
                pool_recycle=1800,
                pool_pre_ping=True,
                connect_args={"connect_timeout": 5},
            )
        self.engine: Engine = create_engine(self.sync_url, **engine_kwargs)
        if self.sync_url.startswith("sqlite"):
            event.listen(self.engine, "connect", self._enable_sqlite_foreign_keys)
        self._session_factory = sessionmaker(bind=self.engine, expire_on_commit=False)
        self._create_schema = create_schema
        self._schema_ready = False
        self._schema_lock = asyncio.Lock()

    @staticmethod
    def _enable_sqlite_foreign_keys(dbapi_connection: Any, _connection_record: Any) -> None:
        cursor = dbapi_connection.cursor()
        cursor.execute("PRAGMA foreign_keys=ON")
        cursor.close()

    async def _ensure_schema(self) -> None:
        if not self._create_schema or self._schema_ready:
            return
        async with self._schema_lock:
            if not self._schema_ready:
                await asyncio.to_thread(ChatHistoryBase.metadata.create_all, self.engine)
                self._schema_ready = True

    async def _run(self, operation, /, *args):
        await self._ensure_schema()
        return await asyncio.to_thread(operation, *args)

    async def dispose(self) -> None:
        await asyncio.to_thread(self.engine.dispose)

    async def create_session(
        self,
        *,
        tenant_id: str,
        user_id: str,
        title: str = "",
        agent_id: str = "default",
    ) -> ChatSession:
        record = ChatSession(title=title, agent_id=agent_id, user_id=user_id)
        return await self._run(self._create_session, tenant_id, user_id, record)

    def _create_session(self, tenant_id: str, user_id: str, record: ChatSession) -> ChatSession:
        with self._session_factory() as session:
            session.add(
                ChatSessionModel(
                    id=record.id,
                    tenant_id=tenant_id,
                    user_id=user_id,
                    title=record.title,
                    agent_id=record.agent_id,
                    created_at=record.created_at,
                    updated_at=record.updated_at,
                    message_count=0,
                )
            )
            session.commit()
        return record

    async def list_sessions(
        self,
        *,
        tenant_id: str,
        user_id: str,
        limit: int,
    ) -> tuple[list[ChatSession], int]:
        return await self._run(self._list_sessions, tenant_id, user_id, limit)

    def _list_sessions(self, tenant_id: str, user_id: str, limit: int) -> tuple[list[ChatSession], int]:
        with self._session_factory() as session:
            principal_filter = (
                ChatSessionModel.tenant_id == tenant_id,
                ChatSessionModel.user_id == user_id,
            )
            total = int(
                session.scalar(
                    select(func.count()).select_from(ChatSessionModel).where(*principal_filter)
                )
                or 0
            )
            statement = (
                select(ChatSessionModel)
                .where(*principal_filter)
                .order_by(ChatSessionModel.updated_at.desc())
                .limit(limit)
            )
            records = [_session_record(model) for model in session.scalars(statement).all()]
            return records, total

    async def get_session(
        self,
        *,
        tenant_id: str,
        user_id: str,
        session_id: str,
    ) -> ChatSession | None:
        return await self._run(self._get_session, tenant_id, user_id, session_id)

    def _get_session(self, tenant_id: str, user_id: str, session_id: str) -> ChatSession | None:
        with self._session_factory() as session:
            statement = select(ChatSessionModel).where(
                ChatSessionModel.id == session_id,
                ChatSessionModel.tenant_id == tenant_id,
                ChatSessionModel.user_id == user_id,
            )
            model = session.scalar(statement)
            if model is None:
                return None
            messages = session.scalars(
                select(ChatMessageModel)
                .where(
                    ChatMessageModel.session_id == session_id,
                    ChatMessageModel.tenant_id == tenant_id,
                    ChatMessageModel.user_id == user_id,
                )
                .order_by(ChatMessageModel.timestamp.asc())
            ).all()
            return _session_record(model, [_message_record(message) for message in messages])

    async def append_message(
        self,
        *,
        tenant_id: str,
        user_id: str,
        session_id: str,
        role: str,
        content: str,
        metadata: dict[str, Any] | None = None,
    ) -> ChatMessageRecord | None:
        record = ChatMessageRecord(role=role, content=content, metadata=metadata or {})
        return await self._run(self._append_message, tenant_id, user_id, session_id, record)

    def _append_message(
        self,
        tenant_id: str,
        user_id: str,
        session_id: str,
        record: ChatMessageRecord,
    ) -> ChatMessageRecord | None:
        with self._session_factory() as session:
            title = ChatSessionModel.title
            if record.role == "user":
                title = case(
                    (ChatSessionModel.title == "", record.content[:50]),
                    else_=ChatSessionModel.title,
                )
            result = session.execute(
                update(ChatSessionModel)
                .where(
                    ChatSessionModel.id == session_id,
                    ChatSessionModel.tenant_id == tenant_id,
                    ChatSessionModel.user_id == user_id,
                )
                .values(
                    message_count=ChatSessionModel.message_count + 1,
                    updated_at=case(
                        (ChatSessionModel.updated_at < record.timestamp, record.timestamp),
                        else_=ChatSessionModel.updated_at,
                    ),
                    title=title,
                )
            )
            if result.rowcount != 1:
                return None
            session.add(
                ChatMessageModel(
                    id=record.id,
                    session_id=session_id,
                    tenant_id=tenant_id,
                    user_id=user_id,
                    role=record.role,
                    content=record.content,
                    timestamp=record.timestamp,
                    metadata_payload=record.metadata,
                )
            )
            session.commit()
        return record

    async def delete_session(
        self,
        *,
        tenant_id: str,
        user_id: str,
        session_id: str,
    ) -> bool:
        return await self._run(self._delete_session, tenant_id, user_id, session_id)

    def _delete_session(self, tenant_id: str, user_id: str, session_id: str) -> bool:
        with self._session_factory() as session:
            statement = select(ChatSessionModel).where(
                ChatSessionModel.id == session_id,
                ChatSessionModel.tenant_id == tenant_id,
                ChatSessionModel.user_id == user_id,
            )
            model = session.scalar(statement)
            if model is None:
                return False
            session.delete(model)
            session.commit()
            return True

    async def clear_sessions(self, *, tenant_id: str, user_id: str) -> int:
        return await self._run(self._clear_sessions, tenant_id, user_id)

    def _clear_sessions(self, tenant_id: str, user_id: str) -> int:
        with self._session_factory() as session:
            result = session.execute(
                delete(ChatSessionModel).where(
                    ChatSessionModel.tenant_id == tenant_id,
                    ChatSessionModel.user_id == user_id,
                )
            )
            session.commit()
            return int(result.rowcount or 0)


def create_chat_history_store(settings: Settings | None = None) -> SqlChatHistoryStore:
    resolved_settings = settings or get_settings()
    if resolved_settings.app_mode == "production":
        database_url = resolved_settings.database_url
        normalized_url = normalize_sync_database_url(database_url).lower()
        if not normalized_url.startswith("postgresql+psycopg://"):
            raise RuntimeError("production chat history requires PostgreSQL")
        return SqlChatHistoryStore(database_url, create_schema=False)

    configured_url = resolved_settings.database_url.strip()
    if configured_url.lower().startswith("sqlite") and ":memory:" not in configured_url.lower():
        database_url = configured_url
    else:
        data_dir = Path(PROJECT_ROOT) / "data"
        data_dir.mkdir(parents=True, exist_ok=True)
        database_url = f"sqlite:///{(data_dir / 'chat_history.db').as_posix()}"
    return SqlChatHistoryStore(database_url, create_schema=True)


@lru_cache
def get_chat_history_store() -> SqlChatHistoryStore:
    return create_chat_history_store()
