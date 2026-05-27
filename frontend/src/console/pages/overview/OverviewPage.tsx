import React from "react";

export type OverviewPageProps = {
  dispatch: DispatchResult | null;
  organizationGraph: OrganizationGraphView;
  meetingRooms: MeetingRoomSummary[];
  realtime: RealtimeSnapshot;
  memory: MemorySnapshot;
  avatars: RoleAvatar[];
  onOpenAgent?: (agentId: string) => void;
  onOpenRoom?: (roomId: string) => void;
  onOpenAction?: (actionKey: string) => void;
  onOpenConversation?: (conversationId: string) => void;
  onOpenAudit?: () => void;
  onOpenPendingItem?: (itemKey: string) => void;
};

export function OverviewPage(props: OverviewPageProps) {
  const onlineAgents = props.realtime.online_agents.length;
  const activeRooms = props.meetingRooms.length;
  const unreadCount = props.realtime.unread_count;
  const recentConversations = props.realtime.conversations.slice(0, 4);
  const recentMessages = props.realtime.messages.slice(0, 6);
  const pendingItems = [
    { key: "pending_execution", label: "待恢复执行", value: props.dispatch?.status === "suggested" ? 1 : 0, action: "open_workflow", alertKey: "alert_execution" },
    { key: "pending_audit", label: "待审核事项", value: props.realtime.messages.filter((msg) => msg.message_type === "audit" || msg.message_type === "alert").length || 0, action: "open_audit", alertKey: "alert_audit" },
    { key: "pending_tools", label: "待启用工具", value: props.organizationGraph.agent_instances.filter((agent) => agent.status !== "online").length ? 2 : 0, action: "open_tools", alertKey: "alert_tools" },
    { key: "pending_org", label: "待确认权限", value: props.organizationGraph.departments.length > 0 ? 1 : 0, action: "open_org", alertKey: "alert_org" },
  ];
  const platformEntries = [
    { label: "运行控制", action: "open_execution", page: "execution_overview" },
    { label: "工具中心", action: "open_tools", page: "tools_overview" },
    { label: "记忆中心", action: "open_memory", page: "memory_overview" },
    { label: "组织权限中心", action: "open_org", page: "org_overview" },
    { label: "能力市场", action: "open_market", page: "market_overview" },
    { label: "全局导航", action: "open_search", page: "search_overview" },
    { label: "统一审计", action: "open_audit", page: "audit" },
  ];
  const recentEntries = [
    { label: "最近工作流", action: "open_workflow", hint: "查看最近调度任务", page: "workflow" },
    { label: "最近会议室", action: "open_rooms", hint: "回到最近协作空间", page: "meeting_room" },
    { label: "最近对话", action: "open_chat", hint: "继续未完成交流", page: "realtime_chat" },
    { label: "最近审计", action: "open_audit", hint: "查看最近异常回放", page: "audit" },
  ];
  const favoriteEntries = [
    { label: "运行控制", action: "open_execution", hint: "执行总览与恢复", page: "execution_overview" },
    { label: "工具中心", action: "open_tools", hint: "能力与插件管理", page: "tools_overview" },
    { label: "能力市场", action: "open_market", hint: "发现与启用能力", page: "market_overview" },
    { label: "统一审计", action: "open_audit", hint: "风险与回放", page: "audit" },
  ];

  return (
    <div className="space-y-4">
      <section className="rounded-2xl border bg-gradient-to-r from-slate-900 to-slate-700 p-5 text-white shadow-sm">
        <div className="flex flex-col gap-4 lg:flex-row lg:items-center lg:justify-between">
          <div>
            <div className="text-sm text-slate-300">平台驾驶舱</div>
            <h1 className="mt-1 text-2xl font-bold">统一控制台总览</h1>
            <p className="mt-2 max-w-2xl text-sm text-slate-200">集中查看运行态势、能力入口、待处理事项和最近访问，快速切换到核心业务板块。</p>
          </div>
          <div className="grid grid-cols-2 gap-2 sm:grid-cols-3">
            <button className="rounded-lg bg-white/10 px-3 py-2 text-sm hover:bg-white/20" onClick={() => props.onOpenAction?.("open_search")}>全局搜索</button>
            <button className="rounded-lg bg-white/10 px-3 py-2 text-sm hover:bg-white/20" onClick={() => props.onOpenAction?.("open_audit")}>统一审计</button>
            <button className="rounded-lg bg-white/10 px-3 py-2 text-sm hover:bg-white/20" onClick={() => props.onOpenAction?.("open_execution")}>运行控制</button>
            <button className="rounded-lg bg-white/10 px-3 py-2 text-sm hover:bg-white/20" onClick={() => props.onOpenAction?.("open_tools")}>工具中心</button>
            <button className="rounded-lg bg-white/10 px-3 py-2 text-sm hover:bg-white/20" onClick={() => props.onOpenAction?.("open_memory")}>记忆中心</button>
            <button className="rounded-lg bg-white/10 px-3 py-2 text-sm hover:bg-white/20" onClick={() => props.onOpenAction?.("open_org")}>组织权限</button>
            <button className="rounded-lg bg-white/10 px-3 py-2 text-sm hover:bg-white/20" onClick={() => props.onOpenAction?.("open_market")}>能力市场</button>
          </div>
        </div>
      </section>

      <section className="grid gap-4 md:grid-cols-2 xl:grid-cols-4">
        <MetricCard label="在线智能体" value={String(onlineAgents)} description={`当前参与协作的智能体 ${onlineAgents} 个`} onClick={() => props.onOpenAction?.("open_agents")} />
        <MetricCard label="活跃会议室" value={String(activeRooms)} description={`最近活跃会议室 ${activeRooms} 个`} onClick={() => props.onOpenAction?.("open_rooms")} />
        <MetricCard label="未读消息" value={String(unreadCount)} description={`待处理消息 ${unreadCount} 条`} onClick={() => props.onOpenAction?.("open_chat")} />
        <MetricCard label="调度置信度" value={props.dispatch ? `${Math.round(props.dispatch.suggestion.confidence * 100)}%` : "-"} description={props.dispatch ? `建议等级：${props.dispatch.status}` : "暂无调度建议"} onClick={() => props.onOpenAction?.("open_workflow")} />
      </section>

      <section className="grid gap-4 xl:grid-cols-[minmax(0,1fr)_360px]">
        <div className="space-y-4">
          <Card title="待处理事项">
            <div className="grid gap-3 md:grid-cols-2 xl:grid-cols-4">
              {pendingItems.map((item) => (
                <button key={item.key} className="rounded-xl border bg-gray-50 p-4 text-left hover:bg-gray-100" onClick={() => props.onOpenPendingItem?.(item.key) ?? props.onOpenAction?.(item.action)}>
                  <div className="text-sm text-gray-500">{item.label}</div>
                  <div className="mt-2 text-2xl font-bold">{item.value}</div>
                  <div className="mt-1 text-xs text-gray-500">对应告警：{item.alertKey}</div>
                </button>
              ))}
            </div>
          </Card>

          <Card title="平台入口">
            <div className="grid gap-2 md:grid-cols-2 xl:grid-cols-3">
              {platformEntries.map((entry) => (
                <button key={entry.label} className="rounded-xl border px-3 py-3 text-left hover:bg-gray-50" onClick={() => props.onOpenAction?.(entry.action)}>
                  <div className="font-medium">{entry.label}</div>
                  <div className="mt-1 text-xs text-gray-500">快速进入对应板块</div>
                </button>
              ))}
            </div>
          </Card>

          <div className="grid gap-4 md:grid-cols-2">
            <Card title="最近访问">
              <div className="space-y-2">
                {recentEntries.map((entry) => (
                  <button key={entry.label} className="w-full rounded-xl border px-3 py-2 text-left hover:bg-gray-50" onClick={() => props.onOpenAction?.(entry.action)}>
                    <div className="font-medium">{entry.label}</div>
                    <div className="text-xs text-gray-500">{entry.hint}</div>
                    <div className="mt-1 text-[11px] text-gray-400">页面：{entry.page}</div>
                  </button>
                ))}
              </div>
            </Card>

            <Card title="常用入口">
              <div className="space-y-2">
                {favoriteEntries.map((entry) => (
                  <button key={entry.label} className="w-full rounded-xl border px-3 py-2 text-left hover:bg-gray-50" onClick={() => props.onOpenAction?.(entry.action)}>
                    <div className="font-medium">{entry.label}</div>
                    <div className="text-xs text-gray-500">{entry.hint}</div>
                    <div className="mt-1 text-[11px] text-gray-400">页面：{entry.page}</div>
                  </button>
                ))}
              </div>
            </Card>
          </div>

          <div className="grid gap-4 md:grid-cols-2">
            <DispatchSummaryCard dispatch={props.dispatch} onExecuteAction={props.onOpenAction} />
            <RecommendedActionsCard actions={props.dispatch?.suggestion.next_actions ?? []} onExecuteAction={props.onOpenAction} />
          </div>

          <div className="grid gap-4 md:grid-cols-2">
            <ActiveAgentsCard agents={props.organizationGraph.agent_instances} avatars={props.avatars} onOpenAgent={props.onOpenAgent} />
            <ActiveRoomsCard rooms={props.meetingRooms} onOpenRoom={props.onOpenRoom} />
          </div>

          <div className="grid gap-4 md:grid-cols-2">
            <RecentMessagesCard messages={recentMessages} avatars={props.avatars} onOpenConversation={props.onOpenConversation} />
            <RecentConversationsCard conversations={recentConversations} onOpenConversation={props.onOpenConversation} />
          </div>

          <div className="grid gap-4 md:grid-cols-2">
            <MemorySnapshotCard memory={props.memory} />
            <RiskAlertsCard onOpenAudit={props.onOpenAudit} />
          </div>
        </div>

        <aside className="space-y-4">
          <OrganizationSummaryCard graph={props.organizationGraph} />
          <SystemQuickActions onOpenAction={props.onOpenAction} />
        </aside>
      </section>
    </div>
  );
}

