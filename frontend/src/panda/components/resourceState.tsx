import React from 'react'
import { usePandaWorkspaceLifecycle } from '../state/PandaWorkspaceContext'
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

  if (status === 'loading' && count === 0) {
    return <PandaLoadingState title={loadingTitle} description={loadingDescription} />
  }

  if (status === 'error' && count === 0) {
    return (
      <PandaErrorState
        title="资源暂不可用"
        description={error?.message ?? '当前资源切片加载失败，等待后端接口或本地回退数据恢复。'}
        action={
          <button className="panda-state-action" type="button" onClick={() => void refresh()}>
            重新同步资源
          </button>
        }
      />
    )
  }

  if (count === 0) {
    return <PandaEmptyState title={emptyTitle} description={emptyDescription} />
  }

  return <>{children}</>
}
