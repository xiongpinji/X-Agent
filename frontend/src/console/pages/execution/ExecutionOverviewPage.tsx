import React from "react";

export type ExecutionOverviewPageProps = {
  resourceType?: string;
  resourceId?: string;
  activeRuns?: number;
  pendingRuns?: number;
  failedRuns?: number;
  completedRuns?: number;
  interventionCount?: number;
  riskLevel?: string;
  dispatch?: DispatchResult | null;
  executionPlan?: Record<string, unknown> | null;
  recommendations?: Array<{ action: string; reason: string; confidence: string }>;
  linkedDispatchSummary?: { summary?: { title?: string } | null; data?: Record<string, unknown> | null } | null;
  linkedExecutionSummary?: { summary?: { title?: string } | null; data?: Record<string, unknown> | null } | null;
  linkedAuditSummary?: { summary?: { title?: string } | null; data?: Record<string, unknown> | null } | null;
  linkedMessagesSummary?: { summary?: { title?: string } | null; data?: Record<string, unknown> | null } | null;
  onOpenDetail?: (runId: string) => void;
  onOpenRecovery?: (runId: string) => void;
  onOpenDispatch?: (runId: string) => void;
};

const demoActiveRuns = [
  {
    runId: "run-001",
    name: "内容生成任务",
    step: "草稿生成",
    status: "running",
    progress: 72,
    owner: "短剧导演",
  },
  {
    runId: "run-002",
    name: "审计回放任务",
    step: "链路聚合",
    status: "running",
    progress: 48,
    owner: "管理员",
  },
];

const demoFailedRuns = [
  {
    runId: "run-003",
    name: "工具执行任务",
    reason: "tool timeout",
    step: "调用工具",
    recovery: "可重试",
  },
];

const demoRecommendations = [
  {
    action: "优先处理失败任务",
    reason: "当前有任务卡在工具执行步骤",
    confidence: "92%",
  },
  {
    action: "检查最近的审计链",
    reason: "失败任务已经生成可追踪证据",
    confidence: "88%",
  },
];

export function ExecutionOverviewPage(props: ExecutionOverviewPageProps) {
  const activeRuns = props.activeRuns ?? demoActiveRuns.length;
  const pendingRuns = props.pendingRuns ?? 4;
  const failedRuns = props.failedRuns ?? demoFailedRuns.length;
  const completedRuns = props.completedRuns ?? 12;
  const interventionCount = props.interventionCount ?? 1;
  const riskLevel = props.riskLevel ?? "中等";
  const resourceType = props.resourceType ?? "execution_control_overview";
  const resourceId = props.resourceId ?? "-";
  const recommendations = props.recommendations ?? demoRecommendations;

  return (
    <div className="space-y-4">
      <section className="rounded-2xl border bg-white p-4 shadow-sm">
        <div className="text-xs text-gray-500">{resourceType}</div>
        <div className="mt-1 text-sm text-gray-700">资源 ID：{resourceId}</div>
        {props.linkedDispatchSummary?.summary?.title ? <div className="mt-2 text-xs text-gray-500">调度摘要：{props.linkedDispatchSummary.summary.title} · {activeRuns} 个活跃任务</div> : null}
        {props.linkedExecutionSummary?.summary?.title ? <div className="mt-1 text-xs text-gray-500">执行摘要：{props.linkedExecutionSummary.summary.title} · {completedRuns} 个已完成</div> : null}
        {props.linkedAuditSummary?.summary?.title ? <div className="mt-1 text-xs text-gray-500">审计摘要：{props.linkedAuditSummary.summary.title} · {failedRuns} 个失败</div> : null}
        {props.linkedMessagesSummary?.summary?.title ? <div className="mt-1 text-xs text-gray-500">消息摘要：{props.linkedMessagesSummary.summary.title} · {pendingRuns} 个待处理</div> : null}
      </section>

      <section className="grid gap-4 md:grid-cols-2 xl:grid-cols-6">
        <StatCard label="活跃执行" value={String(activeRuns)} />
        <StatCard label="待处理任务" value={String(pendingRuns)} />
        <StatCard label="失败任务" value={String(failedRuns)} />
        <StatCard label="已完成" value={String(completedRuns)} />
        <StatCard label="待人工介入" value={String(interventionCount)} />
        <StatCard label="风险等级" value={riskLevel} />
      </section>

      <section className="grid gap-4 xl:grid-cols-[minmax(0,1fr)_360px]">
        <div className="space-y-4">
          <Panel title="活跃执行">
            <div className="space-y-3">
              {demoActiveRuns.map((run) => (
                <button key={run.runId} className="w-full rounded-xl border px-3 py-3 text-left hover:bg-gray-50" onClick={() => props.onOpenDetail?.(run.runId)}>
                  <div className="flex items-center justify-between gap-3">
                    <div>
                      <div className="font-medium text-gray-900">{run.name}</div>
                      <div className="text-xs text-gray-500">当前步骤：{run.step} · 负责人：{run.owner}</div>
                    </div>
                    <div className="text-xs text-blue-600">{run.progress}%</div>
                  </div>
                  <div className="mt-2 h-2 rounded-full bg-gray-100">
                    <div className="h-2 rounded-full bg-blue-600" style={{ width: `${run.progress}%` }} />
                  </div>
                </button>
              ))}
            </div>
          </Panel>

          <Panel title="失败任务">
            <div className="space-y-3">
              {demoFailedRuns.map((run) => (
                <button key={run.runId} className="w-full rounded-xl border border-red-200 bg-red-50 px-3 py-3 text-left hover:bg-red-100" onClick={() => props.onOpenRecovery?.(run.runId)}>
                  <div className="font-medium text-gray-900">{run.name}</div>
                  <div className="mt-1 text-xs text-gray-600">失败步骤：{run.step} · 原因：{run.reason}</div>
                  <div className="mt-2 text-xs text-red-700">恢复状态：{run.recovery}</div>
                </button>
              ))}
            </div>
          </Panel>
        </div>

        <aside className="space-y-4">
          <Panel title="风险建议">
            <div className="space-y-3">
              {demoRecommendations.map((item) => (
                <button key={item.action} className="w-full rounded-xl border px-3 py-3 text-left hover:bg-gray-50" onClick={() => props.onOpenDispatch?.("execution-control") }>
                  <div className="font-medium">{item.action}</div>
                  <div className="mt-1 text-xs text-gray-500">{item.reason}</div>
                  <div className="mt-2 text-xs text-blue-600">置信度 {item.confidence}</div>
                </button>
              ))}
              <div className="text-xs text-gray-500">当前活跃：{activeRuns} · 失败：{failedRuns} · 待介入：{interventionCount}</div>
            </div>
          </Panel>

          <Panel title="快捷入口">
            <div className="grid gap-2">
              <button className="rounded-xl border px-3 py-2 text-left hover:bg-gray-50" onClick={() => props.onOpenDetail?.("run-001")}>打开执行详情</button>
              <button className="rounded-xl border px-3 py-2 text-left hover:bg-gray-50" onClick={() => props.onOpenRecovery?.("run-003")}>打开失败恢复</button>
              <button className="rounded-xl border px-3 py-2 text-left hover:bg-gray-50" onClick={() => props.onOpenDispatch?.("execution-control")}>打开调度建议</button>
            </div>
          </Panel>
        </aside>
      </section>
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
    <section className="rounded-2xl border bg-white p-4 shadow-sm">
      <h3 className="text-base font-semibold text-gray-900">{title}</h3>
      <div className="mt-3">{children}</div>
    </section>
  );
}
