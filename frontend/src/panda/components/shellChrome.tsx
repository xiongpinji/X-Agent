import { navItems } from '../data/navigation'
import type { PandaPage } from '../types'
import { BrandLockup, WorkspaceSwitcher } from './shellBranding'
export { BrandLockup, TopBarActions, WorkspaceSwitcher } from './shellBranding'
export { MobileStatusRow, TopBar, TopBarStatus } from './shellTopbar'

export type ShellNavigationProps = {
  activePage: PandaPage
  onSelectPage: (page: PandaPage) => void
}

export function Sidebar({ activePage, onSelectPage }: ShellNavigationProps) {
  return (
    <aside className="panda-sidebar">
      <BrandLockup />
      <ShellNavigation activePage={activePage} onSelectPage={onSelectPage} />
      <WorkspaceSwitcher />
    </aside>
  )
}

export function ShellNavigation({ activePage, onSelectPage }: ShellNavigationProps) {
  return (
    <nav className="panda-nav" aria-label="Panda Agent 主导航">
      {navItems.map((item) => {
        const Icon = item.icon
        return (
          <button
            key={item.id}
            className={`panda-nav-button ${activePage === item.id ? 'is-active' : ''}`}
            type="button"
            aria-current={activePage === item.id ? 'page' : undefined}
            aria-label={`打开${item.label}模块`}
            onClick={() => onSelectPage(item.id)}
          >
            <Icon size={18} aria-hidden="true" />
            <span className="text-sm font-medium">{item.label}</span>
          </button>
        )
      })}
    </nav>
  )
}
