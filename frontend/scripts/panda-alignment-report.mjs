import { assert, buildResourceKeyBoundary, read } from './panda-script-utils.mjs'
import { getPandaAlignmentContext } from './panda-alignment-context.mjs'
import { buildPandaCloseoutEvidence } from './panda-closeout-evidence.mjs'
import { getPandaStrictFailures } from './panda-route-rollover-plan.mjs'

const pandaAlignmentContext = getPandaAlignmentContext()
const { manifest, contracts, routeRollover, modulePageStructure } = pandaAlignmentContext
const contractSource = read('src/panda/pageResourceContracts.ts')
const resourceReadinessSource = read('src/panda/api/resourceReadiness.ts')
const resourceKeySource = read('src/panda/api/resourceKeys.ts')
const resourceKeyBoundary = buildResourceKeyBoundary(resourceKeySource)
const outputJson = process.argv.includes('--json')
const strictMode = process.argv.includes('--strict')

assert(contracts.size === manifest.routes.length, 'Panda alignment report contract count must match manifest route count')
assert(resourceReadinessSource.includes('pandaRouteReadiness'), 'Panda alignment report requires the route readiness source')
assert(resourceReadinessSource.includes('pandaBackendAlignmentReadiness'), 'Panda alignment report requires backend readiness gates')
assert(resourceReadinessSource.includes('approval, sandbox, auth, secret, and execution policy remain backend-owned'), 'Panda readiness source must keep high-risk policy ownership backend-owned')

