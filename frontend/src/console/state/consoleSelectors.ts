import type { ConsoleState, RealtimeSnapshot } from "./consoleReducer";

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
  return state.roleCatalog.templates.find((role) => role.role_id === state.selectedRoleTemplateId) ?? null;
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
    avatars: (primary.avatars as RoleAvatar[] | undefined) ?? state.avatars,
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
    avatars: (primary.avatars as RoleAvatar[] | undefined) ?? state.avatars,
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
    avatars: (primary.avatars as RoleAvatar[] | undefined) ?? state.avatars,
    presence: (primary.realtime as RealtimeSnapshot | undefined)?.presence ?? state.realtime.presence,
    currentSenderId: state.console.agent_id ?? state.console.user_id,
  };
}

export function selectRoleCatalogData(state: ConsoleState) {
  const primary = selectEnvelopePrimary(state);
  return {
    envelope: state.envelope,
    roleCatalog: (primary.role_catalog as RoleCatalog | undefined) ?? state.roleCatalog,
    selectedRoleTemplateId: state.selectedRoleTemplateId,
    avatars: (primary.avatars as RoleAvatar[] | undefined) ?? state.avatars,
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
    roleCatalog: (primary.role_catalog as RoleCatalog | undefined) ?? state.roleCatalog,
    workflowSummary,
    traceSummary: linked?.trace ?? null,
    activeWorkflowId: workflowSummary?.data?.workflow_id ?? workflowSummary?.summary?.workflow_id ?? state.selectedWorkflowId ?? null,
    primary,
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

export function selectExecutionControlOverviewData(state: ConsoleState) {
  const api = state.executionControlOverview;
  if (api) {
    return {
      resourceType: api.resource_type,
      resourceId: api.resource_id,
      activeRuns: api.primary.active_runs,
      pendingRuns: api.primary.pending_runs,
      failedRuns: api.primary.failed_runs,
      completedRuns: api.primary.completed_runs,
      interventionCount: api.primary.intervention_count,
      riskLevel: api.primary.risk_level,
      dispatch: api.primary.dispatch,
      executionPlan: api.primary.execution_plan,
      recommendations: [{ action: api.linked_summaries.dispatch.summary.title, reason: "来自后端运行控制总览接口", confidence: "95%" }],
      linkedDispatchSummary: api.linked_summaries.dispatch,
      linkedExecutionSummary: api.linked_summaries.execution,
      linkedAuditSummary: api.linked_summaries.audit,
      linkedMessagesSummary: api.linked_summaries.messages,
    };
  }

  const dispatch = state.dispatch;
  const activeRuns = dispatch.pending.length ? dispatch.pending.length : dispatch.actions.length;
  const failedRuns = dispatch.last_result ? 1 : 0;
  const completedRuns = dispatch.actions.filter((action) => action.status === "completed").length;
  const pendingRuns = dispatch.pending.length;

  return {
    resourceType: "execution_control_overview",
    resourceId: state.console.session_id || state.console.user_id,
    activeRuns,
    pendingRuns,
    failedRuns,
    completedRuns,
    interventionCount: failedRuns ? 1 : 0,
    riskLevel: failedRuns ? "中等" : "低",
    dispatch,
    executionPlan: dispatch.last_result ? { task_id: dispatch.last_result.task_id } : null,
    recommendations: failedRuns
      ? [
          { action: "优先重试失败任务", reason: "当前存在失败结果", confidence: "92%" },
          { action: "打开恢复页面", reason: "便于快速处理异常", confidence: "88%" },
        ]
      : [{ action: "继续监控活跃执行", reason: "当前没有明显失败", confidence: "90%" }],
    linkedDispatchSummary: { summary: { title: "dispatch" }, data: dispatch as unknown as Record<string, unknown> },
    linkedExecutionSummary: { summary: { title: "execution" }, data: (dispatch.last_result as unknown as Record<string, unknown>) ?? {} },
    linkedAuditSummary: { summary: { title: "audit" }, data: {} },
    linkedMessagesSummary: { summary: { title: "messages" }, data: {} },
  };
}

export function selectExecutionControlDetailData(state: ConsoleState) {
  return {
    runId: state.selectedWorkflowId ?? state.dispatch.last_result?.task_id ?? "run-001",
    summary: {
      name: "工具调用工作流",
      status: "运行中",
      triggerSource: "工作流调度",
      owner: state.console.agent_id || state.console.user_id,
    },
    steps: [
      { name: "接收任务", status: "done", duration: "2s", result: "已进入队列" },
      { name: "生成计划", status: "done", duration: "8s", result: "已完成规划" },
      { name: "调用工具", status: "running", duration: "18s", result: "等待工具返回" },
      { name: "汇总结果", status: "pending", duration: "-", result: "未开始" },
    ],
    toolCalls: [
      { tool: "dispatch", time: "10:12", status: "success", cost: "120ms" },
      { tool: "memory.read", time: "10:13", status: "success", cost: "32ms" },
      { tool: "tool.execute", time: "10:14", status: "running", cost: "pending" },
    ],
    linkedTitles: {
      messages: "关联消息",
      audit: "审计记录",
      memory: "记忆引用",
    },
  };
}

export function selectExecutionControlRecoveryData(state: ConsoleState) {
  return {
    runId: state.selectedAuditMessageId ?? state.dispatch.last_result?.task_id ?? "run-003",
    failure: {
      status: "可恢复",
      level: "中",
      currentStep: "工具执行步骤",
      canRetry: true,
    },
    reasons: [
      { title: "外部工具超时", detail: "工具调用等待超过阈值，当前最适合优先重试。", level: "中" },
      { title: "输入参数缺失", detail: "上游节点未提供完整参数，需要人工确认。", level: "高" },
    ],
    recoverySummary: {
      before: "失败",
      after: "待重试",
      suggestion: "先重试，再确认外部依赖。",
    },
    recommendation: "恢复建议：优先检查外部工具是否恢复。",
  };
}

export function selectExecutionControlDispatchData(state: ConsoleState) {
  return {
    runId: state.selectedWorkflowId ?? state.dispatch.last_result?.task_id ?? "execution-control",
    recommendation: {
      action: "优先重试工具调用",
      confidence: "92%",
      risk: "低",
      requiresConfirmation: false,
    },
    recommendations: [
      { action: "优先重试工具调用", reason: "当前失败集中在外部工具超时，重试收益最高。", confidence: "92%", risk: "低" },
      { action: "等待人工确认", reason: "当外部依赖不稳定时避免连续自动重试。", confidence: "76%", risk: "中" },
    ],
    reasoning: {
      trigger: "工具超时 / 任务卡住",
      relatedModules: "工作流、消息、审计、记忆",
      summary: "当前失败点集中在单一外部依赖。",
    },
    impact: {
      expectedResult: "恢复执行并继续当前任务",
      sideEffect: "重复执行消耗额外资源",
      scope: "当前任务及其相关工作流节点",
    },
  };
}

export function selectExecutionOverviewData(state: ConsoleState) {
  return selectExecutionControlOverviewData(state);
}

export function selectExecutionDetailData(state: ConsoleState) {
  return selectExecutionControlDetailData(state);
}

export function selectExecutionRecoveryData(state: ConsoleState) {
  return selectExecutionControlRecoveryData(state);
}

export function selectExecutionDispatchData(state: ConsoleState) {
  return selectExecutionControlDispatchData(state);
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
                    : state.activePage === "execution_overview"
                      ? "运行控制"
                      : state.activePage === "execution_detail"
                        ? "执行详情"
                        : state.activePage === "execution_recovery"
                          ? "失败恢复"
                          : state.activePage === "execution_dispatch"
                            ? "调度建议"
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