function MetricCard({ label, value, description, onClick }: { label: string; value: string; description?: string; onClick?: () => void }) {
  return (
    <button className="rounded-2xl border bg-white p-4 text-left shadow-sm transition hover:bg-gray-50" onClick={onClick}>
      <div className="text-sm text-gray-500">{label}</div>
      <div className="mt-2 text-2xl font-bold">{value}</div>
      {description ? <div className="mt-2 text-xs text-gray-500">{description}</div> : null}
    </button>
  );
}

function Card({ title, children }: { title: string; children: React.ReactNode }) {
  return (
    <section className="rounded-2xl border bg-white p-4 shadow-sm">
      <h3 className="text-base font-semibold">{title}</h3>
      <div className="mt-3">{children}</div>
    </section>
  );
}

function DispatchSummaryCard({ dispatch, onExecuteAction }: { dispatch: DispatchResult | null; onExecuteAction?: (actionKey: string) => void; }) {
  if (!dispatch) return <Card title="调度建议"><div className="text-sm text-gray-500">暂无调度信息。</div></Card>;
  return (
    <Card title="调度建议">
      <div className="text-sm text-gray-700">{dispatch.suggestion.reason.summary}</div>
      <div className="mt-3 text-sm text-gray-500">置信度：{Math.round(dispatch.suggestion.confidence * 100)}%</div>
      <div className="mt-3 flex flex-wrap gap-2">
        <button className="rounded-lg border px-3 py-2 text-sm hover:bg-gray-50" onClick={() => onExecuteAction?.("open_workflow")}>查看工作流</button>
        <button className="rounded-lg border px-3 py-2 text-sm hover:bg-gray-50" onClick={() => onExecuteAction?.("open_audit")}>查看审计</button>
      </div>
    </Card>
  );
}

