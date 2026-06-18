import React from "react";
import { getAuthHeaders } from "../../../services/authHeaders";

export type ExecutionDispatchPageProps = {
  runId?: string;
  recommendation?: { action?: string; confidence?: string; risk?: string; requiresConfirmation?: boolean } | null;
  recommendations?: Array<{ action: string; reason: string; confidence: string; risk: string }>;
  reasoning?: { trigger?: string; relatedModules?: string; summary?: string } | null;
  impact?: { expectedResult?: string; sideEffect?: string; scope?: string } | null;
  onBack?: () => void;
  onOpenDetail?: (runId: string) => void;
  onOpenRecovery?: (runId: string) => void;
};

type ExecutionDispatchApiResponse = {
  resource_type: string;
  resource_id: string;
  primary: {
    run_id?: string;
    suggested_action?: string;
    confidence?: number;
    risk_level?: string;
    requires_confirmation?: boolean;
    impact_summary?: string;
    decision_reason?: string;
    recommended_order?: string[];
  };
  linked_summaries: {
    workflow?: { summary?: { title?: string } | null; data?: Record<string, unknown> | null };
    execution?: { summary?: { title?: string } | null; data?: Record<string, unknown> | null };
    dispatch?: { summary?: { title?: string } | null; data?: Record<string, unknown> | null };
    audit?: { summary?: { title?: string } | null; data?: Record<string, unknown> | null };
    messages?: { summary?: { title?: string } | null; data?: Record<string, unknown> | null };
    tools?: { summary?: { title?: string } | null; data?: Record<string, unknown> | null };
  };
};

const demoRecommendations = [
  {
    action: "优先重试工具调用",
    reason: "当前失败集中在外部工具超时，重试收益最高。",
    confidence: "92%",
    risk: "低",
  },
  {
    action: "等待人工确认",
    reason: "当外部依赖不稳定时避免连续自动重试。",
    confidence: "76%",
    risk: "中",
  },
];

export function ExecutionDispatchPage(props: ExecutionDispatchPageProps) {
  const runId = props.runId ?? "execution-control";
  const [apiData, setApiData] = React.useState<ExecutionDispatchApiResponse | null>(null);

  React.useEffect(() => {
    let cancelled = false;
    const load = async () => {
      try {
        const response = await fetch(`/api/v1/execution-control/dispatch/${encodeURIComponent(runId)}`, { method: "GET", headers: { "Content-Type": "application/json", ...getAuthHeaders() } });
        if (!response.ok) return;
        const payload = (await response.json()) as ExecutionDispatchApiResponse;
        if (!cancelled) setApiData(payload);
      } catch (error) {
        console.warn("Failed to load execution dispatch", error);
      }
    };
    void load();
    return () => {
      cancelled = true;
    };
  }, [runId]);

  const recommendation =
    props.recommendation ??
    (apiData
      ? {
          action: apiData.primary.suggested_action,
          confidence: apiData.primary.confidence != null ? `${Math.round(apiData.primary.confidence * 100)}%` : undefined,
          risk: apiData.primary.risk_level,
          requiresConfirmation: apiData.primary.requires_confirmation,
        }
      : { action: "优先重试工具调用", confidence: "92%", risk: "低", requiresConfirmation: false });

  const recommendations = props.recommendations ?? demoRecommendations;
  const reasoning =
    props.reasoning ??
    (apiData
      ? {
          trigger: apiData.linked_summaries.dispatch?.summary?.title ?? "工具超时 / 任务卡住",
          relatedModules: apiData.linked_summaries.workflow?.summary?.title ?? "工作流、消息、审计、记忆",
          summary: apiData.primary.decision_reason ?? apiData.primary.impact_summary ?? "当前失败点集中在单一外部依赖。",
        }
      : { trigger: "工具超时 / 任务卡住", relatedModules: "工作流、消息、审计、记忆", summary: "当前失败点集中在单一外部依赖。" });

  const impact = props.impact ?? { expectedResult: "恢复执行并继续当前任务", sideEffect: "重复执行消耗额外资源", scope: "当前任务及其相关工作流节点" };
  const recommendedOrder = apiData?.primary.recommended_order?.join(" → ") ?? "重试 → 检查依赖 → 恢复执行";

  return (
    <div className="space-y-4">
      <section className="rounded-2xl border bg-white p-4 shadow-sm">
        <div className="flex items-start justify-between gap-3">
          <div>
            <h2 className="text-lg font-semibold">调度建议</h2>
            <p className="text-sm text-gray-500">任务 {runId} 当前的下一步动作建议。</p>
          </div>
          <div className="flex gap-2">
            <button className="rounded-lg border px-3 py-2 text-sm hover:bg-gray-50" onClick={props.onBack}>返回总览</button>
            <button className="rounded-lg border px-3 py-2 text-sm hover:bg-gray-50" onClick={() => props.onOpenDetail?.(runId)}>查看详情</button>
          </div>
        </div>
      </section>

      <section className="grid gap-4 xl:grid-cols-[minmax(0,1fr)_360px]">
        <div className="space-y-4">
          <Panel title="当前建议摘要">
            <div className="grid gap-3 md:grid-cols-2">
              <Info label="建议动作" value={recommendation.action ?? "-"} />
              <Info label="置信度" value={recommendation.confidence ?? "-"} />
              <Info label="风险等级" value={recommendation.risk ?? "-"} />
              <Info label="是否需要确认" value={recommendation.requiresConfirmation ? "是" : "否"} />
              <Info label="决策理由" value={apiData?.primary.decision_reason ?? "-"} />
              <Info label="推荐顺序" value={recommendedOrder} />
            </div>
          </Panel>

          <Panel title="建议列表">
            <div className="space-y-3">
              {recommendations.map((item) => (
                <button key={item.action} className="w-full rounded-xl border px-3 py-3 text-left hover:bg-gray-50" onClick={() => props.onOpenRecovery?.(runId)}>
                  <div className="flex items-center justify-between gap-3">
                    <div className="font-medium text-gray-900">{item.action}</div>
                    <div className="text-xs text-gray-500">{item.risk}</div>
                  </div>
                  <div className="mt-1 text-sm text-gray-600">{item.reason}</div>
                  <div className="mt-2 text-xs text-blue-600">置信度 {item.confidence}</div>
                </button>
              ))}
            </div>
          </Panel>

          <Panel title="决策依据">
            <div className="space-y-2 text-sm text-gray-600">
              <div>触发条件：{reasoning.trigger ?? "-"}</div>
              <div>关联模块：{reasoning.relatedModules ?? "-"}</div>
              <div>推理摘要：{reasoning.summary ?? "-"}</div>
            </div>
          </Panel>
        </div>

        <aside className="space-y-4">
          <Panel title="可执行动作">
            <div className="grid gap-2">
              <button className="rounded-xl border px-3 py-2 text-left hover:bg-gray-50">立即执行</button>
              <button className="rounded-xl border px-3 py-2 text-left hover:bg-gray-50">进入确认</button>
              <button className="rounded-xl border px-3 py-2 text-left hover:bg-gray-50">调整参数</button>
              <button className="rounded-xl border px-3 py-2 text-left hover:bg-gray-50" onClick={() => props.onOpenRecovery?.(runId)}>进入恢复页</button>
            </div>
          </Panel>

          <Panel title="影响评估">
            <div className="space-y-2 text-sm text-gray-600">
              <div>预期结果：{impact.expectedResult ?? "-"}</div>
              <div>潜在副作用：{impact.sideEffect ?? "-"}</div>
              <div>影响范围：{impact.scope ?? "-"}</div>
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
