import React from "react";

export type MemoryManagementPageProps = {
  pendingChanges?: number;
  activeChanges?: number;
  archivedChanges?: number;
  reviewRequired?: number;
  riskLevel?: string;
};

export function MemoryManagementPage(props: MemoryManagementPageProps) {
  return (
    <div className="space-y-4">
      <section className="console-section">
        <h2 className="text-lg font-semibold">记忆管理</h2>
        <p className="text-sm text-gray-500">管理记忆、经验和引用的变更与审核。</p>
      </section>

      <section className="console-kpi-row">
        <StatCard label="待变更" value={String(props.pendingChanges ?? 0)} />
        <StatCard label="活跃变更" value={String(props.activeChanges ?? 0)} />
        <StatCard label="已归档" value={String(props.archivedChanges ?? 0)} />
        <StatCard label="需审核" value={String(props.reviewRequired ?? 0)} />
        <StatCard label="风险等级" value={props.riskLevel ?? "-"} />
      </section>

      <section className="grid gap-4 xl:grid-cols-[minmax(0,1fr)_360px]">
        <Panel title="审核队列">
          <div className="space-y-3 text-sm text-gray-600">
            <div>暂无具体变更列表，后续可接后端审核数据。</div>
          </div>
        </Panel>

        <Panel title="操作区">
          <div className="grid gap-2">
            <button className="border-b px-3 py-2 text-left hover:bg-gray-50">批准选中项</button>
            <button className="border-b px-3 py-2 text-left hover:bg-gray-50">拒绝选中项</button>
            <button className="border-b px-3 py-2 text-left hover:bg-gray-50">刷新审核队列</button>
          </div>
        </Panel>
      </section>
    </div>
  );
}

function StatCard({ label, value }: { label: string; value: string }) {
  return (
    <div className="console-kpi"><span className="kpi-label">{label}</span><span className="kpi-value">{value}</span></div>
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
