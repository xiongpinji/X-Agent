import React from "react";

export type NavigationShortcutsPageProps = {
  shortcutCount?: number;
  favoriteCount?: number;
  recentCount?: number;
  riskLevel?: string;
  onOpenRecent?: () => void;
  onOpenFavorites?: () => void;
  onOpenSearch?: () => void;
};

export function NavigationShortcutsPage(props: NavigationShortcutsPageProps) {
  return (
    <div className="space-y-4">
      <section className="console-section">
        <h2 className="text-lg font-semibold">快捷切换</h2>
        <p className="text-sm text-gray-500">显示最近访问、常用入口和快速操作。</p>
      </section>
      <section className="console-kpi-row">
        <StatCard label="快捷方式" value={String(props.shortcutCount ?? 0)} />
        <StatCard label="常用入口" value={String(props.favoriteCount ?? 0)} />
        <StatCard label="最近访问" value={String(props.recentCount ?? 0)} />
        <StatCard label="风险等级" value={props.riskLevel ?? "-"} />
      </section>
      <Panel title="快捷列表">
        <div className="grid gap-2">
          <button className="border-b px-3 py-2 text-left hover:bg-gray-50" onClick={() => props.onOpenRecent?.()}>最近访问</button>
          <button className="border-b px-3 py-2 text-left hover:bg-gray-50" onClick={() => props.onOpenFavorites?.()}>常用入口</button>
          <button className="border-b px-3 py-2 text-left hover:bg-gray-50" onClick={() => props.onOpenSearch?.()}>打开搜索</button>
        </div>
      </Panel>
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
