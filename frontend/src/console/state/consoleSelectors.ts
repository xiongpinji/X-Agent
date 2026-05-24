import type { ConsoleState } from "./consoleReducer";

export function selectEnvelopePrimary(state: ConsoleState) {
  return state.envelope?.primary ?? {};
}

export function selectEnvelopeLinkedSummaries(state: ConsoleState) {
  return state.envelope?.linked_summaries ?? null;
}

export function selectSelectedNode(state: ConsoleState) {
  return state.organizationGraph?.nodes?.find((node) => node.node_id === state.selectedNodeId) ?? null;
}

export function selectSelectedAgent(state: ConsoleState) {
  return state.organizationGraph?.agent_instances?.find((agent) => agent.agent_id === state.console.agent_id || agent.agent_id === state.selectedNodeId) ?? null;
}

export function selectSelectedRoleTemplate(state: ConsoleState) {
  return state.roleCatalog.find((role) => role.role_id === state.selectedRoleTemplateId) ?? null;
}

export function selectSelectedWorkflow(state: ConsoleState) {
  return state.selectedWorkflowId;
}

export function selectSelectedAuditMessage(state: ConsoleState) {
  return state.selectedAuditMessageId;
}

export function selectActiveRoom(state: ConsoleState) {
  return state.meetingRooms.find((room) => room.room_id === state.activeRoomId) ?? null;
}

export function selectActiveConversation(state: ConsoleState) {
  return state.conversations.find((conversation) => conversation.conversation_id === state.activeConversationId) ?? null;
}

export function selectActiveRoomMessages(state: ConsoleState) {
  const room = selectActiveRoom(state);
  return room?.messages ?? [];
}

export function selectActiveConversationMessages(state: ConsoleState) {
  const conversation = selectActiveConversation(state);
  return conversation?.messages ?? [];
}

export function selectOverviewData(state: ConsoleState) {
  const primary = selectEnvelopePrimary(state);
  return {
    envelope: state.envelope,
    dispatch: (primary.dispatch as DispatchResult | undefined) ?? state.dispatch,
    organizationGraph: (primary.organization_graph as OrganizationGraphView | undefined) ?? state.organizationGraph,
    meetingRooms: ((primary.meeting_rooms as { rooms?: MeetingRoomSummary[] } | undefined)?.rooms) ?? state.meetingRooms,
    realtime: (primary.realtime as RealtimeSnapshot | undefined) ?? state.realtime,
    memory: (primary.memory as MemorySnapshot | undefined) ?? state.memory,
    avatars: (primary.avatars as Record<string, string> | undefined) ?? state.avatars,
  };
}

export function selectOverviewPageData(state: ConsoleState) {
  const overview = selectOverviewData(state);
  return {
    dispatch: overview.dispatch,
    organizationGraph: overview.organizationGraph,
    meetingRooms: overview.meetingRooms,
    realtime: overview.realtime,
    memory: overview.memory,
    avatars: overview.avatars,
    recentConversations: overview.realtime.conversations.slice(0, 4),
    recentMessages: overview.realtime.messages.slice(0, 6),
    onlineAgents: overview.realtime.online_agents.length,
    activeRooms: overview.meetingRooms.length,
    unreadCount: overview.realtime.unread_count,
    confidence: overview.dispatch ? Math.round(overview.dispatch.suggestion.confidence * 100) : null,
  };
}

export function selectContextData(state: ConsoleState) {
  return {
    currentUser: state.console.user_id,
    activeRoomName: selectActiveRoom(state)?.name ?? "-",
    activeConversationTitle: selectActiveConversation(state)?.title ?? "-",
    selectedNodeName: selectSelectedNode(state)?.name ?? "-",
    selectedAgentName: selectSelectedAgent(state)?.name ?? "-",
    selectedRoleTemplateName: selectSelectedRoleTemplate(state)?.role_name ?? "-",
    selectedWorkflowId: selectSelectedWorkflow(state) ?? "-",
    selectedAuditMessageId: selectSelectedAuditMessage(state) ?? "-",
  };
}

export function selectIdentityData(state: ConsoleState) {
  return {
    agentId: state.console.agent_id,
    userId: state.console.user_id,
    tenantId: state.console.tenant_id,
    orgId: state.console.org_id,
    mode: state.console.mode,
  };
}

export function selectMeetingRoomData(state: ConsoleState) {
  const primary = selectEnvelopePrimary(state);
  return {
    envelope: state.envelope,
    rooms: ((primary.meeting_rooms as { rooms?: MeetingRoomSummary[] } | undefined)?.rooms) ?? state.meetingRooms,
    activeRoomId: state.activeRoomId,
    messages: selectActiveRoomMessages(state),
    avatars: (primary.avatars as Record<string, string> | undefined) ?? state.avatars,
    currentSenderId: state.console.agent_id ?? state.console.user_id,
  };
}

