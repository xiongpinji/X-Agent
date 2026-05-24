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
  const traceData = selectTraceData(state);
  const auditData = selectAuditData(state);
  const identityData = selectIdentityData(state);
  const meetingRoomData = selectMeetingRoomData(state);
  const chatData = selectChatData(state);
  const roleCatalogData = selectRoleCatalogData(state);
  const shellUiData = selectShellUiData(state);
  const contextData = selectContextData(state);

  const selectorValidation = React.useMemo(
    () => validateConsoleSelectors(overviewPageData, workflowData, traceData, auditData, contextData),
    [overviewPageData, workflowData, traceData, auditData, contextData],
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
            {...overviewPageData}
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
            onOpenAction={(actionKey) => {
              if (actionKey === "open_workflow") openWorkflow();
              if (actionKey === "open_audit") openAudit();
              if (actionKey === "open_rooms") dispatch({ type: "page/set", payload: "meeting_room" });
              if (actionKey === "open_chat") dispatch({ type: "page/set", payload: "realtime_chat" });
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
            <button className="rounded-lg border px-2 py-1 hover:bg-gray-50" onClick={() => dispatch({ type: "page/set", payload: "meeting_room" })}>会议室</button>
            <button className="rounded-lg border px-2 py-1 hover:bg-gray-50" onClick={() => dispatch({ type: "page/set", payload: "realtime_chat" })}>对话</button>
            <button className="rounded-lg border px-2 py-1 hover:bg-gray-50" onClick={() => dispatch({ type: "page/set", payload: "workflow" })}>工作流</button>
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
