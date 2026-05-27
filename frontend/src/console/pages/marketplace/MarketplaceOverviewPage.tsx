import React from "react";

export type MarketplaceOverviewPageProps = {
  resourceType?: string;
  resourceId?: string;
  totalItems?: number;
  publishedItems?: number;
  installedItems?: number;
  pendingApprovals?: number;
  riskLevel?: string;
  linkedMarketSummary?: { summary?: { title?: string } | null; data?: Record<string, unknown> | null } | null;
  linkedPluginsSummary?: { summary?: { title?: string } | null; data?: Record<string, unknown> | null } | null;
  linkedToolsSummary?: { summary?: { title?: string } | null; data?: Record<string, unknown> | null } | null;
  linkedHistorySummary?: { summary?: { title?: string } | null; data?: Record<string, unknown> | null } | null;
  onOpenDetail?: () => void;
  onOpenManagement?: () => void;
  onOpenHistory?: () => void;
};

type MarketplaceOverviewApiResponse = {
  resource_type: string;
  resource_id: string;
  primary: {
    total_items?: number;
    published_items?: number;
    installed_items?: number;
    pending_approvals?: number;
    risk_level?: string;
  };
  linked_summaries: {
    market?: { summary?: { title?: string } | null; data?: Record<string, unknown> | null };
    plugins?: { summary?: { title?: string } | null; data?: Record<string, unknown> | null };
    tools?: { summary?: { title?: string } | null; data?: Record<string, unknown> | null };
    history?: { summary?: { title?: string } | null; data?: Record<string, unknown> | null };
  };
};

export function MarketplaceOverviewPage(props: MarketplaceOverviewPageProps) {
  const [apiData, setApiData] = React.useState<MarketplaceOverviewApiResponse | null>(null);

  React.useEffect(() => {
    let cancelled = false;
    const load = async () => {
      try {
        const response = await fetch("/api/v1/marketplace-control/overview", { method: "GET", headers: { "Content-Type": "application/json" } });
        if (!response.ok) return;
        const payload = (await response.json()) as MarketplaceOverviewApiResponse;
        if (!cancelled) setApiData(payload);
      } catch (error) {
        console.warn("Failed to load marketplace overview", error);
      }
    };
    void load();
    return () => {
      cancelled = true;
    };
  }, []);

  const resourceType = props.resourceType ?? apiData?.resource_type ?? "marketplace_center_overview";
  const resourceId = props.resourceId ?? apiData?.resource_id ?? "-";
  const totalItems = props.totalItems ?? apiData?.primary.total_items ?? 0;
  const publishedItems = props.publishedItems ?? apiData?.primary.published_items ?? 0;
  const installedItems = props.installedItems ?? apiData?.primary.installed_items ?? 0;
  const pendingApprovals = props.pendingApprovals ?? apiData?.primary.pending_approvals ?? 0;
  const riskLevel = props.riskLevel ?? apiData?.primary.risk_level ?? "低";

  return (
    <div className="space-y-4">
      <section className="rounded-2xl border bg-white p-4 shadow-sm">
        <div className="text-xs text-gray-500">{resourceType}</div>
        <div className="mt-1 text-sm text-gray-700">资源 ID：{resourceId}</div>
        <div className="mt-2 text-xs text-gray-500">市场摘要：{apiData?.linked_summaries.market?.summary?.title ?? props.linkedMarketSummary?.summary?.title ?? "market"} · {totalItems} 个能力</div>
        <div className="mt-1 text-xs text-gray-500">插件摘要：{apiData?.linked_summaries.plugins?.summary?.title ?? props.linkedPluginsSummary?.summary?.title ?? "plugins"} · {publishedItems} 个已发布</div>
        <div className="mt-1 text-xs text-gray-500">工具摘要：{apiData?.linked_summaries.tools?.summary?.title ?? props.linkedToolsSummary?.summary?.title ?? "tools"} · {installedItems} 个已安装</div>
        <div className="mt-1 text-xs text-gray-500">历史摘要：{apiData?.linked_summaries.history?.summary?.title ?? props.linkedHistorySummary?.summary?.title ?? "history"} · {pendingApprovals} 个待审批</div>
      </section>

      <section className="grid gap-4 md:grid-cols-2 xl:grid-cols-5">
        <StatCard label="能力总数" value={String(totalItems)} />
        <StatCard label="已发布" value={String(publishedItems)} />
        <StatCard label="已安装" value={String(installedItems)} />
        <StatCard label="待审批" value={String(pendingApprovals)} />
        <StatCard label="风险等级" value={riskLevel} />
      </section>

      <section className="grid gap-4 xl:grid-cols-[minmax(0,1fr)_360px]">
        <Panel title="市场概览">
          <div className="space-y-2 text-sm text-gray-600">
            <div>能力市场用于发现、安装和启用能力。</div>
          </div>
        </Panel>

        <Panel title="快捷入口">
          <div className="grid gap-2">
            <button className="rounded-xl border px-3 py-2 text-left hover:bg-gray-50" onClick={() => props.onOpenDetail?.()}>查看能力详情</button>
            <button className="rounded-xl border px-3 py-2 text-left hover:bg-gray-50" onClick={() => props.onOpenManagement?.()}>进入安装管理</button>
            <button className="rounded-xl border px-3 py-2 text-left hover:bg-gray-50" onClick={() => props.onOpenHistory?.()}>查看发布历史</button>
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
