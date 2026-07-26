import { useCallback, useEffect, useMemo, useRef, useState } from "react";
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

function getSseEventId(event: MessageEvent<string>): string | null {
  const lastEventId = event.lastEventId?.trim();
  return lastEventId || null;
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

  const eventSourceRef = useRef<EventSource | null>(null);
  const pollingTimerRef = useRef<ReturnType<typeof setInterval> | null>(null);
  const aliveRef = useRef(true);
  const lastEventIdRef = useRef<string | null>(null);
  const reconnectDelayRef = useRef<number>(1000);
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
    (event: UnifiedMessageEvent) => {
      const currentState = stateRef.current;
      switch (event.event_type) {
        case "message.created":
        case "message.updated": {
          const message = event.payload as RealtimeMessage;
          dispatch({ type: "realtime/update", payload: mergeRealtimeMessage(currentState.realtime, message) });
          break;
        }
        case "room.updated": {
          const room = event.payload as MeetingRoomSummary;
          dispatch({ type: "rooms/update", payload: mergeRoomUpdate(currentState.meetingRooms, room) });
          break;
        }
        case "conversation.updated": {
          const conversation = event.payload as ConversationSummary;
          dispatch({ type: "realtime/update", payload: mergeConversationUpdate(currentState.realtime, conversation) });
          break;
        }
        case "presence.updated": {
          const presence = event.payload as PresenceMap;
          dispatch({ type: "realtime/update", payload: mergePresenceUpdate(currentState.realtime, presence) });
          break;
        }
        case "workflow.updated":
        case "audit.created":
        case "system.notification": {
          const payload = event.payload ?? {};
          if (payload.realtime) dispatch({ type: "realtime/update", payload: payload.realtime as RealtimeSnapshot });
          if (payload.dispatch) dispatch({ type: "dispatch/update", payload: payload.dispatch as DispatchResult });
          if (payload.rooms) dispatch({ type: "rooms/update", payload: payload.rooms as MeetingRoomSummary[] });
          break;
        }
        default:
          break;
      }
    },
    [dispatch],
  );

  const refreshMessagesOnly = useCallback(async () => {
    try {
      const response = await fetch(bootstrapUrl, { method: "GET", headers: { "Content-Type": "application/json" } });
      if (!response.ok) return;

      const data = (await response.json()) as ConsoleBootstrapResponse;
      if (!aliveRef.current) return;

      const validation = validateConsoleBootstrapResponse(data);
      warnConsoleBootstrapIssues(validation);
      dispatch({ type: "bootstrap/success", payload: data });
      setLastSyncedAt(new Date().toISOString());
    } catch {
      // ignore transient errors
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
    if (state.console.tenant_id) url.searchParams.set("tenant_id", state.console.tenant_id);
    if (state.console.org_id) url.searchParams.set("org_id", state.console.org_id);
    if (state.activeRoomId) url.searchParams.set("room_id", state.activeRoomId);
    if (state.activeConversationId) url.searchParams.set("conversation_id", state.activeConversationId);
    if (state.console.agent_id) url.searchParams.set("agent_id", state.console.agent_id);
    if (state.console.user_id) url.searchParams.set("user_id", state.console.user_id);
    url.searchParams.set("include_system", "true");
    url.searchParams.set("include_audit", "true");
    url.searchParams.set("include_workflow", "true");
    if (lastEventIdRef.current) url.searchParams.set("last_event_id", lastEventIdRef.current);
    return url;
  }, [messagesStreamUrl, state.activeConversationId, state.activeRoomId, state.console.agent_id, state.console.org_id, state.console.tenant_id, state.console.user_id]);

  const connectSSE = useCallback(() => {
    try {
      clearReconnectTimer();
      eventSourceRef.current?.close();

      const eventSource = new EventSource(getStreamUrl().toString());
      eventSourceRef.current = eventSource;

      const handleSsePayload = (rawEvent: MessageEvent<string>) => {
        if (!aliveRef.current) return;
        try {
          const payload = JSON.parse(rawEvent.data) as UnifiedMessageEvent;
          const eventId = getSseEventId(rawEvent);
          if (eventId) lastEventIdRef.current = eventId;
          if (payload.event_id) lastEventIdRef.current = payload.event_id;
          handleRealtimeEvent(payload);
          setLastSyncedAt(new Date().toISOString());
          setSyncError(null);
        } catch (error) {
          console.warn("Invalid SSE payload", error);
        }
      };

      eventSource.onopen = () => {
        if (!aliveRef.current) return;
        reconnectAttemptRef.current = 0;
        reconnectDelayRef.current = 1000;
        setSyncStatus("sse");
        setSyncError(null);
        stopPolling();
      };

      eventSource.addEventListener("system.notification", handleSsePayload as EventListener);
      eventSource.onmessage = handleSsePayload;

      eventSource.onerror = () => {
        if (!aliveRef.current) return;
        eventSource.close();
        eventSourceRef.current = null;
        reconnectAttemptRef.current += 1;
        setSyncStatus("polling");
        startPolling();
        clearReconnectTimer();
        reconnectTimerRef.current = setTimeout(() => {
          if (!aliveRef.current) return;
          reconnectDelayRef.current = Math.min(reconnectDelayRef.current * 2, 30000);
          connectSSE();
        }, reconnectDelayRef.current);
      };
    } catch (error) {
      setSyncStatus("polling");
      setSyncError(error instanceof Error ? error.message : "Failed to start SSE");
      startPolling();
    }
  }, [clearReconnectTimer, getStreamUrl, handleRealtimeEvent, startPolling, stopPolling]);

  const refreshBootstrap = useCallback(async () => {
    dispatch({ type: "bootstrap/start" });
    setSyncStatus("bootstrapping");
    setSyncError(null);

    try {
      const response = await fetch(bootstrapUrl, { method: "GET", headers: { "Content-Type": "application/json" } });
      if (!response.ok) throw new Error(`Bootstrap failed: ${response.status}`);

      const data = (await response.json()) as ConsoleBootstrapResponse;
      if (!aliveRef.current) return;

      dispatch({ type: "bootstrap/success", payload: data });
      setLastSyncedAt(new Date().toISOString());
      setSyncStatus("sse");
    } catch (error) {
      const message = error instanceof Error ? error.message : "Unknown bootstrap error";
      setSyncError(message);
      setSyncStatus("error");
      dispatch({ type: "bootstrap/error", error: message });
      startPolling();
    }
  }, [bootstrapUrl, dispatch, startPolling]);

  useEffect(() => {
    if (!enabled) return;
    aliveRef.current = true;

    if (!didInitialBootstrapRef.current) {
      didInitialBootstrapRef.current = true;
      void refreshBootstrap().then(() => {
        if (aliveRef.current) connectSSE();
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
      eventSourceRef.current?.close();
      eventSourceRef.current = null;
      stopPolling();
      clearReconnectTimer();
    };
  }, [clearReconnectTimer, connectSSE, enabled, refreshBootstrap, refreshMessagesOnly, stopPolling]);

  const manualRefresh = useCallback(async () => {
    lastEventIdRef.current = null;
    reconnectDelayRef.current = 1000;
    reconnectAttemptRef.current = 0;
    await refreshBootstrap();
    connectSSE();
  }, [connectSSE, refreshBootstrap]);

  const reconnect = useCallback(() => {
    lastEventIdRef.current = lastEventIdRef.current ?? null;
    reconnectDelayRef.current = 1000;
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
