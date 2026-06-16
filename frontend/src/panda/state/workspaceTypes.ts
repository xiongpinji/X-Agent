import type { PandaResourceSnapshot, PandaResourceSource } from '../api/resourceSnapshotTypes'

export type PandaWorkspaceStatus = 'loading' | 'ready' | 'error'

export type PandaWorkspaceContextValue = {
  readonly resources: Readonly<PandaResourceSnapshot>
  readonly status: PandaWorkspaceStatus
  readonly source: PandaResourceSource
  readonly error: Error | null
  readonly refreshedAt: string
  readonly refresh: () => Promise<void>
}

export type PandaWorkspaceLifecycle = Omit<PandaWorkspaceContextValue, 'resources'>
