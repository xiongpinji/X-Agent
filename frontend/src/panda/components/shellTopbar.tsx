import { Search } from 'lucide-react'
import { TopBarActions } from './shellControls'

export function MobileStatusRow({ pageLabel, connectionLabel }: { pageLabel: string; connectionLabel: string }) {
  return (
    <div className="panda-mobile-status" aria-live="polite">
      <span>{pageLabel}</span>
      <span>{connectionLabel}</span>
    </div>
  )
}

export function TopBar({ pageLabel, connectionLabel }: { pageLabel: string; connectionLabel: string }) {
  return (
    <header className="panda-topbar">
      <label className="panda-search">
        <Search size={18} aria-hidden="true" />
        <input aria-label="全局搜索" placeholder="搜索智能体、工作流、项目、审计证据..." />
        <span className="text-xs" aria-hidden="true">⌘K</span>
      </label>
      <TopBarStatus pageLabel={pageLabel} connectionLabel={connectionLabel} />
      <TopBarActions />
    </header>
  )
}

export function TopBarStatus({ pageLabel, connectionLabel }: { pageLabel: string; connectionLabel: string }) {
  return (
    <div className="panda-topbar-status text-sm text-slate-400">
      <span className="text-slate-200">{pageLabel}</span>
      <span className="mx-2">/</span>
      <span>{connectionLabel}</span>
    </div>
  )
}
