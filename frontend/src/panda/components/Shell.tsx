import type { ReactNode } from 'react'
import type { PandaPage } from '../types'
import { MobileStatusRow, Sidebar, TopBar } from './shellChrome'
import { buildShellConnectionViewModel } from './shellConnectionViewModel'
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
export { buildShellConnectionViewModel } from './shellConnectionViewModel'
export type { ShellConnectionViewModel } from './shellConnectionViewModel'

type PandaShellFrameProps = {
  activePage: PandaPage
  pageLabel: string
  isLoading: boolean
  error: string | null
  onSelectPage: (page: PandaPage) => void
  rightRail: ReactNode
  children: ReactNode
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
  const { connectionLabel } = buildShellConnectionViewModel({ isLoading, error })

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
