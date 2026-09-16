import React from "react";

import { ConsoleReadEmpty, ConsoleReadFailure, ConsoleReadLoading } from "@/console/components/ReadState";
import { useConsoleResource } from "@/console/readResource";

export type ExecutionRecoveryPageProps = {
  /** 要查看的 run。为 null 表示尚未选中 —— 页面不发请求，显示空态。 */
  runId?: string | null;
  failure?: { status?: string; level?: string; currentStep?: string; canRetry?: boolean } | null;
  reasons?: Array<{ title: string; detail: string; level: string }> | null;
  recoverySummary?: { before?: string; after?: string; suggestion?: string } | null;
  recommendation?: string | null;
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

const READ_ACTION = "加载失败恢复信息";

/**
 * 任务失败恢复页。
 *
 * 历史缺陷（读路径 Critical，B1）：加载失败时用硬编码对象兜底 ——
 * `{ status: "可恢复", level: "中", currentStep: "工具执行步骤", canRetry: true }`
 * 外加 `demoReasons`（「外部工具超时 / 当前最适合优先重试」）与
 * 「先重试，再确认外部依赖」。用户看到的是一套**看起来像真的处置指引**，
 * 而该 run 的真实状态从未加载成功 —— 会据此以为「重试就行」，
 * 放弃真正需要的升级处置。
 *
 * 现在：加载失败 → 失败态（可重试）；加载成功但字段缺失 → 如实显示「-」；
 * 确实没有失败原因记录 → 空态。三条路径互相可判别。
 */
export function ExecutionRecoveryPage(props: ExecutionRecoveryPageProps) {
  const runId = props.runId ?? null;
  const resource = useConsoleResource<ExecutionRecoveryApiResponse>(
    runId === null ? null : `/api/v1/execution-control/recovery/${encodeURIComponent(runId)}`,
    READ_ACTION,
    [runId],
  );
  const apiData = resource.data;
  const primary = apiData?.primary;

  // props 覆盖优先（测试 / 嵌入场景）。没有真实来源时一律留 null —— 绝不兜底成
  // 一个看起来合理的业务对象。
  const failure =
    props.failure ??
    (primary
      ? {
          status: primary.status,
          level: primary.failure_level,
          currentStep: primary.current_step,
          canRetry: primary.can_retry,
        }
      : null);

  const reasons = props.reasons ?? null;
  const recoverySummary = props.recoverySummary ?? null;
  const failureReason = primary?.failure_reason ?? null;
  const retryPriority = primary?.retry_priority;
  const recoveryMode = primary?.recovery_mode;

  const openDetail = runId === null ? undefined : () => props.onOpenDetail?.(runId);

  const header = (
    <section className="console-section">
      <div className="flex items-start justify-between gap-3">
        <div>
          <h2 className="text-lg font-semibold">失败恢复</h2>
          <p className="text-sm text-gray-500">
            {runId === null ? "尚未选择要查看的任务。" : `任务 ${runId} 的恢复与重试决策。`}
          </p>
        </div>
        <div className="flex gap-2">
          <button className="border px-3 py-2 text-sm hover:bg-gray-50" onClick={props.onBack}>
            返回总览
          </button>
          {openDetail && (
            <button className="border px-3 py-2 text-sm hover:bg-gray-50" onClick={openDetail}>
              查看详情
            </button>
          )}
        </div>
      </div>
    </section>
  );

  if (runId === null) {
    return (
      <div className="space-y-4">
        {header}
        <ConsoleReadEmpty title="未选择执行任务" description="请从运行控制页选择一个任务后再查看恢复信息。" />
      </div>
    );
  }

  // 失败 / 加载优先于一切：数据源没成功，就不能渲染任何结论。
  if (resource.status === "loading" || resource.status === "idle") {
    return (
      <div className="space-y-4">
        {header}
        <ConsoleReadLoading action={READ_ACTION} />
      </div>
    );
  }

  if (resource.status === "failed") {
    return (
      <div className="space-y-4">
        {header}
        <ConsoleReadFailure action={READ_ACTION} message={resource.error} onRetry={resource.reload} />
      </div>
    );
  }

  return (
    <div className="space-y-4">
      {header}

      <section className="grid gap-4 xl:grid-cols-[minmax(0,1fr)_360px]">
        <div className="space-y-4">
          <Panel title="失败摘要">
            <div className="grid gap-3 md:grid-cols-2">
              <Info label="失败状态" value={failure?.status ?? "-"} />
              <Info label="错误等级" value={failure?.level ?? "-"} />
              <Info label="当前卡点" value={failure?.currentStep ?? "-"} />
              <Info label="是否可重试" value={failure ? (failure.canRetry ? "是" : "否") : "-"} />
              <Info label="是否可回滚" value={primary?.can_rollback != null ? (primary.can_rollback ? "是" : "否") : "-"} />
              <Info label="是否需要人工" value={primary?.needs_human != null ? (primary.needs_human ? "是" : "否") : "-"} />
              <Info label="重试优先级" value={retryPriority ?? "-"} />
              <Info label="恢复模式" value={recoveryMode ?? "-"} />
            </div>
          </Panel>

          <Panel title="失败原因">
            {reasons && reasons.length > 0 ? (
              <div className="space-y-3">
                {reasons.map((item) => (
                  <div key={item.title} className="border-b px-3 py-3">
                    <div className="flex items-center justify-between gap-3">
                      <div className="font-medium">{item.title}</div>
                      {item.level ? <div className="text-xs text-gray-500">等级 {item.level}</div> : null}
                    </div>
                    {item.detail ? <div className="mt-1 text-sm text-gray-600">{item.detail}</div> : null}
                  </div>
                ))}
              </div>
            ) : failureReason ? (
              <div className="border-b px-3 py-3">
                <div className="font-medium">{failureReason}</div>
                <div className="mt-1 text-xs text-gray-500">等级 {failure?.level ?? "-"}</div>
              </div>
            ) : (
              <ConsoleReadEmpty title="暂无失败原因记录" description="后端没有返回该任务的失败原因明细。" />
            )}
          </Panel>

          <Panel title="恢复结果">
            {recoverySummary ? (
              <div className="space-y-2 text-sm text-gray-600">
                <div>恢复前状态：{recoverySummary.before ?? "-"}</div>
                <div>恢复后状态：{recoverySummary.after ?? "-"}</div>
                <div>建议动作：{recoverySummary.suggestion ?? "-"}</div>
              </div>
            ) : (
              <ConsoleReadEmpty title="暂无恢复结果" description="后端未返回恢复前后状态。" />
            )}
          </Panel>
        </div>

        <aside className="space-y-4">
          <Panel title="恢复建议">
            <div className="space-y-2 text-sm text-gray-600">
              <div>{props.recommendation ?? "后端未提供恢复建议。"}</div>
            </div>
          </Panel>

          <Panel title="可执行动作">
            <div className="grid gap-2">
              <button className="border-b px-3 py-2 text-left hover:bg-gray-50">重新执行</button>
              <button className="border-b px-3 py-2 text-left hover:bg-gray-50">回滚到上一节点</button>
              <button
                className="border-b px-3 py-2 text-left hover:bg-gray-50"
                onClick={() => props.onOpenAudit?.(runId)}
              >
                打开审计
              </button>
            </div>
          </Panel>
        </aside>
      </section>
    </div>
  );
}

function Info({ label, value }: { label: string; value: string }) {
  return (
    <div className="flex items-baseline justify-between gap-3 border-b py-2">
      <div className="text-xs text-gray-500">{label}</div>
      <div className="font-data font-medium text-gray-900">{value}</div>
    </div>
  );
}

function Panel({ title, children }: { title: string; children: React.ReactNode }) {
  return (
    <section className="console-section">
      <h3 className="text-base font-semibold text-gray-900">{title}</h3>
      <div className="mt-3">{children}</div>
    </section>
  );
}
