from __future__ import annotations

import asyncio
from collections import defaultdict, deque
from datetime import UTC, datetime
from typing import Annotated
from uuid import uuid4

from fastapi import APIRouter, Depends, Query
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field

from backend.app.core.security import Principal
from backend.app.dependencies import enforce_scope, get_current_principal

router = APIRouter(prefix="/api/v1/messages", tags=["messages"])
PrincipalDependency = Annotated[Principal, Depends(get_current_principal)]

HISTORY_LIMIT = 1000

# Final event reference for `messages/stream`.
#
# Event type -> domain -> typical consumer
# - system.notification   -> system       -> bootstrap, heartbeat, connection status
# - room.created          -> room         -> ConsoleShell / OrganizationGraphPage / MeetingRoomsPage
# - room.member_added     -> room         -> ConsoleShell / MeetingRoomsPage / OrganizationGraphPage
# - room.closed           -> room         -> ConsoleShell / AuditReplayPage / MeetingRoomsPage
# - message.created       -> room         -> ConsoleShell / RealtimeChatPage / AuditReplayPage
# - workflow.updated      -> workflow     -> ConsoleShell / WorkflowPage / AuditReplayPage
# - audit.created         -> audit        -> AuditReplayPage
# - conversation.updated  -> conversation -> ConsoleShell / RealtimeChatPage
# - presence.updated      -> system       -> ConsoleShell / RealtimeChatPage
# - custom.*              -> custom       -> extension-specific consumers
#
# Notes:
# - Frontend uses `event_id` as SSE `id:` for Last-Event-ID replay.
# - `include_system/include_audit/include_workflow` filter by domain, not raw prefix.
# - Replay is de-duplicated by `event_id` and by channel history.
EVENT_DOMAIN_PREFIXES: dict[str, tuple[str, ...]] = {
    "system": ("system.",),
    "audit": ("audit.",),
    "workflow": ("workflow.",),
    "room": ("room.", "message."),
    "conversation": ("conversation.",),
}


class MessageStreamFilter(BaseModel):
    tenant_id: str | None = None
    org_id: str | None = None
    room_id: str | None = None
    conversation_id: str | None = None
    agent_id: str | None = None
    user_id: str | None = None
    channel_type: str | None = None
    trace_id: str | None = None
    since: datetime | None = None
    include_system: bool = True
    include_audit: bool = True
    include_workflow: bool = True
    last_event_id: str | None = None


class UnifiedMessageEvent(BaseModel):
    event_id: str = Field(default_factory=lambda: str(uuid4()))
    event_type: str
    timestamp: datetime = Field(default_factory=lambda: datetime.now(UTC))
    trace_id: str | None = None
    tenant_id: str | None = None
    org_id: str | None = None
    room_id: str | None = None
    conversation_id: str | None = None
    agent_id: str | None = None
    user_id: str | None = None
    channel_type: str = "system"
    payload: dict[str, object] = Field(default_factory=dict)


