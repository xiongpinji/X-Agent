/**
 * 组织审核 —— 接**真实**审计流水。
 *
 * 此前这一页与「角色权限」是同一套「双重假」：硬编码 props（13 条事件 / 10 成功 /
 * 3 失败）+ 一次对**未挂载** `/api/v1/organization-control/audit` 的 fetch（恒 404，
 * 被静默吞掉），且渲染是 `props.x ?? apiData?.x` ⇒ props 永远命中。
 *
 * 现在数据来自 `core.audit.AuditStore` —— 与创建组织/部门/岗位智能体时**写的是同
 * 一份存储**，按租户隔离。空就是空，不再显示编造的 13 条。
 */
import React from "react";

import type {
  OrganizationAuditRecord,
  OrganizationAuditSummary,
} from "../../hooks/useOrganizationGovernance";

export type OrganizationAuditPageProps = {
  records: OrganizationAuditRecord[];
  total: number;
  summary: OrganizationAuditSummary;
  /** 后端扫描上界被撑满 ⇒ 列表只是最近一部分，必须显示出来。 */
  truncated?: boolean;
  loading?: boolean;
  error?: string;
};

export function OrganizationAuditPage(props: OrganizationAuditPageProps) {
  return (
    <div className="space-y-4">
      <section className="console-section">
        <h2 className="text-lg font-semibold">组织审核</h2>
        <p className="text-sm text-gray-500">
          组织、部门与岗位智能体的创建流水（与写端点同一份审计存储，按租户隔离）。
        </p>
      </section>

      {props.error ? (
        <p role="alert" className="console-section text-sm text-red-600">
          {props.error}
        </p>
      ) : null}

      <section className="console-kpi-row">
        <StatCard label="事件总数" value={String(props.total)} />
        <StatCard label="成功" value={String(props.summary.success)} />
        <StatCard label="失败" value={String(props.summary.failure)} />
        <StatCard label="最近结果" value={props.summary.latest_outcome ?? "-"} />
      </section>

      {props.truncated ? (
        <p role="status" className="console-section text-sm text-amber-700">
          记录数已达后端扫描上界，下面只显示最近的一部分。
        </p>
      ) : null}

      <Panel title="审核记录">
        {props.loading ? (
          <p role="status" className="text-sm text-gray-500">
            加载中…
          </p>
        ) : props.records.length === 0 ? (
          <p className="text-sm text-gray-500">
            当前租户还没有组织域操作记录。新建组织、部门或岗位智能体后，这里会出现对应的流水。
          </p>
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead>
                <tr className="border-b text-left text-xs text-gray-500">
                  <th className="py-2">时间</th>
                  <th className="py-2">操作人</th>
                  <th className="py-2">动作</th>
                  <th className="py-2">资源</th>
                  <th className="py-2">结果</th>
                </tr>
              </thead>
              <tbody>
                {props.records.map((record) => (
                  <tr key={record.id} className="border-b">
                    <td className="py-2 text-xs text-gray-600">
                      {formatTimestamp(record.created_at)}
                    </td>
                    <td className="py-2">{record.actor_id}</td>
                    <td className="py-2 font-medium">{record.action}</td>
                    <td className="py-2 text-xs text-gray-600">
                      <div>{record.resource_type}</div>
                      <div className="text-gray-400">{record.resource_id ?? "-"}</div>
                    </td>
                    <td className="py-2">
                      <span
                        className={
                          record.outcome === "success"
                            ? "rounded-full bg-green-50 px-2 py-1 text-xs text-green-700"
                            : "rounded-full bg-amber-50 px-2 py-1 text-xs text-amber-700"
                        }
                      >
                        {record.outcome}
                      </span>
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

/** 后端给的是 ISO 串；展示层只做「本地可读」，解析失败就原样返回（不吞错误）。 */
function formatTimestamp(value: string): string {
  const parsed = new Date(value);
  if (Number.isNaN(parsed.getTime())) return value;
  return parsed.toLocaleString();
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
