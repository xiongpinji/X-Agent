import React from "react";
import { getAuthHeaders } from "../../../services/authHeaders";

export type ExecutionDetailPageProps = {
  runId?: string;
  summary?: { name?: string; status?: string; triggerSource?: string; owner?: string } | null;
  steps?: Array<{ name: string; status: string; duration: string; result: string }>;
  toolCalls?: Array<{ tool: string; time: string; status: string; cost: string }>;
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

const demoSteps = [
  { name: "接收任务", status: "done", duration: "2s", result: "已进入队列" },
  { name: "生成计划", status: "done", duration: "8s", result: "已完成规划" },
  { name: "调用工具", status: "running", duration: "18s", result: "等待工具返回" },
  { name: "汇总结果", status: "pending", duration: "-", result: "未开始" },
];

const demoToolCalls = [
  { tool: "dispatch", time: "10:12", status: "success", cost: "120ms" },
  { tool: "memory.read", time: "10:13", status: "success", cost: "32ms" },
  { tool: "tool.execute", time: "10:14", status: "running", cost: "pending" },
];

export function ExecutionDetailPage(props: ExecutionDetailPageProps) {
  const runId = props.runId ?? "run-001";
  const [apiData, setApiData] = React.useState<ExecutionDetailApiResponse | null>(null);

  React.useEffect(() => {
    let cancelled = false;
    const load = async () => {
      try {
        const response = await fetch(`/api/v1/execution-control/detail/${encodeURIComponent(runId)}`, { method: "GET", headers: { "Content-Type": "application/json", ...getAuthHeaders() } });
        if (!response.ok) return;
        const payload = (await response.json()) as ExecutionDetailApiResponse;
        if (!cancelled) setApiData(payload);
      } catch (error) {
        console.warn("Failed to load execution detail", error);
      }
    };
    void load();
    return () => {
      cancelled = true;
    };
  }, [runId]);

  const summary =
    props.summary ??
    (apiData
      ? {
          name: apiData.primary.task_name,
          status: apiData.primary.status,
          triggerSource: apiData.primary.trigger_source,
          owner: apiData.primary.owner,
        }
      : { name: "工具调用工作流", status: "运行中", triggerSource: "工作流调度", owner: "短剧导演" });
  const currentStepLabel = apiData?.primary.current_step_label ?? "当前步骤";
  const progressLabel = apiData?.primary.progress_label ?? `${apiData?.primary.progress ?? 72}%`;
  const riskLevel = apiData?.primary.risk_level ?? "medium";

  const steps = props.steps ?? demoSteps;
  const toolCalls = props.toolCalls ?? demoToolCalls;
  const linkedTitles =
    props.linkedTitles ??
    (apiData
      ? {
          messages: apiData.linked_summaries.messages?.summary?.title,
          audit: apiData.linked_summaries.audit?.summary?.title,
          memory: apiData.linked_summaries.memory?.summary?.title,
        }
      : { messages: "关联消息", audit: "审计记录", memory: "记忆引用" });

  return (
    <div className="space-y-4">
      <section className="rounded-2xl border bg-white p-4 shadow-sm">
        <div className="flex items-start justify-between gap-3">
          <div>
            <h2 className="text-lg font-semibold">执行详情</h2>
            <p className="text-sm text-gray-500">任务 {runId} 的执行剖面。</p>
          </div>
          <div className="flex gap-2">
            <button className="rounded-lg border px-3 py-2 text-sm hover:bg-gray-50" onClick={props.onBack}>返回总览</button>
            <button className="rounded-lg border px-3 py-2 text-sm hover:bg-gray-50" onClick={() => props.onOpenRecovery?.(runId)}>进入恢复</button>
          </div>
        </div>
      </section>

      <section className="grid gap-4 xl:grid-cols-[minmax(0,1fr)_360px]">
        <div className="space-y-4">
          <Panel title="任务摘要">
            <div className="grid gap-3 md:grid-cols-2">
              <Info label="任务名称" value={summary.name ?? "-"} />
              <Info label="当前状态" value={summary.status ?? "-"} />
              <Info label="触发来源" value={summary.triggerSource ?? "-"} />
              <Info label="负责人" value={summary.owner ?? "-"} />
              <Info label={currentStepLabel} value={apiData?.primary.current_step ?? "-"} />
              <Info label="进度" value={progressLabel} />
              <Info label="风险等级" value={riskLevel} />
              <Info label="结果摘要" value={apiData?.primary.result_summary ?? "-"} />
            </div>
          </Panel>

          <Panel title="执行时间线">
            <div className="space-y-3">
              {steps.map((step) => (
                <div key={step.name} className="rounded-xl border px-3 py-3">
                  <div className="flex items-center justify-between gap-3">
                    <div className="font-medium">{step.name}</div>
                    <div className="text-xs text-gray-500">{step.duration}</div>
                  </div>
                  <div className="mt-1 text-sm text-gray-600">{step.result}</div>
                  <div className="mt-2 text-xs text-blue-600">状态：{step.status}</div>
                </div>
              ))}
            </div>
          </Panel>

          <Panel title="消息 / 审计 / 记忆引用">
            <div className="grid gap-3 md:grid-cols-3">
              <LinkCard title={linkedTitles.messages ?? "关联消息"} subtitle="查看执行期间产生的消息事件" onClick={() => props.onOpenMessages?.(runId)} />
              <LinkCard title={linkedTitles.audit ?? "审计记录"} subtitle="查看执行链路审计" onClick={() => props.onOpenAudit?.(runId)} />
              <LinkCard title={linkedTitles.memory ?? "记忆引用"} subtitle="查看关联记忆和证据" onClick={() => props.onOpenMemory?.(runId)} />
            </div>
          </Panel>
        </div>

        <aside className="space-y-4">
          <Panel title="工具调用">
            <div className="space-y-2">
              {toolCalls.map((call) => (
                <div key={`${call.tool}-${call.time}`} className="rounded-xl border px-3 py-3">
                  <div className="flex items-center justify-between gap-3">
                    <div className="font-medium">{call.tool}</div>
                    <div className="text-xs text-gray-500">{call.time}</div>
                  </div>
                  <div className="mt-1 text-xs text-gray-600">状态：{call.status}</div>
                  <div className="mt-1 text-xs text-gray-600">耗时：{call.cost}</div>
                </div>
              ))}
            </div>
          </Panel>

          <Panel title="操作区">
            <div className="grid gap-2">
              <button className="rounded-xl border px-3 py-2 text-left hover:bg-gray-50" onClick={() => props.onOpenDispatch?.(runId)}>查看调度建议</button>
              <button className="rounded-xl border px-3 py-2 text-left hover:bg-gray-50" onClick={() => props.onOpenRecovery?.(runId)}>重新进入恢复</button>
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

function LinkCard({ title, subtitle, onClick }: { title: string; subtitle: string; onClick?: () => void }) {
  return (
    <button className="rounded-xl border px-3 py-3 text-left hover:bg-gray-50" onClick={onClick}>
      <div className="font-medium">{title}</div>
      <div className="mt-1 text-xs text-gray-500">{subtitle}</div>
    </button>
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
