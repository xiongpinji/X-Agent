import { getPandaResourceSnapshot, pandaResources } from './resourceFallbackSnapshot'
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
      return {
        resources: apiResources,
        source: 'api',
      }
    }

    return {
      resources: getPandaResourceSnapshot(),
      source: 'mock',
    }
  } catch (error) {
    return {
      resources: getPandaResourceSnapshot(),
      source: 'mock',
      error: error instanceof Error ? error : new Error('无法加载 Panda 工作台资源'),
    }
  }
}
