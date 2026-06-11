import React from 'react'
import type { PandaResourceSnapshot } from '../api/resourceSnapshotTypes'
import { usePandaWorkspaceResource } from './PandaWorkspaceContext'
import type { CountedModulePageResource } from './modulePageResourceTypes'

export function useCountedModulePageResource<
  ResourceKey extends keyof PandaResourceSnapshot,
  ResourceName extends string,
>(
  resourceKey: ResourceKey,
  resourceName: ResourceName,
): CountedModulePageResource<ResourceName, PandaResourceSnapshot[ResourceKey]> {
  const resources = usePandaWorkspaceResource(resourceKey)
  return React.useMemo(
    () => ({ [resourceName]: resources, count: resources.length }) as CountedModulePageResource<ResourceName, PandaResourceSnapshot[ResourceKey]>,
    [resourceName, resources],
  )
}
