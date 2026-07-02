import React from "react";
import { getAuthHeaders } from "../../../services/authHeaders";

export type OrganizationAuditPageProps = {
  totalEvents?: number;
  successEvents?: number;
  failedEvents?: number;
  lastEventStatus?: string;
  riskLevel?: string;
};

type OrganizationAuditApiResponse = {
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
    organization?: { summary?: { title?: string } | null; data?: Record<string, unknown> | null };
    departments?: { summary?: { title?: string } | null; data?: Record<string, unknown> | null };
    roles?: { summary?: { title?: string } | null; data?: Record<string, unknown> | null };
    audits?: { summary?: { title?: string } | null; data?: Record<string, unknown> | null };
  };
};

export function OrganizationAuditPage(props: OrganizationAuditPageProps) {
  const [apiData, setApiData] = React.useState<OrganizationAuditApiResponse | null>(null);

  React.useEffect(() => {
    let cancelled = false;
    const load = async () => {
      try {
        const response = await fetch("/api/v1/organization-control/audit", { method: "GET", headers: { "Content-Type": "application/json", ...getAuthHeaders() } });
        if (!response.ok) return;
        const payload = (await response.json()) as OrganizationAuditApiResponse;
        if (!cancelled) setApiData(payload);
      } catch (error) {
        console.warn("Failed to load organization audit", error);
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
        <h2 className="text-lg font-semibold">组织审核</h2>
        <p className="text-sm text-gray-500">查看组织权限变更与审核事件。</p>
      </section>
      <section className="grid gap-4 md:grid-cols-2 xl:grid-cols-5">
        <StatCard label="事件总数" value={String(totalEvents)} />
        <StatCard label="成功事件" value={String(successEvents)} />
        <StatCard label="失败事件" value={String(failedEvents)} />
        <StatCard label="最近状态" value={lastEventStatus} />
        <StatCard label="风险等级" value={riskLevel} />
      </section>
      <Panel title="审核记录">
        <div className="space-y-2 text-sm text-gray-600">
          <div>组织摘要：{apiData?.linked_summaries.organization?.summary?.title ?? "-"}</div>
          <div>部门摘要：{apiData?.linked_summaries.departments?.summary?.title ?? "-"}</div>
          <div>角色摘要：{apiData?.linked_summaries.roles?.summary?.title ?? "-"}</div>
          <div>审计摘要：{apiData?.linked_summaries.audits?.summary?.title ?? "-"}</div>
        </div>
      </Panel>
    </div>
  );
}
function StatCard({ label, value }: { label: string; value: string }) { return <div className="rounded-2xl border bg-white p-4 shadow-sm"><div className="text-sm text-gray-500">{label}</div><div className="mt-2 text-xl font-bold">{value}</div></div>; }
function Panel({ title, children }: { title: string; children: React.ReactNode }) { return <section className="rounded-2xl border bg-white p-4 shadow-sm"><h3 className="font-semibold">{title}</h3><div className="mt-3">{children}</div></section>; }