export function selectChatData(state: ConsoleState) {
  const primary = selectEnvelopePrimary(state);
  return {
    envelope: state.envelope,
    conversations: (primary.conversations as ConversationSummary[] | undefined) ?? state.conversations,
    activeConversationId: state.activeConversationId,
    messages: selectActiveConversationMessages(state),
    avatars: (primary.avatars as Record<string, string> | undefined) ?? state.avatars,
    presence: (primary.realtime as RealtimeSnapshot | undefined)?.presence ?? state.realtime.presence,
    currentSenderId: state.console.agent_id ?? state.console.user_id,
  };
}

export function selectRoleCatalogData(state: ConsoleState) {
  const primary = selectEnvelopePrimary(state);
  return {
    envelope: state.envelope,
    roleCatalog: (primary.role_catalog as RoleCatalogItem[] | undefined) ?? state.roleCatalog,
    selectedRoleTemplateId: state.selectedRoleTemplateId,
    avatars: (primary.avatars as Record<string, string> | undefined) ?? state.avatars,
  };
}

export function selectWorkflowData(state: ConsoleState) {
  const linked = selectEnvelopeLinkedSummaries(state);
  const primary = selectEnvelopePrimary(state);
  const workflowSummary = linked?.workflow ?? null;
  return {
    envelope: state.envelope,
    selectedWorkflowId: state.selectedWorkflowId,
    selectedRoleTemplateId: state.selectedRoleTemplateId,
    roleCatalog: (primary.role_catalog as RoleCatalogItem[] | undefined) ?? state.roleCatalog,
    workflowSummary,
    traceSummary: linked?.trace ?? null,
    activeWorkflowId: workflowSummary?.data?.workflow_id ?? workflowSummary?.summary?.workflow_id ?? state.selectedWorkflowId ?? null,
    primary,
  };
}

export function selectTraceData(state: ConsoleState) {
  const linked = selectEnvelopeLinkedSummaries(state);
  return {
    envelope: state.envelope,
    traceSummary: linked?.trace ?? null,
    primary: selectEnvelopePrimary(state),
  };
}

export function selectAuditData(state: ConsoleState) {
  const linked = selectEnvelopeLinkedSummaries(state);
  const primary = selectEnvelopePrimary(state);
  return {
    envelope: state.envelope,
    selectedAuditMessageId: state.selectedAuditMessageId,
    dispatch: (primary.dispatch as DispatchResult | undefined) ?? state.dispatch,
    realtime: (primary.realtime as RealtimeSnapshot | undefined) ?? state.realtime,
    memory: (primary.memory as MemorySnapshot | undefined) ?? state.memory,
    auditSummary: linked?.audit ?? null,
    traceSummary: linked?.trace ?? null,
    primary,
  };
}

export function selectShellUiData(state: ConsoleState) {
  return {
    activePage: state.activePage,
    pageTitle:
      state.activePage === "overview"
        ? "概览"
        : state.activePage === "create_agent"
          ? "创建智能体"
          : state.activePage === "organization_graph"
            ? "组织图"
            : state.activePage === "meeting_room"
              ? "会议室"
              : state.activePage === "realtime_chat"
                ? "实时对话"
                : state.activePage === "role_catalog"
                  ? "角色目录"
                  : state.activePage === "workflow"
                    ? "工作流"
                    : state.activePage === "audit"
                      ? "审计回放"
                      : state.activePage,
    orgName: state.envelope?.primary?.organization_graph && typeof state.envelope.primary.organization_graph === "object"
      ? (state.envelope.primary.organization_graph as OrganizationGraphView).organization?.name ?? "统一控制台"
      : state.organizationGraph?.organization?.name ?? "统一控制台",
    mode: state.console.mode,
    unreadCount: state.realtime.unread_count,
    syncStatus: "unknown",
  };
}

export function selectCurrentContextSummary(state: ConsoleState) {
  return {
    userId: state.console.user_id,
    tenantId: state.console.tenant_id,
    orgId: state.console.org_id,
    agentId: state.console.agent_id,
    activePage: state.activePage,
    activeRoomId: state.activeRoomId,
    activeConversationId: state.activeConversationId,
    selectedNodeId: state.selectedNodeId,
    selectedWorkflowId: state.selectedWorkflowId,
    selectedAuditMessageId: state.selectedAuditMessageId,
    selectedRoleTemplateId: state.selectedRoleTemplateId,
  };
}