function RecommendedActionsCard({ actions, onExecuteAction }: { actions: DispatchAction[]; onExecuteAction?: (actionKey: string) => void; }) {
  return (
    <Card title="推荐动作">
      <div className="space-y-2">
        {actions.length ? actions.map((action) => (
          <button key={action.action} className="w-full rounded-xl border px-3 py-2 text-left hover:bg-gray-50" onClick={() => onExecuteAction?.(action.action)}>
            <div className="font-medium">{action.action}</div>
            <div className="text-xs text-gray-500">{action.reason}</div>
          </button>
        )) : <div className="text-sm text-gray-500">暂无推荐动作。</div>}
      </div>
    </Card>
  );
}

function ActiveAgentsCard({ agents, avatars, onOpenAgent }: { agents: AgentInstance[]; avatars: RoleAvatar[]; onOpenAgent?: (agentId: string) => void; }) {
  return (
    <Card title="在线智能体">
      <div className="space-y-2">
        {agents.length ? agents.map((agent) => {
          const role = avatars.find((a) => a.role_name === agent.title || a.role_name === agent.name);
          return (
            <button key={agent.agent_id} className="flex w-full items-center gap-3 rounded-xl border px-3 py-2 text-left hover:bg-gray-50" onClick={() => onOpenAgent?.(agent.agent_id)}>
              <div className="h-10 w-10 rounded-full bg-gray-200" />
              <div className="min-w-0">
                <div className="font-medium">{agent.name}</div>
                <div className="truncate text-xs text-gray-500">{agent.title} · {role?.display_name ?? "默认形象"}</div>
              </div>
            </button>
          );
        }) : <div className="text-sm text-gray-500">暂无在线智能体。</div>}
      </div>
    </Card>
  );
}

