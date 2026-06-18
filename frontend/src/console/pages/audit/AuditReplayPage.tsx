import React from "react";

export type TraceSummarySection = {
  data?: {
    trace_id?: string;
    event_count?: number;
    last_event?: string;
    task?: string;
  };
  summary?: {
    trace_id?: string;
    event_count?: number;
    last_event?: string;
    task?: string;
  };
};

export type AuditSummarySection = {
  data?: {
    count?: number;
    by_action?: Record<string, number>;
    by_resource_type?: Record<string, number>;
    by_outcome?: Record<string, number>;
  };
  summary?: {
    count?: number;
    by_action?: Record<string, number>;
    by_resource_type?: Record<string, number>;
    by_outcome?: Record<string, number>;
  };
};

export type AuditReplayPageProps = {
  envelope?: LinkedSummaryEnvelope | null;
  traceSummary?: TraceSummarySection | null;
  auditSummary?: AuditSummarySection | null;
  dispatch?: DispatchResult | null;
  realtime: RealtimeSnapshot;
  memory: MemorySnapshot;
  selectedMessageId?: string | null;
  onSelectMessage?: (messageId: string) => void;
  onOpenAction?: (actionKey: string) => void;
};

type AuditAlert = {
  title: string;
  source: string;
  level: "low" | "medium" | "high";
  description: string;
  actionLabel: string;
  actionKey: "execution" | "tools" | "memory" | "organization";
};

export function AuditReplayPage(props: AuditReplayPageProps) {
  const traceSummary = props.traceSummary?.data ?? props.traceSummary?.summary ?? props.envelope?.linked_summaries?.trace?.data ?? props.envelope?.linked_summaries?.trace?.summary ?? props.envelope?.primary?.data ?? props.envelope?.primary?.summary ?? null;
  const auditSummary = props.auditSummary?.data ?? props.auditSummary?.summary ?? props.envelope?.linked_summaries?.audit?.data ?? props.envelope?.linked_summaries?.audit?.summary ?? null;
  const selectedMessage = props.realtime.messages.find((msg) => msg.message_id === props.selectedMessageId) ?? null;
  const alertCount = Math.max(props.realtime.messages.length - props.realtime.conversations.length, 0);
  const alerts: AuditAlert[] = [
    { title: "运行控制异常", source: "execution", level: "medium", description: "存在待处理执行恢复项。", actionLabel: "前往运行控制", actionKey: "execution" },
    { title: "工具调用波动", source: "tools", level: "low", description: "近期工具调用量变化明显。", actionLabel: "前往工具中心", actionKey: "tools" },
    { title: "记忆写入审查", source: "memory", level: "low", description: "部分记忆条目需要复核。", actionLabel: "前往记忆中心", actionKey: "memory" },
    { title: "组织权限变更", source: "organization", level: "medium", description: "有待审核的权限调整。", actionLabel: "前往组织权限中心", actionKey: "organization" },
  ];

  return (
    <div className="grid gap-4 lg:grid-cols-[minmax(0,1fr)_340px]">
      <main className="rounded-2xl border bg-white p-4 shadow-sm">
        <header className="flex items-start justify-between gap-3">
          <div>
            <h2 className="text-lg font-semibold">统一审计面板</h2>
            <p className="text-sm text-gray-500">查看关键事件、风险提示、恢复建议与消息回放。</p>
          </div>
          <button className="rounded-lg border px-3 py-2 text-sm hover:bg-gray-50" onClick={() => props.onSelectMessage?.(props.selectedMessageId ?? props.realtime.messages[0]?.message_id ?? "")}>返回当前</button>
        </header>

        <section className="mt-4 grid gap-4 md:grid-cols-2 xl:grid-cols-5">
          <StatCard label="总消息数" value={String(props.realtime.messages.length)} />
          <StatCard label="对话数" value={String(props.realtime.conversations.length)} />
          <StatCard label="在线智能体" value={String(props.realtime.online_agents.length)} />
          <StatCard label="风险告警" value={String(alertCount)} />
          <StatCard label="记忆引用" value={String(props.memory.memory_refs.length)} />
        </section>

        <section className="mt-4">
          <Panel title="风险告警列表">
            <div className="grid gap-2 md:grid-cols-2">
              {alerts.map((alert) => (
                <div key={`${alert.source}-${alert.title}`} className="rounded-xl border p-3">
                  <div className="flex items-center justify-between gap-2">
                    <div className="font-medium">{alert.title}</div>
                    <span className="rounded-full bg-gray-100 px-2 py-1 text-[11px] text-gray-600">{alert.level}</span>
                  </div>
                  <div className="mt-2 text-sm text-gray-600">{alert.description}</div>
                  <div className="mt-3 text-xs text-gray-500">来源：{alert.source}</div>
                  <button className="mt-3 rounded-lg border px-3 py-2 text-sm hover:bg-gray-50" onClick={() => props.onOpenAction?.(alert.actionKey)}>{alert.actionLabel}</button>
                </div>
              ))}
            </div>
          </Panel>
        </section>

        <section className="mt-4"><TraceSummaryCard envelope={props.envelope ?? null} traceSummary={traceSummary} dispatch={props.dispatch ?? null} /></section>
        <section className="mt-4"><ReplayTimeline envelope={props.envelope ?? null} traceSummary={traceSummary} messages={props.realtime.messages} selectedMessageId={props.selectedMessageId} onSelectMessage={props.onSelectMessage} /></section>
        <section className="mt-4"><DecisionPathPanel envelope={props.envelope ?? null} auditSummary={auditSummary} dispatch={props.dispatch ?? null} /></section>
        <section className="mt-4"><AuditTrailPanel envelope={props.envelope ?? null} auditSummary={auditSummary} realtime={props.realtime} /></section>
      </main>

      <aside className="space-y-4 rounded-2xl border bg-white p-4 shadow-sm">
        <RecoveryPanel memory={props.memory} />
        <RelatedSystemsPanel />
        <EventDetailDrawer selectedMessage={selectedMessage} selectedMessageId={props.selectedMessageId} />
      </aside>
    </div>
  );
}

