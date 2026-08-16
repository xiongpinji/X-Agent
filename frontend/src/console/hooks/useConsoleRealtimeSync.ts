import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { ConsoleApiError, fetchConsoleBootstrap, readConsoleEventStream } from "../services/consoleApi";
import type { ConsoleAction, ConsoleBootstrapResponse, ConsoleState, RealtimeSnapshot } from "../state/consoleReducer";
import { validateConsoleBootstrapResponse, warnConsoleBootstrapIssues } from "../state/consoleValidation";

export type RealtimeSyncStatus = "idle" | "bootstrapping" | "sse" | "polling" | "error";

type UseConsoleRealtimeSyncOptions = {
  enabled?: boolean;
  pollingIntervalMs?: number;
  bootstrapUrl?: string;
  messagesStreamUrl?: string;
};

type UnifiedMessageEvent = {
  event_type: string;
  event_id?: string;
  timestamp?: string;
  trace_id?: string | null;
  tenant_id?: string | null;
  org_id?: string | null;
  room_id?: string | null;
  conversation_id?: string | null;
  agent_id?: string | null;
  user_id?: string | null;
  channel_type?: string;
  payload?: Record<string, unknown>;
};

type ConsoleRealtimeSyncHandle = {
  syncStatus: RealtimeSyncStatus;
  lastSyncedAt: string | null;
  syncError: string | null;
  manualRefresh: () => Promise<void>;
  refreshMessagesOnly: () => Promise<void>;
  reconnect: () => void;
  stopPolling: () => void;
  startPolling: () => void;
};

const RECONNECT_BASE_DELAY_MS = 1000;
const RECONNECT_MAX_DELAY_MS = 30000;
const RECONNECT_JITTER_RATIO = 0.25;

function jitteredReconnectDelay(baseDelay: number): number {
  return Math.min(
    RECONNECT_MAX_DELAY_MS,
    Math.round(
      baseDelay * (1 - RECONNECT_JITTER_RATIO + Math.random() * RECONNECT_JITTER_RATIO * 2),
    ),
  );
}

function asRecord(value: unknown): Record<string, unknown> | null {
  return value !== null && typeof value === "object" && !Array.isArray(value)
    ? value as Record<string, unknown>
    : null;
}

function asNonEmptyString(value: unknown): string | null {
  return typeof value === "string" && value.trim() ? value : null;
}

function normalizeRealtimeMessage(event: UnifiedMessageEvent): RealtimeMessage | null {
  const payload = asRecord(event.payload);
  const message = asRecord(payload?.message) ?? payload;
  if (!message) return null;
  const messageId = asNonEmptyString(message.message_id);
  const content = asNonEmptyString(message.content);
  const createdAt = asNonEmptyString(message.created_at);
  const senderId = asNonEmptyString(message.sender_id);
  if (!messageId || !content || !createdAt || !senderId) return null;
  const metadata = asRecord(message.metadata);

  return {
    message_id: messageId,
    room_id: asNonEmptyString(message.room_id) ?? event.room_id ?? null,
    conversation_id: asNonEmptyString(message.conversation_id)
      ?? asNonEmptyString(metadata?.conversation_id)
      ?? event.conversation_id
      ?? null,
    sender_id: senderId,
    sender_type: asNonEmptyString(message.sender_type) ?? undefined,
    sender_name: asNonEmptyString(message.sender_name) ?? senderId,
    content,
    message_type: asNonEmptyString(message.message_type)
      ?? asNonEmptyString(metadata?.message_type)
      ?? "text",
    created_at: createdAt,
  };
}

function normalizeMeetingRoom(event: UnifiedMessageEvent): MeetingRoomSummary | null {
  const payload = asRecord(event.payload);
  const room = asRecord(payload?.room) ?? payload;
  if (!room) return null;
  const roomId = asNonEmptyString(room.room_id) ?? event.room_id ?? null;
  const topic = asNonEmptyString(room.topic) ?? asNonEmptyString(room.name);
  if (!roomId || !topic) return null;
  const rawMembers = Array.isArray(room.member_agent_ids)
    ? room.member_agent_ids
    : Array.isArray(room.members)
      ? room.members
      : [];
  const members = rawMembers.filter((member): member is string => typeof member === "string" && Boolean(member.trim()));
  const memberCount = typeof room.member_count === "number" && Number.isFinite(room.member_count)
    ? room.member_count
    : members.length;

  return {
    room_id: roomId,
    name: asNonEmptyString(room.name) ?? topic,
    topic,
    status: asNonEmptyString(room.status) ?? "active",
    department_id: asNonEmptyString(room.department_id) ?? undefined,
    member_count: memberCount,
    member_agent_ids: members,
  };
}

