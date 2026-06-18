import React from "react";
import { getAuthHeaders } from "../../../services/authHeaders";

export type ToolsOverviewPageProps = {
  resourceType?: string;
  resourceId?: string;
  totalTools?: number;
  enabledTools?: number;
  disabledTools?: number;
  pluginCount?: number;
  resourceCount?: number;
  riskLevel?: string;
  linkedToolsSummary?: { summary?: { title?: string } | null; data?: Record<string, unknown> | null } | null;
  linkedPluginsSummary?: { summary?: { title?: string } | null; data?: Record<string, unknown> | null } | null;
  linkedResourcesSummary?: { summary?: { title?: string } | null; data?: Record<string, unknown> | null } | null;
  linkedHistorySummary?: { summary?: { title?: string } | null; data?: Record<string, unknown> | null } | null;
  onOpenDetail?: () => void;
  onOpenPlugins?: () => void;
  onOpenHistory?: () => void;
};

type ToolsOverviewApiResponse = {
  resource_type: string;
  resource_id: string;
  primary: {
    total_tools?: number;
    enabled_tools?: number;
    disabled_tools?: number;
    plugin_count?: number;
    resource_count?: number;
    risk_level?: string;
  };
  linked_summaries: {
    tools?: { summary?: { title?: string } | null; data?: Record<string, unknown> | null };
    plugins?: { summary?: { title?: string } | null; data?: Record<string, unknown> | null };
    resources?: { summary?: { title?: string } | null; data?: Record<string, unknown> | null };
    history?: { summary?: { title?: string } | null; data?: Record<string, unknown> | null };
  };
};

export function ToolsOverviewPage(props: ToolsOverviewPageProps) {
  const [apiData, setApiData] = React.useState<ToolsOverviewApiResponse | null>(null);
  React.useEffect(() => {
    let cancelled = false;
    const load = async () => {
      try {
        const response = await fetch("/api/v1/tools-control/overview", { method: "GET", headers: { "Content-Type": "application/json", ...getAuthHeaders() } });
        if (!response.ok) return;
        const payload = (await response.json()) as ToolsOverviewApiResponse;
        if (!cancelled) setApiData(payload);
      } catch (error) {
        console.warn("Failed to load tools overview", error);
      }
    };
    void load();
    return () => {
      cancelled = true;
    };
  }, []);

  const resourceType = props.resourceType ?? apiData?.resource_type ?? "tools_center_overview";
  const resourceId = props.resourceId ?? apiData?.resource_id ?? "-";
  const totalTools = props.totalTools ?? apiData?.primary.total_tools ?? 0;
  const enabledTools = props.enabledTools ?? apiData?.primary.enabled_tools ?? 0;
  const disabledTools = props.disabledTools ?? apiData?.primary.disabled_tools ?? 0;
  const pluginCount = props.pluginCount ?? apiData?.primary.plugin_count ?? 0;
  const resourceCount = props.resourceCount ?? apiData?.primary.resource_count ?? 0;
  const riskLevel = props.riskLevel ?? apiData?.primary.risk_level ?? "低";

  return (
    <div className="space-y-4">
      <section className="rounded-2xl border bg-white p-4 shadow-sm">
        <div className="text-xs text-gray-500">{resourceType}</div>
        <div className="mt-1 text-sm text-gray-700">资源 ID：{resourceId}</div>
        <div className="mt-2 text-xs text-gray-500">工具摘要：{apiData?.linked_summaries.tools?.summary?.title ?? props.linkedToolsSummary?.summary?.title ?? "tools"} · {totalTools} 个工具</div>
        <div className="mt-1 text-xs text-gray-500">插件摘要：{apiData?.linked_summaries.plugins?.summary?.title ?? props.linkedPluginsSummary?.summary?.title ?? "plugins"} · {pluginCount} 个插件</div>
        <div className="mt-1 text-xs text-gray-500">资源摘要：{apiData?.linked_summaries.resources?.summary?.title ?? props.linkedResourcesSummary?.summary?.title ?? "resources"} · {resourceCount} 个资源</div>
        <div className="mt-1 text-xs text-gray-500">历史摘要：{apiData?.linked_summaries.history?.summary?.title ?? props.linkedHistorySummary?.summary?.title ?? "history"} · {disabledTools} 个停用项</div>
      </section>

      <section className="grid gap-4 md:grid-cols-2 xl:grid-cols-5">
        <StatCard label="工具总数" value={String(totalTools)} />
        <StatCard label="启用工具" value={String(enabledTools)} />
        <StatCard label="停用工具" value={String(disabledTools)} />
        <StatCard label="插件数" value={String(pluginCount)} />
        <StatCard label="资源数" value={String(resourceCount)} />
      </section>

      <section className="grid gap-4 xl:grid-cols-[minmax(0,1fr)_360px]">
        <Panel title="工具概览">
          <div className="space-y-2 text-sm text-gray-600">
            <div>当前风险等级：{riskLevel}</div>
            <div>工具中心用于统一管理能力、资源和插件。</div>
          </div>
        </Panel>

        <Panel title="快捷入口">
          <div className="grid gap-2">
            <button className="rounded-xl border px-3 py-2 text-left hover:bg-gray-50" onClick={() => props.onOpenDetail?.()}>查看工具详情</button>
            <button className="rounded-xl border px-3 py-2 text-left hover:bg-gray-50" onClick={() => props.onOpenPlugins?.()}>进入插件管理</button>
            <button className="rounded-xl border px-3 py-2 text-left hover:bg-gray-50" onClick={() => props.onOpenHistory?.()}>查看调用历史</button>
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
