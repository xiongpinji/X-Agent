export type ConsolePage =
  | "overview"
  | "create_agent"
  | "organization_graph"
  | "meeting_room"
  | "realtime_chat"
  | "role_catalog"
  | "workflow"
  | "audit";

export type ConsoleMode = "production" | "admin" | string;

export type ConsoleContextSummary = {
  userId: string;
  tenantId: string;
  orgId: string;
  agentId: string;
};

export type RealtimeSnapshot = {
  messages: RealtimeMessage[];
  conversations: ConversationSummary[];
  presence: PresenceMap;
  online_agents: string[];
  unread_count: number;
  last_message_at?: string | null;
};

export type ConsoleBootstrapResponse = {
  console?: {
    mode?: string;
    tenant_id?: string;
    org_id?: string;
    agent_id?: string;
    user_id?: string;
  };
  envelope?: LinkedSummaryEnvelope | null;
};

export type ConsoleState = {
  activePage: ConsolePage;
  console: {
    mode: ConsoleMode;
    tenant_id: string;
    org_id: string;
    agent_id: string;
    user_id: string;
  };
  organizationGraph: OrganizationGraphView | null;
  envelope: LinkedSummaryEnvelope | null;
  meetingRooms: MeetingRoomSummary[];
  realtime: RealtimeSnapshot;
  memory: MemorySnapshot;
  avatars: Record<string, string>;
  roleCatalog: RoleCatalogItem[];
  conversations: ConversationSummary[];
  activeRoomId: string | null;
  activeConversationId: string | null;
  selectedNodeId: string | null;
  selectedWorkflowId: string | null;
  selectedAuditMessageId: string | null;
  selectedRoleTemplateId: string | null;
  dispatch: DispatchResult;
};

export type ConsoleAction =
  | { type: "bootstrap/start" }
  | { type: "bootstrap/success"; payload: ConsoleBootstrapResponse }
  | { type: "bootstrap/error"; error: string }
  | { type: "page/set"; payload: ConsolePage }
  | { type: "room/setActive"; payload: string | null }
  | { type: "conversation/setActive"; payload: string | null }
  | { type: "node/setSelected"; payload: string | null }
  | { type: "workflow/setSelected"; payload: string | null }
  | { type: "audit/setSelectedMessage"; payload: string | null }
  | { type: "roleTemplate/setSelected"; payload: string | null }
  | { type: "agent/setSelected"; payload: string | null }
  | { type: "realtime/update"; payload: RealtimeSnapshot }
  | { type: "rooms/update"; payload: MeetingRoomSummary[] }
  | { type: "dispatch/update"; payload: DispatchResult }
  | { type: "graph/update"; payload: OrganizationGraphView }
  | { type: "memory/update"; payload: MemorySnapshot }
  | { type: "avatars/update"; payload: Record<string, string> }
  | { type: "roleCatalog/update"; payload: RoleCatalogItem[] }
  | { type: "conversations/update"; payload: ConversationSummary[] };

export function createInitialConsoleState(): ConsoleState {
  return {
    activePage: "overview",
    console: {
      mode: "production",
      tenant_id: "default",
      org_id: "",
      agent_id: "",
      user_id: "anonymous",
    },
    organizationGraph: null,
    envelope: null,
    meetingRooms: [],
    realtime: {
      messages: [],
      conversations: [],
      presence: {},
      online_agents: [],
      unread_count: 0,
      last_message_at: null,
    },
    memory: {
      items: [],
      summary: null,
    },
    avatars: {},
    roleCatalog: [],
    conversations: [],
    activeRoomId: null,
    activeConversationId: null,
    selectedNodeId: null,
    selectedWorkflowId: null,
    selectedAuditMessageId: null,
    selectedRoleTemplateId: null,
    dispatch: {
      actions: [],
      queue_size: 0,
      pending: [],
      last_result: null,
    },
  };
}

function hydrateStateFromEnvelope(state: ConsoleState, payload: ConsoleBootstrapResponse): ConsoleState {
  const envelope = payload.envelope ?? state.envelope;
  const primary = envelope?.primary ?? {};
  const consoleSummary = (primary.console ?? payload.console ?? state.console) as Partial<ConsoleState["console"]>;
  return {
    ...state,
    console: {
      ...state.console,
      ...consoleSummary,
    },
    envelope,
    organizationGraph: (primary.organization_graph as OrganizationGraphView | undefined) ?? state.organizationGraph,
    meetingRooms: ((primary.meeting_rooms as { rooms?: MeetingRoomSummary[] } | undefined)?.rooms) ?? state.meetingRooms,
    realtime: (primary.realtime as RealtimeSnapshot | undefined) ?? state.realtime,
    memory: (primary.memory as MemorySnapshot | undefined) ?? state.memory,
    avatars: (primary.avatars as Record<string, string> | undefined) ?? state.avatars,
    roleCatalog: (primary.role_catalog as RoleCatalogItem[] | undefined) ?? state.roleCatalog,
    conversations: (primary.conversations as ConversationSummary[] | undefined) ?? state.conversations,
    dispatch: (primary.dispatch as DispatchResult | undefined) ?? state.dispatch,
  };
}

export function consoleReducer(state: ConsoleState, action: ConsoleAction): ConsoleState {
  switch (action.type) {
    case "bootstrap/start":
      return state;
    case "bootstrap/error":
      return state;
    case "bootstrap/success":
      return hydrateStateFromEnvelope(state, action.payload);
    case "page/set":
      return { ...state, activePage: action.payload };
    case "room/setActive":
      return { ...state, activeRoomId: action.payload };
    case "conversation/setActive":
      return { ...state, activeConversationId: action.payload };
    case "node/setSelected":
      return { ...state, selectedNodeId: action.payload };
    case "workflow/setSelected":
      return { ...state, selectedWorkflowId: action.payload };
    case "audit/setSelectedMessage":
      return { ...state, selectedAuditMessageId: action.payload };
    case "roleTemplate/setSelected":
      return { ...state, selectedRoleTemplateId: action.payload };
    case "agent/setSelected":
      return {
        ...state,
        selectedNodeId: action.payload,
        console: {
          ...state.console,
          agent_id: action.payload ?? state.console.agent_id,
        },
      };
    case "realtime/update":
      return { ...state, realtime: action.payload };
    case "rooms/update":
      return { ...state, meetingRooms: action.payload };
    case "dispatch/update":
      return { ...state, dispatch: action.payload };
    case "graph/update":
      return { ...state, organizationGraph: action.payload };
    case "memory/update":
      return { ...state, memory: action.payload };
    case "avatars/update":
      return { ...state, avatars: action.payload };
    case "roleCatalog/update":
      return { ...state, roleCatalog: action.payload };
    case "conversations/update":
      return { ...state, conversations: action.payload };
    default:
      return state;
  }
}
