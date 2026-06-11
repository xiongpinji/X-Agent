import { extractResourceKeyPairs, read, readJson } from './panda-script-utils.mjs'
import { extractPandaPageResourceContracts } from './panda-contract-parser.mjs'
import { getPandaModulePageStructure } from './panda-module-page-structure.mjs'
import { buildPandaRouteRolloverPlan } from './panda-route-rollover-plan.mjs'

export const PANDA_ALIGNMENT_CONTEXT_SOURCE = 'frontend/scripts/panda-alignment-context.mjs'

export function getPandaAlignmentContext() {
  const manifest = readJson('src/panda/pandaFrontendManifest.json')
  const contracts = extractPandaPageResourceContracts(read('src/panda/pageResourceContracts.ts'))
  const resourceKeyPairs = extractResourceKeyPairs(read('src/panda/api/resourceKeys.ts'))
  const apiKeyByViewKey = new Map(resourceKeyPairs.map((pair) => [pair.viewKey, pair.apiKey]))
  const routeRollover = buildPandaRouteRolloverPlan({ manifest, contracts, apiKeyByViewKey })
  const modulePageStructure = getPandaModulePageStructure()

  return {
    sourceScript: PANDA_ALIGNMENT_CONTEXT_SOURCE,
    manifest,
    contracts,
    resourceKeyPairs,
    apiKeyByViewKey,
    routeRollover,
    modulePageStructure,
  }
}
