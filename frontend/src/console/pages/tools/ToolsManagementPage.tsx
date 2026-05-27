import React from "react";

export type ToolsManagementPageProps = {
  pendingChanges?: number;
  enabledChanges?: number;
  disabledChanges?: number;
  reviewRequired?: number;
  riskLevel?: string;
};

type ToolsManagementApiResponse = {
  resource_type: string;
  resource_id: string;
  primary: {
    pending_changes?: number;
    enabled_changes?: number;
    disabled_changes?: number;
    review_required?: number;
    risk_level?: string;
  };
  linked_summaries: {
    tools?: { summary?: { title?: string } | null; data?: Record<string, unknown> | null };
    plugins?: { summary?: { title?: string } | null; data?: Record<string, unknown> | null };
    resources?: { summary?: { title?: string } | null; data?: Record<string, unknown> | null };
    history?: { summary?: { title?: string } | null; data?: Record<string, unknown> | null };
  };
};

export function ToolsManagementPage(props: ToolsManagementPageProps) {
  const [apiData, setApiData] = React.useState<ToolsManagementApiResponse | null>(null);

  React.useEffect(() => {
    let cancelled = false;
    const load = async () => {
      try {
        const response = await fetch("/api/v1/tools-control/management", { method: "GET", headers: { "Content-Type": "application/json" } });
        if (!response.ok) return;
        const payload = (await response.json()) as ToolsManagementApiResponse;
        if (!cancelled) setApiData(payload);
      } catch (error) {
        console.warn("Failed to load tools management", error);
      }
    };
    void load();
    return () => {
      cancelled = true;
    };
  }, []);

  const pendingChanges = props.pendingChanges ?? apiData?.primary.pending_changes ?? 0;
  const enabledChanges = props.enabledChanges ?? apiData?.primary.enabled_changes ?? 0;
  const disabledChanges = props.disabledChanges ?? apiData?.primary.disabled_changes ?? 0;
  const reviewRequired = props.reviewRequired ?? apiData?.primary.review_required ?? 0;
  const riskLevel = props.riskLevel ?? apiData?.primary.risk_level ?? "-";

  return (
    <div className="space-y-4">
      <section className="rounded-2xl border bg-white p-4 shadow-sm">
        <h2 className="text-lg font-semibold">工具管理</h2>
        <p className="text-sm text-gray-500">管理工具和插件的启用、停用与审核。</p>
      </section>

      <section className="grid gap-4 md:grid-cols-2 xl:grid-cols-5">
        <StatCard label="待变更" value={String(pendingChanges)} />
        <StatCard label="启用变更" value={String(enabledChanges)} />
        <StatCard label="停用变更" value={String(disabledChanges)} />
        <StatCard label="需审核" value={String(reviewRequired)} />
        <StatCard label="风险等级" value={riskLevel} />
      </section>

      <section className="grid gap-4 xl:grid-cols-[minmax(0,1fr)_360px]">
        <Panel title="审核队列">
          <div className="space-y-3 text-sm text-gray-600">
            <div>工具摘要：{apiData?.linked_summaries.tools?.summary?.title ?? "-"}</div>
            <div>插件摘要：{apiData?.linked_summaries.plugins?.summary?.title ?? "-"}</div>
            <div>资源摘要：{apiData?.linked_summaries.resources?.summary?.title ?? "-"}</div>
            <div>历史摘要：{apiData?.linked_summaries.history?.summary?.title ?? "-"}</div>
          </div>
        </Panel>

        <Panel title="操作区">
          <div className="grid gap-2">
            <button className="rounded-xl border px-3 py-2 text-left hover:bg-gray-50">批准选中项</button>
            <button className="rounded-xl border px-3 py-2 text-left hover:bg-gray-50">拒绝选中项</button>
            <button className="rounded-xl border px-3 py-2 text-left hover:bg-gray-50">刷新审核队列</button>
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
