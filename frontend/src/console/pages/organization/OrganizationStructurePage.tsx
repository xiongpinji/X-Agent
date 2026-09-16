/**
 * 组织结构页 —— 真实组织 / 部门数据。
 *
 * ★ 这里此前是一张**假页面**：它渲染的是 `ConsoleShell` 硬编码传进来的 fixture
 * （`rootName="统一控制台" departmentCount={8} memberCount={86} roleCount={24}`），
 * 同时去 fetch 一个**未挂载**的 `/api/v1/organization-control/structure`（恒 404）。
 * 由于渲染写成 `props.x ?? apiData?.x ?? 默认值`，props 永远命中 ⇒ 真实响应即使
 * 拿到了也会被静默丢弃，页面上永远是那 8 个部门 / 86 个成员。
 *
 * 这与「用户刚在控制台建了部门，来组织结构却看不到」是同一件事的两面，所以
 * (c) 把它改成直接消费 `/api/v1/organization/*` 的真实数据，且**不再保留任何
 * props 覆盖真值的通道** —— 那种写法正是让假数据盖住真数据的机制。
 */
import React from "react";

import type {
  DepartmentRecord,
  OrganizationRecord,
} from "../../hooks/useOrganizationDirectory";

export type OrganizationStructurePageProps = {
  organizations: OrganizationRecord[];
  departments: DepartmentRecord[];
  activeOrgId: string | null;
  loading: boolean;
  error: string;
  onSelectOrg: (orgId: string) => void;
  /** 当前组织下的岗位智能体数（来自组织图，不是本页的数据源）。 */
  agentCount?: number;
};

export function OrganizationStructurePage(props: OrganizationStructurePageProps) {
  const activeOrg =
    props.organizations.find((item) => item.org_id === props.activeOrgId) ?? null;
  const departmentNameById = new Map(
    props.departments.map((item) => [item.department_id, item.name]),
  );
  const rootDepartments = props.departments.filter(
    (item) => item.parent_department_id === null,
  );

  return (
    <div className="space-y-4">
      <section className="console-section">
        <h2 className="text-lg font-semibold">组织结构</h2>
        <p className="text-sm text-gray-500">
          来自组织域真实数据的部门列表 —— 在组织图页新增的部门会立刻出现在这里。
        </p>
        {props.organizations.length > 1 ? (
          <label className="mt-3 block max-w-sm">
            <div className="mb-1 text-sm font-medium text-gray-700">查看的组织</div>
            <select
              className="w-full border px-3 py-2"
              value={props.activeOrgId ?? ""}
              onChange={(event) => props.onSelectOrg(event.target.value)}
            >
              {props.organizations.map((organization) => (
                <option key={organization.org_id} value={organization.org_id}>
                  {organization.name}
                </option>
              ))}
            </select>
          </label>
        ) : null}
      </section>

      {props.error ? (
        <p role="alert" className="console-section text-sm text-red-600">
          {props.error}
        </p>
      ) : null}

      <section className="console-kpi-row">
        <StatCard label="根组织" value={activeOrg?.name ?? "-"} />
        <StatCard label="部门数" value={String(props.departments.length)} />
        <StatCard label="成员数" value={String(props.agentCount ?? 0)} />
        <StatCard label="组织数" value={String(props.organizations.length)} />
      </section>

      <Panel title="组织树">
        <div className="space-y-2 text-sm text-gray-600">
          <div>所属租户：{activeOrg?.tenant_id ?? "-"}</div>
          <div>组织状态：{activeOrg?.status ?? "-"}</div>
          <div>创建者：{activeOrg?.owner_user_id ?? "-"}</div>
          <div>一级部门：{rootDepartments.length} 个</div>
          <div>组织说明：{activeOrg?.description || "-"}</div>
        </div>
      </Panel>

      <Panel title="部门列表">
        {props.loading ? (
          <p className="text-sm text-gray-500">加载中…</p>
        ) : props.departments.length === 0 ? (
          <p className="text-sm text-gray-500">
            当前组织还没有部门。到「组织图」页用「新建部门」建一个。
          </p>
        ) : (
          <table className="w-full text-left text-sm">
            <thead className="text-xs uppercase tracking-wide text-gray-400">
              <tr>
                <th className="py-2">部门</th>
                <th className="py-2">上级部门</th>
                <th className="py-2">负责人</th>
                <th className="py-2">职责</th>
              </tr>
            </thead>
            <tbody>
              {props.departments.map((department) => (
                <tr key={department.department_id} className="border-t">
                  <td className="py-2 font-medium">{department.name}</td>
                  <td className="py-2 text-gray-500">
                    {department.parent_department_id
                      ? departmentNameById.get(department.parent_department_id) ??
                        department.parent_department_id
                      : "—"}
                  </td>
                  <td className="py-2 text-gray-500">
                    {department.leader_agent_id ? "已指定" : "—"}
                  </td>
                  <td className="py-2 text-gray-500">{department.mission || "—"}</td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </Panel>
    </div>
  );
}

function StatCard({ label, value }: { label: string; value: string }) {
  return (
    <div className="console-kpi">
      <span className="kpi-label">{label}</span>
      <span className="kpi-value">{value}</span>
    </div>
  );
}

function Panel({ title, children }: { title: string; children: React.ReactNode }) {
  return (
    <section className="console-section">
      <h3 className="font-semibold">{title}</h3>
      <div className="mt-3">{children}</div>
    </section>
  );
}
