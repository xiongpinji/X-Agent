/**
 * 组织权限中心（概览）。
 *
 * 此前本页会额外 fetch 一次 `/api/v1/organization-control/overview` —— 那个路由
 * **未挂载**，恒 404，且失败分支是 `if (!response.ok) return`（静默吞掉）⇒ 页面
 * 一直在用 props 里的数字当 0 显示。也就是说：**每次打开这一页都会打一个必然失败
 * 的请求，然后把失败伪装成「没有数据」**。
 *
 * 现在删掉那次 fetch，只认外部传入的真实数据（全部来自组织域真实端点）。
 */
import React from "react";

export type OrganizationCenterOverviewPageProps = {
  organizationName: string;
  totalDepartments: number;
  totalAgents: number;
  /** 岗位模板总数（真实角色目录）。 */
  totalRoleTemplates: number;
  /** 该组织下真实在用的智能体数量。 */
  inUseAgents: number;
  /** 当前租户的组织域审计事件总数。 */
  auditTotal: number;
  auditFailure: number;
  loading?: boolean;
  error?: string;
  onOpenStructure?: () => void;
  onOpenRoles?: () => void;
  onOpenAudit?: () => void;
};

export function OrganizationCenterOverviewPage(
  props: OrganizationCenterOverviewPageProps,
) {
  return (
    <div className="space-y-4">
      <header className="console-page-header">
        <h1 className="page-title">组织权限中心</h1>
        <div className="console-resource-id">
          组织：{props.organizationName || "未选择组织"}
        </div>
        <div className="console-summary-line">
          部门 {props.totalDepartments} 个 · 智能体 {props.totalAgents} 个
        </div>
        <div className="console-summary-line">
          岗位模板 {props.totalRoleTemplates} 个 · 在用 {props.inUseAgents} 个
        </div>
        <div className="console-summary-line">
          组织域审计 {props.auditTotal} 条 · 失败 {props.auditFailure} 条
        </div>
      </header>

      {props.error ? (
        <p role="alert" className="console-section text-sm text-red-600">
          {props.error}
        </p>
      ) : null}

      <section className="console-kpi-row">
        <StatCard label="部门数" value={String(props.totalDepartments)} />
        <StatCard label="智能体数" value={String(props.totalAgents)} />
        <StatCard label="岗位模板" value={String(props.totalRoleTemplates)} />
        <StatCard label="在用岗位" value={String(props.inUseAgents)} />
        <StatCard label="审计事件" value={String(props.auditTotal)} />
      </section>

      <section className="grid gap-4 xl:grid-cols-[minmax(0,1fr)_360px]">
        <Panel title="组织概览">
          <div className="space-y-2 text-sm text-gray-600">
            <div>组织权限中心用于治理组织、岗位模板与审计流水。</div>
            <div className="text-xs text-gray-500">
              当前结构：{props.totalDepartments} 个部门 · {props.totalAgents} 个智能体 ·{" "}
              {props.totalRoleTemplates} 个岗位模板
            </div>
            <div className="text-xs text-gray-500">
              审计：共 {props.auditTotal} 条，其中失败 {props.auditFailure} 条
            </div>
            {props.loading ? (
              <div role="status" className="text-xs text-gray-400">
                正在同步组织治理数据…
              </div>
            ) : null}
          </div>
        </Panel>

        <Panel title="快捷入口">
          <div className="grid gap-2">
            {props.onOpenStructure ? (
              <button
                className="border-b px-3 py-2 text-left hover:bg-gray-50"
                onClick={() => props.onOpenStructure?.()}
              >
                查看组织结构
              </button>
            ) : null}
            {props.onOpenRoles ? (
              <button
                className="border-b px-3 py-2 text-left hover:bg-gray-50"
                onClick={() => props.onOpenRoles?.()}
              >
                查看角色权限
              </button>
            ) : null}
            {props.onOpenAudit ? (
              <button
                className="border-b px-3 py-2 text-left hover:bg-gray-50"
                onClick={() => props.onOpenAudit?.()}
              >
                查看审核队列
              </button>
            ) : null}
          </div>
        </Panel>
      </section>
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
      <h3 className="text-base font-semibold text-gray-900">{title}</h3>
      <div className="mt-3">{children}</div>
    </section>
  );
}
