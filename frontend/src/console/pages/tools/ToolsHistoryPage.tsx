import React from "react";
import { getAuthHeaders } from "../../../services/authHeaders";

export type ToolsHistoryPageProps = {
  totalEvents?: number;
  successEvents?: number;
  failedEvents?: number;
  lastEventStatus?: string;
  riskLevel?: string;
};

type ToolsHistoryApiResponse = {
  resource_type: string;
  resource_id: string;
  primary: {
    total_events?: number;
    success_events?: number;
    failed_events?: number;
    last_event_status?: string;
    risk_level?: string;
  };
  linked_summaries: {
    tools?: { summary?: { title?: string } | null; data?: Record<string, unknown> | null };
    plugins?: { summary?: { title?: string } | null; data?: Record<string, unknown> | null };
    resources?: { summary?: { title?: string } | null; data?: Record<string, unknown> | null };
    history?: { summary?: { title?: string } | null; data?: Record<string, unknown> | null };
  };
};

export function ToolsHistoryPage(props: ToolsHistoryPageProps) {
  const [apiData, setApiData] = React.useState<ToolsHistoryApiResponse | null>(null);

  React.useEffect(() => {
    let cancelled = false;
    const load = async () => {
      try {
        const response = await fetch("/api/v1/tools-control/history", { method: "GET", headers: { "Content-Type": "application/json", ...getAuthHeaders() } });
        if (!response.ok) return;
        const payload = (await response.json()) as ToolsHistoryApiResponse;
        if (!cancelled) setApiData(payload);
      } catch (error) {
        console.warn("Failed to load tools history", error);
      }
    };
    void load();
    return () => {
      cancelled = true;
    };
  }, []);

  const totalEvents = props.totalEvents ?? apiData?.primary.total_events ?? 0;
  const successEvents = props.successEvents ?? apiData?.primary.success_events ?? 0;
  const failedEvents = props.failedEvents ?? apiData?.primary.failed_events ?? 0;
  const lastEventStatus = props.lastEventStatus ?? apiData?.primary.last_event_status ?? "-";
  const riskLevel = props.riskLevel ?? apiData?.primary.risk_level ?? "-";

  return (
    <div className="space-y-4">
      <section className="rounded-2xl border bg-white p-4 shadow-sm">
        <h2 className="text-lg font-semibold">调用历史</h2>
        <p className="text-sm text-gray-500">查看工具、插件与资源的历史事件。</p>
      </section>

      <section className="grid gap-4 md:grid-cols-2 xl:grid-cols-5">
        <StatCard label="事件总数" value={String(totalEvents)} />
        <StatCard label="成功事件" value={String(successEvents)} />
        <StatCard label="失败事件" value={String(failedEvents)} />
        <StatCard label="最近状态" value={lastEventStatus} />
        <StatCard label="风险等级" value={riskLevel} />
      </section>

      <section className="grid gap-4 xl:grid-cols-[minmax(0,1fr)_360px]">
        <Panel title="历史摘要">
          <div className="space-y-3 text-sm text-gray-600">
            <div>工具摘要：{apiData?.linked_summaries.tools?.summary?.title ?? "-"}</div>
            <div>插件摘要：{apiData?.linked_summaries.plugins?.summary?.title ?? "-"}</div>
            <div>资源摘要：{apiData?.linked_summaries.resources?.summary?.title ?? "-"}</div>
            <div>历史摘要：{apiData?.linked_summaries.history?.summary?.title ?? "-"}</div>
          </div>
        </Panel>

        <Panel title="操作区">
          <div className="grid gap-2">
            <button className="rounded-xl border px-3 py-2 text-left hover:bg-gray-50">筛选成功事件</button>
            <button className="rounded-xl border px-3 py-2 text-left hover:bg-gray-50">筛选失败事件</button>
            <button className="rounded-xl border px-3 py-2 text-left hover:bg-gray-50">导出历史记录</button>
          </div>
        </Panel>
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