class _MessageEventBus:
    def __init__(self) -> None:
        self._subscribers: dict[str, list[asyncio.Queue[UnifiedMessageEvent]]] = defaultdict(list)
        self._history: dict[str, deque[UnifiedMessageEvent]] = defaultdict(lambda: deque(maxlen=HISTORY_LIMIT))
        self._history_by_id: dict[str, UnifiedMessageEvent] = {}

    def clear(self) -> None:
        self._subscribers.clear()
        self._history.clear()
        self._history_by_id.clear()

    def clear_channel(self, channel_key: str) -> bool:
        existed = channel_key in self._history or channel_key in self._subscribers
        self._subscribers.pop(channel_key, None)
        history = self._history.pop(channel_key, None)
        if history is not None:
            for event in history:
                self._history_by_id.pop(event.event_id, None)
        return existed

    def clear_trace(self, trace_id: str) -> int:
        removed_count = 0
        for channel_key in list(self._history.keys()):
            history = self._history[channel_key]
            remaining = deque(maxlen=HISTORY_LIMIT)
            for event in history:
                if event.trace_id == trace_id:
                    self._history_by_id.pop(event.event_id, None)
                    removed_count += 1
                    continue
                remaining.append(event)
            if remaining:
                self._history[channel_key] = remaining
            else:
                self._history.pop(channel_key, None)
                self._subscribers.pop(channel_key, None)
        return removed_count

    def clear_domain(self, domain: str) -> int:
        removed_count = 0
        for channel_key in list(self._history.keys()):
            history = self._history[channel_key]
            remaining = deque(maxlen=HISTORY_LIMIT)
            for event in history:
                if _event_domain(event.event_type) == domain:
                    self._history_by_id.pop(event.event_id, None)
                    removed_count += 1
                    continue
                remaining.append(event)
            if remaining:
                self._history[channel_key] = remaining
            else:
                self._history.pop(channel_key, None)
                self._subscribers.pop(channel_key, None)
        return removed_count

    def get_domain_counts(self, channel_key: str) -> dict[str, int]:
        counts: dict[str, int] = defaultdict(int)
        for event in self._history.get(channel_key, []):
            counts[_event_domain(event.event_type)] += 1
        return dict(counts)

    def get_event_types(self, channel_key: str) -> list[str]:
        return [event.event_type for event in self._history.get(channel_key, [])]

    def get_history_by_domain(self, channel_key: str, domain: str) -> list[UnifiedMessageEvent]:
        return [event for event in self._history.get(channel_key, []) if _event_domain(event.event_type) == domain]

    def get_channel_snapshot(self, channel_key: str) -> dict[str, object]:
        history = list(self._history.get(channel_key, []))
        return {
            "channel_key": channel_key,
            "history_count": len(history),
            "subscriber_count": len(self._subscribers.get(channel_key, [])),
            "event_types": [event.event_type for event in history],
            "domain_counts": self.get_domain_counts(channel_key),
            "last_event_id": history[-1].event_id if history else None,
            "last_event_type": history[-1].event_type if history else None,
        }

    def get_channel_index(self) -> list[dict[str, object]]:
        return [self.get_channel_snapshot(channel_key) for channel_key in sorted(self._history.keys())]

    def get_history_by_trace(self, trace_id: str) -> list[UnifiedMessageEvent]:
        return [event for events in self._history.values() for event in events if event.trace_id == trace_id]

    def get_history_by_domain_global(self, domain: str) -> list[UnifiedMessageEvent]:
        return [event for events in self._history.values() for event in events if _event_domain(event.event_type) == domain]

    def subscribe(self, channel_key: str) -> asyncio.Queue[UnifiedMessageEvent]:
        queue: asyncio.Queue[UnifiedMessageEvent] = asyncio.Queue()
        self._subscribers[channel_key].append(queue)
        return queue

    def unsubscribe(self, channel_key: str, queue: asyncio.Queue[UnifiedMessageEvent]) -> None:
        queues = self._subscribers.get(channel_key)
        if not queues:
            return
        if queue in queues:
            queues.remove(queue)
        if not queues:
            self._subscribers.pop(channel_key, None)

    def record(self, channel_key: str, event: UnifiedMessageEvent) -> None:
        history = self._history[channel_key]
        if history and history[-1].event_id == event.event_id:
            return
        if event.event_id in self._history_by_id:
            return
        history.append(event)
        self._history_by_id[event.event_id] = event

    async def publish(self, channel_key: str, event: UnifiedMessageEvent) -> None:
        self.record(channel_key, event)
        for queue in self._subscribers.get(channel_key, []):
            await queue.put(event)

    def get_history(
        self,
        channel_key: str,
        *,
        since: datetime | None = None,
        last_event_id: str | None = None,
    ) -> list[UnifiedMessageEvent]:
        history = list(self._history.get(channel_key, []))
        if last_event_id:
            anchor = self._history_by_id.get(last_event_id)
            if anchor is not None:
                history = [event for event in history if _is_newer_event(event, anchor)]
            else:
                history = [event for event in history if event.event_id != last_event_id]
        if since:
            history = [event for event in history if event.timestamp >= since]
        return _dedupe_events(history)


