import React from "react";
import { getAuthHeaders } from "../../../services/authHeaders";

export type OrganizationStructurePageProps = {
  rootName?: string;
  departmentCount?: number;
  memberCount?: number;
  roleCount?: number;
  riskLevel?: string;
};

type OrganizationStructureApiResponse = {
  resource_type: string;
  resource_id: string;
  primary: {
    root_name?: string;
    department_count?: number;
    member_count?: number;
    role_count?: number;
    risk_level?: string;
  };
  linked_summaries: {
    organization?: { summary?: { title?: string } | null; data?: Record<string, unknown> | null };
    departments?: { summary?: { title?: string } | null; data?: Record<string, unknown> | null };
    roles?: { summary?: { title?: string } | null; data?: Record<string, unknown> | null };
    audits?: { summary?: { title?: string } | null; data?: Record<string, unknown> | null };
  };
};

export function OrganizationStructurePage(props: OrganizationStructurePageProps) {
  const [apiData, setApiData] = React.useState<OrganizationStructureApiResponse | null>(null);

  React.useEffect(() => {
    let cancelled = false;
    const load = async () => {
      try {
        const response = await fetch("/api/v1/organization-control/structure", { method: "GET", headers: { "Content-Type": "application/json", ...getAuthHeaders() } });
        if (!response.ok) return;
        const payload = (await response.json()) as OrganizationStructureApiResponse;
        if (!cancelled) setApiData(payload);
      } catch (error) {
        console.warn("Failed to load organization structure", error);
      }
    };
    void load();
    return () => {
      cancelled = true;
    };
  }, []);

  const rootName = props.rootName ?? apiData?.primary.root_name ?? "-";
  const departmentCount = props.departmentCount ?? apiData?.primary.department_count ?? 0;
  const memberCount = props.memberCount ?? apiData?.primary.member_count ?? 0;
  const roleCount = props.roleCount ?? apiData?.primary.role_count ?? 0;
  const riskLevel = props.riskLevel ?? apiData?.primary.risk_level ?? "低";

  return (
    <div className="space-y-4">
      <section className="rounded-2xl border bg-white p-4 shadow-sm">
        <h2 className="text-lg font-semibold">组织结构</h2>
        <p className="text-sm text-gray-500">查看组织树、部门层级和成员分布。</p>
      </section>
      <section className="grid gap-4 md:grid-cols-2 xl:grid-cols-4">
        <StatCard label="根组织" value={rootName} />
        <StatCard label="部门数" value={String(departmentCount)} />
        <StatCard label="成员数" value={String(memberCount)} />
        <StatCard label="角色数" value={String(roleCount)} />
      </section>
      <Panel title="组织树">
        <div className="space-y-2 text-sm text-gray-600">
          <div>风险等级：{riskLevel}</div>
          <div>组织树摘要：{apiData?.linked_summaries.organization?.summary?.title ?? "-"}</div>
          <div>部门树摘要：{apiData?.linked_summaries.departments?.summary?.title ?? "-"}</div>
          <div>角色绑定摘要：{apiData?.linked_summaries.roles?.summary?.title ?? "-"}</div>
          <div>审计摘要：{apiData?.linked_summaries.audits?.summary?.title ?? "-"}</div>
        </div>
      </Panel>
    </div>
  );
}
function StatCard({ label, value }: { label: string; value: string }) { return <div className="rounded-2xl border bg-white p-4 shadow-sm"><div className="text-sm text-gray-500">{label}</div><div className="mt-2 text-xl font-bold">{value}</div></div>; }
function Panel({ title, children }: { title: string; children: React.ReactNode }) { return <section className="rounded-2xl border bg-white p-4 shadow-sm"><h3 className="font-semibold">{title}</h3><div className="mt-3">{children}</div></section>; }
