import { writeFileSync } from 'node:fs'
import { getPandaAlignmentContext } from './panda-alignment-context.mjs'
import { buildPandaCloseoutEvidence } from './panda-closeout-evidence.mjs'
import { extractPandaPageResourceContracts } from './panda-contract-parser.mjs'
import {
  buildPendingRouteSignature,
  buildResourceKeyBoundary,
  extractApiResourcesFromPendingRouteSignatures,
  extractResourceKeyPairs,
  read,
  readJson,
  sameMembers,
  unique,
} from './panda-script-utils.mjs'
import {
  pandaModulePageResourceHookByPage,
  pandaModulePageResourceTypeByPage,
} from './panda-workbench-verify-config.mjs'

const outputJson = process.argv.includes('--json')

function diffMembers(left, right) {
  return {
    missingFromLeft: right.filter((item) => !left.includes(item)),
    missingFromRight: left.filter((item) => !right.includes(item)),
  }
}

function extractValidationKeys(source, resourceKeySource) {
  if (!source.includes('pandaResourceValidationKeys = pandaApiResourceKeys')) {
    return []
  }
  return extractResourceApiKeys(resourceKeySource)
}

function extractResourceViewKeys(source) {
  return unique(extractResourceKeyPairs(source).map((item) => item.viewKey))
}

function extractResourceApiKeys(source) {
  return unique(extractResourceKeyPairs(source).map((item) => item.apiKey))
}

function extractApiSnapshotKeys(source) {
  const body = source.match(/export type ApiPandaResourceSnapshot = \{([\s\S]*?)\n\}/)?.[1] ?? ''
  return unique([...body.matchAll(/^\s*([A-Za-z0-9_]+)\?:/gm)].map((match) => match[1]))
}

function extractMapperApiKeys(source) {
  if (source.includes("from './resourceSnapshotAdapter'")) {
    return extractMapperApiKeys(read('src/panda/api/resourceSnapshotAdapter.ts'))
  }
  if (source.includes("from './resourceKeys'")) {
    return extractResourceApiKeys(read('src/panda/api/resourceKeys.ts'))
  }
  const body = source.match(/export function mapPandaResourceSnapshot\(snapshot: ApiPandaResourceSnapshot\) \{([\s\S]*?)\n\}/)?.[1] ?? ''
  return unique([...body.matchAll(/snapshot\.([A-Za-z0-9_]+)/g)].map((match) => match[1]))
}

function extractViewSnapshotKeys(source) {
  const body = source.match(/export type PandaResourceSnapshot = \{([\s\S]*?)\n\}/)?.[1] ?? ''
  return unique([...body.matchAll(/^\s*([A-Za-z0-9]+):/gm)].map((match) => match[1]))
}

