import React from "react";
import { ConsoleLayout } from "./components/layout/ConsoleLayout";
import { ConsoleSyncStatusBadge } from "./components/layout/ConsoleSyncStatusBadge";
import { useConsoleDispatch, useConsoleState } from "./state/consoleContext";
import {
  selectAuditData,
  selectChatData,
  selectContextData,
  selectIdentityData,
  selectMeetingRoomData,
  selectOverviewData,
  selectOverviewPageData,
  selectRoleCatalogData,
  selectShellUiData,
  selectTraceData,
  selectWorkflowData,
} from "./state/consoleSelectors";
import {
  selectExecutionControlDetailData,
  selectExecutionControlDispatchData,
  selectExecutionControlOverviewData,
  selectExecutionControlRecoveryData,
} from "./state/executionControlSelectors";
import { selectToolsCenterOverviewData } from "./state/toolsCenterSelectors";
import { selectMemoryCenterOverviewData } from "./state/memoryCenterSelectors";
import { selectOrganizationCenterOverviewData } from "./state/organizationCenterSelectors";
import { selectMarketplaceCenterOverviewData } from "./state/marketplaceCenterSelectors";
import { selectNavigationCenterOverviewData } from "./state/navigationCenterSelectors";
import { validateConsoleBootstrapResponse, validateConsoleSelectors, warnConsoleBootstrapIssues } from "./state/consoleValidation";
import { useConsoleRealtimeSync } from "./hooks/useConsoleRealtimeSync";
import { OverviewPage } from "./pages/overview/OverviewPage";
import { CreateAgentPage } from "./pages/agents/CreateAgentPage";
import { OrganizationGraphPage } from "./pages/graph/OrganizationGraphPage";
import { MeetingRoomsPage } from "./pages/meetings/MeetingRoomsPage";
import { RealtimeChatPage } from "./pages/chat/RealtimeChatPage";
import { RoleCatalogPage } from "./pages/roles/RoleCatalogPage";
import { WorkflowPage } from "./pages/workflow/WorkflowPage";
import { AuditReplayPage } from "./pages/audit/AuditReplayPage";
import { ExecutionOverviewPage } from "./pages/execution/ExecutionOverviewPage";
import { OrganizationCenterOverviewPage } from "./pages/organization/OrganizationCenterOverviewPage";
import { MarketplaceOverviewPage } from "./pages/marketplace/MarketplaceOverviewPage";
import { NavigationOverviewPage } from "./pages/navigation/NavigationOverviewPage";
import { OrganizationStructurePage } from "./pages/organization/OrganizationStructurePage";
import { OrganizationRolesPage } from "./pages/organization/OrganizationRolesPage";
import { OrganizationAuditPage } from "./pages/organization/OrganizationAuditPage";
import { ExecutionDetailPage } from "./pages/execution/ExecutionDetailPage";
import { ExecutionRecoveryPage } from "./pages/execution/ExecutionRecoveryPage";
import { ExecutionDispatchPage } from "./pages/execution/ExecutionDispatchPage";
import { ToolsOverviewPage } from "./pages/tools/ToolsOverviewPage";
import { ToolsDetailPage } from "./pages/tools/ToolsDetailPage";
import { ToolsManagementPage } from "./pages/tools/ToolsManagementPage";
import { ToolsHistoryPage } from "./pages/tools/ToolsHistoryPage";
import { MemoryOverviewPage } from "./pages/memory/MemoryOverviewPage";
import { MemoryDetailPage } from "./pages/memory/MemoryDetailPage";
import { MemoryManagementPage } from "./pages/memory/MemoryManagementPage";
import { MemoryHistoryPage } from "./pages/memory/MemoryHistoryPage";

