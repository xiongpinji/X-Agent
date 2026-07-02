import React from "react";
import { getAuthHeaders } from "../../../services/authHeaders";

export type MemoryOverviewPageProps = {
  resourceType?: string;
  resourceId?: string;
  totalMemories?: number;
  activeMemories?: number;
  archivedMemories?: number;
  referencedMemories?: number;
  riskLevel?: string;
  linkedMemoriesSummary?: { summary?: { title?: string } | null; data?: Record<string, unknown> | null } | null;
  linkedExperiencesSummary?: { summary?: { title?: string } | null; data?: Record<string, unknown> | null } | null;
  linkedReferencesSummary?: { summary?: { title?: string } | null; data?: Record<string, unknown> | null } | null;
  linkedHistorySummary?: { summary?: { title?: string } | null; data?: Record<string, unknown> | null } | null;
  onOpenDetail?: () => void;
  onOpenManagement?: () => void;
  onOpenHistory?: () => void;
};

type MemoryOverviewApiResponse = {
  resource_type: string;
  resource_id: string;
  primary: {
    total_memories?: number;
    active_memories?: number;
    archived_memories?: number;
    referenced_memories?: number;
    risk_level?: string;
  };
  linked_summaries: {
    memories?: { summary?: { title?: string } | null; data?: Record<string, unknown> | null };
    experiences?: { summary?: { title?: string } | null; data?: Record<string, unknown> | null };
    references?: { summary?: { title?: string } | null; data?: Record<string, unknown> | null };
    history?: { summary?: { title?: string } | null; data?: Record<string, unknown> | null };
  };
};

export function MemoryOverviewPage(props: MemoryOverviewPageProps) {
  const [apiData, setApiData] = React.useState<MemoryOverviewApiResponse | null>(null);

  React.useEffect(() => {
    let cancelled = false;
    const load = async () => {
      try {
        const response = await fetch("/api/v1/memory-control/overview", { method: "GET", headers: { "Content-Type": "application/json", ...getAuthHeaders() } });
        if (!response.ok) return;
        const payload = (await response.json()) as MemoryOverviewApiResponse;
        if (!cancelled) setApiData(payload);
      } catch (error) {
        console.warn("Failed to load memory overview", error);
      }
    };
    void load();
    return () => {
      cancelled = true;
    };
  }, []);

  const resourceType = props.resourceType ?? apiData?.resource_type ?? "memory_center_overview";
  const resourceId = props.resourceId ?? apiData?.resource_id ?? "-";
  const totalMemories = props.totalMemories ?? apiData?.primary.total_memories ?? 0;
  const activeMemories = props.activeMemories ?? apiData?.primary.active_memories ?? 0;
  const archivedMemories = props.archivedMemories ?? apiData?.primary.archived_memories ?? 0;
  const referencedMemories = props.referencedMemories ?? apiData?.primary.referenced_memories ?? 0;
  const riskLevel = props.riskLevel ?? apiData?.primary.risk_level ?? "低";

  return (
    <div className="space-y-4">
      <section className="rounded-2xl border bg-white p-4 shadow-sm">
        <div className="text-xs text-gray-500">{resourceType}</div>
        <div className="mt-1 text-sm text-gray-700">资源 ID：{resourceId}</div>
        <div className="mt-2 text-xs text-gray-500">记忆摘要：{apiData?.linked_summaries.memories?.summary?.title ?? props.linkedMemoriesSummary?.summary?.title ?? "memories"} · {totalMemories} 条记忆</div>
        <div className="mt-1 text-xs text-gray-500">经验摘要：{apiData?.linked_summaries.experiences?.summary?.title ?? props.linkedExperiencesSummary?.summary?.title ?? "experiences"} · {activeMemories} 条活跃经验</div>
        <div className="mt-1 text-xs text-gray-500">引用摘要：{apiData?.linked_summaries.references?.summary?.title ?? props.linkedReferencesSummary?.summary?.title ?? "references"} · {referencedMemories} 次引用</div>
        <div className="mt-1 text-xs text-gray-500">历史摘要：{apiData?.linked_summaries.history?.summary?.title ?? props.linkedHistorySummary?.summary?.title ?? "history"} · {archivedMemories} 条归档</div>
      </section>

      <section className="grid gap-4 md:grid-cols-2 xl:grid-cols-4">
        <StatCard label="记忆总数" value={String(totalMemories)} />
        <StatCard label="活跃记忆" value={String(activeMemories)} />
        <StatCard label="已归档" value={String(archivedMemories)} />
        <StatCard label="被引用" value={String(referencedMemories)} />
      </section>

      <section className="grid gap-4 xl:grid-cols-[minmax(0,1fr)_360px]">
        <Panel title="记忆概览">
          <div className="space-y-2 text-sm text-gray-600">
            <div>当前风险等级：{riskLevel}</div>
            <div>记忆中心用于沉淀执行结果、经验和证据。</div>
            <div className="text-xs text-gray-500">当前可见：{totalMemories} 条 · 归档：{archivedMemories} 条 · 引用：{referencedMemories} 次</div>
          </div>
        </Panel>

        <Panel title="快捷入口">
          <div className="grid gap-2">
            <button className="rounded-xl border px-3 py-2 text-left hover:bg-gray-50" onClick={() => props.onOpenDetail?.()}>查看记忆详情</button>
            <button className="rounded-xl border px-3 py-2 text-left hover:bg-gray-50" onClick={() => props.onOpenManagement?.()}>进入经验管理</button>
            <button className="rounded-xl border px-3 py-2 text-left hover:bg-gray-50" onClick={() => props.onOpenHistory?.()}>查看历史记录</button>
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
