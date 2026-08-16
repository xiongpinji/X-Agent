from __future__ import annotations

import asyncio
from collections import OrderedDict, defaultdict, deque
from datetime import UTC, datetime
from typing import Annotated
from uuid import uuid4

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field

from backend.app.core.security import Principal
from backend.app.dependencies import enforce_scope, get_current_principal

router = APIRouter(prefix="/api/v1/messages", tags=["messages"])
PrincipalDependency = Annotated[Principal, Depends(get_current_principal)]

HISTORY_LIMIT = 1000
SUBSCRIBER_QUEUE_LIMIT = 256
MAX_SUBSCRIBERS_PER_CHANNEL = 64
REPLAY_DEDUPE_LIMIT = HISTORY_LIMIT
MAX_ACTIVE_CHANNELS_PER_TENANT = 128
MAX_HISTORY_CHANNELS_PER_TENANT = 256
MAX_CHANNEL_INDEX_RESULTS = 100
_UNSCOPED_TENANT = "*"

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


class _BoundedEventIds:
    def __init__(self, *, maxlen: int, values: list[str] | None = None) -> None:
        self._maxlen = maxlen
        self._order: deque[str] = deque()
        self._values: set[str] = set()
        for value in values or []:
            self.remember(value)

    def __len__(self) -> int:
        return len(self._values)

    def remember(self, value: str) -> bool:
        if value in self._values:
            return False
        if len(self._order) >= self._maxlen:
            self._values.discard(self._order.popleft())
        self._order.append(value)
        self._values.add(value)
        return True


class MessageStreamCapacityError(RuntimeError):
    pass


