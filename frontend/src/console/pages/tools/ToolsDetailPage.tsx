import React from "react";
import { getAuthHeaders } from "../../../services/authHeaders";

export type ToolsDetailPageProps = {
  toolId?: string;
  toolName?: string;
  status?: string;
  version?: string;
  owner?: string;
  riskLevel?: string;
  description?: string;
  onOpenHistory?: () => void;
  onOpenPlugins?: () => void;
  onOpenResources?: () => void;
};

type ToolsDetailApiResponse = {
  resource_type: string;
  resource_id: string;
  primary: {
    tool_id?: string;
    tool_name?: string;
    status?: string;
    version?: string;
    owner?: string;
    risk_level?: string;
    description?: string;
  };
  linked_summaries: {
    history?: { summary?: { title?: string } | null; data?: Record<string, unknown> | null };
    plugins?: { summary?: { title?: string } | null; data?: Record<string, unknown> | null };
    resources?: { summary?: { title?: string } | null; data?: Record<string, unknown> | null };
    audit?: { summary?: { title?: string } | null; data?: Record<string, unknown> | null };
  };
};

export function ToolsDetailPage(props: ToolsDetailPageProps) {
  const [apiData, setApiData] = React.useState<ToolsDetailApiResponse | null>(null);
  const toolId = props.toolId ?? "tool-001";

  React.useEffect(() => {
    let cancelled = false;
    const load = async () => {
      try {
        const response = await fetch(`/api/v1/tools-control/detail/${encodeURIComponent(toolId)}`, { method: "GET", headers: { "Content-Type": "application/json", ...getAuthHeaders() } });
        if (!response.ok) return;
        const payload = (await response.json()) as ToolsDetailApiResponse;
        if (!cancelled) setApiData(payload);
      } catch (error) {
        console.warn("Failed to load tool detail", error);
      }
    };
    void load();
    return () => {
      cancelled = true;
    };
  }, [toolId]);

  const toolName = props.toolName ?? apiData?.primary.tool_name ?? "-";
  const status = props.status ?? apiData?.primary.status ?? "-";
  const version = props.version ?? apiData?.primary.version ?? "-";
  const owner = props.owner ?? apiData?.primary.owner ?? "-";
  const riskLevel = props.riskLevel ?? apiData?.primary.risk_level ?? "-";
  const description = props.description ?? apiData?.primary.description ?? "-";

  return (
    <div className="space-y-4">
      <section className="rounded-2xl border bg-white p-4 shadow-sm">
        <h2 className="text-lg font-semibold">工具详情</h2>
        <p className="text-sm text-gray-500">查看单个工具的状态、版本和归属信息。</p>
      </section>

      <section className="grid gap-4 md:grid-cols-2 xl:grid-cols-4">
        <StatCard label="工具 ID" value={toolId} />
        <StatCard label="工具名称" value={toolName} />
        <StatCard label="状态" value={status} />
        <StatCard label="版本" value={version} />
      </section>

      <section className="grid gap-4 xl:grid-cols-[minmax(0,1fr)_360px]">
        <Panel title="基础信息">
          <div className="grid gap-3 md:grid-cols-2">
            <Info label="归属人" value={owner} />
            <Info label="风险等级" value={riskLevel} />
            <Info label="描述" value={description} />
            <Info label="历史摘要" value={apiData?.linked_summaries.history?.summary?.title ?? "-"} />
            <Info label="插件摘要" value={apiData?.linked_summaries.plugins?.summary?.title ?? "-"} />
            <Info label="资源摘要" value={apiData?.linked_summaries.resources?.summary?.title ?? "-"} />
          </div>
        </Panel>

        <Panel title="快捷操作">
          <div className="grid gap-2">
            <button className="rounded-xl border px-3 py-2 text-left hover:bg-gray-50" onClick={() => props.onOpenHistory?.()}>查看调用历史</button>
            <button className="rounded-xl border px-3 py-2 text-left hover:bg-gray-50" onClick={() => props.onOpenPlugins?.()}>查看绑定插件</button>
            <button className="rounded-xl border px-3 py-2 text-left hover:bg-gray-50" onClick={() => props.onOpenResources?.()}>查看资源依赖</button>
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
