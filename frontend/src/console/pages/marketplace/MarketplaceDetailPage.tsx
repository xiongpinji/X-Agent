import React from "react";

export type MarketplaceDetailPageProps = {
  itemId?: string;
  itemName?: string;
  itemType?: string;
  version?: string;
  status?: string;
  owner?: string;
  riskLevel?: string;
  description?: string;
  onOpenInstall?: () => void;
  onOpenEnable?: () => void;
  onOpenDependencies?: () => void;
};

type MarketplaceDetailApiResponse = {
  resource_type: string;
  resource_id: string;
  primary: {
    item_id?: string;
    item_name?: string;
    item_type?: string;
    version?: string;
    status?: string;
    owner?: string;
    risk_level?: string;
    description?: string;
  };
  linked_summaries: {
    market?: { summary?: { title?: string } | null; data?: Record<string, unknown> | null };
    plugins?: { summary?: { title?: string } | null; data?: Record<string, unknown> | null };
    tools?: { summary?: { title?: string } | null; data?: Record<string, unknown> | null };
    history?: { summary?: { title?: string } | null; data?: Record<string, unknown> | null };
  };
};

export function MarketplaceDetailPage(props: MarketplaceDetailPageProps) {
  const [apiData, setApiData] = React.useState<MarketplaceDetailApiResponse | null>(null);
  const itemId = props.itemId ?? "item-001";

  React.useEffect(() => {
    let cancelled = false;
    const load = async () => {
      try {
        const response = await fetch(`/api/v1/marketplace-control/detail/${encodeURIComponent(itemId)}`, { method: "GET", headers: { "Content-Type": "application/json" } });
        if (!response.ok) return;
        const payload = (await response.json()) as MarketplaceDetailApiResponse;
        if (!cancelled) setApiData(payload);
      } catch (error) {
        console.warn("Failed to load marketplace detail", error);
      }
    };
    void load();
    return () => {
      cancelled = true;
    };
  }, [itemId]);

  const itemName = props.itemName ?? apiData?.primary.item_name ?? "-";
  const itemType = props.itemType ?? apiData?.primary.item_type ?? "-";
  const version = props.version ?? apiData?.primary.version ?? "-";
  const status = props.status ?? apiData?.primary.status ?? "-";
  const owner = props.owner ?? apiData?.primary.owner ?? "-";
  const riskLevel = props.riskLevel ?? apiData?.primary.risk_level ?? "-";
  const description = props.description ?? apiData?.primary.description ?? "-";

  return (
    <div className="space-y-4">
      <section className="rounded-2xl border bg-white p-4 shadow-sm">
        <h2 className="text-lg font-semibold">能力详情</h2>
        <p className="text-sm text-gray-500">查看市场条目的类型、版本和归属信息。</p>
      </section>

      <section className="grid gap-4 md:grid-cols-2 xl:grid-cols-4">
        <StatCard label="条目 ID" value={itemId} />
        <StatCard label="名称" value={itemName} />
        <StatCard label="类型" value={itemType} />
        <StatCard label="版本" value={version} />
      </section>

      <section className="grid gap-4 xl:grid-cols-[minmax(0,1fr)_360px]">
        <Panel title="基础信息">
          <div className="grid gap-3 md:grid-cols-2">
            <Info label="状态" value={status} />
            <Info label="归属人" value={owner} />
            <Info label="风险等级" value={riskLevel} />
            <Info label="描述" value={description} />
            <Info label="市场摘要" value={apiData?.linked_summaries.market?.summary?.title ?? "-"} />
            <Info label="插件摘要" value={apiData?.linked_summaries.plugins?.summary?.title ?? "-"} />
            <Info label="工具摘要" value={apiData?.linked_summaries.tools?.summary?.title ?? "-"} />
            <Info label="历史摘要" value={apiData?.linked_summaries.history?.summary?.title ?? "-"} />
          </div>
        </Panel>

        <Panel title="快捷操作">
          <div className="grid gap-2">
            <button className="rounded-xl border px-3 py-2 text-left hover:bg-gray-50" onClick={() => props.onOpenInstall?.()}>申请安装</button>
            <button className="rounded-xl border px-3 py-2 text-left hover:bg-gray-50" onClick={() => props.onOpenEnable?.()}>申请启用</button>
            <button className="rounded-xl border px-3 py-2 text-left hover:bg-gray-50" onClick={() => props.onOpenDependencies?.()}>查看依赖</button>
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
      <div className="mt-2 text-xl font-bold text-gray-900">{value}</div>
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
