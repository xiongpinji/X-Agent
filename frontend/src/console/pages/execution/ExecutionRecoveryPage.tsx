import React from "react";

export type ExecutionRecoveryPageProps = {
  runId?: string;
  failure?: { status?: string; level?: string; currentStep?: string; canRetry?: boolean } | null;
  reasons?: Array<{ title: string; detail: string; level: string }>;
  recoverySummary?: { before?: string; after?: string; suggestion?: string } | null;
  recommendation?: string;
  onBack?: () => void;
  onOpenDetail?: (runId: string) => void;
  onOpenAudit?: (runId: string) => void;
};

type ExecutionRecoveryApiResponse = {
  resource_type: string;
  resource_id: string;
  primary: {
    run_id?: string;
    status?: string;
    failure_level?: string;
    failure_reason?: string;
    current_step?: string;
    can_retry?: boolean;
    can_rollback?: boolean;
    needs_human?: boolean;
    retry_priority?: string;
    recovery_mode?: string;
  };
  linked_summaries: {
    workflow?: { summary?: { title?: string } | null; data?: Record<string, unknown> | null };
    dispatch?: { summary?: { title?: string } | null; data?: Record<string, unknown> | null };
    messages?: { summary?: { title?: string } | null; data?: Record<string, unknown> | null };
    tools?: { summary?: { title?: string } | null; data?: Record<string, unknown> | null };
    audit?: { summary?: { title?: string } | null; data?: Record<string, unknown> | null };
    memory?: { summary?: { title?: string } | null; data?: Record<string, unknown> | null };
    recovery?: { summary?: { title?: string } | null; data?: Record<string, unknown> | null };
  };
};

const demoReasons = [
  {
    title: "外部工具超时",
    detail: "工具调用等待超过阈值，当前最适合优先重试。",
    level: "中",
  },
  {
    title: "输入参数缺失",
    detail: "上游节点未提供完整参数，需要人工确认。",
    level: "高",
  },
];

export function ExecutionRecoveryPage(props: ExecutionRecoveryPageProps) {
  const runId = props.runId ?? "run-003";
  const [apiData, setApiData] = React.useState<ExecutionRecoveryApiResponse | null>(null);

  React.useEffect(() => {
    let cancelled = false;
    const load = async () => {
      try {
        const response = await fetch(`/api/v1/execution-control/recovery/${encodeURIComponent(runId)}`, { method: "GET", headers: { "Content-Type": "application/json" } });
        if (!response.ok) return;
        const payload = (await response.json()) as ExecutionRecoveryApiResponse;
        if (!cancelled) setApiData(payload);
      } catch (error) {
        console.warn("Failed to load execution recovery", error);
      }
    };
    void load();
    return () => {
      cancelled = true;
    };
  }, [runId]);

  const failure =
    props.failure ??
    (apiData
      ? {
          status: apiData.primary.status,
          level: apiData.primary.failure_level,
          currentStep: apiData.primary.current_step,
          canRetry: apiData.primary.can_retry,
        }
      : { status: "可恢复", level: "中", currentStep: "工具执行步骤", canRetry: true });

  const reasons = props.reasons ?? demoReasons;
  const recoverySummary = props.recoverySummary ?? { before: "失败", after: "待重试", suggestion: "先重试，再确认外部依赖。" };
  const recommendation = props.recommendation ?? (apiData?.primary.failure_reason ? `恢复建议：${apiData.primary.failure_reason}` : "恢复建议：优先检查外部工具是否恢复。");
  const retryPriority = apiData?.primary.retry_priority ?? "中";
  const recoveryMode = apiData?.primary.recovery_mode ?? "automatic-first";

  return (
    <div className="space-y-4">
      <section className="rounded-2xl border bg-white p-4 shadow-sm">
        <div className="flex items-start justify-between gap-3">
          <div>
            <h2 className="text-lg font-semibold">失败恢复</h2>
            <p className="text-sm text-gray-500">任务 {runId} 的恢复与重试决策。</p>
          </div>
          <div className="flex gap-2">
            <button className="rounded-lg border px-3 py-2 text-sm hover:bg-gray-50" onClick={props.onBack}>返回总览</button>
            <button className="rounded-lg border px-3 py-2 text-sm hover:bg-gray-50" onClick={() => props.onOpenDetail?.(runId)}>查看详情</button>
          </div>
        </div>
      </section>

      <section className="grid gap-4 xl:grid-cols-[minmax(0,1fr)_360px]">
        <div className="space-y-4">
          <Panel title="失败摘要">
            <div className="grid gap-3 md:grid-cols-2">
              <Info label="失败状态" value={failure.status ?? "-"} />
              <Info label="错误等级" value={failure.level ?? "-"} />
              <Info label="当前卡点" value={failure.currentStep ?? "-"} />
              <Info label="是否可重试" value={failure.canRetry ? "是" : "否"} />
              <Info label="重试优先级" value={retryPriority} />
              <Info label="恢复模式" value={recoveryMode} />
            </div>
          </Panel>

          <Panel title="失败原因">
            <div className="space-y-3">
              {reasons.map((item) => (
                <div key={item.title} className="rounded-xl border px-3 py-3">
                  <div className="flex items-center justify-between gap-3">
                    <div className="font-medium">{item.title}</div>
                    <div className="text-xs text-gray-500">等级 {item.level}</div>
                  </div>
                  <div className="mt-1 text-sm text-gray-600">{item.detail}</div>
                </div>
              ))}
            </div>
          </Panel>

          <Panel title="恢复结果">
            <div className="space-y-2 text-sm text-gray-600">
              <div>恢复前状态：{recoverySummary.before ?? "-"}</div>
              <div>恢复后状态：{recoverySummary.after ?? "-"}</div>
              <div>建议动作：{recoverySummary.suggestion ?? "-"}</div>
            </div>
          </Panel>
        </div>

        <aside className="space-y-4">
          <Panel title="恢复建议">
            <div className="space-y-2 text-sm text-gray-600">
              <div>{recommendation}</div>
              <div>1. 若问题持续，切换为人工确认。</div>
              <div>2. 保留审计记录，方便复盘。</div>
            </div>
          </Panel>

          <Panel title="可执行动作">
            <div className="grid gap-2">
              <button className="rounded-xl border px-3 py-2 text-left hover:bg-gray-50">重新执行</button>
              <button className="rounded-xl border px-3 py-2 text-left hover:bg-gray-50">回滚到上一节点</button>
              <button className="rounded-xl border px-3 py-2 text-left hover:bg-gray-50" onClick={() => props.onOpenAudit?.(runId)}>打开审计</button>
            </div>
          </Panel>
        </aside>
      </section>
    </div>
  );
}

function Info({ label, value }: { label: string; value: string }) {
  return (
    <div className="rounded-xl border bg-gray-50 p-3">
      <div className="text-xs text-gray-500">{label}</div>
      <div className="mt-1 font-medium text-gray-900">{value}</div>
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