const rows = routeRollover.routes.map((route) => ({
  route: route.route,
  readiness: route.readiness,
  endpoint: route.endpoint,
  resources: route.viewResources.join(', '),
  apiResources: route.apiResources.join(', '),
  runtimeFields: route.runtimeFields.join(', '),
  needs: route.apiNeeds.join('; '),
}))
const apiWired = rows.filter((row) => row.readiness === 'api-wired')
const mockReady = rows.filter((row) => row.readiness === 'mock-ready')
const closeoutEvidence = buildPandaCloseoutEvidence({ manifest, routeRollover, resourceKeyBoundary })
const adapterEvidence = {
  status: manifest.resourceBoundary?.adapterProbe ? 'passed' : 'missing',
  executableProbe: manifest.resourceBoundary?.adapterProbe,
  adapter: 'src/panda/api/adapters.ts',
  apiContracts: manifest.resourceBoundary?.apiContracts ?? 'src/panda/api/apiContracts.ts',
  homeApiContracts: manifest.resourceBoundary?.homeApiContracts ?? 'src/panda/api/homeApiContracts.ts',
  executionApiContracts: manifest.resourceBoundary?.executionApiContracts ?? 'src/panda/api/executionApiContracts.ts',
  organizationApiContracts: manifest.resourceBoundary?.organizationApiContracts ?? 'src/panda/api/organizationApiContracts.ts',
  knowledgeApiContracts: manifest.resourceBoundary?.knowledgeApiContracts ?? 'src/panda/api/knowledgeApiContracts.ts',
  governanceApiContracts: manifest.resourceBoundary?.governanceApiContracts ?? 'src/panda/api/governanceApiContracts.ts',
  resourceApiContracts: manifest.resourceBoundary?.resourceApiContracts ?? 'src/panda/api/resourceApiContracts.ts',
  snapshotApiContracts: manifest.resourceBoundary?.snapshotApiContracts ?? 'src/panda/api/snapshotApiContracts.ts',
  executionResourceAdapters: manifest.resourceBoundary?.executionResourceAdapters ?? 'src/panda/api/executionResourceAdapters.ts',
  organizationResourceAdapters: manifest.resourceBoundary?.organizationResourceAdapters ?? 'src/panda/api/organizationResourceAdapters.ts',
  knowledgeResourceAdapters: manifest.resourceBoundary?.knowledgeResourceAdapters ?? 'src/panda/api/knowledgeResourceAdapters.ts',
  governanceResourceAdapters: manifest.resourceBoundary?.governanceResourceAdapters ?? 'src/panda/api/governanceResourceAdapters.ts',
  modules: [
    'src/panda/api/homeAdapters.ts',
    manifest.resourceBoundary?.executionResourceAdapters ?? 'src/panda/api/executionResourceAdapters.ts',
    manifest.resourceBoundary?.organizationResourceAdapters ?? 'src/panda/api/organizationResourceAdapters.ts',
    manifest.resourceBoundary?.knowledgeResourceAdapters ?? 'src/panda/api/knowledgeResourceAdapters.ts',
    manifest.resourceBoundary?.governanceResourceAdapters ?? 'src/panda/api/governanceResourceAdapters.ts',
    'src/panda/api/resourceItemAdapters.ts',
    'src/panda/api/resourceSnapshotAdapter.ts',
  ],
  scope: [
    'tone fallback',
    'progress clamping',
    'snake_case runtime metadata mapping',
    'evidence refs and agent permissions copy semantics',
    'aggregate resource snapshot mapping',
  ],
}
const resourcesValidationEvidence = {
  status: manifest.resourceBoundary?.validation && manifest.resourceBoundary?.invalidApiFallback === 'mock-with-error' ? 'passed' : 'missing',
  validation: manifest.resourceBoundary?.validation,
  snapshotTypes: manifest.resourceBoundary?.snapshotTypes,
  fallbackSnapshot: manifest.resourceBoundary?.fallbackSnapshot,
  apiLoader: manifest.resourceBoundary?.apiLoader,
  executableProbe: manifest.resourceBoundary?.validationProbe,
  invalidApiFallback: manifest.resourceBoundary?.invalidApiFallback,
  expectedShape: 'ApiPandaResourceSnapshot may only contain known resource fields, and every provided resource field must be an object array.',
}
const resourcesContractEvidence = {
  status: manifest.resourceBoundary?.contractProbe ? 'passed' : 'missing',
  executableProbe: manifest.resourceBoundary?.contractProbe,
  workspaceProvider: manifest.resourceBoundary?.provider,
  workspaceTypes: manifest.resourceBoundary?.providerTypes,
  workspaceRuntime: manifest.resourceBoundary?.providerRuntime,
  workspaceHooks: manifest.resourceBoundary?.providerHooks,
  hashRouteHook: manifest.resourceBoundary?.hashRouteHook,
  homeWorkbenchHook: manifest.resourceBoundary?.homeWorkbenchHook,
  compatibilityBarrel: manifest.resourceBoundary?.contracts ?? 'src/panda/resourceContracts.ts',
  pageContracts: manifest.resourceBoundary?.pageContracts ?? 'src/panda/pageResourceContracts.ts',
  runtimeFields: manifest.resourceBoundary?.runtimeFields ?? 'src/panda/resourceRuntimeFields.ts',
  contractTypes: manifest.resourceBoundary?.contractTypes ?? 'src/panda/resourceContractTypes.ts',
  comparedSources: [
    'src/panda/pandaFrontendManifest.json',
    manifest.resourceBoundary?.keyMap,
    manifest.resourceBoundary?.readiness,
    manifest.resourceBoundary?.validation,
    manifest.resourceBoundary?.apiContracts,
    manifest.resourceBoundary?.homeApiContracts,
    manifest.resourceBoundary?.executionApiContracts,
    manifest.resourceBoundary?.organizationApiContracts,
    manifest.resourceBoundary?.knowledgeApiContracts,
    manifest.resourceBoundary?.governanceApiContracts,
    manifest.resourceBoundary?.resourceApiContracts,
    manifest.resourceBoundary?.snapshotApiContracts,
    'src/panda/api/adapters.ts',
    'src/panda/api/resourceSnapshotAdapter.ts',
    manifest.resourceBoundary?.snapshotTypes,
    manifest.resourceBoundary?.fallbackSnapshot,
    manifest.resourceBoundary?.apiLoader,
    manifest.resourceBoundary?.client,
    manifest.resourceBoundary?.provider,
    manifest.resourceBoundary?.providerTypes,
    manifest.resourceBoundary?.providerRuntime,
    manifest.resourceBoundary?.providerHooks,
    manifest.resourceBoundary?.hashRouteHook,
    manifest.resourceBoundary?.homeWorkbenchHook,
    manifest.resourceBoundary?.contracts,
    manifest.resourceBoundary?.pageContracts,
    manifest.resourceBoundary?.runtimeFields,
    manifest.resourceBoundary?.contractTypes,
    pandaAlignmentContext.sourceScript,
    closeoutEvidence.sourceScript,
    routeRollover.sourceScript,
    modulePageStructure.sourceScript,
    modulePageStructure.content,
    modulePageStructure.shell,
    modulePageStructure.resources,
  ].filter(Boolean),
  expectedAlignment: 'manifest apiKeys/viewKeys, shared resource key pairs, validation keys, ApiPandaResourceSnapshot keys, mapper reads, PandaResourceSnapshot keys, fallback keys, page contract keys, mock-ready contract field completeness, closeout pending route handoff fields, standard module page content keys/page fields, standard module page -> hook -> PageResources type bindings, and route readiness stay in sync.',
}
const routeApiResourcesEvidence = closeoutEvidence.routeApiResourcesEvidence
assert(
  routeApiResourcesEvidence.unknownRouteApiResources.length === 0,
  `Panda alignment report route apiResources must stay inside shared resource key boundary: ${routeApiResourcesEvidence.unknownRouteApiResources.join(', ')}`,
)
assert(
  routeApiResourcesEvidence.missingRouteApiResources.length === 0,
  `Panda alignment report route apiResources must cover every shared API resource key: ${routeApiResourcesEvidence.missingRouteApiResources.join(', ')}`,
)
const summary = {
  productName: manifest.productName,
  technicalCore: manifest.technicalCore,
  status: manifest.status,
  mode: strictMode ? 'strict' : 'closeout',
  routeCount: rows.length,
  apiWiredCount: apiWired.length,
  mockReadyCount: mockReady.length,
  resourcesBff: {
    endpoint: manifest.bff.resourcesEndpoint,
    flag: manifest.bff.resourcesFlag,
    defaultValue: manifest.bff.resourcesFlagDefault,
  },
  deliveryReadiness: manifest.deliveryReadiness,
  frontendCloseout: manifest.frontendCloseout,
  visualReviewTargets: manifest.visualReviewTargets,
  accessibilityEvidence: manifest.accessibilityEvidence,
  visualReviewEvidence: manifest.visualReviewEvidence,
  scriptedQaEvidence: manifest.scriptedQaEvidence,
  resourceKeyBoundary,
  modulePageStructure,
  adapterEvidence,
  resourcesValidationEvidence,
  resourcesContractEvidence,
  routeApiResourcesEvidence,
  resourceReadiness: {
    source: manifest.resourceBoundary.readiness,
    backendGate: 'pandaBackendAlignmentReadiness',
    routeList: 'pandaRouteReadiness',
    viewResourceField: 'resources',
    apiResourceField: 'apiResources',
    apiResourceSource: manifest.resourceBoundary.keyMap,
    strictPassRequires: [
      'all Panda routes api-wired',
      'resources BFF enabled only after ApiPandaResourceSnapshot validation passes',
      'approval, sandbox, auth, secret, and execution policy remain backend-owned',
    ],
  },
  nextFrontendTasks: manifest.nextFrontendTasks,
  alignmentContextSource: pandaAlignmentContext.sourceScript,
  closeoutEvidenceSource: closeoutEvidence.sourceScript,
  routeRolloverSource: routeRollover.sourceScript,
  frontendCompletion: closeoutEvidence.frontendCompletion,
  backendAlignmentBlockers: closeoutEvidence.backendAlignmentBlockers,
  backendAlignmentHandoff: closeoutEvidence.backendAlignmentHandoff,
  routes: rows,
  backendAlignmentPending: manifest.backendAlignmentPending,
}

