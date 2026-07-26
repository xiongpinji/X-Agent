export type ConsolePage =
  | "overview"
  | "create_agent"
  | "organization_graph"
  | "meeting_room"
  | "realtime_chat"
  | "role_catalog"
  | "workflow"
  | "execution_overview"
  | "execution_detail"
  | "execution_recovery"
  | "execution_dispatch"
  | "tools_overview"
  | "tools_detail"
  | "tools_management"
  | "tools_history"
  | "memory_overview"
  | "memory_detail"
  | "memory_management"
  | "memory_history"
  | "org_overview"
  | "org_structure"
  | "org_roles"
  | "org_audit"
  | "market_overview"
  | "market_detail"
  | "market_management"
  | "market_history"
  | "search_overview"
  | "search_results"
  | "search_shortcuts"
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
    session_id?: string;
    user_id?: string;
  };
  envelope?: LinkedSummaryEnvelope | null;
  // 后端 /api/v1/workbench 实际返回扁平字段（dispatch、organization_graph、
  // meeting_rooms、realtime、memory、avatars、role_catalog 等），
  // hydrate 时以 envelope.primary 优先、顶层扁平字段兜底。
  [key: string]: unknown;
};

export type ConsoleState = {
  activePage: ConsolePage;
  console: {
    mode: ConsoleMode;
    tenant_id: string;
    org_id: string;
    agent_id: string;
    session_id: string;
    user_id: string;
  };
  bootstrap: ConsoleBootstrapResponse | null;
  organizationGraph: OrganizationGraphView | null;
  envelope: LinkedSummaryEnvelope | null;
  meetingRooms: MeetingRoomSummary[];
  realtime: RealtimeSnapshot;
  memory: MemorySnapshot;
  avatars: RoleAvatar[];
  memoryCenterOverview: MemoryCenterOverview | null;
  roleCatalog: RoleCatalog;
  conversations: ConversationSummary[];
  activeRoomId: string | null;
  activeConversationId: string | null;
  selectedNodeId: string | null;
  selectedWorkflowId: string | null;
  selectedAuditMessageId: string | null;
  selectedRoleTemplateId: string | null;
  dispatch: DispatchResult;
  executionControlOverview: ExecutionControlOverview | null;
  toolsCenterOverview: ToolsCenterOverview | null;
  organizationCenterOverview: OrganizationCenterOverview | null;
  marketplaceCenterOverview: MarketplaceCenterOverview | null;
  navigationCenterOverview: NavigationCenterOverview | null;
};

export type NavigationCenterOverview = {
  resource_type: string;
  resource_id: string;
  primary: {
    recent_pages: string[];
    favorite_pages: string[];
    search_enabled: boolean;
    risk_level: string;
  };
  linked_summaries: {
    recent: { summary: { title: string }; data: Record<string, unknown> };
    favorites: { summary: { title: string }; data: Record<string, unknown> };
    search: { summary: { title: string }; data: Record<string, unknown> };
    shortcuts: { summary: { title: string }; data: Record<string, unknown> };
  };
};

export type MarketplaceCenterOverview = {
  resource_type: string;
  resource_id: string;
  primary: {
    total_items: number;
    published_items: number;
    installed_items: number;
    pending_approvals: number;
    risk_level: string;
  };
  linked_summaries: {
    market: { summary: { title: string }; data: Record<string, unknown> };
    plugins: { summary: { title: string }; data: Record<string, unknown> };
    tools: { summary: { title: string }; data: Record<string, unknown> };
    history: { summary: { title: string }; data: Record<string, unknown> };
  };
};

export type OrganizationCenterOverview = {
  resource_type: string;
  resource_id: string;
  primary: {
    total_departments: number;
    total_roles: number;
    total_members: number;
    pending_reviews: number;
    risk_level: string;
  };
  linked_summaries: {
    organization: { summary: { title: string }; data: Record<string, unknown> };
    departments: { summary: { title: string }; data: Record<string, unknown> };
    roles: { summary: { title: string }; data: Record<string, unknown> };
    audits: { summary: { title: string }; data: Record<string, unknown> };
  };
};

export type MemoryCenterOverview = {
  resource_type: string;
  resource_id: string;
  primary: {
    total_memories: number;
    active_memories: number;
    archived_memories: number;
    referenced_memories: number;
    risk_level: string;
  };
  linked_summaries: {
    memories: { summary: { title: string }; data: Record<string, unknown> };
    experiences: { summary: { title: string }; data: Record<string, unknown> };
    references: { summary: { title: string }; data: Record<string, unknown> };
    history: { summary: { title: string }; data: Record<string, unknown> };
  };
};

export type ToolsCenterOverview = {
  resource_type: string;
  resource_id: string;
  primary: {
    total_tools: number;
    enabled_tools: number;
    disabled_tools: number;
    plugin_count: number;
    resource_count: number;
    risk_level: string;
  };
  linked_summaries: {
    tools: { summary: { title: string }; data: Record<string, unknown> };
    plugins: { summary: { title: string }; data: Record<string, unknown> };
    resources: { summary: { title: string }; data: Record<string, unknown> };
    history: { summary: { title: string }; data: Record<string, unknown> };
  };
};

