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
};

export function OverviewPage(props: OverviewPageProps) {
  const onlineAgents = props.realtime.online_agents.length;
  const activeRooms = props.meetingRooms.length;
  const unreadCount = props.realtime.unread_count;
  const recentConversations = props.realtime.conversations.slice(0, 4);
  const recentMessages = props.realtime.messages.slice(0, 6);

  return (
    <div className="space-y-4">
      <section className="grid gap-4 md:grid-cols-2 xl:grid-cols-4">
        <MetricCard label="在线智能体" value={String(onlineAgents)} onClick={() => props.onOpenAction?.("open_agents")} />
        <MetricCard label="活跃会议室" value={String(activeRooms)} onClick={() => props.onOpenAction?.("open_rooms")} />
        <MetricCard label="未读消息" value={String(unreadCount)} onClick={() => props.onOpenAction?.("open_chat")} />
        <MetricCard label="调度置信度" value={props.dispatch ? `${Math.round(props.dispatch.suggestion.confidence * 100)}%` : "-"} onClick={() => props.onOpenAction?.("open_workflow")} />
      </section>

      <section className="rounded-2xl border bg-white p-4 shadow-sm">
        <div className="flex items-center justify-between gap-3">
          <div>
            <h2 className="text-base font-semibold">快捷返回</h2>
            <p className="text-sm text-gray-500">快速返回当前工作上下文。</p>
          </div>
          <div className="flex flex-wrap gap-2">
            <button className="rounded-lg border px-3 py-2 text-sm hover:bg-gray-50" onClick={() => props.onOpenAction?.("open_rooms")}>会议室</button>
            <button className="rounded-lg border px-3 py-2 text-sm hover:bg-gray-50" onClick={() => props.onOpenAction?.("open_chat")}>实时通讯</button>
            <button className="rounded-lg border px-3 py-2 text-sm hover:bg-gray-50" onClick={() => props.onOpenAction?.("open_workflow")}>工作流</button>
            <button className="rounded-lg border px-3 py-2 text-sm hover:bg-gray-50" onClick={() => props.onOpenAction?.("open_audit")}>审计</button>
          </div>
        </div>
      </section>

      <div className="flex flex-wrap gap-2">
        <button className="rounded-lg border px-3 py-2 text-sm hover:bg-gray-50" onClick={() => props.onOpenAction?.("open_workflow")}>返回工作流</button>
        <button className="rounded-lg border px-3 py-2 text-sm hover:bg-gray-50" onClick={() => props.onOpenAction?.("open_audit")}>返回审计</button>
        <button className="rounded-lg border px-3 py-2 text-sm hover:bg-gray-50" onClick={() => props.onOpenAction?.("open_rooms")}>返回会议室</button>
        <button className="rounded-lg border px-3 py-2 text-sm hover:bg-gray-50" onClick={() => props.onOpenAction?.("open_chat")}>返回对话</button>
      </div>

      <section className="grid gap-4 xl:grid-cols-[minmax(0,1fr)_360px]">
        <div className="space-y-4">
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