class _MessageEventBus:
    def __init__(self) -> None:
        self._subscribers: dict[str, list[asyncio.Queue[UnifiedMessageEvent]]] = defaultdict(list)
        self._history: dict[str, deque[UnifiedMessageEvent]] = defaultdict(lambda: deque(maxlen=HISTORY_LIMIT))
        self._history_by_id: dict[str, UnifiedMessageEvent] = {}
        self._history_id_refcounts: dict[str, int] = {}
        self._channel_event_ids: dict[str, set[str]] = defaultdict(set)
        self._tenant_channels: dict[str, OrderedDict[str, None]] = defaultdict(OrderedDict)
        self._channel_tenant: dict[str, str] = {}
        self._active_tenant_channels: dict[str, set[str]] = defaultdict(set)
        self._subscriber_tenant: dict[str, str] = {}

    def clear(self) -> None:
        self._subscribers.clear()
        self._history.clear()
        self._history_by_id.clear()
        self._history_id_refcounts.clear()
        self._channel_event_ids.clear()
        self._tenant_channels.clear()
        self._channel_tenant.clear()
        self._active_tenant_channels.clear()
        self._subscriber_tenant.clear()

    def clear_channel(self, channel_key: str) -> bool:
        existed = channel_key in self._history or channel_key in self._subscribers
        self._subscribers.pop(channel_key, None)
        self._remove_active_channel_registration(channel_key)
        self._drop_channel_history(channel_key)
        self._remove_channel_registration(channel_key)
        return existed

    def clear_trace(self, trace_id: str, *, tenant_id: str | None = None) -> int:
        removed_event_ids: set[str] = set()
        for channel_key in list(self._history.keys()):
            history = self._history[channel_key]
            remaining = deque(maxlen=HISTORY_LIMIT)
            removed_ids: list[str] = []
            for event in history:
                if event.trace_id == trace_id and (
                    tenant_id is None or event.tenant_id == tenant_id
                ):
                    removed_ids.append(event.event_id)
                    removed_event_ids.add(event.event_id)
                    continue
                remaining.append(event)
            if remaining:
                self._history[channel_key] = remaining
                self._channel_event_ids[channel_key] = {
                    event.event_id for event in remaining
                }
            else:
                self._history.pop(channel_key, None)
                self._channel_event_ids.pop(channel_key, None)
                if not self._subscribers.get(channel_key):
                    self._remove_active_channel_registration(channel_key)
                self._remove_channel_registration(channel_key)
            for event_id in removed_ids:
                self._release_history_id(event_id)
        return len(removed_event_ids)

    def clear_domain(self, domain: str, *, tenant_id: str | None = None) -> int:
        removed_event_ids: set[str] = set()
        for channel_key in list(self._history.keys()):
            history = self._history[channel_key]
            remaining = deque(maxlen=HISTORY_LIMIT)
            removed_ids: list[str] = []
            for event in history:
                if _event_domain(event.event_type) == domain and (
                    tenant_id is None or event.tenant_id == tenant_id
                ):
                    removed_ids.append(event.event_id)
                    removed_event_ids.add(event.event_id)
                    continue
                remaining.append(event)
            if remaining:
                self._history[channel_key] = remaining
                self._channel_event_ids[channel_key] = {
                    event.event_id for event in remaining
                }
            else:
                self._history.pop(channel_key, None)
                self._channel_event_ids.pop(channel_key, None)
                if not self._subscribers.get(channel_key):
                    self._remove_active_channel_registration(channel_key)
                self._remove_channel_registration(channel_key)
            for event_id in removed_ids:
                self._release_history_id(event_id)
        return len(removed_event_ids)

    def get_domain_counts(self, channel_key: str) -> dict[str, int]:
        counts: dict[str, int] = defaultdict(int)
        for event in self._history.get(channel_key, []):
            counts[_event_domain(event.event_type)] += 1
        return dict(counts)

    def get_event_types(self, channel_key: str) -> list[str]:
        return [event.event_type for event in self._history.get(channel_key, [])]

    def get_history_by_domain(self, channel_key: str, domain: str) -> list[UnifiedMessageEvent]:
        return [event for event in self._history.get(channel_key, []) if _event_domain(event.event_type) == domain]

    def get_channel_snapshot(
        self,
        channel_key: str,
        *,
        tenant_id: str | None = None,
    ) -> dict[str, object]:
        history = [
            event
            for event in self._history.get(channel_key, [])
            if tenant_id is None or event.tenant_id == tenant_id
        ]
        return {
            "channel_key": channel_key,
            "history_count": len(history),
            "subscriber_count": len(self._subscribers.get(channel_key, [])),
            "event_types": [event.event_type for event in history],
            "domain_counts": self.get_domain_counts(channel_key),
            "last_event_id": history[-1].event_id if history else None,
            "last_event_type": history[-1].event_type if history else None,
        }

    def get_channel_index(self, *, tenant_id: str | None = None) -> dict[str, object]:
        if tenant_id is None:
            channel_keys = sorted(
                channel_key
                for channel_key in self._history
                if not self._is_tenant_channel(channel_key)
            )
        else:
            channel_keys = [
                channel_key
                for channel_key in self._tenant_channels.get(tenant_id, {})
                if not self._is_tenant_channel(channel_key)
            ]
        total = len(channel_keys)
        selected = list(reversed(channel_keys[-MAX_CHANNEL_INDEX_RESULTS:]))
        return {
            "items": [
                self.get_channel_snapshot(channel_key, tenant_id=tenant_id)
                for channel_key in selected
            ],
            "total": total,
            "truncated": total > MAX_CHANNEL_INDEX_RESULTS,
        }

    def get_history_by_trace(
        self,
        trace_id: str,
        *,
        tenant_id: str | None = None,
    ) -> list[UnifiedMessageEvent]:
        return _dedupe_events(
            [
                event
                for events in self._history.values()
                for event in events
                if event.trace_id == trace_id
                and (tenant_id is None or event.tenant_id == tenant_id)
            ]
        )

    def get_history_by_domain_global(
        self,
        domain: str,
        *,
        tenant_id: str | None = None,
    ) -> list[UnifiedMessageEvent]:
        return _dedupe_events(
            [
                event
                for events in self._history.values()
                for event in events
                if _event_domain(event.event_type) == domain
                and (tenant_id is None or event.tenant_id == tenant_id)
            ]
        )

    def _is_tenant_channel(self, channel_key: str) -> bool:
        tenant_key = self._channel_tenant.get(channel_key)
        if tenant_key is None:
            return False
        tenant_id = None if tenant_key == _UNSCOPED_TENANT else tenant_key
        return channel_key == build_channel_key(tenant_id=tenant_id)

    def subscribe(
        self,
        channel_key: str,
        *,
        tenant_id: str | None = None,
    ) -> asyncio.Queue[UnifiedMessageEvent]:
        tenant_key = tenant_id or self._channel_tenant.get(channel_key) or _UNSCOPED_TENANT
        registered_tenant = self._subscriber_tenant.get(channel_key)
        if registered_tenant is not None and registered_tenant != tenant_key:
            raise MessageStreamCapacityError
        queues = self._subscribers.get(channel_key)
        if queues and len(queues) >= MAX_SUBSCRIBERS_PER_CHANNEL:
            raise MessageStreamCapacityError
        if not queues:
            active_channels = self._active_tenant_channels.get(tenant_key)
            if (
                active_channels is not None
                and len(active_channels) >= MAX_ACTIVE_CHANNELS_PER_TENANT
            ):
                raise MessageStreamCapacityError
            if active_channels is None:
                active_channels = self._active_tenant_channels[tenant_key]
            active_channels.add(channel_key)
            self._subscriber_tenant[channel_key] = tenant_key
        queue: asyncio.Queue[UnifiedMessageEvent] = asyncio.Queue(maxsize=SUBSCRIBER_QUEUE_LIMIT)
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
            self._remove_active_channel_registration(channel_key)

    def _remove_active_channel_registration(self, channel_key: str) -> None:
        tenant_key = self._subscriber_tenant.pop(channel_key, None)
        if tenant_key is None:
            return
        active_channels = self._active_tenant_channels.get(tenant_key)
        if active_channels is None:
            return
        active_channels.discard(channel_key)
        if not active_channels:
            self._active_tenant_channels.pop(tenant_key, None)

    def record(
        self,
        channel_key: str,
        event: UnifiedMessageEvent,
        *,
        protected_channels: set[str] | None = None,
    ) -> bool:
        channel_event_ids = self._channel_event_ids.get(channel_key)
        if channel_event_ids is not None and event.event_id in channel_event_ids:
            return True
        existing = self._history_by_id.get(event.event_id)
        if existing is not None and existing != event:
            return False
        if not self._touch_channel(
            channel_key,
            event.tenant_id,
            protected_channels=protected_channels,
        ):
            return False
        history = self._history[channel_key]
        if channel_event_ids is None:
            channel_event_ids = self._channel_event_ids[channel_key]
        evicted_id = (
            history[0].event_id
            if history.maxlen is not None and len(history) == history.maxlen
            else None
        )
        history.append(event)
        channel_event_ids.add(event.event_id)
        if existing is None:
            self._history_by_id[event.event_id] = event
        self._history_id_refcounts[event.event_id] = (
            self._history_id_refcounts.get(event.event_id, 0) + 1
        )
        if evicted_id is not None:
            channel_event_ids.discard(evicted_id)
            self._release_history_id(evicted_id)
        return True

    def _touch_channel(
        self,
        channel_key: str,
        tenant_id: str | None,
        *,
        protected_channels: set[str] | None = None,
    ) -> bool:
        tenant_key = tenant_id or _UNSCOPED_TENANT
        previous_tenant = self._channel_tenant.get(channel_key)
        if previous_tenant is not None and previous_tenant != tenant_key:
            return False
        channels = self._tenant_channels[tenant_key]
        if channel_key in channels:
            channels.move_to_end(channel_key)
            return True
        while len(channels) >= MAX_HISTORY_CHANNELS_PER_TENANT:
            evicted_channel = next(
                (
                    candidate
                    for candidate in channels
                    if candidate not in (protected_channels or set())
                    and not self._subscribers.get(candidate)
                ),
                None,
            )
            if evicted_channel is None:
                if not channels:
                    self._tenant_channels.pop(tenant_key, None)
                return False
            channels.pop(evicted_channel)
            self._channel_tenant.pop(evicted_channel, None)
            self._drop_channel_history(evicted_channel)
        channels[channel_key] = None
        self._channel_tenant[channel_key] = tenant_key
        return True

    def _remove_channel_registration(self, channel_key: str) -> None:
        tenant_key = self._channel_tenant.pop(channel_key, None)
        if tenant_key is None:
            return
        channels = self._tenant_channels.get(tenant_key)
        if channels is None:
            return
        channels.pop(channel_key, None)
        if not channels:
            self._tenant_channels.pop(tenant_key, None)

    def _drop_channel_history(self, channel_key: str) -> None:
        history = self._history.pop(channel_key, None)
        self._channel_event_ids.pop(channel_key, None)
        if history is None:
            return
        for event in history:
            self._release_history_id(event.event_id)

    def _release_history_id(self, event_id: str) -> None:
        remaining = self._history_id_refcounts.get(event_id, 0) - 1
        if remaining > 0:
            self._history_id_refcounts[event_id] = remaining
            return
        self._history_id_refcounts.pop(event_id, None)
        self._history_by_id.pop(event_id, None)

    def _rollback_latest_record(
        self,
        channel_key: str,
        event_id: str,
        evicted_event: UnifiedMessageEvent | None,
    ) -> bool:
        history = self._history.get(channel_key)
        if not history or history[-1].event_id != event_id:
            return False
        history.pop()
        self._channel_event_ids[channel_key].discard(event_id)
        self._release_history_id(event_id)
        if evicted_event is not None:
            existing = self._history_by_id.get(evicted_event.event_id)
            if existing is not None and existing != evicted_event:
                return False
            history.appendleft(evicted_event)
            self._channel_event_ids[channel_key].add(evicted_event.event_id)
            if existing is None:
                self._history_by_id[evicted_event.event_id] = evicted_event
            self._history_id_refcounts[evicted_event.event_id] = (
                self._history_id_refcounts.get(evicted_event.event_id, 0) + 1
            )
        if not history:
            self._history.pop(channel_key, None)
            self._channel_event_ids.pop(channel_key, None)
            self._remove_channel_registration(channel_key)
        return True

    def _plan_channel_records(
        self,
        channel_keys: list[str],
        event: UnifiedMessageEvent,
    ) -> tuple[
        str,
        list[str],
        list[tuple[str, deque[UnifiedMessageEvent] | None]],
    ] | None:
        existing = self._history_by_id.get(event.event_id)
        if existing is not None and existing != event:
            return None
        tenant_key = event.tenant_id or _UNSCOPED_TENANT
        channels = self._tenant_channels.get(tenant_key, {})
        new_channels = [
            channel_key
            for channel_key in channel_keys
            if channel_key not in channels
            and event.event_id not in self._channel_event_ids.get(channel_key, set())
        ]
        if any(
            self._channel_tenant.get(channel_key) not in {None, tenant_key}
            for channel_key in channel_keys
        ):
            return None
        free_slots = max(0, MAX_HISTORY_CHANNELS_PER_TENANT - len(channels))
        protected_channels = set(channel_keys)
        evictable_channels = [
            channel_key
            for channel_key in channels
            if channel_key not in protected_channels
            and not self._subscribers.get(channel_key)
        ]
        required_evictions = max(0, len(new_channels) - free_slots)
        if required_evictions > len(evictable_channels):
            return None
        return (
            tenant_key,
            list(channels),
            [
                (channel_key, self._history.get(channel_key))
                for channel_key in evictable_channels[:required_evictions]
            ],
        )

    def _rollback_records(
        self,
        records: list[tuple[str, UnifiedMessageEvent | None]],
        event_id: str,
    ) -> None:
        rollback_ok = True
        for channel_key, evicted_event in reversed(records):
            rollback_ok = (
                self._rollback_latest_record(channel_key, event_id, evicted_event)
                and rollback_ok
            )
        if not rollback_ok:
            raise MessageStreamCapacityError("message_history_rollback_failed")

    def _restore_evicted_channels(
        self,
        tenant_key: str,
        original_order: list[str],
        snapshots: list[tuple[str, deque[UnifiedMessageEvent] | None]],
    ) -> bool:
        snapshot_keys = {channel_key for channel_key, _history in snapshots}
        for channel_key, history in snapshots:
            registered_tenant = self._channel_tenant.get(channel_key)
            if registered_tenant is not None:
                if registered_tenant != tenant_key:
                    return False
                continue
            self._channel_tenant[channel_key] = tenant_key
            if history is None:
                continue
            self._history[channel_key] = history
            self._channel_event_ids[channel_key] = {
                event.event_id for event in history
            }
            for historical_event in history:
                existing = self._history_by_id.get(historical_event.event_id)
                if existing is not None and existing != historical_event:
                    return False
                if existing is None:
                    self._history_by_id[historical_event.event_id] = historical_event
                self._history_id_refcounts[historical_event.event_id] = (
                    self._history_id_refcounts.get(historical_event.event_id, 0) + 1
                )

        current_order = list(self._tenant_channels.get(tenant_key, {}))
        restored_order = [
            channel_key
            for channel_key in original_order
            if channel_key in current_order or channel_key in snapshot_keys
        ]
        restored_order.extend(
            channel_key
            for channel_key in current_order
            if channel_key not in restored_order
        )
        if restored_order:
            self._tenant_channels[tenant_key] = OrderedDict.fromkeys(restored_order)
        return True

    def _rollback_publish(
        self,
        records: list[tuple[str, UnifiedMessageEvent | None]],
        event_id: str,
        tenant_key: str,
        original_order: list[str],
        eviction_snapshots: list[tuple[str, deque[UnifiedMessageEvent] | None]],
    ) -> None:
        rollback_ok = True
        try:
            self._rollback_records(records, event_id)
        except MessageStreamCapacityError:
            rollback_ok = False
        restore_ok = self._restore_evicted_channels(
            tenant_key,
            original_order,
            eviction_snapshots,
        )
        if not rollback_ok or not restore_ok:
            raise MessageStreamCapacityError("message_history_rollback_failed")

    async def publish(self, channel_key: str, event: UnifiedMessageEvent) -> None:
        tenant_channel_key = build_channel_key(tenant_id=event.tenant_id)
        channel_keys = list(dict.fromkeys((tenant_channel_key, channel_key)))
        record_plan = self._plan_channel_records(channel_keys, event)
        if record_plan is None:
            raise MessageStreamCapacityError("message_history_capacity_exceeded")
        tenant_key, original_order, eviction_snapshots = record_plan
        protected_channels = set(channel_keys)
        newly_recorded: list[tuple[str, UnifiedMessageEvent | None]] = []
        for target_channel in channel_keys:
            already_recorded = event.event_id in self._channel_event_ids.get(
                target_channel, set()
            )
            history = self._history.get(target_channel)
            evicted_event = (
                history[0]
                if not already_recorded
                and history is not None
                and history.maxlen is not None
                and len(history) == history.maxlen
                else None
            )
            try:
                recorded = self.record(
                    target_channel,
                    event,
                    protected_channels=protected_channels,
                )
            except Exception:
                if (
                    not already_recorded
                    and event.event_id
                    in self._channel_event_ids.get(target_channel, set())
                ):
                    newly_recorded.append((target_channel, evicted_event))
                self._rollback_publish(
                    newly_recorded,
                    event.event_id,
                    tenant_key,
                    original_order,
                    eviction_snapshots,
                )
                raise MessageStreamCapacityError(
                    "message_history_capacity_exceeded"
                ) from None
            if not recorded:
                if (
                    not already_recorded
                    and event.event_id
                    in self._channel_event_ids.get(target_channel, set())
                ):
                    newly_recorded.append((target_channel, evicted_event))
                self._rollback_publish(
                    newly_recorded,
                    event.event_id,
                    tenant_key,
                    original_order,
                    eviction_snapshots,
                )
                raise MessageStreamCapacityError("message_history_capacity_exceeded")
            if not already_recorded:
                newly_recorded.append((target_channel, evicted_event))

        for target_channel in channel_keys:
            for queue in self._subscribers.get(target_channel, []):
                if queue.full():
                    while not queue.empty():
                        queue.get_nowait()
                    queue.put_nowait(
                        UnifiedMessageEvent(
                            event_id="",
                            event_type="stream.gap",
                            tenant_id=event.tenant_id,
                            org_id=event.org_id,
                            room_id=event.room_id,
                            conversation_id=event.conversation_id,
                            agent_id=event.agent_id,
                            user_id=event.user_id,
                            channel_type=event.channel_type,
                            trace_id=event.trace_id,
                            payload={"reason": "subscriber_overflow"},
                        )
                    )
                    continue
                queue.put_nowait(event)

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