function mergeRealtimeMessage(realtime: RealtimeSnapshot, message: RealtimeMessage): RealtimeSnapshot {
  const exists = realtime.messages.some((item) => item.message_id === message.message_id);
  const messages = exists
    ? realtime.messages.map((item) => (item.message_id === message.message_id ? message : item))
    : [...realtime.messages, message];

  return {
    ...realtime,
    messages,
    last_message_at: message.created_at,
  };
}

function mergeRoomUpdate(rooms: MeetingRoomSummary[], room: MeetingRoomSummary): MeetingRoomSummary[] {
  const exists = rooms.some((item) => item.room_id === room.room_id);
  return exists ? rooms.map((item) => (item.room_id === room.room_id ? room : item)) : [...rooms, room];
}

function mergeConversationUpdate(realtime: RealtimeSnapshot, conversation: ConversationSummary): RealtimeSnapshot {
  const exists = realtime.conversations.some((item) => item.conversation_id === conversation.conversation_id);
  const conversations = exists
    ? realtime.conversations.map((item) => (item.conversation_id === conversation.conversation_id ? conversation : item))
    : [...realtime.conversations, conversation];

  return { ...realtime, conversations };
}

function mergePresenceUpdate(realtime: RealtimeSnapshot, presence: PresenceMap): RealtimeSnapshot {
  const nextPresence = { ...realtime.presence, ...presence };
  return {
    ...realtime,
    presence: nextPresence,
    online_agents: Object.entries(nextPresence)
      .filter(([, value]) => value.online)
      .map(([agentId]) => agentId),
  };
}