function StatCard({ label, value }: { label: string; value: string }) {
  return (
    <div className="rounded-2xl border bg-white p-4 shadow-sm">
      <div className="text-sm text-gray-500">{label}</div>
      <div className="mt-2 text-2xl font-bold text-gray-900">{value}</div>
    </div>
  );
}

function Panel({ title, children }: { title: string; children: React.ReactNode }) {
  return (
    <section className="rounded-2xl border p-4">
      <h3 className="font-semibold">{title}</h3>
      <div className="mt-3">{children}</div>
    </section>
  );
}

function TraceSummaryCard({ envelope, traceSummary, dispatch }: { envelope: LinkedSummaryEnvelope | null; traceSummary: { trace_id?: string; event_count?: number; last_event?: string; task?: string } | null; dispatch: DispatchResult | null }) {
  const summary = traceSummary ?? envelope?.linked_summaries?.primary ?? null;
  return (
    <section className="rounded-2xl border p-4">
      <h3 className="font-semibold">Trace 概览</h3>
      {summary ? (
        <div className="mt-3 space-y-2 text-sm text-gray-600">
          <div>资源类型：{envelope?.resource_type ?? "-"}</div>
          <div>资源 ID：{envelope?.resource_id ?? "-"}</div>
          <div>Trace ID：{summary.trace_id ?? dispatch?.trace_id ?? "-"}</div>
          <div>事件数：{summary.event_count ?? dispatch?.suggestion.confidence ?? 0}</div>
          <div>最后事件：{summary.last_event ?? "-"}</div>
        </div>
      ) : dispatch ? (
        <div className="mt-3 space-y-2 text-sm text-gray-600">
          <div>状态：{dispatch.status}</div>
          <div>Trace ID：{dispatch.trace_id ?? "-"}</div>
          <div>生成时间：{dispatch.generated_at}</div>
          <div>置信度：{Math.round(dispatch.suggestion.confidence * 100)}%</div>
        </div>
      ) : (
        <div className="mt-3 text-sm text-gray-500">暂无调度数据</div>
      )}
    </section>
  );
}

function ReplayTimeline({ envelope, traceSummary, messages, selectedMessageId, onSelectMessage }: { envelope: LinkedSummaryEnvelope | null; traceSummary: { trace_id?: string; event_count?: number; last_event?: string; task?: string } | null; messages: RealtimeMessage[]; selectedMessageId?: string | null; onSelectMessage?: (messageId: string) => void; }) {
  return (
    <section className="rounded-2xl border p-4">
      <div className="flex items-center justify-between">
        <h3 className="font-semibold">消息回放</h3>
        <div className="text-xs text-gray-500">共 {messages.length} 条</div>
      </div>
      <div className="mt-3 space-y-3">
        {messages.length ? messages.map((msg) => {
          const isSelected = selectedMessageId === msg.message_id;
          return (
            <button
              key={msg.message_id}
              className={`w-full rounded-xl border px-3 py-2 text-left transition hover:bg-gray-50 ${isSelected ? "border-blue-500 bg-blue-50" : ""}`}
              onClick={() => onSelectMessage?.(msg.message_id)}
            >
              <div className="flex items-center justify-between text-xs text-gray-500">
                <span>{msg.sender_name}</span>
                <span>{msg.created_at}</span>
              </div>
              <div className="mt-2 text-sm">{msg.content}</div>
              <div className="mt-2 flex flex-wrap gap-2 text-[11px] text-gray-500">
                <span className="rounded-full bg-gray-100 px-2 py-1">{msg.message_type}</span>
                {msg.room_id ? <span className="rounded-full bg-gray-100 px-2 py-1">room:{msg.room_id}</span> : null}
                {msg.conversation_id ? <span className="rounded-full bg-gray-100 px-2 py-1">conv:{msg.conversation_id}</span> : null}
              </div>
            </button>
          );
        }) : (
          <div className="text-sm text-gray-500">暂无回放消息</div>
        )}
      </div>
    </section>
  );
}

