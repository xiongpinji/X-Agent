import React from "react";

import { ConsoleReadEmpty } from "@/console/components/ReadState";

export type ExecutionOverviewPageProps = {
  resourceType?: string;
  resourceId?: string;
  /** 当前唯一可查看的 run（真实选中项）。为 null 时不提供任何「查看详情/恢复/调度」入口。 */
  runId?: string | null;
  /** 总览信封是否到达。false 时不渲染任何数值结论。 */
  loaded?: boolean;
  activeRuns?: number | null;
  pendingRuns?: number | null;
  failedRuns?: number | null;
  completedRuns?: number | null;
  interventionCount?: number | null;
  riskLevel?: string | null;
  dispatch?: DispatchResult | null;
  executionPlan?: Record<string, unknown> | null;
  recommendations?: Array<{ action: string; reason: string; confidence?: string }>;
  linkedDispatchSummary?: { summary?: { title?: string } | null; data?: Record<string, unknown> | null } | null;
  linkedExecutionSummary?: { summary?: { title?: string } | null; data?: Record<string, unknown> | null } | null;
  linkedAuditSummary?: { summary?: { title?: string } | null; data?: Record<string, unknown> | null } | null;
  linkedMessagesSummary?: { summary?: { title?: string } | null; data?: Record<string, unknown> | null } | null;
  onOpenDetail?: (runId: string) => void;
  onOpenRecovery?: (runId: string) => void;
  onOpenDispatch?: (runId: string) => void;
};

/**
 * 运行控制总览。
 *
 * 历史缺陷（读路径 Critical，扫描器扫不到 —— 本页根本不 fetch，所以没有
 * `if (!ok)` 站点）：整页渲染三组硬编码 demo —— `demoActiveRuns`（内容生成任务 /
 * 短剧导演 / 72%）· `demoFailedRuns`（工具超时 / 可重试）· `demoRecommendations`
 * （置信度 92%），且 `_recommendations` 变量算完就被丢掉、列表仍用 demo 数组。
 * KPI 还兜底成 `?? 4` / `?? 12` / `?? "中等"`。用户看到的是一个**从没查过**的
 * 控制台。
 *
 * 现在：数值只来自真实信封；信封未到达显示「未加载」而不是 0；没有运行列表
 * 数据源时显示空态；不编造 `run-001` 这类 id 当入口。
 */
export function ExecutionOverviewPage(props: ExecutionOverviewPageProps) {
  const loaded = props.loaded ?? false;
  const resourceType = props.resourceType ?? "execution_control_overview";
  const resourceId = props.resourceId ?? "-";
  const runId = props.runId ?? null;
  const recommendations = props.recommendations ?? [];

  const num = (value: number | null | undefined) => (loaded && value != null ? String(value) : "-");
  const riskLevel = loaded ? (props.riskLevel ?? "-") : "未加载";

  return (
    <div className="space-y-4">
      <header className="console-page-header">
        <h1 className="page-title">运行控制</h1>
        <div className="console-resource-id">
          {resourceType} · 资源 ID：{resourceId}
        </div>
        {props.linkedDispatchSummary?.summary?.title ? (
          <div className="console-summary-line">调度摘要：{props.linkedDispatchSummary.summary.title}</div>
        ) : null}
        {props.linkedExecutionSummary?.summary?.title ? (
          <div className="console-summary-line">执行摘要：{props.linkedExecutionSummary.summary.title}</div>
        ) : null}
        {props.linkedAuditSummary?.summary?.title ? (
          <div className="console-summary-line">审计摘要：{props.linkedAuditSummary.summary.title}</div>
        ) : null}
        {props.linkedMessagesSummary?.summary?.title ? (
          <div className="console-summary-line">消息摘要：{props.linkedMessagesSummary.summary.title}</div>
        ) : null}
      </header>

      {!loaded && (
        <ConsoleReadEmpty
          title="总览数据尚未加载"
          description="后端 /api/v1/execution-control/overview 未返回数据，以下指标无可信来源。"
        />
      )}

      <section className="console-kpi-row">
        <StatCard label="活跃执行" value={num(props.activeRuns)} />
        <StatCard label="待处理任务" value={num(props.pendingRuns)} />
        <StatCard label="失败任务" value={num(props.failedRuns)} />
        <StatCard label="已完成" value={num(props.completedRuns)} />
        <StatCard label="待人工介入" value={num(props.interventionCount)} />
        <StatCard label="风险等级" value={riskLevel} />
      </section>

      <section className="grid gap-4 xl:grid-cols-[minmax(0,1fr)_360px]">
        <div className="space-y-4">
          <Panel title="活跃执行">
            <ConsoleReadEmpty
              title="暂无活跃执行列表"
              description="后端未提供运行列表接口，这里不再用示例任务填充。"
            />
          </Panel>

          <Panel title="失败任务">
            <ConsoleReadEmpty
              title="暂无失败任务列表"
              description="后端未提供运行列表接口，这里不再用示例任务填充。"
            />
          </Panel>
        </div>

        <aside className="space-y-4">
          <Panel title="风险建议">
            {recommendations.length > 0 ? (
              <div className="space-y-3">
                {recommendations.map((item) => (
                  <button
                    key={item.action}
                    className="w-full border-b px-3 py-3 text-left hover:bg-gray-50"
                    onClick={() => {
                      if (runId !== null) props.onOpenDispatch?.(runId);
                    }}
                  >
                    <div className="font-medium">{item.action}</div>
                    <div className="mt-1 text-xs text-gray-500">{item.reason}</div>
                    {item.confidence ? (
                      <div className="mt-2 text-xs text-blue-600">置信度 {item.confidence}</div>
                    ) : null}
                  </button>
                ))}
                <div className="text-xs text-gray-500">
                  当前活跃：{num(props.activeRuns)} · 失败：{num(props.failedRuns)} · 待介入：
                  {num(props.interventionCount)}
                </div>
              </div>
            ) : (
              <ConsoleReadEmpty
                title="暂无风险建议"
                description="后端未返回建议数据，前端不再自行编造建议与置信度。"
              />
            )}
          </Panel>

          <Panel title="快捷入口">
            {runId !== null ? (
              <div className="grid gap-2">
                <button className="border-b px-3 py-2 text-left hover:bg-gray-50" onClick={() => props.onOpenDetail?.(runId)}>
                  打开执行详情
                </button>
                <button className="border-b px-3 py-2 text-left hover:bg-gray-50" onClick={() => props.onOpenRecovery?.(runId)}>
                  打开失败恢复
                </button>
                <button className="border-b px-3 py-2 text-left hover:bg-gray-50" onClick={() => props.onOpenDispatch?.(runId)}>
                  打开调度建议
                </button>
              </div>
            ) : (
              <ConsoleReadEmpty title="尚未选中任务" description="选中一个运行后才能查看详情 / 恢复 / 调度。" />
            )}
          </Panel>
        </aside>
      </section>
    </div>
  );
}

function StatCard({ label, value }: { label: string; value: string }) {
  return (
    <div className="console-kpi">
      <span className="kpi-label">{label}</span>
      <span className="kpi-value">{value}</span>
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
