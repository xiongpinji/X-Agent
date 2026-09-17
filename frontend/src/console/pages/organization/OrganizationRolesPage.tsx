/**
 * 角色与权限 —— 接**真实**岗位模板目录。
 *
 * 此前这一页是「双重假」：
 * 1. 调用方硬编码 props（24 角色 / 21 启用 / 3 待审 / 12 权限集 / medium）；
 * 2. 页面自己又 fetch 一次**未挂载**的 `/api/v1/organization-control/roles`
 *    （恒 404，被 `if (!response.ok) return` 静默吞掉）；
 * 3. 渲染写成 `props.x ?? apiData?.x` ⇒ props 永远命中 ⇒ **即使后端真返回数据也
 *    永远不会显示**。
 *
 * 现在这一页是纯展示：只认外部传入的真实数据；没有数据就说没有，不编。
 * 「在用」列是该组织下真实创建过的智能体数量（后端 `list_agents` 数出来的）。
 */
import React from "react";

import type { OrganizationRoleTemplate } from "../../hooks/useOrganizationGovernance";

export type OrganizationRolesPageProps = {
  templates: OrganizationRoleTemplate[];
  totalTemplates: number;
  inUseTotal: number;
  roleGroups: Record<string, string[]>;
  /** 当前组织；为空表示尚未选择组织。 */
  activeOrgId: string | null;
  loading?: boolean;
  error?: string;
};

export function OrganizationRolesPage(props: OrganizationRolesPageProps) {
  const templatesWithUsage = props.templates.filter((item) => item.in_use > 0).length;

  return (
    <div className="space-y-4">
      <section className="console-section">
        <h2 className="text-lg font-semibold">角色与权限</h2>
        <p className="text-sm text-gray-500">
          岗位模板取自组织域的真实角色目录；「在用」是该组织下真实创建过的智能体数量。
        </p>
      </section>

      {props.error ? (
        <p role="alert" className="console-section text-sm text-red-600">
          {props.error}
        </p>
      ) : null}

      <section className="console-kpi-row">
        <StatCard label="模板总数" value={String(props.totalTemplates)} />
        <StatCard label="有在用的模板" value={String(templatesWithUsage)} />
        <StatCard label="在用智能体" value={String(props.inUseTotal)} />
        <StatCard
          label="角色分组"
          value={String(Object.keys(props.roleGroups).length)}
        />
        <StatCard label="当前组织" value={props.activeOrgId ?? "未选择"} />
      </section>

      <Panel title="岗位模板">
        {props.loading ? (
          <p role="status" className="text-sm text-gray-500">
            加载中…
          </p>
        ) : props.templates.length === 0 ? (
          <p className="text-sm text-gray-500">
            当前没有可用的岗位模板（角色目录为空）。
          </p>
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead>
                <tr className="border-b text-left text-xs text-gray-500">
                  <th className="py-2">岗位</th>
                  <th className="py-2">分组</th>
                  <th className="py-2">职级</th>
                  <th className="py-2">在用</th>
                  <th className="py-2">核心技能</th>
                </tr>
              </thead>
              <tbody>
                {props.templates.map((template) => (
                  <tr key={template.role_id} className="border-b">
                    <td className="py-2">
                      <div className="font-medium">{template.role_name}</div>
                      <div className="text-xs text-gray-500">{template.title}</div>
                    </td>
                    <td className="py-2">{template.category || "-"}</td>
                    <td className="py-2">{template.level || "-"}</td>
                    <td className="py-2">{template.in_use}</td>
                    <td className="py-2 text-xs text-gray-600">
                      {template.core_skills.slice(0, 3).join("、") || "-"}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
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