function ActiveRoomsCard({ rooms, onOpenRoom }: { rooms: MeetingRoomSummary[]; onOpenRoom?: (roomId: string) => void; }) {
  return (
    <Card title="会议室">
      <div className="space-y-2">
        {rooms.length ? rooms.map((room) => (
          <button key={room.room_id} className="w-full rounded-xl border px-3 py-2 text-left hover:bg-gray-50" onClick={() => onOpenRoom?.(room.room_id)}>
            <div className="font-medium">{room.name}</div>
            <div className="text-xs text-gray-500">{room.topic}</div>
          </button>
        )) : <div className="text-sm text-gray-500">暂无会议室。</div>}
      </div>
    </Card>
  );
}

function RecentMessagesCard({ messages, avatars, onOpenConversation }: { messages: RealtimeMessage[]; avatars: RoleAvatar[]; onOpenConversation?: (conversationId: string) => void; }) {
  return (
    <Card title="最近消息">
      <div className="space-y-3">
        {messages.length ? messages.map((msg) => {
          const avatar = avatars.find((a) => a.avatar_id === msg.sender_avatar_id);
          return (
            <button key={msg.message_id} className="w-full rounded-xl border px-3 py-2 text-left hover:bg-gray-50" onClick={() => msg.conversation_id && onOpenConversation?.(msg.conversation_id)}>
              <div className="text-xs text-gray-500">{avatar?.display_name ?? msg.sender_name} · {msg.created_at}</div>
              <div className="mt-1 text-sm">{msg.content}</div>
            </button>
          );
        }) : <div className="text-sm text-gray-500">暂无消息。</div>}
      </div>
    </Card>
  );
}

function RecentConversationsCard({ conversations, onOpenConversation }: { conversations: ConversationSummary[]; onOpenConversation?: (conversationId: string) => void; }) {
  return (
    <Card title="最近对话">
      <div className="space-y-2">
        {conversations.length ? conversations.map((conversation) => (
          <button key={conversation.conversation_id} className="w-full rounded-xl border px-3 py-2 text-left hover:bg-gray-50" onClick={() => onOpenConversation?.(conversation.conversation_id)}>
            <div className="font-medium">{conversation.title}</div>
            <div className="text-xs text-gray-500">未读 {conversation.unread_count} · 成员 {conversation.participant_ids.length}</div>
          </button>
        )) : <div className="text-sm text-gray-500">暂无对话。</div>}
      </div>
    </Card>
  );
}

function MemorySnapshotCard({ memory }: { memory: MemorySnapshot; }) {
  return <Card title="记忆摘要"><div className="text-sm text-gray-600">会话摘要：{memory.session_summary ? "已存在" : "无"}</div><div className="mt-2 text-sm text-gray-600">记忆引用：{memory.memory_refs.length}</div></Card>;
}

function RiskAlertsCard({ onOpenAudit }: { onOpenAudit?: () => void }) {
  const alerts = [
    { label: "执行异常", detail: "存在待恢复执行项", action: "open_audit" },
    { label: "工具波动", detail: "工具调用有变化", action: "open_tools" },
    { label: "权限调整", detail: "有待审核权限变更", action: "open_org" },
    { label: "能力发布", detail: "市场条目待确认", action: "open_market" },
  ];

  return (
    <Card title="风险提示">
      <div className="space-y-2 text-sm text-gray-600">
        {alerts.map((alert) => (
          <button key={alert.label} className="w-full rounded-xl border px-3 py-2 text-left hover:bg-gray-50" onClick={onOpenAudit}>
            <div className="font-medium text-gray-900">{alert.label}</div>
            <div className="text-xs text-gray-500">{alert.detail}</div>
          </button>
        ))}
      </div>
      <button className="mt-3 rounded-lg border px-3 py-2 text-sm hover:bg-gray-50" onClick={onOpenAudit}>查看审计</button>
    </Card>
  );
}

