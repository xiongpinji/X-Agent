import React from "react";

export type OrganizationCenterOverviewPageProps = {
  resourceType?: string;
  resourceId?: string;
  totalDepartments?: number;
  totalRoles?: number;
  totalMembers?: number;
  pendingReviews?: number;
  riskLevel?: string;
  linkedOrganizationSummary?: { summary?: { title?: string } | null; data?: Record<string, unknown> | null } | null;
  linkedDepartmentsSummary?: { summary?: { title?: string } | null; data?: Record<string, unknown> | null } | null;
  linkedRolesSummary?: { summary?: { title?: string } | null; data?: Record<string, unknown> | null } | null;
  linkedAuditsSummary?: { summary?: { title?: string } | null; data?: Record<string, unknown> | null } | null;
  onOpenStructure?: () => void;
  onOpenRoles?: () => void;
  onOpenAudit?: () => void;
};

type OrganizationOverviewApiResponse = {
  resource_type: string;
  resource_id: string;
  primary: {
    total_departments?: number;
    total_roles?: number;
    total_members?: number;
    pending_reviews?: number;
    risk_level?: string;
  };
  linked_summaries: {
    organization?: { summary?: { title?: string } | null; data?: Record<string, unknown> | null };
    departments?: { summary?: { title?: string } | null; data?: Record<string, unknown> | null };
    roles?: { summary?: { title?: string } | null; data?: Record<string, unknown> | null };
    audits?: { summary?: { title?: string } | null; data?: Record<string, unknown> | null };
  };
};

export function OrganizationCenterOverviewPage(props: OrganizationCenterOverviewPageProps) {
  const [apiData, setApiData] = React.useState<OrganizationOverviewApiResponse | null>(null);

  React.useEffect(() => {
    let cancelled = false;
    const load = async () => {
      try {
        const response = await fetch("/api/v1/organization-control/overview", { method: "GET", headers: { "Content-Type": "application/json" } });
        if (!response.ok) return;
        const payload = (await response.json()) as OrganizationOverviewApiResponse;
        if (!cancelled) setApiData(payload);
      } catch (error) {
        console.warn("Failed to load organization overview", error);
      }
    };
    void load();
    return () => {
      cancelled = true;
    };
  }, []);

  const resourceType = props.resourceType ?? apiData?.resource_type ?? "organization_center_overview";
  const resourceId = props.resourceId ?? apiData?.resource_id ?? "-";
  const totalDepartments = props.totalDepartments ?? apiData?.primary.total_departments ?? 0;
  const totalRoles = props.totalRoles ?? apiData?.primary.total_roles ?? 0;
  const totalMembers = props.totalMembers ?? apiData?.primary.total_members ?? 0;
  const pendingReviews = props.pendingReviews ?? apiData?.primary.pending_reviews ?? 0;
  const riskLevel = props.riskLevel ?? apiData?.primary.risk_level ?? "低";

  return (
    <div className="space-y-4">
      <section className="rounded-2xl border bg-white p-4 shadow-sm">
        <div className="text-xs text-gray-500">{resourceType}</div>
        <div className="mt-1 text-sm text-gray-700">资源 ID：{resourceId}</div>
        <div className="mt-2 text-xs text-gray-500">组织摘要：{apiData?.linked_summaries.organization?.summary?.title ?? props.linkedOrganizationSummary?.summary?.title ?? "organization"} · {totalMembers} 名成员</div>
        <div className="mt-1 text-xs text-gray-500">部门摘要：{apiData?.linked_summaries.departments?.summary?.title ?? props.linkedDepartmentsSummary?.summary?.title ?? "departments"} · {totalDepartments} 个部门</div>
        <div className="mt-1 text-xs text-gray-500">角色摘要：{apiData?.linked_summaries.roles?.summary?.title ?? props.linkedRolesSummary?.summary?.title ?? "roles"} · {totalRoles} 个角色</div>
        <div className="mt-1 text-xs text-gray-500">审计摘要：{apiData?.linked_summaries.audits?.summary?.title ?? props.linkedAuditsSummary?.summary?.title ?? "audits"} · {pendingReviews} 个待审</div>
      </section>

      <section className="grid gap-4 md:grid-cols-2 xl:grid-cols-5">
        <StatCard label="部门数" value={String(totalDepartments)} />
        <StatCard label="角色数" value={String(totalRoles)} />
        <StatCard label="成员数" value={String(totalMembers)} />
        <StatCard label="待审核" value={String(pendingReviews)} />
        <StatCard label="风险等级" value={riskLevel} />
      </section>

      <section className="grid gap-4 xl:grid-cols-[minmax(0,1fr)_360px]">
        <Panel title="组织概览">
          <div className="space-y-2 text-sm text-gray-600">
            <div>组织权限中心用于治理组织、角色和权限。</div>
            <div className="text-xs text-gray-500">当前结构：{totalDepartments} 个部门 · {totalRoles} 个角色 · {totalMembers} 名成员</div>
            <div className="text-xs text-gray-500">待审核：{pendingReviews} 项 · 风险：{riskLevel}</div>
          </div>
        </Panel>

        <Panel title="快捷入口">
          <div className="grid gap-2">
            <button className="rounded-xl border px-3 py-2 text-left hover:bg-gray-50" onClick={() => props.onOpenStructure?.()}>查看组织结构</button>
            <button className="rounded-xl border px-3 py-2 text-left hover:bg-gray-50" onClick={() => props.onOpenRoles?.()}>查看角色权限</button>
            <button className="rounded-xl border px-3 py-2 text-left hover:bg-gray-50" onClick={() => props.onOpenAudit?.()}>查看审核队列</button>
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
