import React from "react";

import { ConsoleReadEmpty, ConsoleReadFailure, ConsoleReadLoading } from "@/console/components/ReadState";
import { useConsoleResource } from "@/console/readResource";

export type ExecutionDetailPageProps = {
  /** 要查看的 run。为 null 表示尚未选中 —— 页面不发请求，显示空态。 */
  runId?: string | null;
  summary?: { name?: string; status?: string; triggerSource?: string; owner?: string } | null;
  steps?: Array<{ name: string; status: string; duration: string; result: string }> | null;
  toolCalls?: Array<{ tool: string; time: string; status: string; cost: string }> | null;
  linkedTitles?: { messages?: string; audit?: string; memory?: string } | null;
  onBack?: () => void;
  onOpenRecovery?: (runId: string) => void;
  onOpenAudit?: (runId: string) => void;
  onOpenDispatch?: (runId: string) => void;
  onOpenMessages?: (runId: string) => void;
  onOpenMemory?: (runId: string) => void;
};

type ExecutionDetailApiResponse = {
  resource_type: string;
  resource_id: string;
  primary: {
    run_id?: string;
    task_name?: string;
    status?: string;
    trigger_source?: string;
    owner?: string;
    current_step?: string;
    current_step_label?: string;
    progress?: number;
    progress_label?: string;
    result_summary?: string;
    risk_level?: string;
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

const READ_ACTION = "加载执行详情";

/**
 * 执行详情。
 *
 * 历史缺陷（读路径 Critical，B1）：`props.steps ?? demoSteps` / `props.summary ??
 * { name: "工具调用工作流", status: "运行中", ... }` / `?? 72%` / `?? "medium"`。
 * 而 selector 又通过 props 注入了同一批硬编码值 ⇒ 页面 fetch 到的真实数据被静默
 * 丢弃，用户看到的是**一套看起来完全合理的执行剖面**，无从分辨真假。
 *
 * 现在：失败 → 失败态（可重试）；成功但字段缺失 → 如实「-」；确实没有明细 → 空态。
 */
export function ExecutionDetailPage(props: ExecutionDetailPageProps) {
  const runId = props.runId ?? null;
  const resource = useConsoleResource<ExecutionDetailApiResponse>(
    runId === null ? null : `/api/v1/execution-control/detail/${encodeURIComponent(runId)}`,
    READ_ACTION,
    [runId],
  );
  const apiData = resource.data;

  // props 覆盖优先（测试 / 嵌入场景）。没有真实来源时一律留 null —— 绝不兜底成
  // 一个看起来合理的业务对象。
  const summary =
    props.summary ??
    (apiData
      ? {
          name: apiData.primary.task_name,
          status: apiData.primary.status,
          triggerSource: apiData.primary.trigger_source,
          owner: apiData.primary.owner,
        }
      : null);
  const steps = props.steps ?? null;
  const toolCalls = props.toolCalls ?? null;
  const linkedTitles =
    props.linkedTitles ??
    (apiData
      ? {
          messages: apiData.linked_summaries.messages?.summary?.title,
          audit: apiData.linked_summaries.audit?.summary?.title,
          memory: apiData.linked_summaries.memory?.summary?.title,
        }
      : null);

  const currentStepLabel = apiData?.primary.current_step_label ?? "当前步骤";
  const progressLabel =
    apiData?.primary.progress_label ??
    (apiData?.primary.progress != null ? `${apiData.primary.progress}%` : null);
  const riskLevel = apiData?.primary.risk_level ?? null;

  // 头部在「未选中」分支里也要用，所以在这里就把 runId 收窄掉，
  // 避免闭包里残留 `string | null`。
  const openRecovery = runId === null ? undefined : () => props.onOpenRecovery?.(runId);

  const header = (
    <section className="console-section">
      <div className="flex items-start justify-between gap-3">
        <div>
          <h2 className="text-lg font-semibold">执行详情</h2>
          <p className="text-sm text-gray-500">
            {runId === null ? "尚未选择要查看的任务。" : `任务 ${runId} 的执行剖面。`}
          </p>
        </div>
        <div className="flex gap-2">
          <button className="border px-3 py-2 text-sm hover:bg-gray-50" onClick={props.onBack}>
            返回总览
          </button>
          {openRecovery && (
            <button className="border px-3 py-2 text-sm hover:bg-gray-50" onClick={openRecovery}>
              进入恢复
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
        <ConsoleReadEmpty title="未选择执行任务" description="请从运行控制页选择一个任务后再查看执行详情。" />
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
          <Panel title="任务摘要">
            <div className="grid gap-3 md:grid-cols-2">
              <Info label="任务名称" value={summary?.name ?? "-"} />
              <Info label="当前状态" value={summary?.status ?? "-"} />
              <Info label="触发来源" value={summary?.triggerSource ?? "-"} />
              <Info label="负责人" value={summary?.owner ?? "-"} />
              <Info label={currentStepLabel} value={apiData?.primary.current_step ?? "-"} />
              <Info label="进度" value={progressLabel ?? "-"} />
              <Info label="风险等级" value={riskLevel ?? "-"} />
              <Info label="结果摘要" value={apiData?.primary.result_summary ?? "-"} />
            </div>
          </Panel>

          <Panel title="执行时间线">
            {steps && steps.length > 0 ? (
              <div className="space-y-3">
                {steps.map((step) => (
                  <div key={step.name} className="border-b px-3 py-3">
                    <div className="flex items-center justify-between gap-3">
                      <div className="font-medium">{step.name}</div>
                      <div className="text-xs text-gray-500">{step.duration}</div>
                    </div>
                    <div className="mt-1 text-sm text-gray-600">{step.result}</div>
                    <div className="mt-2 text-xs text-blue-600">状态：{step.status}</div>
                  </div>
                ))}
              </div>
            ) : (
              <ConsoleReadEmpty title="暂无执行步骤明细" description="后端 detail 接口未返回步骤列表。" />
            )}
          </Panel>

          <Panel title="消息 / 审计 / 记忆引用">
            <div className="grid gap-3">
              <LinkCard
                title={linkedTitles?.messages ?? "关联消息"}
                subtitle="查看执行期间产生的消息事件"
                onClick={() => props.onOpenMessages?.(runId)}
              />
              <LinkCard
                title={linkedTitles?.audit ?? "审计记录"}
                subtitle="查看执行链路审计"
                onClick={() => props.onOpenAudit?.(runId)}
              />
              <LinkCard
                title={linkedTitles?.memory ?? "记忆引用"}
                subtitle="查看关联记忆和证据"
                onClick={() => props.onOpenMemory?.(runId)}
              />
            </div>
          </Panel>
        </div>

        <aside className="space-y-4">
          <Panel title="工具调用">
            {toolCalls && toolCalls.length > 0 ? (
              <div className="space-y-2">
                {toolCalls.map((call) => (
                  <div key={`${call.tool}-${call.time}`} className="border-b px-3 py-3">
                    <div className="flex items-center justify-between gap-3">
                      <div className="font-medium">{call.tool}</div>
                      <div className="text-xs text-gray-500">{call.time}</div>
                    </div>
                    <div className="mt-1 text-xs text-gray-600">状态：{call.status}</div>
                    <div className="mt-1 text-xs text-gray-600">耗时：{call.cost}</div>
                  </div>
                ))}
              </div>
            ) : (
              <ConsoleReadEmpty title="暂无工具调用明细" description="后端 detail 接口未返回工具调用列表。" />
            )}
          </Panel>

          <Panel title="操作区">
            <div className="grid gap-2">
              <button className="border-b px-3 py-2 text-left hover:bg-gray-50" onClick={() => props.onOpenDispatch?.(runId)}>
                查看调度建议
              </button>
              <button className="border-b px-3 py-2 text-left hover:bg-gray-50" onClick={() => props.onOpenRecovery?.(runId)}>
                重新进入恢复
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

function LinkCard({ title, subtitle, onClick }: { title: string; subtitle: string; onClick?: () => void }) {
  return (
    <button className="border-b px-3 py-3 text-left hover:bg-gray-50" onClick={onClick}>
      <div className="font-medium">{title}</div>
      <div className="mt-1 text-xs text-gray-500">{subtitle}</div>
    </button>
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
