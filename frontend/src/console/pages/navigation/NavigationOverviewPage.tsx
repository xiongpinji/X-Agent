import React from "react";

export type NavigationOverviewPageProps = {
  resourceType?: string;
  resourceId?: string;
  recentPages?: string[];
  favoritePages?: string[];
  searchEnabled?: boolean;
  riskLevel?: string;
  linkedRecentSummary?: { summary?: { title?: string } | null; data?: Record<string, unknown> | null } | null;
  linkedFavoritesSummary?: { summary?: { title?: string } | null; data?: Record<string, unknown> | null } | null;
  linkedSearchSummary?: { summary?: { title?: string } | null; data?: Record<string, unknown> | null } | null;
  linkedShortcutsSummary?: { summary?: { title?: string } | null; data?: Record<string, unknown> | null } | null;
  onOpenPage?: (pageKey: string) => void;
  onOpenSearch?: () => void;
};

export function NavigationOverviewPage(props: NavigationOverviewPageProps) {
  const resourceType = props.resourceType ?? "navigation_center_overview";
  const resourceId = props.resourceId ?? "-";
  const recentPages = props.recentPages ?? [];
  const favoritePages = props.favoritePages ?? [];
  const searchEnabled = props.searchEnabled ?? true;
  const riskLevel = props.riskLevel ?? "低";

  return (
    <div className="space-y-4">
      <section className="rounded-2xl border bg-white p-4 shadow-sm">
        <div className="text-xs text-gray-500">{resourceType}</div>
        <div className="mt-1 text-sm text-gray-700">资源 ID：{resourceId}</div>
        <div className="mt-2 text-xs text-gray-500">最近摘要：{props.linkedRecentSummary?.summary?.title ?? "recent pages"} · {recentPages.length} 条最近访问</div>
        <div className="mt-1 text-xs text-gray-500">收藏摘要：{props.linkedFavoritesSummary?.summary?.title ?? "favorite pages"} · {favoritePages.length} 个常用入口</div>
        <div className="mt-1 text-xs text-gray-500">搜索摘要：{props.linkedSearchSummary?.summary?.title ?? "search index"} · {searchEnabled ? "搜索已启用" : "搜索未启用"}</div>
        <div className="mt-1 text-xs text-gray-500">快捷摘要：{props.linkedShortcutsSummary?.summary?.title ?? "quick shortcuts"} · {String((props.linkedShortcutsSummary?.data && Object.keys(props.linkedShortcutsSummary.data).length) || 0)} 个快捷项</div>
      </section>

      <section className="grid gap-4 md:grid-cols-2 xl:grid-cols-5">
        <StatCard label="最近访问" value={String(recentPages.length)} />
        <StatCard label="常用入口" value={String(favoritePages.length)} />
        <StatCard label="搜索可用" value={searchEnabled ? "是" : "否"} />
        <StatCard label="快捷方式" value={String((props.linkedShortcutsSummary?.data && Object.keys(props.linkedShortcutsSummary.data).length) || 0)} />
        <StatCard label="风险等级" value={riskLevel} />
      </section>

      <section className="grid gap-4 xl:grid-cols-[minmax(0,1fr)_360px]">
        <Panel title="最近访问">
          <div className="space-y-2 text-sm text-gray-600">
            {recentPages.map((page) => (
              <button key={page} className="w-full rounded-lg border px-3 py-2 text-left hover:bg-gray-50" onClick={() => props.onOpenPage?.(page)}>{page}</button>
            ))}
          </div>
        </Panel>

        <Panel title="常用入口">
          <div className="space-y-2 text-sm text-gray-600">
            {favoritePages.map((page) => (
              <button key={page} className="w-full rounded-lg border px-3 py-2 text-left hover:bg-gray-50" onClick={() => props.onOpenPage?.(page)}>{page}</button>
            ))}
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