function OrganizationSummaryCard({ graph }: { graph: OrganizationGraphView }) {
  return <Card title="组织概览"><div className="text-sm text-gray-600">部门数：{graph.departments.length}</div><div className="mt-2 text-sm text-gray-600">智能体数：{graph.agent_instances.length}</div><div className="mt-2 text-sm text-gray-600">会议室数：{graph.meeting_rooms.length}</div></Card>;
}

function SystemQuickActions({ onOpenAction }: { onOpenAction?: (actionKey: string) => void; }) {
  return <Card title="快捷入口"><div className="grid gap-2"><button className="rounded-xl border px-3 py-2 text-left hover:bg-gray-50" onClick={() => onOpenAction?.("open_workflow")}>打开工作流</button><button className="rounded-xl border px-3 py-2 text-left hover:bg-gray-50" onClick={() => onOpenAction?.("open_audit")}>打开审计</button><button className="rounded-xl border px-3 py-2 text-left hover:bg-gray-50" onClick={() => onOpenAction?.("open_rooms")}>打开会议室</button><button className="rounded-xl border px-3 py-2 text-left hover:bg-gray-50" onClick={() => onOpenAction?.("open_chat")}>打开实时通讯</button></div></Card>;
}

function MetricCard({ label, value, onClick }: { label: string; value: string; onClick?: () => void }) {
  return (
    <button className="rounded-2xl border bg-white p-4 text-left shadow-sm transition hover:bg-gray-50" onClick={onClick}>
      <div className="text-sm text-gray-500">{label}</div>
      <div className="mt-2 text-2xl font-bold">{value}</div>
    </button>
  );
}

function Card({ title, children }: { title: string; children: React.ReactNode }) {
  return (
    <section className="rounded-2xl border bg-white p-4 shadow-sm">
      <h3 className="text-base font-semibold">{title}</h3>
      <div className="mt-3">{children}</div>
    </section>
  );
}

function DispatchSummaryCard({ dispatch, onExecuteAction }: { dispatch: DispatchResult | null; onExecuteAction?: (actionKey: string) => void; }) {
  if (!dispatch) return <Card title="调度建议"><div className="text-sm text-gray-500">暂无调度信息。</div></Card>;
  return (
    <Card title="调度建议">
      <div className="text-sm text-gray-700">{dispatch.suggestion.reason.summary}</div>
      <div className="mt-3 text-sm text-gray-500">置信度：{Math.round(dispatch.suggestion.confidence * 100)}%</div>
      <div className="mt-3 flex flex-wrap gap-2">
        <button className="rounded-lg border px-3 py-2 text-sm hover:bg-gray-50" onClick={() => onExecuteAction?.("open_workflow")}>查看工作流</button>
        <button className="rounded-lg border px-3 py-2 text-sm hover:bg-gray-50" onClick={() => onExecuteAction?.("open_audit")}>查看审计</button>
      </div>
    </Card>
  );
}

function RecommendedActionsCard({ actions, onExecuteAction }: { actions: DispatchAction[]; onExecuteAction?: (actionKey: string) => void; }) {
  return (
    <Card title="推荐动作">
      <div className="space-y-2">
        {actions.length ? actions.map((action) => (
          <button key={action.action} className="w-full rounded-xl border px-3 py-2 text-left hover:bg-gray-50" onClick={() => onExecuteAction?.(action.action)}>
            <div className="font-medium">{action.action}</div>
            <div className="text-xs text-gray-500">{action.reason}</div>
          </button>
        )) : <div className="text-sm text-gray-500">暂无推荐动作。</div>}
      </div>
    </Card>
  );
}

function ActiveAgentsCard({ agents, avatars, onOpenAgent }: { agents: AgentInstance[]; avatars: RoleAvatar[]; onOpenAgent?: (agentId: string) => void; }) {
  return (
    <Card title="在线智能体">
      <div className="space-y-2">
        {agents.length ? agents.map((agent) => {
          const role = avatars.find((a) => a.role_name === agent.title || a.role_name === agent.name);
          return (
            <button key={agent.agent_id} className="flex w-full items-center gap-3 rounded-xl border px-3 py-2 text-left hover:bg-gray-50" onClick={() => onOpenAgent?.(agent.agent_id)}>
              <div className="h-10 w-10 rounded-full bg-gray-200" />
              <div className="min-w-0">
                <div className="font-medium">{agent.name}</div>
                <div className="truncate text-xs text-gray-500">{agent.title} · {role?.display_name ?? "默认形象"}</div>
              </div>
            </button>
          );
        }) : <div className="text-sm text-gray-500">暂无在线智能体。</div>}
      </div>
    </Card>
  );
}

