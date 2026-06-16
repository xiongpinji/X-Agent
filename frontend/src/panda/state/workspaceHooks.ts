import React from 'react'
import type { PandaResourceSnapshot } from '../api/resourceSnapshotTypes'
import { PandaWorkspaceLifecycleContext, PandaWorkspaceResourcesContext } from './workspaceProvider'
import type { PandaWorkspaceContextValue, PandaWorkspaceLifecycle } from './workspaceTypes'

export function usePandaWorkspace(): PandaWorkspaceContextValue {
  return {
    resources: usePandaWorkspaceResources(),
    ...usePandaWorkspaceLifecycle(),
  }
}

export function usePandaWorkspaceLifecycle(): PandaWorkspaceLifecycle {
  const lifecycle = React.useContext(PandaWorkspaceLifecycleContext)
  if (!lifecycle) {
    throw new Error('usePandaWorkspaceLifecycle must be used inside PandaWorkspaceProvider')
  }
  return lifecycle
}

function usePandaWorkspaceResources(): Readonly<PandaResourceSnapshot> {
  const resources = React.useContext(PandaWorkspaceResourcesContext)
  if (!resources) {
    throw new Error('usePandaWorkspaceResource must be used inside PandaWorkspaceProvider')
  }
  return resources
}

export function usePandaWorkspaceResource<Key extends keyof PandaResourceSnapshot>(key: Key): Readonly<PandaResourceSnapshot>[Key] {
  return usePandaWorkspaceResources()[key]
}
