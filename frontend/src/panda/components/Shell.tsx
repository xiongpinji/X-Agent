import type { ReactNode } from 'react'
import type { PandaPage } from '../types'
import { MobileStatusRow, Sidebar, TopBar } from './shellChrome'
export {
  BrandLockup,
  MobileStatusRow,
  ShellNavigation,
  Sidebar,
  TopBar,
  TopBarActions,
  TopBarStatus,
  WorkspaceSwitcher,
} from './shellChrome'
export type { ShellNavigationProps } from './shellChrome'

type PandaShellFrameProps = {
  activePage: PandaPage
  pageLabel: string
  isLoading: boolean
  error: string | null
  onSelectPage: (page: PandaPage) => void
  rightRail: ReactNode
  children: ReactNode
}

function getWorkbenchConnectionLabel(isLoading: boolean, error: string | null) {
  if (isLoading) {
    return '同步工作台数据中'
  }

  return error ? '本地演示数据已接管' : '已连接 X-Agent Core'
}

export function PandaShellFrame({
  activePage,
  pageLabel,
  isLoading,
  error,
  onSelectPage,
  rightRail,
  children,
}: PandaShellFrameProps) {
  const connectionLabel = getWorkbenchConnectionLabel(isLoading, error)

  return (
    <div className="panda-shell">
      <a className="panda-skip-link" href="#panda-main-content">跳到主工作区</a>
      <Sidebar activePage={activePage} onSelectPage={onSelectPage} />
      <div className="panda-main-shell">
        <TopBar pageLabel={pageLabel} connectionLabel={connectionLabel} />
        <MobileStatusRow pageLabel={pageLabel} connectionLabel={connectionLabel} />
        <main id="panda-main-content" className="panda-content" aria-label={`${pageLabel} 工作区`}>
          {children}
        </main>
      </div>
      {rightRail}
    </div>
  )
}