function extractGetSnapshotKeys(source) {
  const body = source.match(/export function getPandaResourceSnapshot\(\): PandaResourceSnapshot \{[\s\S]*?return \{([\s\S]*?)\n\s*\}/)?.[1] ?? ''
  return unique([...body.matchAll(/^\s*([A-Za-z0-9]+),?/gm)].map((match) => match[1]))
}

function extractParsedPageContracts(source) {
  return [...extractPandaPageResourceContracts(source).values()]
}

function extractResourceContractKeys(source) {
  return unique(extractParsedPageContracts(source).flatMap((contract) => contract.resourceKeys))
}

function extractResourceContractRoutes(source) {
  return unique(extractParsedPageContracts(source).map((contract) => contract.page))
}

function extractResourceContractEndpoints(source) {
  return unique(extractParsedPageContracts(source).map((contract) => contract.bffEndpoint))
}

function extractMockReadyContractRoutes(source) {
  return unique(
    extractParsedPageContracts(source)
      .filter((contract) => contract.readiness === 'mock-ready')
      .map((contract) => contract.page),
  )
}

function extractModuleContentPages(source) {
  const body = source.match(/export const pandaModulePageContent: Record<PandaStandardModulePage, ModulePageContent> = \{([\s\S]*?)\n\}/)?.[1] ?? ''
  return unique([...body.matchAll(/^\s{2}([A-Za-z0-9]+):\s*\{/gm)].map((match) => match[1]))
}

function extractModuleContentPageFields(source) {
  const body = source.match(/export const pandaModulePageContent: Record<PandaStandardModulePage, ModulePageContent> = \{([\s\S]*?)\n\}/)?.[1] ?? ''
  const values = []
  const entryPattern = /^\s{2}([A-Za-z0-9]+):\s*\{([\s\S]*?)^\s{2}\},/gm
  for (const match of body.matchAll(entryPattern)) {
    const key = match[1]
    const page = match[2].match(/page:\s*'([^']+)'/)?.[1]
    if (page) {
      values.push(`${key}:${page}`)
    }
  }
  return unique(values)
}

function extractReadinessRouteKeys(source) {
  if (!source.includes('Object.values(pandaPageResourceContracts)')) {
    return []
  }
  return extractResourceContractRoutes(read('src/panda/pageResourceContracts.ts'))
}

function extractReadinessResourceKeys(source) {
  if (!source.includes('resources: contract.resourceKeys')) {
    return []
  }
  return extractResourceContractKeys(read('src/panda/pageResourceContracts.ts'))
}

function extractReadinessApiResourceKeys(source) {
  if (!source.includes('apiResources: contract.resourceKeys.map(resolvePandaApiResourceKey)')) {
    return []
  }
  const apiKeyByViewKey = new Map(extractResourceKeyPairs(read('src/panda/api/resourceKeys.ts')).map((pair) => [pair.viewKey, pair.apiKey]))
  return unique(extractResourceContractKeys(read('src/panda/pageResourceContracts.ts')).map((key) => apiKeyByViewKey.get(key) ?? key))
}

function extractReadinessEndpoints(source) {
  if (!source.includes('endpoint: contract.bffEndpoint')) {
    return []
  }
  return extractResourceContractEndpoints(read('src/panda/pageResourceContracts.ts'))
}

function extractReadinessPendingRoutes(source) {
  if (!source.includes('pendingRoutes: pandaRouteReadiness.filter((item) => item.backendOwned)')) {
    return []
  }
  return extractMockReadyContractRoutes(read('src/panda/pageResourceContracts.ts'))
}

function check(name, leftName, rightName, left, right, detail) {
  return {
    name,
    status: sameMembers(left, right) ? 'passed' : 'failed',
    leftName,
    rightName,
    detail,
    diff: diffMembers(left, right),
  }
}

function checkBoolean(name, condition, detail) {
  return {
    name,
    status: condition ? 'passed' : 'failed',
    leftName: 'actual',
    rightName: 'expected',
    detail,
    diff: {
      missingFromLeft: condition ? [] : ['focused contract module ownership'],
      missingFromRight: [],
    },
  }
}

function getIncompleteMockReadyContractRoutes(contracts) {
  return contracts
    .filter((contract) => contract.readiness === 'mock-ready')
    .filter(
      (contract) =>
        contract.objectKey !== contract.page ||
        !contract.bffEndpoint ||
        contract.resourceKeys.length === 0 ||
        contract.runtimeFields.length === 0 ||
        contract.apiNeeds.length === 0,
    )
    .map((contract) => contract.page)
}

const adapters = read('src/panda/api/adapters.ts')
const resourceSnapshotAdapter = read('src/panda/api/resourceSnapshotAdapter.ts')
const apiContracts = read('src/panda/api/apiContracts.ts')
const snapshotApiContracts = read('src/panda/api/snapshotApiContracts.ts')
const homeApiContracts = read('src/panda/api/homeApiContracts.ts')
const resourceApiContracts = read('src/panda/api/resourceApiContracts.ts')
const executionApiContracts = read('src/panda/api/executionApiContracts.ts')
const organizationApiContracts = read('src/panda/api/organizationApiContracts.ts')
const knowledgeApiContracts = read('src/panda/api/knowledgeApiContracts.ts')
const governanceApiContracts = read('src/panda/api/governanceApiContracts.ts')
const resourceSnapshotTypes = read('src/panda/api/resourceSnapshotTypes.ts')
const resourceFallbackSnapshot = read('src/panda/api/resourceFallbackSnapshot.ts')
const resourcesApiLoader = read('src/panda/api/resourcesApiLoader.ts')
const resourcesClient = read('src/panda/api/resourcesClient.ts')
const resourcesValidation = read('src/panda/api/resourcesValidation.ts')
const resourceContracts = read('src/panda/resourceContracts.ts')
const pageResourceContracts = read('src/panda/pageResourceContracts.ts')
const resourceRuntimeFields = read('src/panda/resourceRuntimeFields.ts')
const resourceContractTypes = read('src/panda/resourceContractTypes.ts')
const resourceKeys = read('src/panda/api/resourceKeys.ts')
const resourceReadiness = read('src/panda/api/resourceReadiness.ts')
const routeTypes = read('src/panda/types/routeTypes.ts')
const modulePageContent = read('src/panda/data/modulePageContent.tsx')
const modulePageTypes = read('src/panda/data/modulePageTypes.ts')
const modulePageActions = read('src/panda/data/modulePageActions.tsx')
const modulePageContentCatalog = read('src/panda/data/modulePageContentCatalog.tsx')
const manifest = readJson('src/panda/pandaFrontendManifest.json')
const parsedPageContracts = [...extractPandaPageResourceContracts(pageResourceContracts).values()]
const pandaAlignmentContext = getPandaAlignmentContext()
const resourceKeyBoundary = buildResourceKeyBoundary(resourceKeys)
const closeoutEvidence = buildPandaCloseoutEvidence({
  manifest,
  routeRollover: pandaAlignmentContext.routeRollover,
  resourceKeyBoundary,
})

const validationKeys = extractValidationKeys(resourcesValidation, resourceKeys)
const apiSnapshotKeys = extractApiSnapshotKeys(snapshotApiContracts)
const mapperApiKeys = extractMapperApiKeys(resourceSnapshotAdapter)
const viewSnapshotKeys = extractViewSnapshotKeys(resourceSnapshotTypes)
const getSnapshotKeys = extractGetSnapshotKeys(resourceFallbackSnapshot)
const contractKeys = extractResourceContractKeys(pageResourceContracts)
const contractRoutes = extractResourceContractRoutes(pageResourceContracts)
const contractEndpoints = extractResourceContractEndpoints(pageResourceContracts)
const contractMockReadyRoutes = extractMockReadyContractRoutes(pageResourceContracts)
const readinessRoutes = extractReadinessRouteKeys(resourceReadiness)
const readinessResourceKeys = extractReadinessResourceKeys(resourceReadiness)
const readinessApiResourceKeys = extractReadinessApiResourceKeys(resourceReadiness)
const readinessEndpoints = extractReadinessEndpoints(resourceReadiness)
const readinessPendingRoutes = extractReadinessPendingRoutes(resourceReadiness)
const resourceBoundaryApiKeys = extractResourceApiKeys(resourceKeys)
const resourceBoundaryViewKeys = extractResourceViewKeys(resourceKeys)
const standardModulePages = Object.keys(pandaModulePageResourceHookByPage)
const expectedModulePageResourceHookBindings = Object.entries(pandaModulePageResourceHookByPage).map(([page, hook]) => {
  const resourceType = pandaModulePageResourceTypeByPage[page] ?? 'missing-resource-type'
  return `${page}:${hook}:${resourceType}`
})
const modulePageResourceHookBindings = pandaAlignmentContext.modulePageStructure.resourceHooks.map(
  (binding) => `${binding.page}:${binding.hook}:${binding.resourceType}`,
)
const expectedModulePageResourceTypeBindings = Object.entries(pandaModulePageResourceTypeByPage).map(
  ([page, resourceType]) => `${page}:${resourceType}`,
)
const modulePageResourceTypeBindings = pandaAlignmentContext.modulePageStructure.resourceTypes.map(
  (binding) => `${binding.page}:${binding.resourceType}`,
)
const moduleContentPages = extractModuleContentPages(modulePageContentCatalog)
const moduleContentPageFields = extractModuleContentPageFields(modulePageContentCatalog)
const expectedModuleContentPageFields = standardModulePages.map((page) => `${page}:${page}`)
const incompleteMockReadyContractRoutes = getIncompleteMockReadyContractRoutes(parsedPageContracts)
const routeRolloverPendingRouteSignatures = pandaAlignmentContext.routeRollover.pendingRoutes.map((route) =>
  buildPendingRouteSignature({
    route: route.route,
    endpoint: route.endpoint,
    resources: route.viewResources.join(', '),
    apiResources: route.apiResources.join(', '),
    runtimeFields: route.runtimeFields.join(', '),
    apiNeeds: route.apiNeeds.join('; '),
  }),
)
const closeoutPendingRouteSignatures = closeoutEvidence.backendAlignmentBlockers.pendingRoutes.map(buildPendingRouteSignature)
const routeRolloverApiResources = unique(pandaAlignmentContext.routeRollover.routes.flatMap((route) => route.apiResources))
const routeRolloverPendingApiResources = extractApiResourcesFromPendingRouteSignatures(routeRolloverPendingRouteSignatures)
const closeoutPendingApiResources = extractApiResourcesFromPendingRouteSignatures(closeoutPendingRouteSignatures)
const manifestApiKeys = manifest.resourceBoundary?.apiKeys ?? []
const manifestViewKeys = manifest.resourceBoundary?.viewKeys ?? []
const contractModuleOwnership = {
  compatibilityBarrel:
    resourceContracts.includes("from './resourceContractTypes'") &&
    resourceContracts.includes("from './resourceRuntimeFields'") &&
    resourceContracts.includes("from './pageResourceContracts'"),
  pageContractsOwnRoutes: pageResourceContracts.includes('pandaPageResourceContracts'),
  runtimeFieldsOwnCore: resourceRuntimeFields.includes('pandaCoreRuntimeFields'),
  contractTypesOwnShape: resourceContractTypes.includes('PandaPageResourceContract'),
}
const apiContractModuleOwnership = {
  compatibilityBarrel:
    apiContracts.includes("from './homeApiContracts'") &&
    apiContracts.includes("from './resourceApiContracts'") &&
    apiContracts.includes("from './snapshotApiContracts'"),
  homeContractsOwnHome: homeApiContracts.includes('ApiWorkbenchHome'),
  resourceContractsBarrel:
    resourceApiContracts.includes("from './executionApiContracts'") &&
    resourceApiContracts.includes("from './organizationApiContracts'") &&
    resourceApiContracts.includes("from './knowledgeApiContracts'") &&
    resourceApiContracts.includes("from './governanceApiContracts'"),
  executionContractsOwnItems: executionApiContracts.includes('ApiTaskSummary'),
  organizationContractsOwnItems: organizationApiContracts.includes('ApiProjectItem'),
  knowledgeContractsOwnItems: knowledgeApiContracts.includes('ApiKnowledgeSource'),
  governanceContractsOwnItems: governanceApiContracts.includes('ApiAuditEvent'),
  snapshotContractsOwnAggregate: snapshotApiContracts.includes('ApiPandaResourceSnapshot'),
}
const resourceClientModuleOwnership = {
  compatibilityEntrypoint:
    resourcesClient.includes("from './resourceSnapshotTypes'") &&
    resourcesClient.includes("from './resourceFallbackSnapshot'") &&
    resourcesClient.includes("from './resourcesApiLoader'"),
  snapshotTypesOwnViewShape: resourceSnapshotTypes.includes('PandaResourceSnapshot') && resourceSnapshotTypes.includes('PandaResourceLoadResult'),
  fallbackOwnsMockSnapshot:
    resourceFallbackSnapshot.includes('getPandaResourceSnapshot') &&
    resourceFallbackSnapshot.includes("from '../data/mockResources'"),
  apiLoaderOwnsBffMapping:
    resourcesApiLoader.includes('PandaResourcesHttpClient') &&
    resourcesApiLoader.includes('validatePandaResourceSnapshot') &&
    resourcesApiLoader.includes('mapPandaResourceSnapshot'),
  contractTypesUseFocusedSnapshotTypes: resourceContractTypes.includes("from './api/resourceSnapshotTypes'"),
}
const modulePageContentOwnership = {
  routeTypesOwnStandardSubset: routeTypes.includes("PandaStandardModulePage = Exclude<PandaPage, 'home' | 'threads'>"),
  compatibilityBarrel:
    modulePageContent.includes("from './modulePageTypes'") &&
    modulePageContent.includes("from './modulePageActions'") &&
    modulePageContent.includes("from './modulePageContentCatalog'"),
  typesImportStandardSubset: modulePageTypes.includes("import type { PandaStandardModulePage }"),
  catalogUsesStandardSubset: modulePageContentCatalog.includes('Record<PandaStandardModulePage, ModulePageContent>'),
  contentActionsReadonly: modulePageTypes.includes('actions: readonly ModulePageAction[]'),
  actionFactoryReadonly: modulePageActions.includes('): readonly ModulePageAction[]'),
}

const checks = [
  checkBoolean(
    'module-page-content-ownership',
    Object.values(modulePageContentOwnership).every(Boolean),
    'Focused module page content files must keep modulePageContent.tsx as a compatibility barrel, use PandaStandardModulePage, and keep standard page actions readonly.',
  ),
  check(
    'module-content-vs-standard-module-pages',
    'moduleContentPages',
    'standardModulePages',
    moduleContentPages,
    standardModulePages,
    'pandaModulePageContent keys must match the standard module page hook map.',
  ),
  check(
    'module-content-key-vs-page-field',
    'moduleContentPageFields',
    'expectedModuleContentPageFields',
    moduleContentPageFields,
    expectedModuleContentPageFields,
    'Each pandaModulePageContent entry must keep its object key aligned with the embedded page field.',
  ),
  check(
    'module-resource-hooks-vs-type-bindings',
    'modulePageResourceHookBindings',
    'expectedModulePageResourceHookBindings',
    modulePageResourceHookBindings,
    expectedModulePageResourceHookBindings,
    'modulePageStructure.resourceHooks must preserve each standard module page -> focused hook -> explicit PageResources type binding.',
  ),
  check(
    'module-resource-types-vs-type-map',
    'modulePageResourceTypeBindings',
    'expectedModulePageResourceTypeBindings',
    modulePageResourceTypeBindings,
    expectedModulePageResourceTypeBindings,
    'modulePageStructure.resourceTypes must preserve each standard module page -> explicit PageResources type binding.',
  ),
  checkBoolean(
    'mock-ready-contract-field-completeness',
    incompleteMockReadyContractRoutes.length === 0,
    'Every mock-ready page contract must declare matching page/object keys, a BFF endpoint, resource keys, runtime fields, and API needs.',
  ),
  check(
    'closeout-pending-routes-vs-route-rollover',
    'closeoutPendingRouteSignatures',
    'routeRolloverPendingRouteSignatures',
    closeoutPendingRouteSignatures,
    routeRolloverPendingRouteSignatures,
    'backendAlignmentBlockers.pendingRoutes must preserve route rollover endpoint, view/API resources, runtime fields, and API needs for backend handoff.',
  ),
  check(
    'route-rollover-api-resources-vs-resource-boundary-api',
    'routeRolloverApiResources',
    'resourceBoundaryApiKeys',
    routeRolloverApiResources,
    resourceBoundaryApiKeys,
    'Every route rollover apiResources entry must stay inside the shared API resource key boundary.',
  ),
  check(
    'pending-route-api-resources-vs-closeout-api-resources',
    'routeRolloverPendingApiResources',
    'closeoutPendingApiResources',
    routeRolloverPendingApiResources,
    closeoutPendingApiResources,
    'Closeout pending route handoff must preserve pending route apiResources exactly as emitted by route rollover.',
  ),
  checkBoolean(
    'resource-client-module-ownership',
    Object.values(resourceClientModuleOwnership).every(Boolean),
    'resourcesClient.ts must stay a compatibility/loading entrypoint while focused modules own snapshot types, mock fallback, and API loader validation/mapping.',
  ),
  checkBoolean(
    'api-contract-module-ownership',
    Object.values(apiContractModuleOwnership).every(Boolean),
    'apiContracts.ts must stay a compatibility barrel while focused API contract modules own home DTOs, resource DTOs, and aggregate snapshot DTOs.',
  ),
  checkBoolean(
    'contract-module-ownership',
    Object.values(contractModuleOwnership).every(Boolean),
    'resourceContracts.ts must stay a compatibility barrel while focused contract modules own types, runtime fields, and page contracts.',
  ),
  check(
    'manifest-api-vs-resource-boundary-api',
    'manifestApiKeys',
    'resourceBoundaryApiKeys',
    manifestApiKeys,
    resourceBoundaryApiKeys,
    'manifest resourceBoundary.apiKeys must match the shared resource key boundary.',
  ),
  check(
    'manifest-view-vs-resource-boundary-view',
    'manifestViewKeys',
    'resourceBoundaryViewKeys',
    manifestViewKeys,
    resourceBoundaryViewKeys,
    'manifest resourceBoundary.viewKeys must match the shared resource key boundary.',
  ),
  check(
    'resource-boundary-api-vs-api-snapshot',
    'resourceBoundaryApiKeys',
    'apiSnapshotKeys',
    resourceBoundaryApiKeys,
    apiSnapshotKeys,
    'shared resource API keys must match ApiPandaResourceSnapshot keys.',
  ),
  check(
    'resource-boundary-view-vs-view-snapshot',
    'resourceBoundaryViewKeys',
    'viewSnapshotKeys',
    resourceBoundaryViewKeys,
    viewSnapshotKeys,
    'shared resource view keys must match PandaResourceSnapshot keys.',
  ),
  check(
    'validation-vs-api-snapshot',
    'validationKeys',
    'apiSnapshotKeys',
    validationKeys,
    apiSnapshotKeys,
    'resourcesValidation keys must match ApiPandaResourceSnapshot keys.',
  ),
  check(
    'mapper-vs-api-snapshot',
    'mapperApiKeys',
    'apiSnapshotKeys',
    mapperApiKeys,
    apiSnapshotKeys,
    'mapPandaResourceSnapshot must read every API resource key exactly once.',
  ),
  check(
    'view-snapshot-vs-fallback',
    'viewSnapshotKeys',
    'getSnapshotKeys',
    viewSnapshotKeys,
    getSnapshotKeys,
    'PandaResourceSnapshot keys must match getPandaResourceSnapshot fallback keys.',
  ),
  check(
    'contracts-vs-view-snapshot',
    'contractKeys',
    'viewSnapshotKeys',
    contractKeys,
    viewSnapshotKeys,
    'pandaResourceContractKeys must match PandaResourceSnapshot keys.',
  ),
  check(
    'readiness-routes-vs-contract-routes',
    'readinessRoutes',
    'contractRoutes',
    readinessRoutes,
    contractRoutes,
    'pandaRouteReadiness must derive route ids from pandaPageResourceContracts.',
  ),
  check(
    'readiness-resources-vs-contract-resources',
    'readinessResourceKeys',
    'contractKeys',
    readinessResourceKeys,
    contractKeys,
    'pandaRouteReadiness resources must derive from contract resourceKeys.',
  ),
  check(
    'readiness-api-resources-vs-resource-boundary-api',
    'readinessApiResourceKeys',
    'resourceBoundaryApiKeys',
    readinessApiResourceKeys,
    resourceBoundaryApiKeys,
    'pandaRouteReadiness apiResources must derive from contract resourceKeys through the shared resource key boundary.',
  ),
  check(
    'readiness-endpoints-vs-contract-endpoints',
    'readinessEndpoints',
    'contractEndpoints',
    readinessEndpoints,
    contractEndpoints,
    'pandaRouteReadiness endpoints must derive from contract BFF endpoints.',
  ),
  check(
    'readiness-pending-routes-vs-mock-ready-contracts',
    'readinessPendingRoutes',
    'contractMockReadyRoutes',
    readinessPendingRoutes,
    contractMockReadyRoutes,
    'pandaBackendAlignmentReadiness pendingRoutes must match mock-ready contracts.',
  ),
]

const failedChecks = checks.filter((item) => item.status !== 'passed')
const result = {
  productName: 'Panda Agent',
  technicalCore: 'X-Agent Autonomous Framework',
  status: failedChecks.length === 0 ? 'passed' : 'failed',
  checkedAt: new Date().toISOString(),
  sources: {
    validation: 'src/panda/api/resourcesValidation.ts',
    apiContracts: 'src/panda/api/apiContracts.ts',
    homeApiContracts: 'src/panda/api/homeApiContracts.ts',
    resourceApiContracts: 'src/panda/api/resourceApiContracts.ts',
    executionApiContracts: 'src/panda/api/executionApiContracts.ts',
    organizationApiContracts: 'src/panda/api/organizationApiContracts.ts',
    knowledgeApiContracts: 'src/panda/api/knowledgeApiContracts.ts',
    governanceApiContracts: 'src/panda/api/governanceApiContracts.ts',
    snapshotApiContracts: 'src/panda/api/snapshotApiContracts.ts',
    adapters: 'src/panda/api/adapters.ts',
    resourceSnapshotAdapter: 'src/panda/api/resourceSnapshotAdapter.ts',
    resourceSnapshotTypes: 'src/panda/api/resourceSnapshotTypes.ts',
    resourceFallbackSnapshot: 'src/panda/api/resourceFallbackSnapshot.ts',
    resourcesApiLoader: 'src/panda/api/resourcesApiLoader.ts',
    resourcesClient: 'src/panda/api/resourcesClient.ts',
    resourceContracts: 'src/panda/resourceContracts.ts',
    pageResourceContracts: 'src/panda/pageResourceContracts.ts',
    resourceRuntimeFields: 'src/panda/resourceRuntimeFields.ts',
    resourceContractTypes: 'src/panda/resourceContractTypes.ts',
    resourceKeys: 'src/panda/api/resourceKeys.ts',
    resourceReadiness: 'src/panda/api/resourceReadiness.ts',
    routeTypes: 'src/panda/types/routeTypes.ts',
    modulePageContent: 'src/panda/data/modulePageContent.tsx',
    modulePageStructure: 'scripts/panda-module-page-structure.mjs',
    modulePageResources: 'src/panda/state/useModulePageResources.ts',
    manifest: 'src/panda/pandaFrontendManifest.json',
  },
  ownership: {
    ...contractModuleOwnership,
    ...apiContractModuleOwnership,
    ...resourceClientModuleOwnership,
    ...modulePageContentOwnership,
  },
  keys: {
    manifestApiKeys,
    manifestViewKeys,
    resourceBoundaryApiKeys,
    resourceBoundaryViewKeys,
    validationKeys,
    apiSnapshotKeys,
    mapperApiKeys,
    viewSnapshotKeys,
    getSnapshotKeys,
    contractKeys,
    contractRoutes,
    contractEndpoints,
    contractMockReadyRoutes,
    readinessRoutes,
    readinessResourceKeys,
    readinessApiResourceKeys,
    readinessEndpoints,
    readinessPendingRoutes,
    standardModulePages,
    modulePageResourceHookBindings,
    expectedModulePageResourceHookBindings,
    modulePageResourceTypeBindings,
    expectedModulePageResourceTypeBindings,
    moduleContentPages,
    moduleContentPageFields,
    expectedModuleContentPageFields,
    incompleteMockReadyContractRoutes,
    routeRolloverPendingRouteSignatures,
    closeoutPendingRouteSignatures,
    routeRolloverApiResources,
    routeRolloverPendingApiResources,
    closeoutPendingApiResources,
  },
  diffs: Object.fromEntries(checks.map((item) => [item.name, item.diff])),
  checks,
}

if (outputJson) {
  console.log(JSON.stringify(result, null, 2))
} else {
  console.log(`Panda resource contracts: ${result.status}`)
  console.log(`Checks: ${checks.filter((item) => item.status === 'passed').length}/${checks.length} passed`)
  for (const item of failedChecks) {
    console.log(`- [failed] ${item.name}: ${item.detail}`)
    console.log(`  ${item.leftName} missing: ${item.diff.missingFromLeft.join(', ') || '(none)'}`)
    console.log(`  ${item.rightName} missing: ${item.diff.missingFromRight.join(', ') || '(none)'}`)
  }
}

if (process.env.PANDA_RESOURCE_CONTRACT_RESULT_PATH) {
  writeFileSync(process.env.PANDA_RESOURCE_CONTRACT_RESULT_PATH, `${JSON.stringify(result, null, 2)}\n`)
}

if (failedChecks.length > 0) {
  process.exit(1)
}
