import { mockWorkbenchHome } from '../data/mockHome'
import { pandaResources } from './resourceFallbackSnapshot'
import type { PandaResourceSnapshot } from './resourceSnapshotTypes'
import { createPandaResourcesApiLoader, type PandaResourcesHttpClient } from './resourcesApiLoader'
import {
  createPandaResourcesFetchClient,
  resolvePandaResourcesEndpoint,
  type PandaResourcesFetchClientOptions,
} from './resourcesHttpClient'
import type { PandaWorkbenchHomeResult } from './workbenchClient'
import { apiResourceSnapshotFixture } from './resourceSnapshotFixtures'

export const pandaResourcesHttpClientFixture = {
  getPandaResources: async () => apiResourceSnapshotFixture,
} satisfies PandaResourcesHttpClient

export const pandaResourcesApiLoaderFixture = createPandaResourcesApiLoader(pandaResourcesHttpClientFixture)

export const pandaResourcesFetchClientOptionsFixture = {
  endpoint: resolvePandaResourcesEndpoint(''),
  getToken: () => 'fixture-token',
} satisfies PandaResourcesFetchClientOptions

export const pandaResourcesFetchClientFixture = createPandaResourcesFetchClient(pandaResourcesFetchClientOptionsFixture) satisfies PandaResourcesHttpClient

export const workbenchClientFixture = {
  home: mockWorkbenchHome,
  source: 'mock',
  error: new Error('fixture'),
} satisfies PandaWorkbenchHomeResult

export const resourceClientFixture = pandaResources satisfies PandaResourceSnapshot
