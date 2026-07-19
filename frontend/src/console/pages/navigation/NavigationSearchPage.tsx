import React from "react";

export type NavigationSearchPageProps = {
  query?: string;
  resultCount?: number;
  categories?: string[];
  riskLevel?: string;
  onOpenCategory?: (category: string) => void;
  onOpenRecent?: () => void;
};

export function NavigationSearchPage(props: NavigationSearchPageProps) {
  return (
    <div className="space-y-4">
      <section className="rounded-2xl border bg-white p-4 shadow-sm">
        <h2 className="text-lg font-semibold">搜索结果</h2>
        <p className="text-sm text-gray-500">按页面、工具、记忆、组织和能力市场搜索。</p>
      </section>
      <section className="grid gap-4 md:grid-cols-2 xl:grid-cols-4">
        <StatCard label="查询" value={props.query ?? "-"} />
        <StatCard label="结果数" value={String(props.resultCount ?? 0)} />
        <StatCard label="分类" value={String(props.categories?.length ?? 0)} />
        <StatCard label="风险等级" value={props.riskLevel ?? "-"} />
      </section>
      <Panel title="分类">
        <div className="flex flex-wrap gap-2 text-sm text-gray-600">
          {(props.categories ?? []).map((item) => (
            <button key={item} className="rounded-full border px-3 py-1 hover:bg-gray-50" onClick={() => props.onOpenCategory?.(item)}>{item}</button>
          ))}
        </div>
        <div className="mt-3 flex gap-2">
          <button className="rounded-lg border px-3 py-2 text-sm hover:bg-gray-50" onClick={() => props.onOpenRecent?.()}>最近访问</button>
        </div>
      </Panel>
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
