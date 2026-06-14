import { getPandaResourceSnapshot, pandaResources } from './resourceFallbackSnapshot'
import {
  buildPandaApiResourceLoadResult,
  buildPandaMockResourceErrorResult,
  buildPandaMockResourceLoadResult,
} from './resourcesLoadResult'
import { loadPandaResourcesFromApi } from './resourcesApiLoader'
import type { PandaResourceLoadResult } from './resourceSnapshotTypes'

export type { PandaResourceLoadResult, PandaResourceSnapshot, PandaResourceSource } from './resourceSnapshotTypes'
export { getPandaResourceSnapshot, pandaResources } from './resourceFallbackSnapshot'
export {
  createPandaResourcesApiLoader,
  loadPandaResourcesFromApi,
  setPandaResourcesApiLoader,
  type PandaResourcesApiLoader,
  type PandaResourcesHttpClient,
} from './resourcesApiLoader'

export async function loadPandaResources(): Promise<PandaResourceLoadResult> {
  try {
    const apiResources = await loadPandaResourcesFromApi()
    if (apiResources) {
      return buildPandaApiResourceLoadResult(apiResources)
    }

    return buildPandaMockResourceLoadResult()
  } catch (error) {
    return buildPandaMockResourceErrorResult(error)
  }
}
