import React from "react";
import { getAuthHeaders } from "../../../services/authHeaders";

export type MemoryDetailPageProps = {
  memoryId?: string;
  memoryTitle?: string;
  status?: string;
  source?: string;
  owner?: string;
  riskLevel?: string;
  summary?: string;
};

type MemoryDetailApiResponse = {
  resource_type: string;
  resource_id: string;
  primary: {
    memory_id?: string;
    memory_title?: string;
    status?: string;
    source?: string;
    owner?: string;
    risk_level?: string;
    summary?: string;
  };
  linked_summaries: {
    experiences?: { summary?: { title?: string } | null; data?: Record<string, unknown> | null };
    references?: { summary?: { title?: string } | null; data?: Record<string, unknown> | null };
    history?: { summary?: { title?: string } | null; data?: Record<string, unknown> | null };
    audit?: { summary?: { title?: string } | null; data?: Record<string, unknown> | null };
  };
};

export function MemoryDetailPage(props: MemoryDetailPageProps) {
  const [apiData, setApiData] = React.useState<MemoryDetailApiResponse | null>(null);
  const memoryId = props.memoryId ?? "memory-001";

  React.useEffect(() => {
    let cancelled = false;
    const load = async () => {
      try {
        const response = await fetch(`/api/v1/memory-control/detail/${encodeURIComponent(memoryId)}`, { method: "GET", headers: { "Content-Type": "application/json", ...getAuthHeaders() } });
        if (!response.ok) return;
        const payload = (await response.json()) as MemoryDetailApiResponse;
        if (!cancelled) setApiData(payload);
      } catch (error) {
        console.warn("Failed to load memory detail", error);
      }
    };
    void load();
    return () => {
      cancelled = true;
    };
  }, [memoryId]);

  const memoryTitle = props.memoryTitle ?? apiData?.primary.memory_title ?? "-";
  const status = props.status ?? apiData?.primary.status ?? "-";
  const source = props.source ?? apiData?.primary.source ?? "-";
  const owner = props.owner ?? apiData?.primary.owner ?? "-";
  const riskLevel = props.riskLevel ?? apiData?.primary.risk_level ?? "-";
  const summary = props.summary ?? apiData?.primary.summary ?? "-";

  return (
    <div className="space-y-4">
      <section className="rounded-2xl border bg-white p-4 shadow-sm">
        <h2 className="text-lg font-semibold">记忆详情</h2>
        <p className="text-sm text-gray-500">查看单条记忆的状态、来源和摘要信息。</p>
      </section>

      <section className="grid gap-4 md:grid-cols-2 xl:grid-cols-4">
        <StatCard label="记忆 ID" value={memoryId} />
        <StatCard label="标题" value={memoryTitle} />
        <StatCard label="状态" value={status} />
        <StatCard label="来源" value={source} />
      </section>

      <section className="grid gap-4 xl:grid-cols-[minmax(0,1fr)_360px]">
        <Panel title="基础信息">
          <div className="grid gap-3 md:grid-cols-2">
            <Info label="归属人" value={owner} />
            <Info label="风险等级" value={riskLevel} />
            <Info label="摘要" value={summary} />
            <Info label="经验摘要" value={apiData?.linked_summaries.experiences?.summary?.title ?? "-"} />
            <Info label="引用摘要" value={apiData?.linked_summaries.references?.summary?.title ?? "-"} />
            <Info label="历史摘要" value={apiData?.linked_summaries.history?.summary?.title ?? "-"} />
            <Info label="审计摘要" value={apiData?.linked_summaries.audit?.summary?.title ?? "-"} />
          </div>
        </Panel>

        <Panel title="快捷操作">
          <div className="grid gap-2">
            <button className="rounded-xl border px-3 py-2 text-left hover:bg-gray-50">查看引用关系</button>
            <button className="rounded-xl border px-3 py-2 text-left hover:bg-gray-50">查看经验关联</button>
            <button className="rounded-xl border px-3 py-2 text-left hover:bg-gray-50">查看历史记录</button>
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