def _serialize_sse(
    event: UnifiedMessageEvent,
    event_name: str | None = None,
    *,
    include_id: bool = True,
) -> str:
    lines = []
    if event_name:
        lines.append(f"event: {event_name}")
    if include_id:
        lines.append(f"id: {event.event_id}")
    lines.append(f"data: {event.model_dump_json()}")
    return "\n".join(lines) + "\n\n"


@router.get("/stream")
async def stream_messages(
    request: Request,
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
    resume_event_id = request.headers.get("last-event-id") or last_event_id

    stream_filter = MessageStreamFilter(
        tenant_id=principal.tenant_id,
        org_id=org_id,
        room_id=room_id,
        conversation_id=conversation_id,
        agent_id=agent_id,
        user_id=user_id,
        channel_type=channel_type,
        trace_id=trace_id,
        since=datetime.fromisoformat(since) if since else None,
        include_system=include_system,
        include_audit=include_audit,
        include_workflow=include_workflow,
        last_event_id=resume_event_id,
    )

    channel_key = build_channel_key(tenant_id=stream_filter.tenant_id)

    try:
        queue = message_event_bus.subscribe(
            channel_key,
            tenant_id=principal.tenant_id,
        )
    except MessageStreamCapacityError:
        raise HTTPException(
            status_code=429,
            detail={
                "code": "message_stream_capacity_exceeded",
                "message": "Message stream capacity is temporarily exhausted.",
            },
        ) from None
    history = message_event_bus.get_history(
        channel_key,
        since=stream_filter.since,
        last_event_id=stream_filter.last_event_id,
    )
    history = [event for event in history if _event_matches_filter(event, stream_filter)]
    replay_ids = _BoundedEventIds(
        maxlen=REPLAY_DEDUPE_LIMIT,
        values=[event.event_id for event in history],
    )

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
            yield _serialize_sse(hello, "system.notification", include_id=False)

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
                    if event.event_type == "stream.gap":
                        yield _serialize_sse(event, "stream.gap", include_id=False)
                        return
                    if not replay_ids.remember(event.event_id):
                        continue
                    if not _event_matches_filter(event, stream_filter):
                        continue
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
                    yield _serialize_sse(
                        heartbeat,
                        "system.notification",
                        include_id=False,
                    )
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
        tenant_id=principal.tenant_id,
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
        tenant_id=principal.tenant_id,
        org_id=payload.get("org_id") or None,
        room_id=payload.get("room_id") or None,
        conversation_id=payload.get("conversation_id") or None,
        agent_id=payload.get("agent_id") or principal.agent_id,
        user_id=payload.get("user_id") or principal.user_id,
        channel_type=str(payload.get("channel_type") or "system"),
        payload=payload,
    )
    try:
        await message_event_bus.publish(channel_key, event)
    except MessageStreamCapacityError:
        raise HTTPException(
            status_code=503,
            detail={
                "code": "message_delivery_unavailable",
                "message": "Message delivery could not be recorded.",
                "delivery_status": "not_delivered",
            },
        ) from None
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
        tenant_id=principal.tenant_id,
        org_id=org_id,
        room_id=room_id,
        conversation_id=conversation_id,
        agent_id=agent_id or principal.agent_id,
        user_id=user_id or principal.user_id,
        channel_type=channel_type,
        trace_id=trace_id or principal.trace_id,
    )
    return message_event_bus.get_channel_snapshot(
        channel_key,
        tenant_id=principal.tenant_id,
    )


