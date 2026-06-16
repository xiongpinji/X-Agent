import { mapPandaResourceSnapshot, type ApiPandaResourceSnapshot } from './adapters'
import type { PandaResourceSnapshot } from './resourceSnapshotTypes'
import { validatePandaResourceSnapshot } from './resourcesValidation'

export type PandaResourcesApiLoader = () => Promise<ApiPandaResourceSnapshot>

export type PandaResourcesHttpClient = {
  getPandaResources: () => Promise<ApiPandaResourceSnapshot>
}

let pandaResourcesApiLoader: PandaResourcesApiLoader | null = null

export function setPandaResourcesApiLoader(loader: PandaResourcesApiLoader | null) {
  pandaResourcesApiLoader = loader
}

export function createPandaResourcesApiLoader(client: PandaResourcesHttpClient): PandaResourcesApiLoader {
  return async () => validatePandaResourceSnapshot(await client.getPandaResources())
}

export async function loadPandaResourcesFromApi(): Promise<PandaResourceSnapshot | null> {
  if (!pandaResourcesApiLoader) {
    return null
  }
  const snapshot = await pandaResourcesApiLoader()
  return mapPandaResourceSnapshot(snapshot)
}
