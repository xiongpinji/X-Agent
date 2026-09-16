import React from "react";

import { ConsoleReadEmpty, ConsoleReadFailure, ConsoleReadLoading } from "@/console/components/ReadState";
import { useConsoleResource } from "@/console/readResource";

export type ExecutionDispatchPageProps = {
  /** 要查看的 run。为 null 表示尚未选中 —— 页面不发请求，显示空态。 */
  runId?: string | null;
  recommendation?: { action?: string; confidence?: string; risk?: string; requiresConfirmation?: boolean } | null;
  recommendations?: Array<{ action: string; reason: string; confidence: string; risk: string }> | null;
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

const READ_ACTION = "加载调度建议";

/**
 * 调度建议页。
 *
 * 历史缺陷（读路径 Critical，B1）：`props.recommendations ?? demoRecommendations`
 * 里是「优先重试工具调用 / 置信度 92%」；`impact` 兜底成
 * `{ expectedResult: "恢复执行并继续当前任务", ... }`；`recommendedOrder` 兜底成
 * `"重试 → 检查依赖 → 恢复执行"`。这些**看起来像系统决策**，实际是常量 ——
 * 用户会据此执行一个从未被评估过的动作。
 *
 * 现在：只呈现后端真实返回的动作 / 置信度 / 顺序；缺失就如实空着。
 */
export function ExecutionDispatchPage(props: ExecutionDispatchPageProps) {
  const runId = props.runId ?? null;
  const resource = useConsoleResource<ExecutionDispatchApiResponse>(
    runId === null ? null : `/api/v1/execution-control/dispatch/${encodeURIComponent(runId)}`,
    READ_ACTION,
    [runId],
  );
  const apiData = resource.data;

  const primary = apiData?.primary;

  const recommendation =
    props.recommendation ??
    (primary
      ? {
          action: primary.suggested_action,
          confidence: primary.confidence != null ? `${Math.round(primary.confidence * 100)}%` : undefined,
          risk: primary.risk_level,
          requiresConfirmation: primary.requires_confirmation,
        }
      : null);

  // 建议列表：后端只回一条 suggested_action，就如实呈现这一条。
  // 不再用 demo 数组凑出「系统给了两条建议」的错觉。
  const recommendations =
    props.recommendations ??
    (primary?.suggested_action
      ? [
          {
            action: primary.suggested_action,
            reason: primary.decision_reason ?? "",
            confidence: primary.confidence != null ? `${Math.round(primary.confidence * 100)}%` : "",
            risk: primary.risk_level ?? "",
          },
        ]
      : null);

  const reasoning =
    props.reasoning ??
    (primary
      ? {
          trigger: undefined,
          relatedModules: apiData?.linked_summaries.workflow?.summary?.title,
          summary: primary.decision_reason ?? primary.impact_summary,
        }
      : null);

  const impact =
    props.impact ??
    (primary?.impact_summary ? { expectedResult: primary.impact_summary } : null);

  const recommendedOrder = primary?.recommended_order?.length ? primary.recommended_order.join(" → ") : null;

  const openRecovery = runId === null ? undefined : () => props.onOpenRecovery?.(runId);
  const openDetail = runId === null ? undefined : () => props.onOpenDetail?.(runId);

  const header = (
    <section className="console-section">
      <div className="flex items-start justify-between gap-3">
        <div>
          <h2 className="text-lg font-semibold">调度建议</h2>
          <p className="text-sm text-gray-500">
            {runId === null ? "尚未选择要查看的任务。" : `任务 ${runId} 当前的下一步动作建议。`}
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
        <ConsoleReadEmpty title="未选择执行任务" description="请从运行控制页选择一个任务后再查看调度建议。" />
      </div>
    );
  }

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
          <Panel title="当前建议摘要">
            <div className="grid gap-3 md:grid-cols-2">
              <Info label="建议动作" value={recommendation?.action ?? "-"} />
              <Info label="置信度" value={recommendation?.confidence ?? "-"} />
              <Info label="风险等级" value={recommendation?.risk ?? "-"} />
              <Info
                label="是否需要确认"
                value={recommendation ? (recommendation.requiresConfirmation ? "是" : "否") : "-"}
              />
              <Info label="决策理由" value={primary?.decision_reason ?? "-"} />
              <Info label="推荐顺序" value={recommendedOrder ?? "-"} />
            </div>
          </Panel>

          <Panel title="建议列表">
            {recommendations && recommendations.length > 0 ? (
              <div className="space-y-3">
                {recommendations.map((item, index) => (
                  <button
                    key={`${item.action}-${index}`}
                    className="w-full border-b px-3 py-3 text-left hover:bg-gray-50"
                    onClick={openRecovery}
                  >
                    <div className="flex items-center justify-between gap-3">
                      <div className="font-medium text-gray-900">{item.action}</div>
                      {item.risk ? <div className="text-xs text-gray-500">{item.risk}</div> : null}
                    </div>
                    {item.reason ? <div className="mt-1 text-sm text-gray-600">{item.reason}</div> : null}
                    {item.confidence ? (
                      <div className="mt-2 text-xs text-blue-600">置信度 {item.confidence}</div>
                    ) : null}
                  </button>
                ))}
              </div>
            ) : (
              <ConsoleReadEmpty title="暂无调度建议" description="后端 dispatch 接口未返回建议动作。" />
            )}
          </Panel>

          <Panel title="决策依据">
            <div className="space-y-2 text-sm text-gray-600">
              <div>触发条件：{reasoning?.trigger ?? "-"}</div>
              <div>关联模块：{reasoning?.relatedModules ?? "-"}</div>
              <div>推理摘要：{reasoning?.summary ?? "-"}</div>
            </div>
          </Panel>
        </div>

        <aside className="space-y-4">
          <Panel title="可执行动作">
            <div className="grid gap-2">
              <button className="border-b px-3 py-2 text-left hover:bg-gray-50">立即执行</button>
              <button className="border-b px-3 py-2 text-left hover:bg-gray-50">进入确认</button>
              <button className="border-b px-3 py-2 text-left hover:bg-gray-50">调整参数</button>
              {openRecovery && (
                <button className="border-b px-3 py-2 text-left hover:bg-gray-50" onClick={openRecovery}>
                  进入恢复页
                </button>
              )}
            </div>
          </Panel>

          <Panel title="影响评估">
            <div className="space-y-2 text-sm text-gray-600">
              <div>预期结果：{impact?.expectedResult ?? "-"}</div>
              <div>潜在副作用：{impact?.sideEffect ?? "-"}</div>
              <div>影响范围：{impact?.scope ?? "-"}</div>
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
