import React from 'react'
import { getPandaResourceSnapshot, loadPandaResources } from '../api/resourcesClient'
import type { PandaResourceSnapshot, PandaResourceSource } from '../api/resourceSnapshotTypes'
import {
  buildPandaWorkspaceRefreshViewModel,
  formatPandaWorkspaceRefreshTime,
  normalizePandaWorkspaceRefreshError,
} from './workspaceLifecycleViewModel'
import type { PandaWorkspaceLifecycle, PandaWorkspaceStatus } from './workspaceTypes'

export const PandaWorkspaceResourcesContext = React.createContext<Readonly<PandaResourceSnapshot> | null>(null)
export const PandaWorkspaceLifecycleContext = React.createContext<PandaWorkspaceLifecycle | null>(null)

export function PandaWorkspaceProvider({ children }: { children: React.ReactNode }) {
  const [resources, setResources] = React.useState<PandaResourceSnapshot>(() => getPandaResourceSnapshot())
  const [status, setStatus] = React.useState<PandaWorkspaceStatus>('ready')
  const [source, setSource] = React.useState<PandaResourceSource>('mock')
  const [error, setError] = React.useState<Error | null>(null)
  const [refreshedAt, setRefreshedAt] = React.useState(() => formatPandaWorkspaceRefreshTime())
  const refreshSeqRef = React.useRef(0)
  const isMountedRef = React.useRef(false)

  React.useEffect(() => {
    isMountedRef.current = true

    return () => {
      isMountedRef.current = false
    }
  }, [])

  const refresh = React.useCallback(async () => {
    const refreshSeq = refreshSeqRef.current + 1
    refreshSeqRef.current = refreshSeq
    const isCurrentRefresh = () => isMountedRef.current && refreshSeqRef.current === refreshSeq

    try {
      setStatus('loading')
      const result = await loadPandaResources()
      if (!isCurrentRefresh()) {
        return
      }
      const viewModel = buildPandaWorkspaceRefreshViewModel(result)
      setResources(viewModel.resources)
      setSource(viewModel.source)
      setError(viewModel.error)
      setRefreshedAt(viewModel.refreshedAt)
      setStatus(viewModel.status)
    } catch (refreshError) {
      if (!isCurrentRefresh()) {
        return
      }
      setError(normalizePandaWorkspaceRefreshError(refreshError))
      setStatus('error')
    }
  }, [])

  React.useEffect(() => {
    void refresh()
  }, [refresh])

  const lifecycleValue = React.useMemo<PandaWorkspaceLifecycle>(
    () => ({ status, source, error, refreshedAt, refresh }),
    [status, source, error, refreshedAt, refresh],
  )

  return (
    <PandaWorkspaceResourcesContext.Provider value={resources}>
      <PandaWorkspaceLifecycleContext.Provider value={lifecycleValue}>
        {children}
      </PandaWorkspaceLifecycleContext.Provider>
    </PandaWorkspaceResourcesContext.Provider>
  )
}
