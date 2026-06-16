import { pandaPageResourceContracts } from '../pageResourceContracts'
import type { PandaPageResourceContract } from '../resourceContractTypes'
import { pandaResourceKeyPairs, type PandaApiResourceKey } from './resourceKeys'

const pandaApiResourceKeyByViewKey = new Map(pandaResourceKeyPairs)

function resolvePandaApiResourceKey(resourceKey: PandaPageResourceContract['resourceKeys'][number]): PandaApiResourceKey {
  const apiResourceKey = pandaApiResourceKeyByViewKey.get(resourceKey)
  if (!apiResourceKey) {
    throw new Error(`Missing Panda API resource key mapping for ${resourceKey}`)
  }
  return apiResourceKey
}

export type PandaRouteReadinessItem = {
  route: PandaPageResourceContract['page']
  readiness: PandaPageResourceContract['readiness']
  endpoint: string
  resources: PandaPageResourceContract['resourceKeys']
  apiResources: readonly PandaApiResourceKey[]
  runtimeFields: PandaPageResourceContract['runtimeFields']
  needs: PandaPageResourceContract['apiNeeds']
  backendOwned: boolean
}

export const pandaRouteReadiness: PandaRouteReadinessItem[] = Object.values(pandaPageResourceContracts).map(
  (contract) => ({
    route: contract.page,
    readiness: contract.readiness,
    endpoint: contract.bffEndpoint,
    resources: contract.resourceKeys,
    apiResources: contract.resourceKeys.map(resolvePandaApiResourceKey),
    runtimeFields: contract.runtimeFields,
    needs: contract.apiNeeds,
    backendOwned: contract.readiness === 'mock-ready',
  }),
)

export const pandaBackendAlignmentReadiness = {
  resourcesEndpoint: '/api/v1/workbench/resources',
  resourcesFlag: 'VITE_PANDA_RESOURCES_BFF',
  strictPassRequires: [
    'all Panda routes api-wired',
    'resources BFF enabled only after ApiPandaResourceSnapshot validation passes',
    'approval, sandbox, auth, secret, and execution policy remain backend-owned',
  ],
  pendingRoutes: pandaRouteReadiness.filter((item) => item.backendOwned),
} as const
