import React from "react";

export type OrganizationOverviewPageProps = {
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
};

export function OrganizationOverviewPage(props: OrganizationOverviewPageProps) {
  const resourceType = props.resourceType ?? "organization_center_overview";
  const resourceId = props.resourceId ?? "-";
  const totalDepartments = props.totalDepartments ?? 0;
  const totalRoles = props.totalRoles ?? 0;
  const totalMembers = props.totalMembers ?? 0;
  const pendingReviews = props.pendingReviews ?? 0;
  const riskLevel = props.riskLevel ?? "低";

  return (
    <div className="space-y-4">
      <section className="rounded-2xl border bg-white p-4 shadow-sm">
        <div className="text-xs text-gray-500">{resourceType}</div>
        <div className="mt-1 text-sm text-gray-700">资源 ID：{resourceId}</div>
        <div className="mt-2 text-xs text-gray-500">组织摘要：{props.linkedOrganizationSummary?.summary?.title ?? "organization"}</div>
        <div className="mt-1 text-xs text-gray-500">部门摘要：{props.linkedDepartmentsSummary?.summary?.title ?? "departments"}</div>
        <div className="mt-1 text-xs text-gray-500">角色摘要：{props.linkedRolesSummary?.summary?.title ?? "roles"}</div>
        <div className="mt-1 text-xs text-gray-500">审计摘要：{props.linkedAuditsSummary?.summary?.title ?? "audits"}</div>
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
          </div>
        </Panel>

        <Panel title="快捷入口">
          <div className="grid gap-2">
            <button className="rounded-xl border px-3 py-2 text-left hover:bg-gray-50">查看组织结构</button>
            <button className="rounded-xl border px-3 py-2 text-left hover:bg-gray-50">查看角色权限</button>
            <button className="rounded-xl border px-3 py-2 text-left hover:bg-gray-50">查看审核队列</button>
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