message_event_bus = _MessageEventBus()


def build_channel_key(
    *,
    tenant_id: str | None = None,
    org_id: str | None = None,
    room_id: str | None = None,
    conversation_id: str | None = None,
    agent_id: str | None = None,
    user_id: str | None = None,
    channel_type: str | None = None,
    trace_id: str | None = None,
) -> str:
    return "|".join(
        [
            f"tenant:{tenant_id or '*'}",
            f"org:{org_id or '*'}",
            f"room:{room_id or '*'}",
            f"conv:{conversation_id or '*'}",
            f"agent:{agent_id or '*'}",
            f"user:{user_id or '*'}",
            f"channel:{channel_type or '*'}",
            f"trace:{trace_id or '*'}",
        ],
    )


def _event_domain(event_type: str) -> str:
    for domain, prefixes in EVENT_DOMAIN_PREFIXES.items():
        if any(event_type.startswith(prefix) for prefix in prefixes):
            return domain
    return "custom"


def _is_newer_event(candidate: UnifiedMessageEvent, anchor: UnifiedMessageEvent) -> bool:
    if candidate.timestamp > anchor.timestamp:
        return True
    if candidate.timestamp < anchor.timestamp:
        return False
    return candidate.event_id > anchor.event_id


def _dedupe_events(events: list[UnifiedMessageEvent]) -> list[UnifiedMessageEvent]:
    deduped: list[UnifiedMessageEvent] = []
    seen: set[str] = set()
    for event in events:
        if event.event_id in seen:
            continue
        seen.add(event.event_id)
        deduped.append(event)
    return deduped


def _event_matches_filter(event: UnifiedMessageEvent, stream_filter: MessageStreamFilter) -> bool:
    if stream_filter.tenant_id and event.tenant_id != stream_filter.tenant_id:
        return False
    if stream_filter.org_id and event.org_id != stream_filter.org_id:
        return False
    if stream_filter.room_id and event.room_id != stream_filter.room_id:
        return False
    if stream_filter.conversation_id and event.conversation_id != stream_filter.conversation_id:
        return False
    if stream_filter.agent_id and event.agent_id != stream_filter.agent_id:
        return False
    if stream_filter.user_id and event.user_id != stream_filter.user_id:
        return False
    if stream_filter.trace_id and event.trace_id != stream_filter.trace_id:
        return False
    if stream_filter.channel_type and event.channel_type != stream_filter.channel_type:
        return False

    domain = _event_domain(event.event_type)
    if domain == "system" and not stream_filter.include_system:
        return False
    if domain == "audit" and not stream_filter.include_audit:
        return False
    if domain == "workflow" and not stream_filter.include_workflow:
        return False

    return not (stream_filter.since and event.timestamp < stream_filter.since)


def _serialize_sse(event: UnifiedMessageEvent, event_name: str | None = None) -> str:
    lines = []
    if event_name:
        lines.append(f"event: {event_name}")
    lines.append(f"id: {event.event_id}")
    lines.append(f"data: {event.model_dump_json()}")
    return "\n".join(lines) + "\n\n"


