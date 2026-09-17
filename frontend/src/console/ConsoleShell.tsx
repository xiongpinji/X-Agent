import React from "react";
import { ConsoleLayout } from "./components/layout/ConsoleLayout";
import { ConsoleSyncStatusBadge } from "./components/layout/ConsoleSyncStatusBadge";
import { useConsoleDispatch, useConsoleState } from "./state/consoleContext";
import type {
  ExecutionControlOverview,
  MarketplaceCenterOverview,
  MemoryCenterOverview,
  NavigationCenterOverview,
  ToolsCenterOverview,
} from "./state/consoleReducer";
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
  selectWorkflowData,
} from "./state/consoleSelectors";
import {
  selectExecutionControlOverviewData,
  selectExecutionControlRunId,
} from "./state/executionControlSelectors";
import { selectToolsCenterOverviewData } from "./state/toolsCenterSelectors";
import { selectMemoryCenterOverviewData } from "./state/memoryCenterSelectors";
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
import { NavigationSearchPage } from "./pages/navigation/NavigationSearchPage";
import { NavigationShortcutsPage } from "./pages/navigation/NavigationShortcutsPage";
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
import type { AgentCreatePayload, AgentCreateResult } from "./pages/agents/CreateAgentPage";
import type { AuditSummarySection, TraceSummarySection } from "./pages/audit/AuditReplayPage";
import { apiFailureMessage } from "./sendOutcome";
import { consoleFetch } from "./consoleFetch";
import { useOrganizationDirectory } from "./hooks/useOrganizationDirectory";
import { useOrganizationGovernance } from "./hooks/useOrganizationGovernance";
import { OrganizationSwitcher } from "./components/organization/OrganizationSwitcher";
import type {
  NewDepartmentPayload,
  NewOrganizationPayload,
} from "./components/organization/OrganizationSwitcher";

/**
 * 当前组织在 localStorage 的键 —— 让刷新/重开控制台后仍停在同一个组织。
 *
 * 存的是 org_id。陈旧值（组织已被删除、后端内存重置、换了租户）会让 workbench
 * 返回 404，下面有一条自愈 effect 负责清掉它并回退到缺省组织。
 */
const CONSOLE_ORG_STORAGE_KEY = "console_active_org_id";

