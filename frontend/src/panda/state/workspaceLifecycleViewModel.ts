import type { PandaResourceLoadResult } from '../api/resourceSnapshotTypes'
import type { PandaWorkspaceStatus } from './workspaceTypes'

export type PandaWorkspaceRefreshViewModel = {
  readonly resources: PandaResourceLoadResult['resources']
  readonly source: PandaResourceLoadResult['source']
  readonly error: Error | null
  readonly refreshedAt: string
  readonly status: PandaWorkspaceStatus
}

export function formatPandaWorkspaceRefreshTime(): string {
  return new Date().toLocaleTimeString('zh-CN', { hour: '2-digit', minute: '2-digit' })
}

export function buildPandaWorkspaceRefreshViewModel(result: PandaResourceLoadResult): PandaWorkspaceRefreshViewModel {
  return {
    resources: result.resources,
    source: result.source,
    error: result.error ?? null,
    refreshedAt: formatPandaWorkspaceRefreshTime(),
    status: result.error ? 'error' : 'ready',
  }
}

export function normalizePandaWorkspaceRefreshError(refreshError: unknown): Error {
  return refreshError instanceof Error ? refreshError : new Error('无法刷新 Panda 工作台资源')
}
