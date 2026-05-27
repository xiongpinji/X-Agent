import React from "react";

export type MarketplaceManagementPageProps = {
  pendingChanges?: number;
  publishedChanges?: number;
  installedChanges?: number;
  reviewRequired?: number;
  riskLevel?: string;
};

type MarketplaceManagementApiResponse = {
  resource_type: string;
  resource_id: string;
  primary: {
    pending_changes?: number;
    published_changes?: number;
    installed_changes?: number;
    review_required?: number;
    risk_level?: string;
  };
  linked_summaries: {
    market?: { summary?: { title?: string } | null; data?: Record<string, unknown> | null };
    plugins?: { summary?: { title?: string } | null; data?: Record<string, unknown> | null };
    tools?: { summary?: { title?: string } | null; data?: Record<string, unknown> | null };
    history?: { summary?: { title?: string } | null; data?: Record<string, unknown> | null };
  };
};

export function MarketplaceManagementPage(props: MarketplaceManagementPageProps) {
  const [apiData, setApiData] = React.useState<MarketplaceManagementApiResponse | null>(null);

  React.useEffect(() => {
    let cancelled = false;
    const load = async () => {
      try {
        const response = await fetch("/api/v1/marketplace-control/management", { method: "GET", headers: { "Content-Type": "application/json" } });
        if (!response.ok) return;
        const payload = (await response.json()) as MarketplaceManagementApiResponse;
        if (!cancelled) setApiData(payload);
      } catch (error) {
        console.warn("Failed to load marketplace management", error);
      }
    };
    void load();
    return () => {
      cancelled = true;
    };
  }, []);

  const pendingChanges = props.pendingChanges ?? apiData?.primary.pending_changes ?? 0;
  const publishedChanges = props.publishedChanges ?? apiData?.primary.published_changes ?? 0;
  const installedChanges = props.installedChanges ?? apiData?.primary.installed_changes ?? 0;
  const reviewRequired = props.reviewRequired ?? apiData?.primary.review_required ?? 0;
  const riskLevel = props.riskLevel ?? apiData?.primary.risk_level ?? "-";

  return (
    <div className="space-y-4">
      <section className="rounded-2xl border bg-white p-4 shadow-sm">
        <h2 className="text-lg font-semibold">安装 / 启用管理</h2>
        <p className="text-sm text-gray-500">管理能力条目的安装、启用和审核流程。</p>
      </section>

      <section className="grid gap-4 md:grid-cols-2 xl:grid-cols-5">
        <StatCard label="待变更" value={String(pendingChanges)} />
        <StatCard label="已发布变更" value={String(publishedChanges)} />
        <StatCard label="已安装变更" value={String(installedChanges)} />
        <StatCard label="需审核" value={String(reviewRequired)} />
        <StatCard label="风险等级" value={riskLevel} />
      </section>

      <Panel title="审核队列">
        <div className="space-y-3 text-sm text-gray-600">
          <div>市场摘要：{apiData?.linked_summaries.market?.summary?.title ?? "-"}</div>
          <div>插件摘要：{apiData?.linked_summaries.plugins?.summary?.title ?? "-"}</div>
          <div>工具摘要：{apiData?.linked_summaries.tools?.summary?.title ?? "-"}</div>
          <div>历史摘要：{apiData?.linked_summaries.history?.summary?.title ?? "-"}</div>
        </div>
      </Panel>
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