function DecisionPathPanel({ envelope, auditSummary, dispatch }: { envelope: LinkedSummaryEnvelope | null; auditSummary: { count?: number; by_action?: Record<string, number>; by_resource_type?: Record<string, number>; by_outcome?: Record<string, number> } | null; dispatch: DispatchResult | null }) {
  const actionSummary = auditSummary?.by_action ? Object.entries(auditSummary.by_action).slice(0, 4) : [];
  return (
    <section className="rounded-2xl border p-4">
      <h3 className="font-semibold">决策路径</h3>
      <div className="mt-3 space-y-2">
        {dispatch?.suggestion.decision_path?.length ? dispatch.suggestion.decision_path.map((step) => (
          <div key={`${step.step}-${step.name}`} className="rounded-xl border px-3 py-2 text-sm">
            <div className="font-medium">{step.name}</div>
            <div className="text-xs text-gray-500">{step.reason}</div>
            <div className="mt-1 text-xs text-gray-400">置信度：{step.confidence}</div>
          </div>
        )) : (
          <div className="text-sm text-gray-500">暂无决策路径</div>
        )}
        {actionSummary.length ? (
          <div className="mt-3 rounded-xl border bg-gray-50 p-3 text-xs text-gray-600">
            <div className="font-medium text-gray-700">审计动作分布</div>
            <div className="mt-2 space-y-1">
              {actionSummary.map(([action, count]) => (
                <div key={action} className="flex items-center justify-between gap-2">
                  <span>{action}</span>
                  <span>{count}</span>
                </div>
              ))}
            </div>
          </div>
        ) : null}
      </div>
    </section>
  );
}

function AuditTrailPanel({ envelope, auditSummary, realtime }: { envelope: LinkedSummaryEnvelope | null; auditSummary: { count?: number; by_action?: Record<string, number>; by_resource_type?: Record<string, number>; by_outcome?: Record<string, number> } | null; realtime: RealtimeSnapshot }) {
  return (
    <section className="rounded-2xl border p-4">
      <h3 className="font-semibold">审计轨迹</h3>
      <div className="mt-3 grid gap-2 md:grid-cols-3 text-sm text-gray-600">
        <div className="rounded-xl border px-3 py-2">会话数：{realtime.conversations.length}</div>
        <div className="rounded-xl border px-3 py-2">消息数：{realtime.messages.length}</div>
        <div className="rounded-xl border px-3 py-2">在线智能体：{realtime.online_agents.length}</div>
      </div>
    </section>
  );
}

function RecoveryPanel({ memory }: { memory: MemorySnapshot }) {
  return (
    <section>
      <h3 className="font-semibold">恢复建议</h3>
      <div className="mt-3 rounded-xl border p-3 text-sm text-gray-600">
        记忆引用数：{memory.memory_refs.length}
        <br />
        层级统计：{Object.keys(memory.layer_totals).length}
      </div>
    </section>
  );
}

function RelatedSystemsPanel() {
  const systems = ["运行控制", "工具中心", "记忆中心", "组织权限中心", "全局导航"];
  return (
    <section>
      <h3 className="font-semibold">关联系统</h3>
      <div className="mt-3 space-y-2">
        {systems.map((item) => (
          <div key={item} className="rounded-xl border px-3 py-2 text-sm text-gray-600">
            {item}
          </div>
        ))}
      </div>
    </section>
  );
}

function EventDetailDrawer({ selectedMessageId, selectedMessage }: { selectedMessageId?: string | null; selectedMessage: RealtimeMessage | null; }) {
  return (
    <section>
      <h3 className="font-semibold">事件详情</h3>
      <div className="mt-3 rounded-xl border p-3 text-sm text-gray-600">
        {selectedMessage ? (
          <div className="space-y-2">
            <div className="font-medium">{selectedMessage.sender_name}</div>
            <div className="text-xs text-gray-500">{selectedMessage.created_at}</div>
            <div>{selectedMessage.content}</div>
            <div className="text-xs text-gray-400">ID：{selectedMessageId}</div>
          </div>
        ) : (
          <div className="text-gray-500">暂未选中事件</div>
        )}
      </div>
    </section>
  );
}
