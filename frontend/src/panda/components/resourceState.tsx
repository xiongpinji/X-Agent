import React from 'react'
import { usePandaWorkspaceLifecycle } from '../state/PandaWorkspaceContext'
import { buildPandaResourceStateViewModel } from './resourceStateViewModel'
import { PandaEmptyState, PandaErrorState, PandaLoadingState } from './statePanelPrimitives'

export { PandaEmptyState, PandaErrorState, PandaLoadingState, PandaStatePanel } from './statePanelPrimitives'

export function PandaResourceState({
  count,
  emptyTitle,
  emptyDescription,
  loadingTitle = '正在同步资源',
  loadingDescription = '正在读取该模块所需的工作台资源。',
  children,
}: {
  count: number
  emptyTitle: string
  emptyDescription: string
  loadingTitle?: string
  loadingDescription?: string
  children: React.ReactNode
}) {
  const { status, error, refresh } = usePandaWorkspaceLifecycle()
  const state = buildPandaResourceStateViewModel({ count, status, error })

  if (state.kind === 'loading') {
    return <PandaLoadingState title={loadingTitle} description={loadingDescription} />
  }

  if (state.kind === 'error') {
    return (
      <PandaErrorState
        title="资源暂不可用"
        description={state.errorDescription}
        action={
          <button className="panda-state-action" type="button" onClick={() => void refresh()}>
            重新同步资源
          </button>
        }
      />
    )
  }

  if (state.kind === 'empty') {
    return <PandaEmptyState title={emptyTitle} description={emptyDescription} />
  }

  return <>{children}</>
}