const strictFailures = strictMode
  ? getPandaStrictFailures({
      pendingRoutes: routeRollover.pendingRoutes,
      resourcesFlag: manifest.bff.resourcesFlag,
      resourcesFlagDefault: manifest.bff.resourcesFlagDefault,
    })
  : []
summary.strict = {
  enabled: strictMode,
  passed: strictFailures.length === 0,
  failures: strictFailures,
}

if (outputJson) {
  console.log(JSON.stringify(summary, null, 2))
  process.exit(strictFailures.length === 0 ? 0 : 1)
}

console.log(`Panda Agent frontend alignment report`)
console.log(`Product: ${summary.productName} | Core: ${summary.technicalCore}`)
console.log(`Mode: ${summary.mode}`)
console.log(`Routes: ${summary.routeCount} | api-wired: ${summary.apiWiredCount} | mock-ready: ${summary.mockReadyCount}`)
console.log(`Resources BFF: ${summary.resourcesBff.endpoint} | flag ${summary.resourcesBff.flag}=${summary.resourcesBff.defaultValue}`)
console.log(`Visual review target: ${summary.deliveryReadiness.visualReviewTarget}`)
console.log(`Frontend closeout: ${summary.frontendCloseout.currentPhase} | backend dependency: ${summary.frontendCloseout.backendDependency}`)
console.log('')
console.table(rows.map(({ route, readiness, endpoint, resources, apiResources, runtimeFields }) => ({ route, readiness, endpoint, resources, apiResources, runtimeFields })))
console.log('')
console.log('Visual review targets:')
for (const target of summary.visualReviewTargets) {
  console.log(`- ${target.route} ${target.viewport}: ${target.url} (${target.purpose})`)
}
if (summary.visualReviewEvidence) {
  console.log('')
  console.log(`Visual review evidence: ${summary.visualReviewEvidence.status} via ${summary.visualReviewEvidence.browser}`)
  console.log(`- screenshotDir: ${summary.visualReviewEvidence.screenshotDir}`)
  console.log(`- interaction: ${summary.visualReviewEvidence.interaction}`)
}
if (summary.accessibilityEvidence) {
  console.log('')
  console.log(`Accessibility evidence: ${summary.accessibilityEvidence.status}`)
  console.log(`- screenshotDir: ${summary.accessibilityEvidence.screenshotDir}`)
  console.log(`- scope: ${summary.accessibilityEvidence.scope.join(', ')}`)
  console.log(`- browserProof: ${summary.accessibilityEvidence.browserProof}`)
}
if (summary.scriptedQaEvidence) {
  console.log('')
console.log(`Scripted QA evidence: ${summary.scriptedQaEvidence.status}`)
  console.log(`- script: ${summary.scriptedQaEvidence.script}`)
  console.log(`- commands: ${summary.scriptedQaEvidence.commands.join(', ')}`)
  console.log(`- scope: ${summary.scriptedQaEvidence.scope.join(', ')}`)
}
console.log('')
console.log(`Resource key boundary: ${summary.resourceKeyBoundary.keyMap}`)
console.log(`- viewKeys: ${summary.resourceKeyBoundary.viewKeys.join(', ')}`)
console.log(`- apiKeys: ${summary.resourceKeyBoundary.apiKeys.join(', ')}`)
console.log('')
console.log(`Module page structure: ${summary.modulePageStructure.resources}`)
console.log(`- content: ${summary.modulePageStructure.content}`)
console.log(`- shell: ${summary.modulePageStructure.shell}`)
console.log(`- resourceHooks: ${summary.modulePageStructure.resourceHooks.map((binding) => `${binding.page}->${binding.hook}:${binding.resourceType}`).join(', ')}`)
console.log(`- directSelectorExceptions: ${summary.modulePageStructure.directSelectorExceptions.join(', ')}`)
console.log('')
console.log(`Adapter evidence: ${summary.adapterEvidence.status}`)
console.log(`- executableProbe: ${summary.adapterEvidence.executableProbe}`)
console.log(`- adapter: ${summary.adapterEvidence.adapter}`)
console.log(`- apiContracts: ${summary.adapterEvidence.apiContracts}`)
console.log(`- homeApiContracts: ${summary.adapterEvidence.homeApiContracts}`)
console.log(`- executionApiContracts: ${summary.adapterEvidence.executionApiContracts}`)
console.log(`- organizationApiContracts: ${summary.adapterEvidence.organizationApiContracts}`)
console.log(`- knowledgeApiContracts: ${summary.adapterEvidence.knowledgeApiContracts}`)
console.log(`- governanceApiContracts: ${summary.adapterEvidence.governanceApiContracts}`)
console.log(`- resourceApiContracts: ${summary.adapterEvidence.resourceApiContracts}`)
console.log(`- snapshotApiContracts: ${summary.adapterEvidence.snapshotApiContracts}`)
console.log(`- executionResourceAdapters: ${summary.adapterEvidence.executionResourceAdapters}`)
console.log(`- organizationResourceAdapters: ${summary.adapterEvidence.organizationResourceAdapters}`)
console.log(`- knowledgeResourceAdapters: ${summary.adapterEvidence.knowledgeResourceAdapters}`)
console.log(`- governanceResourceAdapters: ${summary.adapterEvidence.governanceResourceAdapters}`)
console.log(`- modules: ${summary.adapterEvidence.modules.join(', ')}`)
console.log(`- scope: ${summary.adapterEvidence.scope.join(', ')}`)
console.log('')
console.log(`Resources validation evidence: ${summary.resourcesValidationEvidence.status}`)
console.log(`- validation: ${summary.resourcesValidationEvidence.validation}`)
console.log(`- executableProbe: ${summary.resourcesValidationEvidence.executableProbe}`)
console.log(`- invalidApiFallback: ${summary.resourcesValidationEvidence.invalidApiFallback}`)
console.log(`- expectedShape: ${summary.resourcesValidationEvidence.expectedShape}`)
console.log('')
console.log(`Resources contract evidence: ${summary.resourcesContractEvidence.status}`)
console.log(`- executableProbe: ${summary.resourcesContractEvidence.executableProbe}`)
console.log(`- compatibilityBarrel: ${summary.resourcesContractEvidence.compatibilityBarrel}`)
console.log(`- pageContracts: ${summary.resourcesContractEvidence.pageContracts}`)
console.log(`- runtimeFields: ${summary.resourcesContractEvidence.runtimeFields}`)
console.log(`- contractTypes: ${summary.resourcesContractEvidence.contractTypes}`)
console.log(`- comparedSources: ${summary.resourcesContractEvidence.comparedSources.join(', ')}`)
console.log(`- expectedAlignment: ${summary.resourcesContractEvidence.expectedAlignment}`)
console.log('')
console.log(`Route API resources evidence: ${summary.routeApiResourcesEvidence.status}`)
console.log(`- routePlan: ${summary.routeApiResourcesEvidence.routePlan}`)
console.log(`- keyMap: ${summary.routeApiResourcesEvidence.keyMap}`)
console.log(`- routeApiResources: ${summary.routeApiResourcesEvidence.routeApiResources.join(', ')}`)
console.log(`- boundaryApiResources: ${summary.routeApiResourcesEvidence.boundaryApiResources.join(', ')}`)
console.log(`- unknownRouteApiResources: ${summary.routeApiResourcesEvidence.unknownRouteApiResources.join(', ') || '(none)'}`)
console.log(`- missingRouteApiResources: ${summary.routeApiResourcesEvidence.missingRouteApiResources.join(', ') || '(none)'}`)
console.log(`- expectedAlignment: ${summary.routeApiResourcesEvidence.expectedAlignment}`)
console.log('')
console.log(`Resource readiness source: ${summary.resourceReadiness.source}`)
console.log(`- routeList: ${summary.resourceReadiness.routeList}`)
console.log(`- backendGate: ${summary.resourceReadiness.backendGate}`)
console.log(`- viewResourceField: ${summary.resourceReadiness.viewResourceField}`)
console.log(`- apiResourceField: ${summary.resourceReadiness.apiResourceField}`)
console.log(`- apiResourceSource: ${summary.resourceReadiness.apiResourceSource}`)
console.log(`- strictPassRequires: ${summary.resourceReadiness.strictPassRequires.join(', ')}`)
console.log('')
console.log(`Frontend completed evidence: ${summary.frontendCompletion.status}`)
for (const item of summary.frontendCompletion.evidence) {
  console.log(`- [${item.status}] ${item.id}: ${item.detail}`)
}
console.log('')
console.log(`Backend alignment blockers: ${summary.backendAlignmentBlockers.status}`)
for (const task of summary.backendAlignmentBlockers.pendingTasks) {
  console.log(`- [pending-backend] ${task.id}: ${task.description}`)
}
for (const route of summary.backendAlignmentBlockers.pendingRoutes) {
  console.log(`- [mock-ready] ${route.route}: ${route.endpoint} (${route.resources})`)
  console.log(`  apiResources: ${route.apiResources}`)
  console.log(`  runtimeFields: ${route.runtimeFields}`)
  console.log(`  apiNeeds: ${route.apiNeeds}`)
}
console.log('')
console.log('Next frontend tasks:')
for (const task of summary.nextFrontendTasks) {
  console.log(`- [${task.status}] ${task.id}: ${task.description}`)
}
console.log('')
console.log('Backend alignment pending:')
for (const item of summary.backendAlignmentPending) {
  console.log(`- ${item}`)
}
console.log('')
console.log('Backend alignment handoff:')
console.log(`- resourcesBffFlag: ${summary.backendAlignmentHandoff.resourcesBffFlag}`)
console.log(`- resourcesBffEndpoint: ${summary.backendAlignmentHandoff.resourcesBffEndpoint}`)
console.log(`- pendingRouteCount: ${summary.backendAlignmentHandoff.pendingRouteCount}`)
console.log(`- pendingRoutes: ${summary.backendAlignmentHandoff.pendingRouteIds.join(', ')}`)
console.log(`- handoffRule: ${summary.backendAlignmentHandoff.handoffRule}`)
console.log('- frontendOwnedCommands:')
for (const command of summary.backendAlignmentHandoff.frontendOwnedCommands) {
  console.log(`  - ${command}`)
}
console.log('- backendOwnedCommands:')
for (const command of summary.backendAlignmentHandoff.backendOwnedCommands) {
  console.log(`  - ${command}`)
}

if (strictFailures.length > 0) {
  console.log('')
  console.log('Strict readiness failures:')
  for (const item of strictFailures) {
    console.log(`- ${item}`)
  }
  process.exit(1)
}