@router.get("/debug/channel-index")
async def get_channel_index(principal: PrincipalDependency) -> dict[str, object]:
    enforce_scope(principal, "agent:run")
    return message_event_bus.get_channel_index(tenant_id=principal.tenant_id)


@router.get("/debug/trace-events")
async def get_trace_events(principal: PrincipalDependency, trace_id: str = Query(...)) -> list[dict[str, object]]:
    enforce_scope(principal, "agent:run")
    return [
        event.model_dump(mode="json")
        for event in message_event_bus.get_history_by_trace(
            trace_id,
            tenant_id=principal.tenant_id,
        )
    ]


@router.get("/debug/domain-events")
async def get_domain_events(principal: PrincipalDependency, domain: str = Query(...)) -> list[dict[str, object]]:
    enforce_scope(principal, "agent:run")
    return [
        event.model_dump(mode="json")
        for event in message_event_bus.get_history_by_domain_global(
            domain,
            tenant_id=principal.tenant_id,
        )
    ]


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
    enforce_scope(principal, "security:manage")
    channel_key = build_channel_key(
        tenant_id=principal.tenant_id,
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
    enforce_scope(principal, "security:manage")
    removed_count = message_event_bus.clear_trace(trace_id, tenant_id=principal.tenant_id)
    return {"trace_id": trace_id, "removed_count": removed_count}


@router.delete("/debug/domain")
async def clear_domain(principal: PrincipalDependency, domain: str = Query(...)) -> dict[str, object]:
    enforce_scope(principal, "security:manage")
    removed_count = message_event_bus.clear_domain(domain, tenant_id=principal.tenant_id)
    return {"domain": domain, "removed_count": removed_count}
