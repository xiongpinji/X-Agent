import React from "react";
import { getAuthHeaders } from "../../../services/authHeaders";

export type OrganizationRolesPageProps = {
  totalRoles?: number;
  activeRoles?: number;
  pendingRoles?: number;
  permissionSets?: number;
  riskLevel?: string;
};

type OrganizationRolesApiResponse = {
  resource_type: string;
  resource_id: string;
  primary: {
    total_roles?: number;
    active_roles?: number;
    pending_roles?: number;
    permission_sets?: number;
    risk_level?: string;
  };
  linked_summaries: {
    organization?: { summary?: { title?: string } | null; data?: Record<string, unknown> | null };
    departments?: { summary?: { title?: string } | null; data?: Record<string, unknown> | null };
    roles?: { summary?: { title?: string } | null; data?: Record<string, unknown> | null };
    audits?: { summary?: { title?: string } | null; data?: Record<string, unknown> | null };
  };
};

export function OrganizationRolesPage(props: OrganizationRolesPageProps) {
  const [apiData, setApiData] = React.useState<OrganizationRolesApiResponse | null>(null);

  React.useEffect(() => {
    let cancelled = false;
    const load = async () => {
      try {
        const response = await fetch("/api/v1/organization-control/roles", { method: "GET", headers: { "Content-Type": "application/json", ...getAuthHeaders() } });
        if (!response.ok) return;
        const payload = (await response.json()) as OrganizationRolesApiResponse;
        if (!cancelled) setApiData(payload);
      } catch (error) {
        console.warn("Failed to load organization roles", error);
      }
    };
    void load();
    return () => {
      cancelled = true;
    };
  }, []);

  const totalRoles = props.totalRoles ?? apiData?.primary.total_roles ?? 0;
  const activeRoles = props.activeRoles ?? apiData?.primary.active_roles ?? 0;
  const pendingRoles = props.pendingRoles ?? apiData?.primary.pending_roles ?? 0;
  const permissionSets = props.permissionSets ?? apiData?.primary.permission_sets ?? 0;
  const riskLevel = props.riskLevel ?? apiData?.primary.risk_level ?? "-";

  return (
    <div className="space-y-4">
      <section className="rounded-2xl border bg-white p-4 shadow-sm">
        <h2 className="text-lg font-semibold">角色与权限</h2>
        <p className="text-sm text-gray-500">查看角色模板、权限绑定和启用状态。</p>
      </section>
      <section className="grid gap-4 md:grid-cols-2 xl:grid-cols-5">
        <StatCard label="角色总数" value={String(totalRoles)} />
        <StatCard label="活跃角色" value={String(activeRoles)} />
        <StatCard label="待审核" value={String(pendingRoles)} />
        <StatCard label="权限集" value={String(permissionSets)} />
        <StatCard label="风险等级" value={riskLevel} />
      </section>
      <Panel title="角色矩阵">
        <div className="space-y-2 text-sm text-gray-600">
          <div>角色矩阵摘要：{apiData?.linked_summaries.roles?.summary?.title ?? "-"}</div>
          <div>组织摘要：{apiData?.linked_summaries.organization?.summary?.title ?? "-"}</div>
          <div>部门摘要：{apiData?.linked_summaries.departments?.summary?.title ?? "-"}</div>
          <div>审计摘要：{apiData?.linked_summaries.audits?.summary?.title ?? "-"}</div>
        </div>
      </Panel>
    </div>
  );
}
function StatCard({ label, value }: { label: string; value: string }) { return <div className="rounded-2xl border bg-white p-4 shadow-sm"><div className="text-sm text-gray-500">{label}</div><div className="mt-2 text-xl font-bold">{value}</div></div>; }
function Panel({ title, children }: { title: string; children: React.ReactNode }) { return <section className="rounded-2xl border bg-white p-4 shadow-sm"><h3 className="font-semibold">{title}</h3><div className="mt-3">{children}</div></section>; }