@router.get("/stream")
async def stream_messages(
    principal: PrincipalDependency,
    tenant_id: str | None = Query(default=None),
    org_id: str | None = Query(default=None),
    room_id: str | None = Query(default=None),
    conversation_id: str | None = Query(default=None),
    agent_id: str | None = Query(default=None),
    user_id: str | None = Query(default=None),
    channel_type: str | None = Query(default=None),
    trace_id: str | None = Query(default=None),
    since: str | None = Query(default=None),
    last_event_id: str | None = Query(default=None),
    include_system: bool = Query(default=True),
    include_audit: bool = Query(default=True),
    include_workflow: bool = Query(default=True),
    replay_only: bool = Query(default=False),
):
    enforce_scope(principal, "agent:run")

    stream_filter = MessageStreamFilter(
        tenant_id=tenant_id or principal.tenant_id,
        org_id=org_id,
        room_id=room_id,
        conversation_id=conversation_id,
        agent_id=agent_id or principal.agent_id,
        user_id=user_id or principal.user_id,
        channel_type=channel_type,
        trace_id=trace_id or principal.trace_id,
        since=datetime.fromisoformat(since) if since else None,
        include_system=include_system,
        include_audit=include_audit,
        include_workflow=include_workflow,
        last_event_id=last_event_id,
    )

    channel_key = build_channel_key(
        tenant_id=stream_filter.tenant_id,
        org_id=stream_filter.org_id,
        room_id=stream_filter.room_id,
        conversation_id=stream_filter.conversation_id,
        agent_id=stream_filter.agent_id,
        user_id=stream_filter.user_id,
        channel_type=stream_filter.channel_type,
        trace_id=stream_filter.trace_id,
    )

    queue = message_event_bus.subscribe(channel_key)
    history = message_event_bus.get_history(
        channel_key,
        since=stream_filter.since,
        last_event_id=stream_filter.last_event_id,
    )
    history = [event for event in history if _event_matches_filter(event, stream_filter)]
    replay_ids = {event.event_id for event in history}

    async def event_generator():
        try:
            hello = UnifiedMessageEvent(
                event_type="system.notification",
                tenant_id=stream_filter.tenant_id,
                org_id=stream_filter.org_id,
                room_id=stream_filter.room_id,
                conversation_id=stream_filter.conversation_id,
                agent_id=stream_filter.agent_id,
                user_id=stream_filter.user_id,
                channel_type="system",
                trace_id=principal.trace_id,
                payload={
                    "status": "connected",
                    "channel_key": channel_key,
                    "filter": stream_filter.model_dump(mode="json"),
                    "server_time": datetime.now(UTC).isoformat(),
                    "history_count": len(history),
                    "last_event_id": stream_filter.last_event_id,
                },
            )
            yield _serialize_sse(hello, "system.notification")

            for historical_event in history:
                yield _serialize_sse(historical_event, historical_event.event_type)

            # replay_only: non-streaming clients (tests, snapshot fetchers) get the
            # connect notice + replayed history then the stream ends, instead of the
            # infinite live heartbeat loop. Real SSE clients omit it and stream live.
            if replay_only:
                return

            while True:
                try:
                    event = await asyncio.wait_for(queue.get(), timeout=15)
                    if event.event_id in replay_ids:
                        continue
                    if not _event_matches_filter(event, stream_filter):
                        continue
                    replay_ids.add(event.event_id)
                    yield _serialize_sse(event, event.event_type)
                except TimeoutError:
                    heartbeat = UnifiedMessageEvent(
                        event_type="system.notification",
                        tenant_id=stream_filter.tenant_id,
                        org_id=stream_filter.org_id,
                        room_id=stream_filter.room_id,
                        conversation_id=stream_filter.conversation_id,
                        agent_id=stream_filter.agent_id,
                        user_id=stream_filter.user_id,
                        channel_type="system",
                        trace_id=principal.trace_id,
                        payload={"type": "heartbeat", "server_time": datetime.now(UTC).isoformat()},
                    )
                    yield _serialize_sse(heartbeat, "system.notification")
        finally:
            message_event_bus.unsubscribe(channel_key, queue)

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache, no-transform",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )


@router.post("/publish-test")
async def publish_test_event(principal: PrincipalDependency, payload: dict[str, object]) -> dict[str, object]:
    enforce_scope(principal, "agent:run")
    channel_key = build_channel_key(
        tenant_id=str(payload.get("tenant_id") or principal.tenant_id),
        org_id=payload.get("org_id") or None,
        room_id=payload.get("room_id") or None,
        conversation_id=payload.get("conversation_id") or None,
        agent_id=payload.get("agent_id") or principal.agent_id,
        user_id=payload.get("user_id") or principal.user_id,
        channel_type=payload.get("channel_type") or None,
        trace_id=payload.get("trace_id") or principal.trace_id,
    )
    event = UnifiedMessageEvent(
        event_type=str(payload.get("event_type") or "system.notification"),
        trace_id=payload.get("trace_id") or principal.trace_id,
        tenant_id=str(payload.get("tenant_id") or principal.tenant_id),
        org_id=payload.get("org_id") or None,
        room_id=payload.get("room_id") or None,
        conversation_id=payload.get("conversation_id") or None,
        agent_id=payload.get("agent_id") or principal.agent_id,
        user_id=payload.get("user_id") or principal.user_id,
        channel_type=str(payload.get("channel_type") or "system"),
        payload=payload,
    )
    await message_event_bus.publish(channel_key, event)
    return {"published": True, "channel_key": channel_key, "event_id": event.event_id, "event_domain": _event_domain(event.event_type)}