export function ConsoleShell() {
  const state = useConsoleState();
  const dispatch = useConsoleDispatch();
  const sync = useConsoleRealtimeSync(state, dispatch, {
    bootstrapUrl: "/api/v1/workbench",
    messagesStreamUrl: "/api/v1/messages/stream",
    pollingIntervalMs: 10000,
  });

  const reconnectAttempts = React.useMemo(() => {
    if (sync.syncStatus === "polling" || sync.syncStatus === "error") return 1;
    return 0;
  }, [sync.syncStatus]);

  const bootstrapValidation = React.useMemo(
    () => validateConsoleBootstrapResponse(state.bootstrap),
    [state.bootstrap],
  );

  const overviewData = selectOverviewData(state);
  const overviewPageData = selectOverviewPageData(state);
  const workflowData = selectWorkflowData(state);
  const auditData = selectAuditData(state);
  const executionOverviewData = selectExecutionControlOverviewData(state);
  const executionDetailData = selectExecutionControlDetailData(state);
  const executionRecoveryData = selectExecutionControlRecoveryData(state);
  const executionDispatchData = selectExecutionControlDispatchData(state);
  const toolsCenterData = selectToolsCenterOverviewData(state);
  const memoryCenterData = selectMemoryCenterOverviewData(state);
  const organizationCenterData = selectOrganizationCenterOverviewData(state);
  const marketplaceCenterData = selectMarketplaceCenterOverviewData(state);
  const navigationCenterData = selectNavigationCenterOverviewData(state);
  const identityData = selectIdentityData(state);
  const meetingRoomData = selectMeetingRoomData(state);
  const chatData = selectChatData(state);
  const roleCatalogData = selectRoleCatalogData(state);
  const shellUiData = selectShellUiData(state);
  const contextData = selectContextData(state);

  const selectorValidation = React.useMemo(
    () => validateConsoleSelectors(overviewPageData, workflowData, auditData, contextData),
    [overviewPageData, workflowData, auditData, contextData],
  );

  React.useEffect(() => {
    warnConsoleBootstrapIssues(bootstrapValidation);
  }, [bootstrapValidation]);

  React.useEffect(() => {
    if (selectorValidation.ok) return;
    for (const issue of selectorValidation.issues) {
      console.warn(`[console-selectors] ${issue.path}: ${issue.message}`);
    }
  }, [selectorValidation]);

  React.useEffect(() => {
    let cancelled = false;

    type OverviewResponse<TPrimary, TLinks> = {
      resource_type: string;
      resource_id: string;
      primary: TPrimary;
      linked_summaries: TLinks;
    };

    const load = async () => {
      try {
        const [executionRes, toolsRes, memoryRes, orgRes, marketRes, navRes] = await Promise.all([
          fetch("/api/v1/execution-control/overview", { method: "GET", headers: { "Content-Type": "application/json" } }),
          fetch("/api/v1/tools-control/overview", { method: "GET", headers: { "Content-Type": "application/json" } }),
          fetch("/api/v1/memory-control/overview", { method: "GET", headers: { "Content-Type": "application/json" } }),
          fetch("/api/v1/organization-control/overview", { method: "GET", headers: { "Content-Type": "application/json" } }),
          fetch("/api/v1/marketplace-control/overview", { method: "GET", headers: { "Content-Type": "application/json" } }),
          fetch("/api/v1/navigation-control/overview", { method: "GET", headers: { "Content-Type": "application/json" } }),
        ]);

        if (cancelled) return;

        if (executionRes.ok) {
          const payload = (await executionRes.json()) as OverviewResponse<ExecutionControlOverview["primary"], ExecutionControlOverview["linked_summaries"]>;
          dispatch({ type: "executionControl/overviewUpdate", payload: payload as unknown as ExecutionControlOverview });
        }
        if (toolsRes.ok) {
          const payload = (await toolsRes.json()) as OverviewResponse<ToolsCenterOverview["primary"], ToolsCenterOverview["linked_summaries"]>;
          dispatch({ type: "toolsCenter/overviewUpdate", payload: payload as unknown as ToolsCenterOverview });
        }
        if (memoryRes.ok) {
          const payload = (await memoryRes.json()) as OverviewResponse<MemoryCenterOverview["primary"], MemoryCenterOverview["linked_summaries"]>;
          dispatch({ type: "memoryCenter/overviewUpdate", payload: payload as unknown as MemoryCenterOverview });
        }
        if (orgRes.ok) {
          const payload = (await orgRes.json()) as OverviewResponse<OrganizationCenterOverview["primary"], OrganizationCenterOverview["linked_summaries"]>;
          dispatch({ type: "organizationCenter/overviewUpdate", payload: payload as unknown as OrganizationCenterOverview });
        }
        if (marketRes.ok) {
          const payload = (await marketRes.json()) as OverviewResponse<MarketplaceCenterOverview["primary"], MarketplaceCenterOverview["linked_summaries"]>;
          dispatch({ type: "marketplaceCenter/overviewUpdate", payload: payload as unknown as MarketplaceCenterOverview });
        }
        if (navRes.ok) {
          const payload = (await navRes.json()) as OverviewResponse<NavigationCenterOverview["primary"], NavigationCenterOverview["linked_summaries"]>;
          dispatch({ type: "navigationCenter/overviewUpdate", payload: payload as unknown as NavigationCenterOverview });
        }
      } catch (error) {
        console.warn("Failed to load platform overview data", error);
      }
    };

    void load();
    return () => {
      cancelled = true;
    };
  }, [dispatch]);

  const openConversation = (conversationId: string) => {
    dispatch({ type: "conversation/setActive", payload: conversationId });
    dispatch({ type: "page/set", payload: "realtime_chat" });
  };

  const openAudit = (messageId?: string) => {
    if (messageId) {
      dispatch({ type: "node/setSelected", payload: messageId });
    }
    dispatch({ type: "page/set", payload: "audit" });
  };

  const openWorkflow = (roleTemplateId?: string) => {
    if (roleTemplateId) {
      dispatch({ type: "roleTemplate/setSelected", payload: roleTemplateId });
    }
    dispatch({ type: "page/set", payload: "workflow" });
  };

  const handleCreateAgent = async (payload: AgentCreatePayload) => {
    console.log("create agent", payload);
    dispatch({ type: "page/set", payload: "organization_graph" });
    if (payload.role_template_id) {
      dispatch({ type: "roleTemplate/setSelected", payload: payload.role_template_id });
    }
    await sync.refreshMessagesOnly();
  };

  const renderPage = () => {
    switch (state.activePage) {
      case "overview":
        return (
          <OverviewPage
            dispatch={executionOverviewData.dispatch}
            organizationGraph={overviewData.organizationGraph ?? emptyGraph()}
            meetingRooms={meetingRoomData.rooms}
            realtime={overviewData.realtime}
            memory={overviewData.memory}
            avatars={overviewData.avatars}
            onOpenAgent={(agentId) => {
              dispatch({ type: "agent/setSelected", payload: agentId });
              dispatch({ type: "page/set", payload: "organization_graph" });
            }}
            onOpenRoom={(roomId) => {
              dispatch({ type: "room/setActive", payload: roomId });
              dispatch({ type: "page/set", payload: "meeting_room" });
            }}
            onOpenConversation={openConversation}
            onOpenAudit={() => openAudit()}
            onOpenPendingItem={(itemKey) => {
              if (itemKey === "pending_execution") dispatch({ type: "page/set", payload: "execution_overview" });
              if (itemKey === "pending_audit") dispatch({ type: "page/set", payload: "audit" });
              if (itemKey === "pending_tools") dispatch({ type: "page/set", payload: "tools_overview" });
              if (itemKey === "pending_org") dispatch({ type: "page/set", payload: "org_overview" });
            }}
            onOpenAction={(actionKey) => {
              if (actionKey === "open_workflow") openWorkflow();
              if (actionKey === "open_audit") openAudit();
              if (actionKey === "open_rooms") dispatch({ type: "page/set", payload: "meeting_room" });
              if (actionKey === "open_chat") dispatch({ type: "page/set", payload: "realtime_chat" });
              if (actionKey === "open_tools") dispatch({ type: "page/set", payload: "tools_overview" });
              if (actionKey === "open_memory") dispatch({ type: "page/set", payload: "memory_overview" });
              if (actionKey === "open_org") dispatch({ type: "page/set", payload: "org_overview" });
              if (actionKey === "open_market") dispatch({ type: "page/set", payload: "market_overview" });
              if (actionKey === "open_search") dispatch({ type: "page/set", payload: "search_overview" });
              if (actionKey === "open_execution") dispatch({ type: "page/set", payload: "execution_overview" });
              if (actionKey === "open_agents") dispatch({ type: "page/set", payload: "organization_graph" });
            }}
            onOpenPendingItem={(itemKey) => {
              if (itemKey === "pending_execution") dispatch({ type: "page/set", payload: "execution_overview" });
              if (itemKey === "pending_audit") dispatch({ type: "page/set", payload: "audit" });
              if (itemKey === "pending_tools") dispatch({ type: "page/set", payload: "tools_overview" });
              if (itemKey === "pending_org") dispatch({ type: "page/set", payload: "org_overview" });
            }}
          />
        );
      case "create_agent":
        return (
          <CreateAgentPage
            roleCatalog={roleCatalogData.roleCatalog}
            organizationGraph={overviewData.organizationGraph ?? emptyGraph()}
            avatars={roleCatalogData.avatars}
            onCreateAgent={handleCreateAgent}
            onPreviewWorkflow={(roleTemplateId) => dispatch({ type: "roleTemplate/setSelected", payload: roleTemplateId })}
            onCancel={() => dispatch({ type: "page/set", payload: "organization_graph" })}
          />
        );
      case "organization_graph":
        return (
          <OrganizationGraphPage
            graph={overviewData.organizationGraph ?? emptyGraph()}
            avatars={overviewData.avatars}
            selectedNodeId={state.selectedNodeId}
            onSelectNode={(nodeId) => dispatch({ type: "node/setSelected", payload: nodeId })}
            onCreateAgentFromNode={() => dispatch({ type: "page/set", payload: "create_agent" })}
            onCreateRoomFromNode={(roomId) => {
              dispatch({ type: "room/setActive", payload: roomId });
              dispatch({ type: "page/set", payload: "meeting_room" });
            }}
          />
        );
      case "meeting_room":
        return (
          <MeetingRoomsPage
            rooms={meetingRoomData.rooms}
            activeRoomId={meetingRoomData.activeRoomId}
            messages={meetingRoomData.messages}
            avatars={meetingRoomData.avatars}
            currentSenderId={meetingRoomData.currentSenderId}
            onSelectRoom={(roomId) => dispatch({ type: "room/setActive", payload: roomId })}
            onRoomMessageSent={sync.refreshMessagesOnly}
            onInviteMemberSent={sync.refreshMessagesOnly}
          />
        );
      case "realtime_chat":
        return (
          <RealtimeChatPage
            conversations={chatData.conversations}
            activeConversationId={chatData.activeConversationId}
            messages={chatData.messages}
            avatars={chatData.avatars}
            presence={chatData.presence}
            currentSenderId={chatData.currentSenderId}
            onSelectConversation={(conversationId) => dispatch({ type: "conversation/setActive", payload: conversationId })}
            onMessageSent={sync.refreshMessagesOnly}
          />
        );
      case "role_catalog":
        return (
          <RoleCatalogPage
            roleCatalog={roleCatalogData.roleCatalog}
            avatars={roleCatalogData.avatars}
            selectedRoleTemplateId={roleCatalogData.selectedRoleTemplateId}
            onSelectRoleTemplate={(roleTemplateId) => dispatch({ type: "roleTemplate/setSelected", payload: roleTemplateId })}
          />
        );
      case "workflow":
        return (
          <WorkflowPage
            envelope={workflowData.envelope ?? null}
            workflowSummary={workflowData.workflowSummary}
            roleCatalog={workflowData.roleCatalog}
            selectedRoleTemplateId={workflowData.selectedRoleTemplateId}
            activeWorkflowId={workflowData.activeWorkflowId}
            onSelectRoleTemplate={(roleTemplateId) => dispatch({ type: "roleTemplate/setSelected", payload: roleTemplateId })}
            onSelectWorkflow={(workflowId) => dispatch({ type: "workflow/setSelected", payload: workflowId })}
          />
        );
      case "execution_overview":
        return (
          <ExecutionOverviewPage
            resourceType="execution_control_overview"
            resourceId={state.console.session_id || state.console.user_id}
            activeRuns={executionOverviewData.activeRuns}
            pendingRuns={executionOverviewData.pendingRuns}
            failedRuns={executionOverviewData.failedRuns}
            completedRuns={executionOverviewData.completedRuns}
            interventionCount={executionOverviewData.interventionCount}
            riskLevel={executionOverviewData.riskLevel}
            dispatch={executionOverviewData.dispatch}
            executionPlan={executionOverviewData.executionPlan}
            recommendations={executionOverviewData.recommendations}
            linkedDispatchSummary={{ summary: { title: "dispatch" }, data: executionOverviewData.dispatch as unknown as Record<string, unknown> }}
            linkedExecutionSummary={{ summary: { title: "execution" }, data: executionOverviewData.executionPlan }}
            linkedAuditSummary={{ summary: { title: auditData.auditSummary?.summary?.title ?? "audit" }, data: {} }}
            linkedMessagesSummary={{ summary: { title: traceData.traceSummary?.summary?.title ?? "messages" }, data: {} }}
            onOpenDetail={(runId) => {
              dispatch({ type: "workflow/setSelected", payload: runId });
              dispatch({ type: "page/set", payload: "execution_detail" });
            }}
            onOpenRecovery={(runId) => {
              dispatch({ type: "audit/setSelectedMessage", payload: runId });
              dispatch({ type: "page/set", payload: "execution_recovery" });
            }}
            onOpenDispatch={(runId) => {
              dispatch({ type: "workflow/setSelected", payload: runId });
              dispatch({ type: "page/set", payload: "execution_dispatch" });
            }}
          />
        );
      case "execution_detail":
        return (
          <ExecutionDetailPage
            runId={executionDetailData.runId}
            summary={executionDetailData.summary}
            steps={executionDetailData.steps}
            toolCalls={executionDetailData.toolCalls}
            linkedTitles={executionDetailData.linkedTitles}
            onBack={() => dispatch({ type: "page/set", payload: "execution_overview" })}
            onOpenRecovery={(runId) => dispatch({ type: "page/set", payload: "execution_recovery" })}
            onOpenAudit={(runId) => dispatch({ type: "audit/setSelectedMessage", payload: runId })}
            onOpenDispatch={(runId) => dispatch({ type: "page/set", payload: "execution_dispatch" })}
          />
        );
      case "execution_recovery":
        return (
          <ExecutionRecoveryPage
            runId={executionRecoveryData.runId}
            failure={executionRecoveryData.failure}
            reasons={executionRecoveryData.reasons}
            recoverySummary={executionRecoveryData.recoverySummary}
            recommendation={executionRecoveryData.recommendation}
            onBack={() => dispatch({ type: "page/set", payload: "execution_overview" })}
            onOpenDetail={(runId) => dispatch({ type: "page/set", payload: "execution_detail" })}
            onOpenAudit={(runId) => dispatch({ type: "audit/setSelectedMessage", payload: runId })}
          />
        );
      case "execution_dispatch":
        return (
          <ExecutionDispatchPage
            runId={executionDispatchData.runId}
            recommendation={executionDispatchData.recommendation}
            recommendations={executionDispatchData.recommendations}
            reasoning={executionDispatchData.reasoning}
            impact={executionDispatchData.impact}
            onBack={() => dispatch({ type: "page/set", payload: "execution_overview" })}
            onOpenDetail={(runId) => dispatch({ type: "page/set", payload: "execution_detail" })}
            onOpenRecovery={(runId) => dispatch({ type: "page/set", payload: "execution_recovery" })}
          />
        );
      case "tools_overview":
        return (
          <ToolsOverviewPage
            {...toolsCenterData}
            onOpenDetail={() => dispatch({ type: "page/set", payload: "tools_detail" })}
            onOpenPlugins={() => dispatch({ type: "page/set", payload: "tools_management" })}
            onOpenHistory={() => dispatch({ type: "page/set", payload: "tools_history" })}
          />
        );
      case "tools_detail":
        return <ToolsDetailPage toolId="tool-001" toolName="dispatch" status="enabled" version="1.0.0" owner={identityData.agentId || identityData.userId} riskLevel="low" description="工具详情与调用概览。" />;
      case "tools_management":
        return <ToolsManagementPage pendingChanges={2} enabledChanges={1} disabledChanges={1} reviewRequired={1} riskLevel="medium" />;
      case "tools_history":
        return <ToolsHistoryPage totalEvents={42} successEvents={35} failedEvents={7} lastEventStatus="success" riskLevel="low" />;
      case "market_overview":
        return (
          <MarketplaceOverviewPage
            {...marketplaceCenterData}
            onOpenDetail={() => dispatch({ type: "page/set", payload: "market_detail" })}
            onOpenManagement={() => dispatch({ type: "page/set", payload: "market_management" })}
            onOpenHistory={() => dispatch({ type: "page/set", payload: "market_history" })}
          />
        );
      case "search_overview":
        return (
          <NavigationOverviewPage
            {...navigationCenterData}
            onOpenPage={(pageKey) => {
              if (pageKey === "overview") dispatch({ type: "page/set", payload: "overview" });
              if (pageKey === "execution_overview") dispatch({ type: "page/set", payload: "execution_overview" });
              if (pageKey === "tools_overview") dispatch({ type: "page/set", payload: "tools_overview" });
              if (pageKey === "memory_overview") dispatch({ type: "page/set", payload: "memory_overview" });
              if (pageKey === "org_overview") dispatch({ type: "page/set", payload: "org_overview" });
              if (pageKey === "market_overview") dispatch({ type: "page/set", payload: "market_overview" });
              if (pageKey === "audit") dispatch({ type: "page/set", payload: "audit" });
            }}
            onOpenSearch={() => dispatch({ type: "page/set", payload: "search_results" })}
          />
        );
      case "search_results":
        return <NavigationSearchPage query="" resultCount={12} categories={["page", "tool", "memory", "organization", "market"]} riskLevel="low" />;
      case "search_shortcuts":
        return <NavigationShortcutsPage shortcutCount={6} favoriteCount={3} recentCount={3} riskLevel="low" />;
      case "memory_overview":
        return (
          <MemoryOverviewPage
            {...memoryCenterData}
            onOpenDetail={() => dispatch({ type: "page/set", payload: "memory_detail" })}
            onOpenManagement={() => dispatch({ type: "page/set", payload: "memory_management" })}
            onOpenHistory={() => dispatch({ type: "page/set", payload: "memory_history" })}
          />
        );
      case "memory_detail":
        return <MemoryDetailPage memoryId="memory-001" memoryTitle="execution_result" status="active" source="execution_result" owner={identityData.agentId || identityData.userId} riskLevel="low" summary="执行结果沉淀为记忆条目。" />;
      case "memory_management":
        return <MemoryManagementPage pendingChanges={3} activeChanges={2} archivedChanges={1} reviewRequired={1} riskLevel="medium" />;
      case "memory_history":
        return <MemoryHistoryPage totalEvents={210} successEvents={198} failedEvents={12} lastEventStatus="updated" riskLevel="low" />;
      case "org_overview":
        return (
          <OrganizationCenterOverviewPage
            {...organizationCenterData}
            onOpenStructure={() => dispatch({ type: "page/set", payload: "org_structure" })}
            onOpenRoles={() => dispatch({ type: "page/set", payload: "org_roles" })}
            onOpenAudit={() => dispatch({ type: "page/set", payload: "org_audit" })}
          />
        );
      case "org_structure":
        return <OrganizationStructurePage rootName="统一控制台" departmentCount={8} memberCount={86} roleCount={24} riskLevel="low" />;
      case "org_roles":
        return <OrganizationRolesPage totalRoles={24} activeRoles={21} pendingRoles={3} permissionSets={12} riskLevel="medium" />;
      case "org_audit":
        return <OrganizationAuditPage totalEvents={13} successEvents={10} failedEvents={3} lastEventStatus="pending" riskLevel="medium" />;
      case "audit":
        return (
          <AuditReplayPage
            envelope={auditData.envelope ?? null}
            traceSummary={traceData.traceSummary}
            auditSummary={auditData.auditSummary}
            dispatch={auditData.dispatch}
            realtime={auditData.realtime}
            memory={auditData.memory}
            selectedMessageId={auditData.selectedAuditMessageId}
            onSelectMessage={(messageId) => dispatch({ type: "audit/setSelectedMessage", payload: messageId })}
            onOpenAction={(actionKey) => {
              if (actionKey === "execution") dispatch({ type: "page/set", payload: "execution_overview" });
              if (actionKey === "tools") dispatch({ type: "page/set", payload: "tools_overview" });
              if (actionKey === "memory") dispatch({ type: "page/set", payload: "memory_overview" });
              if (actionKey === "organization") dispatch({ type: "page/set", payload: "org_overview" });
              if (actionKey === "marketplace") dispatch({ type: "page/set", payload: "market_overview" });
            }}
          />
        );
      default:
        return <div className="rounded-2xl border bg-white p-6 shadow-sm">{state.activePage}</div>;
    }
  };

  return (
    <ConsoleLayout
      sidebar={
        <div className="p-4">
          <div className="text-lg font-bold">统一控制台</div>
          <div className="mt-2 space-y-2 text-sm text-gray-600">
            <div>在线智能体：{overviewPageData.onlineAgents}</div>
            <div>活跃会议室：{overviewPageData.activeRooms}</div>
          </div>
          <div className="mt-4 grid grid-cols-2 gap-2 text-xs">
            <button className="rounded-lg border px-2 py-1 hover:bg-gray-50" onClick={() => dispatch({ type: "page/set", payload: "overview" })}>概览</button>
            <button className="rounded-lg border px-2 py-1 hover:bg-gray-50" onClick={() => dispatch({ type: "page/set", payload: "organization_graph" })}>组织图</button>
            <button className="rounded-lg border px-2 py-1 hover:bg-gray-50" onClick={() => dispatch({ type: "page/set", payload: "org_overview" })}>组织权限中心</button>
            <button className="rounded-lg border px-2 py-1 hover:bg-gray-50" onClick={() => dispatch({ type: "page/set", payload: "org_structure" })}>组织结构</button>
            <button className="rounded-lg border px-2 py-1 hover:bg-gray-50" onClick={() => dispatch({ type: "page/set", payload: "org_roles" })}>角色权限</button>
            <button className="rounded-lg border px-2 py-1 hover:bg-gray-50" onClick={() => dispatch({ type: "page/set", payload: "org_audit" })}>组织审核</button>
            <button className="rounded-lg border px-2 py-1 hover:bg-gray-50" onClick={() => dispatch({ type: "page/set", payload: "meeting_room" })}>会议室</button>
            <button className="rounded-lg border px-2 py-1 hover:bg-gray-50" onClick={() => dispatch({ type: "page/set", payload: "realtime_chat" })}>对话</button>
            <button className="rounded-lg border px-2 py-1 hover:bg-gray-50" onClick={() => dispatch({ type: "page/set", payload: "workflow" })}>工作流</button>
            <button className="rounded-lg border px-2 py-1 hover:bg-gray-50" onClick={() => dispatch({ type: "page/set", payload: "execution_overview" })}>运行控制</button>
            <button className="rounded-lg border px-2 py-1 hover:bg-gray-50" onClick={() => dispatch({ type: "page/set", payload: "tools_overview" })}>工具中心</button>
            <button className="rounded-lg border px-2 py-1 hover:bg-gray-50" onClick={() => dispatch({ type: "page/set", payload: "tools_detail" })}>工具详情</button>
            <button className="rounded-lg border px-2 py-1 hover:bg-gray-50" onClick={() => dispatch({ type: "page/set", payload: "tools_management" })}>工具管理</button>
            <button className="rounded-lg border px-2 py-1 hover:bg-gray-50" onClick={() => dispatch({ type: "page/set", payload: "tools_history" })}>调用历史</button>
            <button className="rounded-lg border px-2 py-1 hover:bg-gray-50" onClick={() => dispatch({ type: "page/set", payload: "market_overview" })}>能力市场</button>
            <button className="rounded-lg border px-2 py-1 hover:bg-gray-50" onClick={() => dispatch({ type: "page/set", payload: "search_overview" })}>全局导航</button>
            <button className="rounded-lg border px-2 py-1 hover:bg-gray-50" onClick={() => dispatch({ type: "page/set", payload: "memory_overview" })}>记忆中心</button>
            <button className="rounded-lg border px-2 py-1 hover:bg-gray-50" onClick={() => dispatch({ type: "page/set", payload: "memory_detail" })}>记忆详情</button>
            <button className="rounded-lg border px-2 py-1 hover:bg-gray-50" onClick={() => dispatch({ type: "page/set", payload: "memory_management" })}>记忆管理</button>
            <button className="rounded-lg border px-2 py-1 hover:bg-gray-50" onClick={() => dispatch({ type: "page/set", payload: "memory_history" })}>记忆历史</button>
            <button className="rounded-lg border px-2 py-1 hover:bg-gray-50" onClick={() => dispatch({ type: "page/set", payload: "audit" })}>审计</button>
          </div>
        </div>
      }
      topBar={
        <div className="flex h-full items-center justify-between gap-4 px-4">
          <div>
            <div className="text-sm font-medium text-gray-700">组织：{overviewData.organizationGraph?.organization?.name ?? "统一控制台"}</div>
            <div className="text-xs text-gray-500">模式：{identityData.mode}</div>
            <div className="text-xs text-gray-500">页面：{shellUiData.pageTitle}</div>
          </div>
          <ConsoleSyncStatusBadge
            status={sync.syncStatus}
            lastSyncedAt={sync.lastSyncedAt}
            error={sync.syncError}
            reconnectAttempts={reconnectAttempts}
            onRefresh={sync.manualRefresh}
            onReconnect={sync.reconnect}
          />
        </div>
      }
      mainArea={renderPage()}
      contextPanel={
        <div className="h-full overflow-y-auto p-4">
          <h3 className="text-lg font-semibold">上下文详情</h3>
          <div className="mt-4 space-y-3 text-sm text-gray-600">
            <div>当前用户：{contextData.currentUser}</div>
            <div>当前会议室：{contextData.activeRoomName}</div>
            <div>当前对话：{contextData.activeConversationTitle}</div>
            <div>选中节点：{contextData.selectedNodeName}</div>
            <div>选中智能体：{contextData.selectedAgentName}</div>
            <div>选中角色模板：{contextData.selectedRoleTemplateName}</div>
            <div>工作流选中：{contextData.selectedWorkflowId}</div>
            <div>审计选中消息：{contextData.selectedAuditMessageId}</div>
          </div>
        </div>
      }
      statusBar={
        <div className="flex h-full items-center justify-between px-4 text-xs text-gray-500">
          <div>同步状态：{sync.syncStatus}</div>
          <div>最近同步：{sync.lastSyncedAt ?? "-"}</div>
          <div>未读消息：{overviewData.realtime.unread_count}</div>
        </div>
      }
    />
  );
}

function emptyGraph(): OrganizationGraphView {
  return { organization: null, departments: [], role_templates: [], agent_instances: [], meeting_rooms: [], nodes: [], edges: [] };
}