export function ConsoleShell() {
  const state = useConsoleState();
  const dispatch = useConsoleDispatch();

  // (c) 组织切换：当前组织由本组件持有，刻意**不放 reducer** —— reducer 是纯函数，
  // 而这里需要懒读 localStorage（刷新后停在同一个组织）。
  // 切换后 bootstrapUrl 变化，hook 内部会用新的 org_id 自动重新 bootstrap，
  // 于是组织图、以及「创建智能体」的目标组织一起跟着变。
  const [activeOrgId, setActiveOrgId] = React.useState<string | null>(() => {
    try {
      return localStorage.getItem(CONSOLE_ORG_STORAGE_KEY);
    } catch {
      return null;
    }
  });

  const bootstrapUrl = React.useMemo(
    () =>
      activeOrgId
        ? `/api/v1/workbench?org_id=${encodeURIComponent(activeOrgId)}`
        : "/api/v1/workbench",
    [activeOrgId],
  );

  const sync = useConsoleRealtimeSync(state, dispatch, {
    bootstrapUrl,
    messagesStreamUrl: "/api/v1/messages/stream",
    pollingIntervalMs: 10000,
  });

  const organizationDirectory = useOrganizationDirectory(activeOrgId);

  // 组织治理数据（岗位模板目录 + 组织域审计流水）。
  // ★ 走 (d) 批次新增的**真实**端点 /api/v1/organization/roles、/audit ——
  // 不是 /api/v1/organization-control/*（那个模块是纯 fixture 且刻意不挂载）。
  const governance = useOrganizationGovernance(activeOrgId);

  /**
   * 按 orgId 拉一份组织图（部门 + 智能体）。
   *
   * 给 CreateAgentPage 的「所属组织」下拉用：在表单里换了组织，就必须换掉
   * 「所属部门」「上级智能体」两个下拉的选项来源 —— 它们是**组织内**的 id，
   * 拿着 A 组织的 department_id 往 B 组织提交，后端只能 404。
   *
   * 直接复用 workbench 端点（与 bootstrap 同源、同结构），不另造一个返回体。
   * 必须走 consoleFetch：裸 fetch 在浏览器里没有凭证。
   */
  const loadOrganizationGraphFor = React.useCallback(
    async (orgId: string): Promise<OrganizationGraphView> => {
      const response = await consoleFetch(
        `/api/v1/workbench?org_id=${encodeURIComponent(orgId)}`,
      );
      if (!response.ok) {
        throw new Error(await apiFailureMessage(response));
      }
      const payload = (await response.json()) as {
        organization_graph?: OrganizationGraphView;
      };
      if (!payload.organization_graph) {
        // 不要把「没有图」当成「空图」悄悄放过：空图会让部门下拉显示
        // 「该组织下还没有部门」，把一次契约不符伪装成一个正常的空状态。
        throw new Error("后端没有返回该组织的组织图");
      }
      return payload.organization_graph;
    },
    [],
  );

  const activeOrganization =
    organizationDirectory.organizations.find(
      (organization) => organization.org_id === activeOrgId,
    ) ?? null;

  /**
   * 陈旧组织 id 自愈。
   *
   * localStorage 里记的 org_id 可能已经不存在（组织被删、后端内存重置、换了租户），
   * 那时 workbench 会**诚实地返回 404**（见 backend/app/api/workbench.py：明确拒绝
   * 而不是静默回退，因为静默回退会让「切换没生效」看起来像「切换成功了」）。
   * 但前端不能因此永久打不开 —— 清掉本地记忆、回退到缺省组织。
   */
  React.useEffect(() => {
    if (!activeOrgId || !sync.syncError) return;
    if (!sync.syncError.includes("404")) return;
    try {
      localStorage.removeItem(CONSOLE_ORG_STORAGE_KEY);
    } catch {
      // localStorage 不可用（隐私模式等）时忽略：回退逻辑本身不依赖它
    }
    setActiveOrgId(null);
  }, [activeOrgId, sync.syncError]);

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
  // 详情 / 恢复 / 调度三页各自去拉真实数据；这里只把「当前选中的 run」交给它们。
  // （历史上这里注入硬编码 fixture，页面里的 `props.x ?? 真值` 因此永远命中 props，
  //  fetch 到的数据被静默丢弃。）
  const executionRunId = selectExecutionControlRunId(state);
  const toolsCenterData = selectToolsCenterOverviewData(state);
  const memoryCenterData = selectMemoryCenterOverviewData(state);
  const marketplaceCenterData = selectMarketplaceCenterOverviewData(state);
  const navigationCenterData = selectNavigationCenterOverviewData(state);
  const identityData = selectIdentityData(state);
  const meetingRoomData = selectMeetingRoomData(state);
  const chatData = selectChatData(state);
  const roleCatalogData = selectRoleCatalogData(state);
  const shellUiData = selectShellUiData(state);
  const contextData = selectContextData(state);
  // trace 数据：从信封 linked_summaries.trace 派生（后端信封可选，缺省时为 null）
  const traceData = React.useMemo(
    () => ({ traceSummary: state.envelope?.linked_summaries?.trace ?? null }),
    [state.envelope],
  );

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
        // ★ 这里刻意**没有** /api/v1/organization-control/overview：那个路由未挂载，
        // 恒 404，而失败分支是 `if (res.ok)` ⇒ 每次开控制台都打一个必然失败的请求，
        // 再把失败伪装成「没有数据」。组织域的真实数据改由上面的
        // useOrganizationGovernance（/api/v1/organization/roles + /audit）与
        // workbench 的组织图承担。
        const [executionRes, toolsRes, memoryRes, marketRes, navRes] = await Promise.all([
          fetch("/api/v1/execution-control/overview", { method: "GET", headers: { "Content-Type": "application/json" } }),
          fetch("/api/v1/tools-control/overview", { method: "GET", headers: { "Content-Type": "application/json" } }),
          fetch("/api/v1/memory-control/overview", { method: "GET", headers: { "Content-Type": "application/json" } }),
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

  const handleCreateAgent = async (payload: AgentCreatePayload): Promise<AgentCreateResult> => {
    // ★ 必须走 consoleFetch：裸 fetch 不带任何凭证，写请求会被 main.py 的
    // CSRFProtectionMiddleware 挡成 403 {"detail":"CSRF token required"}（已实测）。
    const response = await consoleFetch("/api/v1/organization/agents", {
      method: "POST",
      body: JSON.stringify(payload),
    });
    if (!response.ok) {
      // 抛出而非静默 return：CreateAgentPage 的 catch 会把这里的原因渲染进
      // role="alert"。此前这里是 console.log 桩且永不 reject，
      // 那段 catch 是死代码。
      throw new Error(await apiFailureMessage(response));
    }

    const created = (await response.json()) as { agent_id?: string; warnings?: string[] };
    const result: AgentCreateResult = {
      agentId: created.agent_id ?? "",
      warnings: created.warnings ?? [],
    };

    if (result.warnings.length) {
      // 部分成功（例如上级已满编）：留在表单页把原因显示出来，
      // 不要静默跳回组织图 —— 那会让一次「建了但没挂上汇报关系」看起来像全成功。
      return result;
    }

    dispatch({ type: "page/set", payload: "organization_graph" });
    if (payload.role_template_id) {
      dispatch({ type: "roleTemplate/setSelected", payload: payload.role_template_id });
    }
    await sync.manualRefresh();
    return result;
  };

  const handleSelectOrg = (orgId: string) => {
    if (!orgId || orgId === activeOrgId) return;
    setActiveOrgId(orgId);
    try {
      localStorage.setItem(CONSOLE_ORG_STORAGE_KEY, orgId);
    } catch {
      // 忽略：记忆失败只影响「下次打开时停在哪个组织」，不影响本次切换
    }
  };

  const handleCreateOrganization = async (payload: NewOrganizationPayload) => {
    const response = await consoleFetch("/api/v1/organization/organizations", {
      method: "POST",
      body: JSON.stringify(payload),
    });
    if (!response.ok) {
      throw new Error(await apiFailureMessage(response));
    }

    const created = (await response.json()) as { org_id?: string };
    if (created.org_id) {
      // 建完立刻切过去。缺省只展示「最近更新的那一个组织」，不切的话新组织会掉出
      // 视野 —— 用户会以为根本没建成功。这正是 (c) 要根治的「我建的组织不见了」。
      // （切过去之后，组织目录会因为 activeOrgId 变化自动重拉，不需要在这里 reload。）
      handleSelectOrg(created.org_id);
    } else {
      await organizationDirectory.reload();
    }
  };

  const handleCreateDepartment = async (payload: NewDepartmentPayload) => {
    if (!activeOrgId) {
      throw new Error("请先选择一个组织");
    }
    const response = await consoleFetch("/api/v1/organization/departments", {
      method: "POST",
      body: JSON.stringify({ org_id: activeOrgId, ...payload }),
    });
    if (!response.ok) {
      throw new Error(await apiFailureMessage(response));
    }

    await organizationDirectory.reload();
    // 组织图来自 workbench 的 bootstrap，新部门不会自己出现 —— 必须显式刷新，
    // 否则「部门建好了但图上没有」。
    await sync.manualRefresh();
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
          />
        );
      case "create_agent":
        return (
          <CreateAgentPage
            roleCatalog={roleCatalogData.roleCatalog}
            organizationGraph={overviewData.organizationGraph ?? emptyGraph()}
            organizationName={activeOrganization?.name}
            // 「所属组织」在表单里可就地切换：切过去即拉该组织的部门与智能体。
            // 不传 onLoadOrganizationGraph 的话，组件会显式报「无法加载该组织的部门
            // 列表」而不是静默留一张空下拉（见 CreateAgentPage 的切换 effect）。
            organizations={organizationDirectory.organizations.map((organization) => ({
              org_id: organization.org_id,
              name: organization.name,
            }))}
            onLoadOrganizationGraph={loadOrganizationGraphFor}
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
            organizationSwitcher={
              <OrganizationSwitcher
                organizations={organizationDirectory.organizations}
                departments={organizationDirectory.departments}
                activeOrgId={activeOrgId}
                loading={organizationDirectory.loading}
                error={organizationDirectory.error}
                onSelectOrg={handleSelectOrg}
                onCreateOrganization={handleCreateOrganization}
                onCreateDepartment={handleCreateDepartment}
              />
            }
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
              dispatch({ type: "workflow/setSelected", payload: runId });
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
            runId={executionRunId}
            onBack={() => dispatch({ type: "page/set", payload: "execution_overview" })}
            onOpenRecovery={(runId) => {
              dispatch({ type: "workflow/setSelected", payload: runId });
              dispatch({ type: "page/set", payload: "execution_recovery" });
            }}
            onOpenAudit={(runId) => dispatch({ type: "audit/setSelectedMessage", payload: runId })}
            onOpenDispatch={(runId) => {
              dispatch({ type: "workflow/setSelected", payload: runId });
              dispatch({ type: "page/set", payload: "execution_dispatch" });
            }}
          />
        );
      case "execution_recovery":
        return (
          <ExecutionRecoveryPage
            runId={executionRunId}
            onBack={() => dispatch({ type: "page/set", payload: "execution_overview" })}
            onOpenDetail={(runId) => {
              dispatch({ type: "workflow/setSelected", payload: runId });
              dispatch({ type: "page/set", payload: "execution_detail" });
            }}
            onOpenAudit={(runId) => dispatch({ type: "audit/setSelectedMessage", payload: runId })}
          />
        );
      case "execution_dispatch":
        return (
          <ExecutionDispatchPage
            runId={executionRunId}
            onBack={() => dispatch({ type: "page/set", payload: "execution_overview" })}
            onOpenDetail={(runId) => {
              dispatch({ type: "workflow/setSelected", payload: runId });
              dispatch({ type: "page/set", payload: "execution_detail" });
            }}
            onOpenRecovery={(runId) => {
              dispatch({ type: "workflow/setSelected", payload: runId });
              dispatch({ type: "page/set", payload: "execution_recovery" });
            }}
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
        // ★ 全部数字都来自真实来源，**没有一个**硬编码字面量：
        // 组织名/部门数/智能体数来自 workbench 的组织图；岗位模板数与在用数来自
        // /api/v1/organization/roles；审计总数与失败数来自 /api/v1/organization/audit。
        return (
          <OrganizationCenterOverviewPage
            organizationName={
              overviewData.organizationGraph?.organization?.name ??
              activeOrganization?.name ??
              ""
            }
            totalDepartments={overviewData.organizationGraph?.departments.length ?? 0}
            totalAgents={overviewData.organizationGraph?.agent_instances.length ?? 0}
            totalRoleTemplates={governance.roles?.total_templates ?? 0}
            inUseAgents={governance.roles?.in_use_total ?? 0}
            auditTotal={governance.audit?.total ?? 0}
            auditFailure={governance.audit?.summary.failure ?? 0}
            loading={governance.loading}
            error={governance.error}
            onOpenStructure={() => dispatch({ type: "page/set", payload: "org_structure" })}
            onOpenRoles={() => dispatch({ type: "page/set", payload: "org_roles" })}
            onOpenAudit={() => dispatch({ type: "page/set", payload: "org_audit" })}
          />
        );
      case "org_structure":
        return (
          <OrganizationStructurePage
            organizations={organizationDirectory.organizations}
            departments={organizationDirectory.departments}
            activeOrgId={activeOrgId}
            loading={organizationDirectory.loading}
            error={organizationDirectory.error}
            onSelectOrg={handleSelectOrg}
            agentCount={overviewData.organizationGraph?.agent_instances.length ?? 0}
          />
        );
      case "org_roles":
        // 本页此前渲染硬编码占位（24 角色 / 21 启用 / 12 权限集），且数据源
        // /api/v1/organization-control/* 未挂载恒 404。现在接真实角色目录：
        // 模板来自 store.get_role_catalog()，「在用」数是后端按该组织 list_agents
        // 数出来的 —— 与写路径同源，读到的 role_id 可以直接喂回 POST /agents。
        return (
          <OrganizationRolesPage
            templates={governance.roles?.templates ?? []}
            totalTemplates={governance.roles?.total_templates ?? 0}
            inUseTotal={governance.roles?.in_use_total ?? 0}
            roleGroups={governance.roles?.role_groups ?? {}}
            activeOrgId={activeOrgId}
            loading={governance.loading}
            error={governance.error}
          />
        );
      case "org_audit":
        // 本页此前渲染硬编码占位（13 条事件 / 10 成功 / 3 失败），数据源同样未挂载。
        // 现在数据来自 core.audit.AuditStore —— 与创建组织/部门/岗位智能体时写的
        // 是同一份存储，按租户隔离。
        return (
          <OrganizationAuditPage
            records={governance.audit?.records ?? []}
            total={governance.audit?.total ?? 0}
            summary={
              governance.audit?.summary ?? { success: 0, failure: 0, latest_outcome: null }
            }
            truncated={governance.audit?.truncated ?? false}
            loading={governance.loading}
            error={governance.error}
          />
        );
      case "audit":
        return (
          <AuditReplayPage
            envelope={auditData.envelope ?? null}
            traceSummary={traceData.traceSummary as TraceSummarySection | null}
            auditSummary={auditData.auditSummary as AuditSummarySection | null}
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
        return <div className="console-section">{state.activePage}</div>;
    }
  };

  return (
    <ConsoleLayout
      sidebar={
        <div className="p-4">
          <div className="text-base font-medium">统一控制台</div>
          <div className="cell-data mt-3 space-y-1 text-xs opacity-60">
            <div>在线智能体：{overviewPageData.onlineAgents}</div>
            <div>活跃会议室：{overviewPageData.activeRooms}</div>
          </div>
          <nav className="console-nav mt-4">
            <button onClick={() => dispatch({ type: "page/set", payload: "overview" })}>概览</button>
            <button onClick={() => dispatch({ type: "page/set", payload: "organization_graph" })}>组织图</button>
            <button onClick={() => dispatch({ type: "page/set", payload: "org_overview" })}>组织权限中心</button>
            <button onClick={() => dispatch({ type: "page/set", payload: "org_structure" })}>组织结构</button>
            {/* 这两个入口此前被摘除，因为它们指向的是硬编码占位（24 个角色 /
                13 条审核事件），而数据源 /api/v1/organization-control/* 未挂载恒 404。
                (d) 批次把两个页面改接真实端点后，入口恢复 —— 现在它们通往的数据与
                「创建智能体」「新建部门」写入的是同一份存储。 */}
            <button onClick={() => dispatch({ type: "page/set", payload: "org_roles" })}>角色权限</button>
            <button onClick={() => dispatch({ type: "page/set", payload: "org_audit" })}>组织审核</button>
            <button onClick={() => dispatch({ type: "page/set", payload: "meeting_room" })}>会议室</button>
            <button onClick={() => dispatch({ type: "page/set", payload: "realtime_chat" })}>对话</button>
            <button onClick={() => dispatch({ type: "page/set", payload: "workflow" })}>工作流</button>
            <button onClick={() => dispatch({ type: "page/set", payload: "execution_overview" })}>运行控制</button>
            <button onClick={() => dispatch({ type: "page/set", payload: "tools_overview" })}>工具中心</button>
            <button onClick={() => dispatch({ type: "page/set", payload: "tools_detail" })}>工具详情</button>
            <button onClick={() => dispatch({ type: "page/set", payload: "tools_management" })}>工具管理</button>
            <button onClick={() => dispatch({ type: "page/set", payload: "tools_history" })}>调用历史</button>
            <button onClick={() => dispatch({ type: "page/set", payload: "market_overview" })}>能力市场</button>
            <button onClick={() => dispatch({ type: "page/set", payload: "search_overview" })}>全局导航</button>
            <button onClick={() => dispatch({ type: "page/set", payload: "memory_overview" })}>记忆中心</button>
            <button onClick={() => dispatch({ type: "page/set", payload: "memory_detail" })}>记忆详情</button>
            <button onClick={() => dispatch({ type: "page/set", payload: "memory_management" })}>记忆管理</button>
            <button onClick={() => dispatch({ type: "page/set", payload: "memory_history" })}>记忆历史</button>
            <button onClick={() => dispatch({ type: "page/set", payload: "audit" })}>审计</button>
          </nav>
        </div>
      }
      topBar={
        <div className="flex h-full items-center justify-between gap-4 px-4">
          <div className="text-xs opacity-60">
            <span>组织：{overviewData.organizationGraph?.organization?.name ?? activeOrganization?.name ?? "未选择组织"}</span>
            <span className="mx-2">·</span>
            <span>模式：{identityData.mode}</span>
            <span className="mx-2">·</span>
            <span>页面：{shellUiData.pageTitle}</span>
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
          <h3 className="text-sm font-medium">上下文详情</h3>
          <div className="mt-4 space-y-3 text-sm opacity-70">
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
        <div className="cell-data flex h-full items-center justify-between px-4 text-xs opacity-60">
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