export type ExecutionControlOverview = {
  resource_type: string;
  resource_id: string;
  primary: {
    active_runs: number;
    pending_runs: number;
    failed_runs: number;
    completed_runs: number;
    intervention_count: number;
    risk_level: string;
    dispatch: DispatchResult;
    execution_plan: Record<string, unknown>;
  };
  linked_summaries: {
    dispatch: { summary: { title: string }; data: Record<string, unknown> };
    execution: { summary: { title: string }; data: Record<string, unknown> };
    audit: { summary: { title: string }; data: Record<string, unknown> };
    messages: { summary: { title: string }; data: Record<string, unknown> };
  };
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
  | { type: "avatars/update"; payload: RoleAvatar[] }
  | { type: "roleCatalog/update"; payload: RoleCatalog }
  | { type: "conversations/update"; payload: ConversationSummary[] }
  | { type: "executionControl/overviewUpdate"; payload: ExecutionControlOverview }
  | { type: "toolsCenter/overviewUpdate"; payload: ToolsCenterOverview }
  | { type: "memoryCenter/overviewUpdate"; payload: MemoryCenterOverview }
  | { type: "organizationCenter/overviewUpdate"; payload: OrganizationCenterOverview }
  | { type: "marketplaceCenter/overviewUpdate"; payload: MarketplaceCenterOverview }
  | { type: "navigationCenter/overviewUpdate"; payload: NavigationCenterOverview };

export function createInitialConsoleState(): ConsoleState {
  return {
    activePage: "overview",
    console: {
      mode: "production",
      tenant_id: "default",
      org_id: "",
      agent_id: "",
      session_id: "",
      user_id: "anonymous",
    },
    bootstrap: null,
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
      session_summary: null,
      layer_totals: {},
      memory_refs: [],
    },
    avatars: [],
    roleCatalog: { templates: [], workflows: [], role_groups: {}, role_index: {}, avatar_map: {} },
    conversations: [],
    activeRoomId: null,
    activeConversationId: null,
    selectedNodeId: null,
    selectedWorkflowId: null,
    selectedAuditMessageId: null,
    selectedRoleTemplateId: null,
    dispatch: {
      suggestion: { confidence: 0, reason: { summary: "" }, next_actions: [] },
      status: "idle",
      actions: [],
      queue_size: 0,
      pending: [],
      last_result: null,
    },
    executionControlOverview: null,
    toolsCenterOverview: null,
    marketplaceCenterOverview: null,
    navigationCenterOverview: null,
    memoryCenterOverview: null,
    organizationCenterOverview: null,
  };
}

function hydrateStateFromEnvelope(state: ConsoleState, payload: ConsoleBootstrapResponse): ConsoleState {
  const envelope = payload.envelope ?? state.envelope;
  // 后端 /api/v1/workbench 返回扁平字段而非 envelope.primary，做兜底兼容
  const primary = (envelope?.primary ?? (payload as Record<string, unknown>)) as Record<string, unknown>;
  const consoleSummary = (primary.console ?? payload.console ?? state.console) as Partial<ConsoleState["console"]>;
  return {
    ...state,
    bootstrap: payload,
    console: {
      ...state.console,
      ...consoleSummary,
    },
    envelope,
    organizationGraph: (primary.organization_graph as OrganizationGraphView | undefined) ?? state.organizationGraph,
    meetingRooms: ((primary.meeting_rooms as { rooms?: MeetingRoomSummary[] } | undefined)?.rooms) ?? state.meetingRooms,
    realtime: (primary.realtime as RealtimeSnapshot | undefined) ?? state.realtime,
    memory: (primary.memory as MemorySnapshot | undefined) ?? state.memory,
    avatars: (primary.avatars as RoleAvatar[] | undefined) ?? state.avatars,
    roleCatalog: (primary.role_catalog as RoleCatalog | undefined) ?? state.roleCatalog,
    conversations: (primary.conversations as ConversationSummary[] | undefined) ?? state.conversations,
    dispatch: (() => {
      // 后端 DispatchResult 缺少前端跟踪字段（actions/pending/queue_size/last_result），做合并兜底
      const incoming = primary.dispatch as Partial<DispatchResult> | undefined;
      if (!incoming) return state.dispatch;
      return {
        ...state.dispatch,
        ...incoming,
        suggestion: { ...state.dispatch.suggestion, ...(incoming.suggestion ?? {}) },
        actions: incoming.actions ?? state.dispatch.actions,
        pending: incoming.pending ?? state.dispatch.pending,
        queue_size: incoming.queue_size ?? state.dispatch.queue_size,
        last_result: incoming.last_result ?? state.dispatch.last_result,
      };
    })(),
    executionControlOverview: state.executionControlOverview,
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
    case "executionControl/overviewUpdate":
      return { ...state, executionControlOverview: action.payload };
    case "toolsCenter/overviewUpdate":
      return { ...state, toolsCenterOverview: action.payload };
    case "organizationCenter/overviewUpdate":
      return { ...state, organizationCenterOverview: action.payload };
    case "memoryCenter/overviewUpdate":
      return { ...state, memoryCenterOverview: action.payload };
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