function ActiveRoomsCard({ rooms, onOpenRoom }: { rooms: MeetingRoomSummary[]; onOpenRoom?: (roomId: string) => void; }) {
  return (
    <Card title="会议室">
      <div className="space-y-2">
        {rooms.length ? rooms.map((room) => (
          <button key={room.room_id} className="w-full rounded-xl border px-3 py-2 text-left hover:bg-gray-50" onClick={() => onOpenRoom?.(room.room_id)}>
            <div className="font-medium">{room.name}</div>
            <div className="text-xs text-gray-500">{room.topic}</div>
          </button>
        )) : <div className="text-sm text-gray-500">暂无会议室。</div>}
      </div>
    </Card>
  );
}

function RecentMessagesCard({ messages, avatars, onOpenConversation }: { messages: RealtimeMessage[]; avatars: RoleAvatar[]; onOpenConversation?: (conversationId: string) => void; }) {
  return (
    <Card title="最近消息">
      <div className="space-y-3">
        {messages.length ? messages.map((msg) => {
          const avatar = avatars.find((a) => a.avatar_id === msg.sender_avatar_id);
          return (
            <button key={msg.message_id} className="w-full rounded-xl border px-3 py-2 text-left hover:bg-gray-50" onClick={() => msg.conversation_id && onOpenConversation?.(msg.conversation_id)}>
              <div className="text-xs text-gray-500">{avatar?.display_name ?? msg.sender_name} · {msg.created_at}</div>
              <div className="mt-1 text-sm">{msg.content}</div>
            </button>
          );
        }) : <div className="text-sm text-gray-500">暂无消息。</div>}
      </div>
    </Card>
  );
}

function RecentConversationsCard({ conversations, onOpenConversation }: { conversations: ConversationSummary[]; onOpenConversation?: (conversationId: string) => void; }) {
  return (
    <Card title="最近对话">
      <div className="space-y-2">
        {conversations.length ? conversations.map((conversation) => (
          <button key={conversation.conversation_id} className="w-full rounded-xl border px-3 py-2 text-left hover:bg-gray-50" onClick={() => onOpenConversation?.(conversation.conversation_id)}>
            <div className="font-medium">{conversation.title}</div>
            <div className="text-xs text-gray-500">未读 {conversation.unread_count} · 成员 {conversation.participant_ids.length}</div>
          </button>
        )) : <div className="text-sm text-gray-500">暂无对话。</div>}
      </div>
    </Card>
  );
}

function MemorySnapshotCard({ memory }: { memory: MemorySnapshot; }) {
  return <Card title="记忆摘要"><div className="text-sm text-gray-600">会话摘要：{memory.session_summary ? "已存在" : "无"}</div><div className="mt-2 text-sm text-gray-600">记忆引用：{memory.memory_refs.length}</div></Card>;
}

function RiskAlertsCard({ onOpenAudit }: { onOpenAudit?: () => void }) {
  return <Card title="风险提示"><div className="text-sm text-gray-500">暂无明显风险。</div><button className="mt-3 rounded-lg border px-3 py-2 text-sm hover:bg-gray-50" onClick={onOpenAudit}>查看审计</button></Card>;
}

function OrganizationSummaryCard({ graph }: { graph: OrganizationGraphView }) {
  return <Card title="组织概览"><div className="text-sm text-gray-600">部门数：{graph.departments.length}</div><div className="mt-2 text-sm text-gray-600">智能体数：{graph.agent_instances.length}</div><div className="mt-2 text-sm text-gray-600">会议室数：{graph.meeting_rooms.length}</div></Card>;
}

function SystemQuickActions({ onOpenAction }: { onOpenAction?: (actionKey: string) => void; }) {
  return <Card title="快捷入口"><div className="grid gap-2"><button className="rounded-xl border px-3 py-2 text-left hover:bg-gray-50" onClick={() => onOpenAction?.("open_workflow")}>打开工作流</button><button className="rounded-xl border px-3 py-2 text-left hover:bg-gray-50" onClick={() => onOpenAction?.("open_audit")}>打开审计</button><button className="rounded-xl border px-3 py-2 text-left hover:bg-gray-50" onClick={() => onOpenAction?.("open_rooms")}>打开会议室</button><button className="rounded-xl border px-3 py-2 text-left hover:bg-gray-50" onClick={() => onOpenAction?.("open_chat")}>打开实时通讯</button></div></Card>;
}