export function useConsoleRealtimeSync(
  state: ConsoleState,
  dispatch: React.Dispatch<ConsoleAction>,
  options: UseConsoleRealtimeSyncOptions = {},
): ConsoleRealtimeSyncHandle {
  const {
    enabled = true,
    pollingIntervalMs = 10000,
    bootstrapUrl = "/api/v1/workbench",
    messagesStreamUrl = "/api/v1/messages/stream",
  } = options;

  const [syncStatus, setSyncStatus] = useState<RealtimeSyncStatus>("idle");
  const [lastSyncedAt, setLastSyncedAt] = useState<string | null>(null);
  const [syncError, setSyncError] = useState<string | null>(null);

  const streamAbortRef = useRef<AbortController | null>(null);
  const pollingTimerRef = useRef<ReturnType<typeof setInterval> | null>(null);
  const aliveRef = useRef(true);
  const lastEventIdRef = useRef<string | null>(null);
  const reconnectDelayRef = useRef<number>(RECONNECT_BASE_DELAY_MS);
  const reconnectTimerRef = useRef<ReturnType<typeof setTimeout> | null>(null);
  const didInitialBootstrapRef = useRef(false);
  const reconnectAttemptRef = useRef(0);
  const stateRef = useRef(state);

  useEffect(() => {
    stateRef.current = state;
  }, [state]);

  const stopPolling = useCallback(() => {
    if (pollingTimerRef.current) {
      clearInterval(pollingTimerRef.current);
      pollingTimerRef.current = null;
    }
  }, []);

  const clearReconnectTimer = useCallback(() => {
    if (reconnectTimerRef.current) {
      clearTimeout(reconnectTimerRef.current);
      reconnectTimerRef.current = null;
    }
  }, []);

  const handleRealtimeEvent = useCallback(
    (event: UnifiedMessageEvent): boolean => {
      const currentState = stateRef.current;
      switch (event.event_type) {
        case "message.created":
        case "message.updated": {
          const message = normalizeRealtimeMessage(event);
          if (!message) return false;
          const realtime = mergeRealtimeMessage(currentState.realtime, message);
          stateRef.current = { ...currentState, realtime };
          dispatch({ type: "realtime/update", payload: realtime });
          return true;
        }
        case "room.created":
        case "room.member_added":
        case "room.updated":
        case "room.closed": {
          const room = normalizeMeetingRoom(event);
          if (!room) return false;
          const rooms = mergeRoomUpdate(currentState.meetingRooms, room);
          stateRef.current = { ...currentState, meetingRooms: rooms };
          dispatch({ type: "rooms/update", payload: rooms });
          return true;
        }
        case "conversation.updated": {
          const conversation = asRecord(event.payload);
          if (!asNonEmptyString(conversation?.conversation_id)) return false;
          dispatch({
            type: "realtime/update",
            payload: mergeConversationUpdate(
              currentState.realtime,
              conversation as unknown as ConversationSummary,
            ),
          });
          return true;
        }
        case "presence.updated": {
          const presence = asRecord(event.payload);
          if (!presence || Object.keys(presence).length === 0) return false;
          dispatch({
            type: "realtime/update",
            payload: mergePresenceUpdate(
              currentState.realtime,
              presence as unknown as PresenceMap,
            ),
          });
          return true;
        }
        case "workflow.updated":
        case "audit.created": {
          const payload = asRecord(event.payload);
          if (!payload) return false;
          if (payload.realtime) dispatch({ type: "realtime/update", payload: payload.realtime as RealtimeSnapshot });
          if (payload.dispatch) dispatch({ type: "dispatch/update", payload: payload.dispatch as DispatchResult });
          if (payload.rooms) dispatch({ type: "rooms/update", payload: payload.rooms as MeetingRoomSummary[] });
          return true;
        }
        case "system.notification": {
          const payload = asRecord(event.payload);
          if (!payload) return false;
          let applied = false;
          if (payload.realtime) dispatch({ type: "realtime/update", payload: payload.realtime as RealtimeSnapshot });
          if (payload.dispatch) dispatch({ type: "dispatch/update", payload: payload.dispatch as DispatchResult });
          if (payload.rooms) dispatch({ type: "rooms/update", payload: payload.rooms as MeetingRoomSummary[] });
          if (payload.realtime || payload.dispatch || payload.rooms) applied = true;
          return applied;
        }
        default:
          return false;
      }
    },
    [dispatch],
  );

  const refreshMessagesOnly = useCallback(async () => {
    try {
      const data = await fetchConsoleBootstrap<ConsoleBootstrapResponse>({ url: bootstrapUrl });
      if (!aliveRef.current) return;

      if (data.envelope) {
        const validation = validateConsoleBootstrapResponse(data);
        warnConsoleBootstrapIssues(validation);
      }
      dispatch({ type: "bootstrap/success", payload: data });
      setLastSyncedAt(new Date().toISOString());
    } catch (error) {
      if (error instanceof ConsoleApiError && error.status === 401) {
        setSyncError(error.message);
        setSyncStatus("error");
      }
    }
  }, [bootstrapUrl, dispatch]);

  const startPolling = useCallback(() => {
    if (pollingTimerRef.current) return;
    setSyncStatus((current) => (current === "bootstrapping" ? current : "polling"));
    pollingTimerRef.current = setInterval(() => {
      if (!aliveRef.current) return;
      void refreshMessagesOnly();
    }, pollingIntervalMs);
  }, [pollingIntervalMs, refreshMessagesOnly]);

  const getStreamUrl = useCallback(() => {
    const url = new URL(messagesStreamUrl, window.location.origin);
    const currentState = stateRef.current;
    if (currentState.console.org_id) url.searchParams.set("org_id", currentState.console.org_id);
    if (currentState.activeRoomId) url.searchParams.set("room_id", currentState.activeRoomId);
    if (currentState.activeConversationId) url.searchParams.set("conversation_id", currentState.activeConversationId);
    url.searchParams.set("include_system", "true");
    url.searchParams.set("include_audit", "true");
    url.searchParams.set("include_workflow", "true");
    return `${url.pathname}${url.search}`;
  }, [messagesStreamUrl]);

  const connectSSE = useCallback(() => {
    clearReconnectTimer();
    streamAbortRef.current?.abort();
    const controller = new AbortController();
    streamAbortRef.current = controller;

    void readConsoleEventStream({
      url: getStreamUrl(),
      lastEventId: lastEventIdRef.current,
      signal: controller.signal,
      onOpen: () => {
        if (!aliveRef.current) return;
        setSyncStatus("sse");
        setSyncError(null);
        stopPolling();
      },
      onEvent: (streamEvent) => {
        if (!aliveRef.current) return;
        try {
          const payload = JSON.parse(streamEvent.data) as UnifiedMessageEvent;
          if (streamEvent.id) lastEventIdRef.current = streamEvent.id;
          if (handleRealtimeEvent(payload)) {
            reconnectAttemptRef.current = 0;
            reconnectDelayRef.current = RECONNECT_BASE_DELAY_MS;
          }
          setLastSyncedAt(new Date().toISOString());
          setSyncError(null);
        } catch {
          setSyncError("Console received an invalid event.");
        }
      },
    }).then((result) => {
      if (!aliveRef.current || controller.signal.aborted) return;
      streamAbortRef.current = null;
      if (result.lastEventId) lastEventIdRef.current = result.lastEventId;
      if (result.terminal) {
        setSyncStatus("idle");
        stopPolling();
        clearReconnectTimer();
        return;
      }
      reconnectAttemptRef.current += 1;
      setSyncStatus("polling");
      startPolling();
      const reconnectDelay = jitteredReconnectDelay(reconnectDelayRef.current);
      reconnectTimerRef.current = setTimeout(connectSSE, reconnectDelay);
      reconnectDelayRef.current = Math.min(reconnectDelayRef.current * 2, RECONNECT_MAX_DELAY_MS);
    }).catch((error: unknown) => {
      if (!aliveRef.current || controller.signal.aborted) return;
      streamAbortRef.current = null;
      if (error instanceof ConsoleApiError && error.status === 401) {
        setSyncError(error.message);
        setSyncStatus("error");
        stopPolling();
        return;
      }
      reconnectAttemptRef.current += 1;
      setSyncStatus("polling");
      setSyncError("Console event stream disconnected.");
      startPolling();
      const reconnectDelay = jitteredReconnectDelay(reconnectDelayRef.current);
      reconnectTimerRef.current = setTimeout(connectSSE, reconnectDelay);
      reconnectDelayRef.current = Math.min(reconnectDelayRef.current * 2, RECONNECT_MAX_DELAY_MS);
    });
  }, [clearReconnectTimer, getStreamUrl, handleRealtimeEvent, startPolling, stopPolling]);

  const refreshBootstrap = useCallback(async () => {
    dispatch({ type: "bootstrap/start" });
    setSyncStatus("bootstrapping");
    setSyncError(null);

    try {
      const data = await fetchConsoleBootstrap<ConsoleBootstrapResponse>({ url: bootstrapUrl });
      if (!aliveRef.current) return;

      dispatch({ type: "bootstrap/success", payload: data });
      setLastSyncedAt(new Date().toISOString());
      setSyncStatus("sse");
      return true;
    } catch (error) {
      const message = error instanceof Error ? error.message : "Unknown bootstrap error";
      setSyncError(message);
      setSyncStatus("error");
      dispatch({ type: "bootstrap/error", error: message });
      if (error instanceof ConsoleApiError && error.status === 401) {
        stopPolling();
        return false;
      }
      startPolling();
      return false;
    }
  }, [bootstrapUrl, dispatch, startPolling, stopPolling]);

  useEffect(() => {
    if (!enabled) return;
    aliveRef.current = true;

    if (!didInitialBootstrapRef.current) {
      didInitialBootstrapRef.current = true;
      void refreshBootstrap().then((success) => {
        if (aliveRef.current && success) connectSSE();
      });
    } else {
      connectSSE();
    }

    const onVisibilityChange = () => {
      if (document.visibilityState === "visible") {
        void refreshMessagesOnly();
      }
    };
    document.addEventListener("visibilitychange", onVisibilityChange);

    return () => {
      aliveRef.current = false;
      document.removeEventListener("visibilitychange", onVisibilityChange);
      streamAbortRef.current?.abort();
      streamAbortRef.current = null;
      stopPolling();
      clearReconnectTimer();
    };
  }, [clearReconnectTimer, connectSSE, enabled, refreshBootstrap, refreshMessagesOnly, stopPolling]);

  const manualRefresh = useCallback(async () => {
    lastEventIdRef.current = null;
    reconnectDelayRef.current = RECONNECT_BASE_DELAY_MS;
    reconnectAttemptRef.current = 0;
    if (await refreshBootstrap()) connectSSE();
  }, [connectSSE, refreshBootstrap]);

  const reconnect = useCallback(() => {
    lastEventIdRef.current = lastEventIdRef.current ?? null;
    reconnectDelayRef.current = RECONNECT_BASE_DELAY_MS;
    reconnectAttemptRef.current = 0;
    connectSSE();
  }, [connectSSE]);

  return useMemo(
    () => ({
      syncStatus,
      lastSyncedAt,
      syncError,
      manualRefresh,
      refreshMessagesOnly,
      reconnect,
      stopPolling,
      startPolling,
    }),
    [lastSyncedAt, manualRefresh, refreshMessagesOnly, reconnect, startPolling, stopPolling, syncError, syncStatus],
  );
}