@router.get("/debug/channel-snapshot")
async def get_channel_snapshot(
    principal: PrincipalDependency,
    tenant_id: str | None = Query(default=None),
    org_id: str | None = Query(default=None),
    room_id: str | None = Query(default=None),
    conversation_id: str | None = Query(default=None),
    agent_id: str | None = Query(default=None),
    user_id: str | None = Query(default=None),
    channel_type: str | None = Query(default=None),
    trace_id: str | None = Query(default=None),
) -> dict[str, object]:
    enforce_scope(principal, "agent:run")
    channel_key = build_channel_key(
        tenant_id=tenant_id or principal.tenant_id,
        org_id=org_id,
        room_id=room_id,
        conversation_id=conversation_id,
        agent_id=agent_id or principal.agent_id,
        user_id=user_id or principal.user_id,
        channel_type=channel_type,
        trace_id=trace_id or principal.trace_id,
    )
    return message_event_bus.get_channel_snapshot(channel_key)


@router.get("/debug/channel-index")
async def get_channel_index(principal: PrincipalDependency) -> list[dict[str, object]]:
    enforce_scope(principal, "agent:run")
    return message_event_bus.get_channel_index()


@router.get("/debug/trace-events")
async def get_trace_events(principal: PrincipalDependency, trace_id: str = Query(...)) -> list[dict[str, object]]:
    enforce_scope(principal, "agent:run")
    return [event.model_dump(mode="json") for event in message_event_bus.get_history_by_trace(trace_id)]


@router.get("/debug/domain-events")
async def get_domain_events(principal: PrincipalDependency, domain: str = Query(...)) -> list[dict[str, object]]:
    enforce_scope(principal, "agent:run")
    return [event.model_dump(mode="json") for event in message_event_bus.get_history_by_domain_global(domain)]


@router.delete("/debug/channel")
async def clear_channel(
    principal: PrincipalDependency,
    tenant_id: str | None = Query(default=None),
    org_id: str | None = Query(default=None),
    room_id: str | None = Query(default=None),
    conversation_id: str | None = Query(default=None),
    agent_id: str | None = Query(default=None),
    user_id: str | None = Query(default=None),
    channel_type: str | None = Query(default=None),
    trace_id: str | None = Query(default=None),
) -> dict[str, object]:
    enforce_scope(principal, "agent:run")
    channel_key = build_channel_key(
        tenant_id=tenant_id or principal.tenant_id,
        org_id=org_id,
        room_id=room_id,
        conversation_id=conversation_id,
        agent_id=agent_id or principal.agent_id,
        user_id=user_id or principal.user_id,
        channel_type=channel_type,
        trace_id=trace_id or principal.trace_id,
    )
    return {"channel_key": channel_key, "cleared": message_event_bus.clear_channel(channel_key)}


@router.delete("/debug/trace")
async def clear_trace(principal: PrincipalDependency, trace_id: str = Query(...)) -> dict[str, object]:
    enforce_scope(principal, "agent:run")
    removed_count = message_event_bus.clear_trace(trace_id)
    return {"trace_id": trace_id, "removed_count": removed_count}


@router.delete("/debug/domain")
async def clear_domain(principal: PrincipalDependency, domain: str = Query(...)) -> dict[str, object]:
    enforce_scope(principal, "agent:run")
    removed_count = message_event_bus.clear_domain(domain)
    return {"domain": domain, "removed_count": removed_count}
