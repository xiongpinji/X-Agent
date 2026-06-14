import { existsSync } from 'node:fs'
import { resolve } from 'node:path'
import { verifyPandaComponentPrimitives } from './verify-panda-component-primitives.mjs'
import {
  pandaAdapterCheckNames,
  pandaAdapterFixtureBarrelSources,
  pandaAdapterOutputFixtureSymbols,
  pandaAlignmentContextRequiredSymbols,
  pandaAlignmentReportRequiredSymbols,
  pandaAlignmentDocRequiredPhrases,
  pandaAdapterBarrelSymbols,
  pandaApiContractBarrelSymbols,
  pandaApiSnapshotResourceKeys,
  pandaBaseRuntimeFields,
  pandaBootstrapResourcesRequiredSymbols,
  pandaCloseoutPlanRequiredSymbols,
  pandaCloseoutEvidenceRequiredSymbols,
  pandaCoreRuntimeFieldNames,
  pandaDeliveryReadinessExpectations,
  pandaEvidenceRuntimeRouteIds,
  pandaManifestRequiredSafeScopeEntries,
  pandaManifestVerificationCommands,
  pandaPackageScriptExpectations,
  pandaPageBffEndpoints,
  pandaPageResourceContractSymbols,
  pandaPageRegistryRequiredSymbols,
  pandaPureAdapterModuleNames,
  pandaProgressRuntimeFields,
  pandaProgressRuntimeRouteIds,
  pandaResourceBoundaryExpectedEntries,
  pandaResourceContractCheckNames,
  pandaResourceContractBarrelSymbols,
  pandaResourceContractSourceNames,
  pandaResourceContractTypeSymbols,
  pandaResourceDryRunCheckNames,
  pandaResourceKeyBoundarySymbols,
  pandaResourceKeyPairExpectations,
  pandaResourceReadinessRequiredSymbols,
  pandaResourceRuntimeFieldSymbols,
  pandaResourceSnapshotViewKeys,
  pandaResourceValidationRequiredSymbols,
  pandaResourceValidationCheckNames,
  pandaRequiredFrontendTaskIds,
  pandaResourcesBffConfigRequiredSymbols,
  pandaResourcesBffEnvNames,
  pandaResourcesHttpClientRequiredSymbols,
  pandaRuntimeAdapterModuleNames,
  pandaRuntimeApiFieldNames,
  pandaRuntimeMetadataContractSources,
  pandaRuntimeMappingSymbols,
  pandaScriptUtilityConsumerScripts,
  pandaScriptUtilityNames,
  pandaScriptedQaRequiredSymbols,
  pandaShellBrandingSymbols,
  pandaShellLayoutClasses,
  pandaShellRequiredSymbols,
  pandaTsProbeUtilityNames,
  pandaVisualReviewRouteIds,
  pandaWorkbenchPageIds,
  pandaWorkbenchRequiredFiles,
  pandaWorkspaceCompatibilitySymbols,
  pandaWorkspaceProviderSymbols,
  pandaWorkspaceTypeSymbols,
  pandaModulePageResourceHookByPage,
  pandaModulePageResourceHookSymbols,
  pandaModulePageResourceTypeByPage,
  pandaModulePageResourceTypeSymbols,
  pandaVerifyConfigInventoryNames,
  pandaExecutionResourceAdapterSymbols,
  pandaOrganizationResourceAdapterSymbols,
  pandaAgentRoleAdapterSymbols,
  pandaKnowledgeResourceAdapterSymbols,
  pandaGovernanceResourceAdapterSymbols,
  pandaHomeApiContractSymbols,
  pandaExecutionApiContractSymbols,
  pandaOrganizationApiContractSymbols,
  pandaKnowledgeApiContractSymbols,
  pandaGovernanceApiContractSymbols,
  pandaHomeActionContentSymbols,
  pandaHomeContentSymbols,
  pandaMockExecutionResourceSymbols,
  pandaMockKnowledgeResourceSymbols,
  pandaMockOrganizationResourceSymbols,
  pandaMockResourceBarrelSources,
  pandaMockWorkspaceResourceSymbols,
  pandaModuleFallbackContentSymbols,
  pandaResourceClientFixtureSymbols,
  pandaResourceSnapshotFixtureSymbols,
  pandaResourceViewModelTypeNames,
  pandaAgentRoleTypeNames,
  pandaRouteTypeNames,
  pandaRuntimeTypeNames,
  pandaRuntimeViewFieldNames,
  pandaSnapshotApiContractSymbols,
  pandaTypeBarrelSources,
  pandaWorkbenchTypeNames,
  pandaAgentOrganizationSymbols,
  pandaAgentProfileCardSymbols,
  pandaAgentRolePresetSelectorSymbols,
  pandaAuditReplaySymbols,
  pandaAlignmentContextConsumerScripts,
  pandaAutomationRulesSymbols,
  pandaDataCenterSymbols,
  pandaHomeActionComponentSymbols,
  pandaHomePageComponentSymbols,
  pandaKnowledgeBaseSymbols,
  pandaManagementRowPageIds,
  pandaModuleFallbackComponentSymbols,
  pandaModuleDeliverySurfaceSymbols,
  pandaModuleFallbackSurfaceSymbols,
  pandaModulePagePrimitiveSymbols,
  pandaModulePageContentSymbols,
  pandaPageFileById,
  pandaPageFiles,
  pandaProjectWorkspaceSymbols,
  pandaRightRailCardSymbols,
  pandaRightRailFocusedCardSymbols,
  pandaRightRailResourceCardSymbols,
  pandaRightRailStatusCardSymbols,
  pandaSectionHeaderPageIds,
  pandaSettingsCenterSymbols,
  pandaTaskQueueSymbols,
  pandaThreadWorkspaceSymbols,
  pandaToolCenterSymbols,
  pandaWorkflowCanvasSymbols,
} from './panda-workbench-verify-config.mjs'
import {
  assert,
  extractResourceKeyPairs,
  pandaScriptRoot,
  read,
  readJson,
  requestStatus,
  runNodeJson,
  sameMembers,
  unique,
} from './panda-script-utils.mjs'

const root = pandaScriptRoot
const requiredFiles = pandaWorkbenchRequiredFiles
const pageIds = pandaWorkbenchPageIds

function objectLiteralIncludesKey(source, key) {
  return new RegExp(`^\\s*${key}\\s*(?::|,)`, 'm').test(source)
}

function assertPandaBackendAlignmentHandoff(handoff, label) {
  assert(
    sameMembers(handoff?.frontendOwnedCommands ?? [], manifest.frontendHandoffGates?.frontendOwnedCommands ?? []),
    `${label} must reuse manifest frontend-owned commands`,
  )
  assert(
    sameMembers(handoff?.backendOwnedCommands ?? [], manifest.frontendHandoffGates?.backendOwnedCommands ?? []),
    `${label} must reuse manifest backend-owned commands`,
  )
  assert(handoff?.handoffRule === manifest.frontendHandoffGates?.handoffRule, `${label} handoff rule must match the manifest handoff rule`)
  assert(handoff?.resourcesBffFlag === manifest.bff.resourcesFlag, `${label} must reuse the manifest resources BFF flag`)
  assert(handoff?.resourcesBffEndpoint === manifest.bff.resourcesEndpoint, `${label} must reuse the manifest resources BFF endpoint`)
  assert(
    handoff?.pendingRouteCount === alignmentReportJson.backendAlignmentBlockers.pendingRoutes.length,
    `${label} pending route count must match alignment report blockers`,
  )
  assert(
    sameMembers(
      handoff?.pendingRouteIds ?? [],
      alignmentReportJson.backendAlignmentBlockers.pendingRoutes.map((route) => route.route),
    ),
    `${label} pending route ids must match alignment report blockers`,
  )
}

for (const file of requiredFiles) {
  assert(existsSync(resolve(root, file)), `Missing required Panda file: ${file}`)
}

const manifest = readJson('src/panda/pandaFrontendManifest.json')
const contractParser = read('scripts/panda-contract-parser.mjs')
const scriptUtils = read('scripts/panda-script-utils.mjs')
const alignmentContextSource = read('scripts/panda-alignment-context.mjs')
const closeoutEvidenceSource = read('scripts/panda-closeout-evidence.mjs')
const modulePageStructureSource = read('scripts/panda-module-page-structure.mjs')
const routeRolloverPlanSource = read('scripts/panda-route-rollover-plan.mjs')
const tsProbeUtils = read('scripts/panda-ts-probe-utils.mjs')
const verifyConfig = read('scripts/panda-workbench-verify-config.mjs')
const verifyWorkbenchSource = read('scripts/verify-panda-workbench.mjs')
const alignmentReportSource = read('scripts/panda-alignment-report.mjs')
const closeoutPlanSource = read('scripts/panda-frontend-closeout-plan.mjs')
const qaSmokeSource = read('scripts/panda-qa-smoke.mjs')
const resourceDryRunSource = read('scripts/verify-panda-resource-dry-run.mjs')
const resourceContractProbeSource = read('scripts/verify-panda-resource-contracts.mjs')
const resourceValidationSource = read('scripts/verify-panda-resource-validation.mjs')
const adapterProbeSource = read('scripts/verify-panda-adapters.mjs')
const expectedStaticProbeCount = manifest.scriptedQaEvidence?.staticProbeCount
const resourceKeyPairsForManifest = extractResourceKeyPairs(read('src/panda/api/resourceKeys.ts'))
const resourceBoundaryApiKeysForManifest = unique(resourceKeyPairsForManifest.map((pair) => pair.apiKey))
const resourceBoundaryViewKeysForManifest = unique(resourceKeyPairsForManifest.map((pair) => pair.viewKey))
assert(verifyConfig.includes('pandaWorkbenchRequiredFiles'), 'Panda workbench verify config must own the required file inventory')
assert(verifyConfig.includes('pandaWorkbenchPageIds'), 'Panda workbench verify config must own the first-level page inventory')
assert(verifyConfig.includes('pandaManifestRequiredSafeScopeEntries'), 'Panda workbench verify config must own the manifest safe-scope inventory')
assert(verifyConfig.includes('pandaResourceBoundaryExpectedEntries'), 'Panda workbench verify config must own the resource boundary inventory')
assert(verifyConfig.includes('pandaPackageScriptExpectations'), 'Panda workbench verify config must own package script expectations')
assert(verifyConfig.includes('pandaManifestVerificationCommands'), 'Panda workbench verify config must own manifest verification commands')
assert(verifyConfig.includes('pandaVisualReviewRouteIds'), 'Panda workbench verify config must own visual review route expectations')
assert(verifyConfig.includes('pandaRequiredFrontendTaskIds'), 'Panda workbench verify config must own required frontend task expectations')
assert(verifyConfig.includes('pandaVerifyConfigInventoryNames'), 'Panda workbench verify config must own verifier inventory coverage')
assert(verifyConfig.includes('pandaAlignmentContextConsumerScripts'), 'Panda workbench verify config must own alignment context consumer scripts')
assert(verifyConfig.includes('pandaScriptUtilityConsumerScripts'), 'Panda workbench verify config must own script utility consumer scripts')
for (const inventoryName of pandaVerifyConfigInventoryNames) {
  assert(verifyConfig.includes(inventoryName), `Panda workbench verify config must own inventory: ${inventoryName}`)
}
assert(modulePageStructureSource.includes('getPandaModulePageStructure'), 'Panda module page structure utility must expose the shared structure factory')
assert(modulePageStructureSource.includes('PANDA_MODULE_PAGE_STRUCTURE'), 'Panda module page structure utility must expose the stable module structure constants')
assert(modulePageStructureSource.includes("from './panda-workbench-verify-config.mjs'"), 'Panda module page structure utility must derive hook bindings from verify config')
assert(modulePageStructureSource.includes('pandaModulePageResourceTypeByPage'), 'Panda module page structure utility must derive resource type bindings from verify config')
assert(modulePageStructureSource.includes('resourceTypes: Object.entries(pandaModulePageResourceTypeByPage)'), 'Panda module page structure utility must expose page resource type bindings')
for (const symbol of pandaAlignmentContextRequiredSymbols) {
  assert(alignmentContextSource.includes(symbol), `Panda alignment context must expose ${symbol}`)
}
for (const symbol of pandaCloseoutEvidenceRequiredSymbols) {
  assert(closeoutEvidenceSource.includes(symbol), `Panda closeout evidence must expose ${symbol}`)
}
assert(routeRolloverPlanSource.includes('PANDA_ROUTE_ROLLOVER_SOURCE'), 'Panda route rollover utility must expose the stable source marker')
assert(routeRolloverPlanSource.includes('buildPandaRouteRolloverPlan'), 'Panda route rollover utility must expose the shared rollover factory')
assert(routeRolloverPlanSource.includes('getPandaExpectedStrictFailure'), 'Panda route rollover utility must expose the shared strict failure summary')
assert(routeRolloverPlanSource.includes('getPandaStrictFailures'), 'Panda route rollover utility must expose the shared strict failure details')
assert(contractParser.includes('extractPandaPageResourceContracts'), 'Panda contract parser must own page resource contract extraction')
assert(contractParser.includes('pandaCoreRuntimeFields'), 'Panda contract parser must preserve shared core runtime field expansion')
assert(resourceContractProbeSource.includes("from './panda-contract-parser.mjs'"), 'Panda resource contract probe must import the shared contract parser')
assert(resourceContractProbeSource.includes('extractParsedPageContracts'), 'Panda resource contract probe must centralize contract parsing through the shared parser')
assert(!/function extractResourceContractKeys\(source\) \{\s*const values = \[\]/m.test(resourceContractProbeSource), 'Panda resource contract probe must not duplicate page contract resource-key parsing')
for (const utilityName of pandaScriptUtilityNames) {
  assert(scriptUtils.includes(`function ${utilityName}`), `Panda script utils must expose shared helper: ${utilityName}`)
}
for (const utilityName of pandaTsProbeUtilityNames) {
  assert(tsProbeUtils.includes(`function ${utilityName}`), `Panda TS probe utils must expose shared helper: ${utilityName}`)
}
assert(tsProbeUtils.includes('pandaApiProbeFileNames'), 'Panda TS probe utils must own the shared API probe file inventory')
const pandaScriptSources = {
  'panda-alignment-report.mjs': alignmentReportSource,
  'panda-frontend-closeout-plan.mjs': closeoutPlanSource,
  'panda-qa-smoke.mjs': qaSmokeSource,
  'verify-panda-resource-contracts.mjs': resourceContractProbeSource,
}
for (const scriptName of pandaAlignmentContextConsumerScripts) {
  const source = pandaScriptSources[scriptName]
  assert(source, `Panda verifier missing source for alignment context consumer: ${scriptName}`)
  assert(!/^function extractContracts\(/m.test(source), `${scriptName} must not own duplicate Panda contract parsing`)
  assert(source.includes("from './panda-alignment-context.mjs'"), `${scriptName} must import shared Panda alignment context`)
  assert(source.includes("from './panda-closeout-evidence.mjs'"), `${scriptName} must import shared Panda closeout evidence`)
  assert(!source.includes("from './panda-workbench-verify-config.mjs'"), `${scriptName} must not import verify config directly for module page hooks`)
}
for (const scriptName of pandaScriptUtilityConsumerScripts) {
  const source = pandaScriptSources[scriptName]
  assert(source, `Panda verifier missing source for script utility consumer: ${scriptName}`)
  assert(source.includes("from './panda-script-utils.mjs'"), `${scriptName} must import shared Panda script utilities`)
  assert(!/^function read\(/m.test(source), `${scriptName} must not own duplicate file read helper`)
}
assert(!/^function requestStatus\(/m.test(qaSmokeSource), 'panda-qa-smoke.mjs must not own duplicate route status helper')
assert(!/^function buildPendingRouteSignature\(/m.test(resourceContractProbeSource), 'verify-panda-resource-contracts.mjs must not own duplicate pending route signature helper')
assert(!/^function extractApiResourcesFromPendingRouteSignatures\(/m.test(resourceContractProbeSource), 'verify-panda-resource-contracts.mjs must not own duplicate pending route apiResources extraction helper')
assert(resourceValidationSource.includes("from './panda-ts-probe-utils.mjs'"), 'verify-panda-resource-validation.mjs must import shared TS probe utilities')
assert(!resourceValidationSource.includes('ts.transpileModule'), 'verify-panda-resource-validation.mjs must not own duplicate TS transpile template')
assert(adapterProbeSource.includes("from './panda-ts-probe-utils.mjs'"), 'verify-panda-adapters.mjs must import shared TS probe utilities')
assert(!adapterProbeSource.includes('ts.transpileModule'), 'verify-panda-adapters.mjs must not own duplicate TS transpile template')
assert(resourceDryRunSource.includes("from './panda-ts-probe-utils.mjs'"), 'verify-panda-resource-dry-run.mjs must import shared TS probe utilities')
assert(!resourceDryRunSource.includes('ts.transpileModule'), 'verify-panda-resource-dry-run.mjs must not own duplicate TS transpile template')
assert(resourceDryRunSource.includes('resourceSnapshotFixtures.ts'), 'verify-panda-resource-dry-run.mjs must transpile shared resource snapshot fixtures')
assert(resourceDryRunSource.includes('aggregateResourcesBffDryRunFixture'), 'verify-panda-resource-dry-run.mjs must reuse the shared aggregate resources dry-run fixture')
assert(resourceDryRunSource.includes('resourceRuntimeFields.ts'), 'verify-panda-resource-dry-run.mjs must read the shared runtime field contract')
assert(resourceDryRunSource.includes('pandaCoreRuntimeFields'), 'verify-panda-resource-dry-run.mjs must verify aggregate fixtures against pandaCoreRuntimeFields')
assert(resourceDryRunSource.includes('aggregate-fixture-core-runtime-fields'), 'verify-panda-resource-dry-run.mjs must expose a named aggregate fixture core runtime field check')
assert(verifyWorkbenchSource.includes("from './panda-workbench-verify-config.mjs'"), 'Panda workbench verifier must import its inventory config')
assert(verifyWorkbenchSource.includes("from './panda-script-utils.mjs'"), 'Panda workbench verifier must import shared script utilities')
assert(!/^const requiredFiles = \[/m.test(verifyWorkbenchSource), 'Panda workbench verifier must not own the required file inventory inline')
assert(!/^const pageIds = \[/m.test(verifyWorkbenchSource), 'Panda workbench verifier must not own the page inventory inline')
assert(!/safeScope\?\.includes\(['"]frontend\/src\/panda\//.test(verifyWorkbenchSource), 'Panda workbench verifier must not own the manifest safe-scope inventory inline')
assert(!/resourceBoundary\?\.[a-zA-Z]+ === ['"]src\/panda\//.test(verifyWorkbenchSource), 'Panda workbench verifier must not own the resource boundary inventory inline')
assert(!/for \(const command of \[\n\s+'npm run verify:panda'/.test(verifyWorkbenchSource), 'Panda workbench verifier must not own manifest verification commands inline')
assert(!/packageJson\.scripts\?\.\['report:panda'\] ===/.test(verifyWorkbenchSource), 'Panda workbench verifier must not own package script expectations inline')
assert(!/for \(const symbol of \[\n\s+'pandaFrontendManifest\.json'/.test(verifyWorkbenchSource), 'Panda workbench verifier must not own report or QA symbol inventories inline')
assert(!/for \(const checkName of \['tone-fallback'/.test(verifyWorkbenchSource), 'Panda workbench verifier must not own adapter check inventory inline')
assert(!/for \(const utilityName of \['readJson'/.test(verifyWorkbenchSource), 'Panda workbench verifier must not own shared script utility inventory inline')
assert(!/for \(const utilityName of \[\n\s+'createPandaTsProbeTempDir'/.test(verifyWorkbenchSource), 'Panda workbench verifier must not own TS probe utility inventory inline')
assert(!/for \(const \[key, value\] of \[\r?\n\s+\['frontendShell'/.test(verifyWorkbenchSource), 'Panda workbench verifier must not own delivery readiness inventory inline')
assert(!/for \(const field of \['status', 'risk_level', 'updated_at'\]/.test(verifyWorkbenchSource), 'Panda workbench verifier must not own base runtime field inventory inline')
assert(!/for \(const symbol of \[\r?\n\s+'PandaShellFrame'/.test(verifyWorkbenchSource), 'Panda workbench verifier must not own shell symbol inventory inline')
assert(!/for \(const phrase of \['Frontend Engineering Goal'/.test(verifyWorkbenchSource), 'Panda workbench verifier must not own alignment doc phrase inventory inline')
assert(!/for \(const symbol of \['PandaResourceValidationError'/.test(verifyWorkbenchSource), 'Panda workbench verifier must not own resource validation symbol inventory inline')
assert(!/for \(const \[viewKey, apiKey\] of \[\r?\n\s+\['workflowNodes'/.test(verifyWorkbenchSource), 'Panda workbench verifier must not own resource key pair inventory inline')
assert(!/for \(const symbol of \['PANDA_RESOURCES_BFF_ENDPOINT'/.test(verifyWorkbenchSource), 'Panda workbench verifier must not own resources HTTP client symbol inventory inline')
assert(!/for \(const envName of \['VITE_PANDA_RESOURCES_BFF'/.test(verifyWorkbenchSource), 'Panda workbench verifier must not own resources BFF env inventory inline')
assert(!/for \(const endpoint of \[\r?\n\s+'\/api\/v1\/workbench\/home'/.test(verifyWorkbenchSource), 'Panda workbench verifier must not own page BFF endpoint inventory inline')
assert(!/for \(const symbol of \['PandaWorkspaceProvider', 'usePandaWorkspace'/.test(verifyWorkbenchSource), 'Panda workbench verifier must not own workspace symbol inventory inline')
assert(!/for \(const symbol of \['ApiRuntimeMetadata', 'ApiPandaResourceSnapshot'/.test(verifyWorkbenchSource), 'Panda workbench verifier must not own adapter barrel inventory inline')
assert(!/for \(const symbol of \['ApiWorkbenchHome', 'ApiWorkbenchActivityItem'/.test(verifyWorkbenchSource), 'Panda workbench verifier must not own API contract inventory inline')
assert(!/for \(const apiField of \['risk_level', 'owner_agent'/.test(verifyWorkbenchSource), 'Panda workbench verifier must not own runtime API field inventory inline')
assert(!/for \(const source of \['\.\/adapterOutputFixtures'/.test(verifyWorkbenchSource), 'Panda workbench verifier must not own adapter fixture source inventory inline')
assert(!/for \(const typeName of \['PandaPage', 'NavItem'/.test(verifyWorkbenchSource), 'Panda workbench verifier must not own route type inventory inline')
assert(!/for \(const symbol of \['quickActions', 'promptActions'/.test(verifyWorkbenchSource), 'Panda workbench verifier must not own home content inventory inline')
assert(!/for \(const resourceSymbol of \[\r?\n\s+'projects'/.test(verifyWorkbenchSource), 'Panda workbench verifier must not own mock resource inventory inline')
assert(!/for \(const symbol of \['RecentProjects', 'PlatformSnapshot'/.test(verifyWorkbenchSource), 'Panda workbench verifier must not own home component inventory inline')
assert(!/const pageFiles = \[\r?\n\s+'src\/panda\/pages\/HomePage\.tsx'/.test(verifyWorkbenchSource), 'Panda workbench verifier must not own page file inventory inline')
assert(!/for \(const symbol of \['ThreadListPanel', 'ThreadWorkPanel'/.test(verifyWorkbenchSource), 'Panda workbench verifier must not own page component symbol inventory inline')
assert(!/for \(const symbol of \['ResourceSnapshotCard', 'AgentActivityCard'/.test(verifyWorkbenchSource), 'Panda workbench verifier must not own right rail symbol inventory inline')
assert(manifest.productName === 'Panda Agent', 'Panda manifest must use the product brand')
assert(manifest.technicalCore === 'X-Agent Autonomous Framework', 'Panda manifest must preserve the X-Agent technical core')
assert(manifest.entry === 'src/panda/PandaAgentApp.tsx', 'Panda manifest must point to the app entry')
assert(Array.isArray(manifest.routes), 'Panda manifest must list routes')
assert(manifest.routes.length === pageIds.length, 'Panda manifest route count must match Panda navigation')
for (const pageId of pageIds) {
  assert(manifest.routes.includes(pageId), `Panda manifest missing route: ${pageId}`)
}
assert(manifest.bff?.homeEndpoint === '/api/v1/workbench/home', 'Panda manifest must record the home BFF endpoint')
assert(manifest.bff?.resourcesEndpoint === '/api/v1/workbench/resources', 'Panda manifest must record the resources BFF endpoint')
assert(manifest.bff?.resourcesFlag === 'VITE_PANDA_RESOURCES_BFF', 'Panda manifest must record the resources BFF flag')
assert(manifest.bff?.resourcesFlagDefault === 'true', 'Panda manifest must enable resources BFF by default after backend alignment')
for (const [key, value] of pandaDeliveryReadinessExpectations) {
  assert(manifest.deliveryReadiness?.[key] === value, `Panda delivery readiness mismatch: ${key}`)
}
assert(
  manifest.deliveryReadiness?.visualReviewTarget === 'http://127.0.0.1:3000/#threads',
  'Panda delivery readiness must expose the browser visual review target',
)
assert(manifest.frontendCloseout?.currentPhase === 'backend-resources-bff-wired', 'Panda manifest must expose the frontend closeout phase')
assert(manifest.frontendCloseout?.backendDependency === 'resources-bff-page-slices-wired', 'Panda manifest must record the backend dependency for frontend closeout')
for (const [entry, message] of pandaManifestRequiredSafeScopeEntries) {
  assert(manifest.frontendCloseout?.safeScope?.includes(entry), message)
}
assert(manifest.frontendCloseout?.blockedScope?.some((item) => item.includes('sandbox execution policy')), 'Panda manifest must keep high-risk backend scope blocked')
assert(Array.isArray(manifest.visualReviewTargets), 'Panda manifest must expose visual review targets')
assert(manifest.visualReviewTargets.length >= 5, 'Panda manifest must cover desktop and mobile visual review targets')
for (const route of pandaVisualReviewRouteIds) {
  assert(manifest.visualReviewTargets.some((target) => target.route === route), `Panda visual review targets missing route: ${route}`)
}
assert(manifest.visualReviewTargets.some((target) => target.viewport === '390x844'), 'Panda visual review targets must include a mobile viewport')
assert(Array.isArray(manifest.nextFrontendTasks), 'Panda manifest must expose next frontend tasks')
for (const taskId of pandaRequiredFrontendTaskIds) {
  assert(manifest.nextFrontendTasks.some((task) => task.id === taskId), `Panda manifest missing next frontend task: ${taskId}`)
}
assert(manifest.nextFrontendTasks.some((task) => task.id === 'visual-review' && task.status === 'passed'), 'Panda visual review task must record the completed browser QA pass')
assert(manifest.nextFrontendTasks.some((task) => task.id === 'agent-role-card-contract' && task.status === 'passed'), 'Panda manifest must record the agent role card contract as frontend-complete')
assert(manifest.nextFrontendTasks.some((task) => task.id === 'agent-role-card-contract' && task.description?.includes('ApiAgentRolePreset') && task.description?.includes('mapAgentRolePreset')), 'Panda agent role card contract task must name the DTO and mapper boundary')
assert(manifest.visualReviewEvidence?.status === 'passed', 'Panda manifest must record passing visual review evidence')
assert(manifest.visualReviewEvidence?.browser === 'Codex In-app Browser', 'Panda visual review evidence must identify the browser surface')
assert(manifest.visualReviewEvidence?.devServer === 'http://127.0.0.1:3000', 'Panda visual review evidence must record the dev server URL')
assert(manifest.visualReviewEvidence?.routes?.includes('settings'), 'Panda visual review evidence must include the mobile settings route')
assert(manifest.visualReviewEvidence?.interaction?.includes('#workflows'), 'Panda visual review evidence must record the workflow navigation proof')
assert(manifest.nextFrontendTasks.some((task) => task.id === 'accessibility-pass' && task.status === 'passed'), 'Panda accessibility pass must record completion')
assert(manifest.accessibilityEvidence?.status === 'passed', 'Panda manifest must record passing accessibility evidence')
assert(manifest.accessibilityEvidence?.scope?.includes('keyboard focus'), 'Panda accessibility evidence must cover keyboard focus')
assert(manifest.accessibilityEvidence?.scope?.includes('skip link'), 'Panda accessibility evidence must cover the skip link')
assert(manifest.accessibilityEvidence?.scope?.includes('progressbar labels'), 'Panda accessibility evidence must cover progressbar labels')
assert(manifest.accessibilityEvidence?.browserProof?.includes('aria-current=工作流'), 'Panda accessibility evidence must record browser navigation proof')
assert(manifest.accessibilityEvidence?.browserProof?.includes('#panda-main-content'), 'Panda accessibility evidence must record skip link browser proof')
assert(manifest.accessibilityEvidence?.screenshotDir?.includes('panda-a11y-qa-'), 'Panda accessibility evidence must record a local QA screenshot directory')
assert(manifest.accessibilityEvidence?.staticProof?.includes('skip link'), 'Panda accessibility evidence must record static skip link proof')
assert(manifest.scriptedQaEvidence?.status === 'passed', 'Panda manifest must record passing scripted QA evidence')
assert(manifest.scriptedQaEvidence?.script === 'frontend/scripts/panda-qa-smoke.mjs', 'Panda scripted QA evidence must record the QA script path')
assert(manifest.scriptedQaEvidence?.commands?.includes('npm run qa:panda'), 'Panda scripted QA evidence must record the default QA command')
assert(manifest.scriptedQaEvidence?.commands?.includes('npm run qa:panda:json'), 'Panda scripted QA evidence must record the JSON QA command')
assert(manifest.scriptedQaEvidence?.commands?.includes('npm run qa:panda:browser'), 'Panda scripted QA evidence must record the optional browser QA command')
assert(manifest.scriptedQaEvidence?.scope?.includes('skip link and main landmark wiring'), 'Panda scripted QA must cover skip link and main landmark wiring')
assert(manifest.scriptedQaEvidence?.scope?.includes('resources BFF snapshot validation'), 'Panda scripted QA must cover resources BFF snapshot validation')
assert(manifest.scriptedQaEvidence?.scope?.some((item) => item.includes('resources BFF executable validation probe')), 'Panda scripted QA must cover executable resources validation')
assert(manifest.scriptedQaEvidence?.scope?.some((item) => item.includes('resources contract consistency probe')), 'Panda scripted QA must cover resource contract consistency')
assert(manifest.scriptedQaEvidence?.scope?.some((item) => item.includes('resources BFF dry-run fixture')), 'Panda scripted QA must cover resources dry-run fixture')
assert(manifest.scriptedQaEvidence?.scope?.some((item) => item.includes('pandaCoreRuntimeFields') && item.includes('core runtime API field coverage')), 'Panda scripted QA must record pandaCoreRuntimeFields core runtime API coverage')
assert(manifest.scriptedQaEvidence?.scope?.some((item) => item.includes('agent role card contract') && item.includes('ApiAgentRolePreset')), 'Panda scripted QA must record agent role card DTO mapping coverage')
assert(Number.isInteger(expectedStaticProbeCount) && expectedStaticProbeCount > 0, 'Panda scripted QA must record the current static probe count')
assert(manifest.scriptedQaEvidence?.fallback?.includes('static probes still run'), 'Panda scripted QA must document dev-server skip behavior')
for (const [key, expected, message] of pandaResourceBoundaryExpectedEntries) {
  assert(manifest.resourceBoundary?.[key] === expected, message)
}
assert(manifest.resourceBoundary?.apiKeys?.includes('workflow_nodes'), 'Panda manifest must expose aggregate API resource keys')
assert(manifest.resourceBoundary?.viewKeys?.includes('workflowNodes'), 'Panda manifest must expose Panda view resource keys')
assert(sameMembers(manifest.resourceBoundary?.apiKeys ?? [], resourceBoundaryApiKeysForManifest), 'Panda manifest API resource keys must match resourceKeys.ts')
assert(sameMembers(manifest.resourceBoundary?.viewKeys ?? [], resourceBoundaryViewKeysForManifest), 'Panda manifest view resource keys must match resourceKeys.ts')
assert(manifest.frontendHandoffGates?.frontendEvidenceGate === 'passed', 'Panda manifest must record the frontend evidence handoff gate as passed')
assert(manifest.frontendHandoffGates?.strictBackendGate === 'ready', 'Panda manifest must mark strict backend gate ready after BFF alignment')
assert(manifest.frontendHandoffGates?.frontendOwnedCommands?.includes('npm run qa:panda:json'), 'Panda handoff gates must include the scripted QA JSON command')
assert(manifest.frontendHandoffGates?.frontendOwnedCommands?.includes('npm run verify:panda:dry-run'), 'Panda handoff gates must include the resources dry-run command')
assert(manifest.frontendHandoffGates?.backendOwnedCommands?.includes('npm run report:panda:strict'), 'Panda handoff gates must keep strict mode backend-owned before alignment')
assert(manifest.frontendHandoffGates?.handoffRule?.includes('Strict mode is green after the aggregate resources BFF and page slice APIs are wired'), 'Panda handoff gates must explain strict-mode ownership')
for (const command of pandaManifestVerificationCommands) {
  assert(manifest.verification?.includes(command), `Panda manifest missing verification command: ${command}`)
}
assert(manifest.backendAlignmentPending?.some((item) => item.includes('approval, sandbox, auth, secret')), 'Panda manifest must keep high-risk policy ownership on the backend')

const packageJson = readJson('package.json')
for (const [scriptName, expectedCommand, message] of pandaPackageScriptExpectations) {
  assert(packageJson.scripts?.[scriptName] === expectedCommand, message)
}

const alignmentReport = read('scripts/panda-alignment-report.mjs')
for (const symbol of pandaAlignmentReportRequiredSymbols) {
  assert(alignmentReport.includes(symbol), `Panda alignment report missing expected report element: ${symbol}`)
}

const alignmentReportJson = runNodeJson('scripts/panda-alignment-report.mjs', ['--json'])
assert(alignmentReportJson.productName === 'Panda Agent', 'Panda JSON report must expose productName')
assert(alignmentReportJson.routeCount === pageIds.length, 'Panda JSON report route count must match navigation')
assert(alignmentReportJson.apiWiredCount === pageIds.length, 'Panda JSON report must show every route API-wired after backend alignment')
assert(alignmentReportJson.mockReadyCount === 0, 'Panda JSON report must show no mock-ready routes after backend alignment')
assert(alignmentReportJson.resourcesBff?.endpoint === '/api/v1/workbench/resources', 'Panda JSON report must expose resources BFF endpoint')
assert(alignmentReportJson.resourcesBff?.defaultValue === 'true', 'Panda JSON report must enable resources BFF by default after backend alignment')
assert(alignmentReportJson.deliveryReadiness?.visibleContractStrip === 'ready', 'Panda JSON report must expose visible contract strip readiness')
assert(alignmentReportJson.deliveryReadiness?.strictBackendGate === 'ready', 'Panda JSON report must expose ready strict backend gate')
assert(alignmentReportJson.frontendCloseout?.currentPhase === 'backend-resources-bff-wired', 'Panda JSON report must expose backend resources BFF wired phase')
assert(alignmentReportJson.visualReviewTargets?.some((target) => target.route === 'threads'), 'Panda JSON report must expose visual review targets')
assert(alignmentReportJson.visualReviewEvidence?.status === 'passed', 'Panda JSON report must expose visual review evidence')
assert(alignmentReportJson.accessibilityEvidence?.status === 'passed', 'Panda JSON report must expose accessibility evidence')
assert(alignmentReportJson.scriptedQaEvidence?.status === 'passed', 'Panda JSON report must expose scripted QA evidence')
assert(alignmentReportJson.scriptedQaEvidence?.commands?.includes('npm run qa:panda:json'), 'Panda JSON report must expose scripted QA commands')
assert(alignmentReportJson.resourceKeyBoundary?.keyMap === 'src/panda/api/resourceKeys.ts', 'Panda JSON report must expose the shared resource key boundary')
assert(alignmentReportJson.resourceKeyBoundary?.apiKeys?.includes('workflow_nodes'), 'Panda JSON report must expose snake_case API resource keys')
assert(alignmentReportJson.resourceKeyBoundary?.viewKeys?.includes('workflowNodes'), 'Panda JSON report must expose camelCase view resource keys')
assert(alignmentReportJson.resourceKeyBoundary?.pairs?.some((pair) => pair.viewKey === 'workflowNodes' && pair.apiKey === 'workflow_nodes'), 'Panda JSON report must expose view/API resource key pairs')
assert(alignmentReportJson.routes?.every((route) => typeof route.apiResources === 'string'), 'Panda JSON report routes must expose API resource keys')
assert(alignmentReportJson.routes?.some((route) => route.route === 'workflows' && route.apiResources.includes('workflow_nodes')), 'Panda JSON report workflow route must expose snake_case API resources')
assert(
  alignmentReportJson.modulePageStructure?.resources === 'frontend/src/panda/state/useModulePageResources.ts',
  'Panda JSON report must expose the standard module page resource hook boundary',
)
assert(
  alignmentReportJson.modulePageStructure?.resourceHooks?.length === Object.keys(pandaModulePageResourceHookByPage).length,
  'Panda JSON report must expose every standard module page resource hook binding',
)
assert(
  alignmentReportJson.modulePageStructure?.resourceTypes?.length === Object.keys(pandaModulePageResourceTypeByPage).length,
  'Panda JSON report must expose every standard module page resource type binding',
)
for (const [page, hook] of Object.entries(pandaModulePageResourceHookByPage)) {
  const resourceType = pandaModulePageResourceTypeByPage[page]
  assert(resourceType, `Panda verifier missing module page resource type mapping: ${page}`)
  assert(
    alignmentReportJson.modulePageStructure.resourceHooks.some((binding) => binding.page === page && binding.hook === hook && binding.resourceType === resourceType),
    `Panda JSON report missing module page resource hook/type binding: ${page} -> ${hook}:${resourceType}`,
  )
  assert(
    alignmentReportJson.modulePageStructure.resourceTypes.some((binding) => binding.page === page && binding.resourceType === resourceType),
    `Panda JSON report missing module page resource type binding: ${page} -> ${resourceType}`,
  )
}
assert(alignmentReportJson.adapterEvidence?.status === 'passed', 'Panda JSON report must expose adapter behavior evidence')
assert(alignmentReportJson.adapterEvidence?.executableProbe === 'scripts/verify-panda-adapters.mjs', 'Panda JSON report must expose the adapter behavior probe')
assert(alignmentReportJson.adapterEvidence?.modules?.includes('src/panda/api/resourceSnapshotAdapter.ts'), 'Panda JSON report must expose focused adapter modules')
assert(alignmentReportJson.adapterEvidence?.scope?.includes('evidence refs and agent permissions copy semantics'), 'Panda JSON report must expose evidence refs and agent permissions copy adapter coverage')
assert(alignmentReportJson.resourcesValidationEvidence?.status === 'passed', 'Panda JSON report must expose resources validation evidence')
assert(alignmentReportJson.resourcesValidationEvidence?.validation === 'src/panda/api/resourcesValidation.ts', 'Panda JSON report must expose the resources validation file')
assert(alignmentReportJson.resourcesValidationEvidence?.invalidApiFallback === 'mock-with-error', 'Panda JSON report must expose invalid API fallback behavior')
assert(alignmentReportJson.resourcesContractEvidence?.status === 'passed', 'Panda JSON report must expose resources contract evidence')
assert(alignmentReportJson.resourcesContractEvidence?.executableProbe === 'scripts/verify-panda-resource-contracts.mjs', 'Panda JSON report must expose the resource contract probe')
assert(alignmentReportJson.resourcesContractEvidence?.comparedSources?.includes('src/panda/pandaFrontendManifest.json'), 'Panda JSON report must compare resource contracts against the manifest')
assert(alignmentReportJson.resourcesContractEvidence?.comparedSources?.includes('src/panda/api/resourceKeys.ts'), 'Panda JSON report must compare resource contracts against the shared resource key boundary')
assert(alignmentReportJson.resourcesContractEvidence?.comparedSources?.includes('src/panda/api/resourceReadiness.ts'), 'Panda JSON report must compare resource contracts against the readiness boundary')
assert(alignmentReportJson.resourcesContractEvidence?.comparedSources?.includes('src/panda/api/apiContracts.ts'), 'Panda JSON report must compare resource contracts against API snapshot types')
assert(alignmentReportJson.resourcesContractEvidence?.comparedSources?.includes('src/panda/api/resourceSnapshotAdapter.ts'), 'Panda JSON report must compare resource contracts against the focused resource snapshot adapter')
assert(alignmentReportJson.resourcesContractEvidence?.comparedSources?.includes('frontend/scripts/panda-alignment-context.mjs'), 'Panda JSON report must compare resource contracts against the shared alignment context source')
assert(alignmentReportJson.resourcesContractEvidence?.comparedSources?.includes('frontend/scripts/panda-closeout-evidence.mjs'), 'Panda JSON report must compare resource contracts against the shared closeout evidence source')
assert(alignmentReportJson.resourcesContractEvidence?.comparedSources?.includes('frontend/scripts/panda-route-rollover-plan.mjs'), 'Panda JSON report must compare resource contracts against the shared route rollover source')
assert(alignmentReportJson.resourcesContractEvidence?.comparedSources?.includes('frontend/scripts/panda-module-page-structure.mjs'), 'Panda JSON report must compare resource contracts against the shared module page structure source')
assert(alignmentReportJson.resourcesContractEvidence?.comparedSources?.includes('frontend/src/panda/state/useModulePageResources.ts'), 'Panda JSON report must compare resource contracts against the focused module resource hooks')
assert(alignmentReportJson.resourcesContractEvidence?.expectedAlignment?.includes('manifest apiKeys/viewKeys'), 'Panda JSON report must describe manifest resource key alignment')
assert(alignmentReportJson.resourcesContractEvidence?.expectedAlignment?.includes('shared resource key pairs'), 'Panda JSON report must describe shared resource key pair alignment')
assert(alignmentReportJson.resourcesContractEvidence?.expectedAlignment?.includes('mock-ready contract field completeness'), 'Panda JSON report must describe mock-ready contract field completeness')
assert(alignmentReportJson.resourcesContractEvidence?.expectedAlignment?.includes('PageResources type bindings'), 'Panda JSON report must describe standard module hook/type resource binding alignment')
assert(alignmentReportJson.resourcesContractEvidence?.expectedAlignment?.includes('route readiness'), 'Panda JSON report must describe route readiness alignment')
assert(alignmentReportJson.resourceReadiness?.source === 'src/panda/api/resourceReadiness.ts', 'Panda JSON report must expose the resource readiness source')
assert(alignmentReportJson.resourceReadiness?.routeList === 'pandaRouteReadiness', 'Panda JSON report must expose the route readiness list')
assert(alignmentReportJson.resourceReadiness?.backendGate === 'pandaBackendAlignmentReadiness', 'Panda JSON report must expose the backend readiness gate')
assert(alignmentReportJson.resourceReadiness?.viewResourceField === 'resources', 'Panda JSON report must name the route readiness view resource field')
assert(alignmentReportJson.resourceReadiness?.apiResourceField === 'apiResources', 'Panda JSON report must name the route readiness API resource field')
assert(alignmentReportJson.resourceReadiness?.apiResourceSource === 'src/panda/api/resourceKeys.ts', 'Panda JSON report must expose the API resource key source')
assert(alignmentReportJson.resourceReadiness?.strictPassRequires?.includes('all Panda routes api-wired'), 'Panda JSON report must expose strict route readiness requirement')
assert(alignmentReportJson.resourceReadiness?.strictPassRequires?.some((item) => item.includes('execution policy remain backend-owned')), 'Panda JSON report must preserve backend-owned high-risk policy readiness')
assert(alignmentReportJson.frontendCompletion?.status === 'passed', 'Panda JSON report must expose passed frontend completion evidence')
assert(alignmentReportJson.frontendCompletion?.owner === 'frontend', 'Panda JSON report must identify frontend completion ownership')
assert(alignmentReportJson.frontendCompletion?.evidence?.some((item) => item.id === 'scripted-qa-smoke' && item.status === 'passed'), 'Panda JSON report must include scripted QA in frontend completion evidence')
assert(alignmentReportJson.frontendCompletion?.evidence?.some((item) => item.id === 'adapter-behavior-executable' && item.status === 'passed'), 'Panda JSON report must include adapter behavior in frontend completion evidence')
assert(alignmentReportJson.frontendCompletion?.evidence?.some((item) => item.id === 'agent-role-card-contract' && item.status === 'passed'), 'Panda JSON report must include the agent role card contract in frontend completion evidence')
assert(alignmentReportJson.frontendCompletion?.evidence?.some((item) => item.id === 'resources-bff-validation' && item.status === 'passed'), 'Panda JSON report must include resource validation in frontend completion evidence')
assert(alignmentReportJson.frontendCompletion?.evidence?.some((item) => item.id === 'resources-contract-consistency' && item.status === 'passed'), 'Panda JSON report must include resource contract consistency in frontend completion evidence')
assert(alignmentReportJson.frontendCompletion?.evidence?.some((item) => item.id === 'route-api-resources-evidence' && item.status === 'passed'), 'Panda JSON report must include route API resources evidence in frontend completion evidence')
assert(alignmentReportJson.frontendCompletion?.evidence?.some((item) => item.id === 'route-api-resources-evidence' && item.detail?.includes('unknownRouteApiResources') && item.detail?.includes('missingRouteApiResources')), 'Panda JSON report route API resources completion evidence must expose unknown and missing diffs')
assert(alignmentReportJson.frontendCompletion?.evidence?.some((item) => item.id === 'resources-dry-run-fixture' && item.status === 'passed'), 'Panda JSON report must include resources dry-run fixture in frontend completion evidence')
assert(alignmentReportJson.frontendCompletion?.evidence?.some((item) => item.id === 'resources-dry-run-fixture' && item.detail?.includes('pandaCoreRuntimeFields') && item.detail?.includes('core runtime API field coverage')), 'Panda JSON report resources dry-run evidence must mention pandaCoreRuntimeFields core runtime API coverage')
assert(alignmentReportJson.backendAlignmentBlockers?.status === 'passed', 'Panda JSON report must classify backend alignment blockers as passed')
assert(alignmentReportJson.backendAlignmentBlockers?.pendingRoutes?.length === 0, 'Panda JSON report must not list mock-ready routes after backend alignment')
assert(alignmentReportJson.nextFrontendTasks?.some((task) => task.id === 'visual-review'), 'Panda JSON report must expose next frontend tasks')
assert(alignmentReportJson.nextFrontendTasks?.some((task) => task.id === 'scripted-qa-smoke'), 'Panda JSON report must expose scripted QA as a frontend task')
assert(alignmentReportJson.alignmentContextSource === 'frontend/scripts/panda-alignment-context.mjs', 'Panda JSON report must expose the shared alignment context source')
assert(alignmentReportJson.closeoutEvidenceSource === 'frontend/scripts/panda-closeout-evidence.mjs', 'Panda JSON report must expose the shared closeout evidence source')
assert(alignmentReportJson.routeRolloverSource === 'frontend/scripts/panda-route-rollover-plan.mjs', 'Panda JSON report must expose the shared route rollover source')
assertPandaBackendAlignmentHandoff(alignmentReportJson.backendAlignmentHandoff, 'Panda JSON report backend alignment handoff')
assert(alignmentReportJson.backendAlignmentPending?.some((item) => item.includes('approval, sandbox, auth, secret')), 'Panda JSON report must include backend high-risk policy boundary')
assert(alignmentReportJson.strict?.enabled === false, 'Panda JSON report must default to closeout mode')
for (const field of pandaBaseRuntimeFields) {
  assert(
    alignmentReportJson.routes.every((route) => route.runtimeFields?.includes(field)),
    `Panda JSON report must expose runtime field for every route: ${field}`,
  )
}
for (const routeId of pandaProgressRuntimeRouteIds) {
  const route = alignmentReportJson.routes.find((item) => item.route === routeId)
  for (const field of pandaProgressRuntimeFields) {
    assert(route?.runtimeFields?.includes(field), `Panda JSON report missing ${field} for route: ${routeId}`)
  }
}
for (const routeId of pandaEvidenceRuntimeRouteIds) {
  const route = alignmentReportJson.routes.find((item) => item.route === routeId)
  assert(route?.runtimeFields?.includes('evidence_refs'), `Panda JSON report missing evidence_refs for route: ${routeId}`)
}

const strictOutput = runNodeJson('scripts/panda-alignment-report.mjs', ['--json', '--strict'])
assert(strictOutput.strict?.enabled === true, 'Panda strict JSON report must expose strict mode')
assert(strictOutput.strict?.passed === true, 'Panda strict JSON report must pass after resources BFF and page APIs are wired')
assert(strictOutput.strict?.failures?.length === 0, 'Panda strict JSON report must not include readiness failures after backend alignment')
assert(strictOutput.frontendCompletion?.status === 'passed', 'Panda strict JSON report must keep frontend completion evidence passed')
assert(strictOutput.adapterEvidence?.status === 'passed', 'Panda strict JSON report must keep adapter behavior evidence passed')
assert(strictOutput.resourcesValidationEvidence?.status === 'passed', 'Panda strict JSON report must keep resources validation evidence passed')
assert(strictOutput.resourcesContractEvidence?.status === 'passed', 'Panda strict JSON report must keep resources contract evidence passed')
assert(strictOutput.resourceReadiness?.source === 'src/panda/api/resourceReadiness.ts', 'Panda strict JSON report must expose resource readiness evidence')
assert(strictOutput.backendAlignmentBlockers?.status === 'passed', 'Panda strict JSON report must keep backend blockers passed after alignment')

const scriptedQa = read('scripts/panda-qa-smoke.mjs')
for (const symbol of pandaScriptedQaRequiredSymbols) {
  assert(scriptedQa.includes(symbol), `Panda scripted QA missing expected probe or config: ${symbol}`)
}
const scriptedQaJson = runNodeJson('scripts/panda-qa-smoke.mjs', ['--json'])
assert(scriptedQaJson.productName === 'Panda Agent', 'Panda scripted QA JSON must expose productName')
assert(scriptedQaJson.staticStatus === 'passed', 'Panda scripted QA static probes must pass')
assert(scriptedQaJson.staticProbes?.length === expectedStaticProbeCount, 'Panda scripted QA must expose all static probes')
assert(scriptedQaJson.staticProbes?.some((probe) => probe.id === 'skip-link' && probe.passed), 'Panda scripted QA must pass skip-link probe')
assert(scriptedQaJson.staticProbes?.some((probe) => probe.id === 'progress-semantics' && probe.passed), 'Panda scripted QA must pass progress semantics probe')
assert(scriptedQaJson.staticProbes?.some((probe) => probe.id === 'resources-bff-validation' && probe.passed), 'Panda scripted QA must pass resources BFF validation probe')
assert(scriptedQaJson.staticProbes?.some((probe) => probe.id === 'resources-validation-executable' && probe.passed), 'Panda scripted QA must pass executable resources validation probe')
assert(scriptedQaJson.staticProbes?.some((probe) => probe.id === 'resources-contract-consistency' && probe.passed), 'Panda scripted QA must pass resource contract consistency probe')
assert(scriptedQaJson.staticProbes?.some((probe) => probe.id === 'resources-contract-consistency' && probe.detail?.includes('manifest')), 'Panda scripted QA must describe manifest resource contract coverage')
assert(scriptedQaJson.staticProbes?.some((probe) => probe.id === 'resources-contract-consistency' && probe.detail?.includes('shared resource key pairs')), 'Panda scripted QA must describe shared resource key pair coverage')
assert(scriptedQaJson.staticProbes?.some((probe) => probe.id === 'resources-contract-consistency' && probe.detail?.includes('mock-ready contract fields')), 'Panda scripted QA must describe mock-ready contract field coverage')
assert(scriptedQaJson.staticProbes?.some((probe) => probe.id === 'resources-contract-consistency' && probe.detail?.includes('PageResources type bindings')), 'Panda scripted QA must describe standard module hook/type resource binding coverage')
assert(scriptedQaJson.staticProbes?.some((probe) => probe.id === 'route-api-resources-evidence' && probe.passed), 'Panda scripted QA must pass route API resources evidence probe')
assert(scriptedQaJson.staticProbes?.some((probe) => probe.id === 'route-api-resources-evidence' && probe.detail?.includes('unknown') && probe.detail?.includes('missing')), 'Panda scripted QA route API resources evidence probe must describe unknown and missing key diffs')
assert(scriptedQaJson.staticProbes?.some((probe) => probe.id === 'adapter-behavior-executable' && probe.passed), 'Panda scripted QA must pass adapter behavior probe')
assert(scriptedQaJson.staticProbes?.some((probe) => probe.id === 'adapter-behavior-executable' && probe.detail?.includes('evidence refs and agent permissions copy semantics')), 'Panda scripted QA adapter probe must mention evidence refs and agent permissions copy semantics')
assert(scriptedQaJson.staticProbes?.some((probe) => probe.id === 'adapter-behavior-executable' && probe.detail?.includes('agent role preset mapping')), 'Panda scripted QA adapter probe must mention agent role preset mapping')
assert(scriptedQaJson.staticProbes?.some((probe) => probe.id === 'agent-role-card-contract' && probe.passed), 'Panda scripted QA must pass the agent role card contract probe')
assert(scriptedQaJson.staticProbes?.some((probe) => probe.id === 'agent-role-card-contract' && probe.detail?.includes('ApiAgentRolePreset') && probe.detail?.includes('portrait key registry')), 'Panda scripted QA role card probe must mention the DTO and portrait registry')
assert(scriptedQaJson.staticProbes?.some((probe) => probe.id === 'resource-dry-run-fixture' && probe.passed), 'Panda scripted QA must pass resources dry-run fixture probe')
assert(scriptedQaJson.staticProbes?.some((probe) => probe.id === 'resource-dry-run-fixture' && probe.detail?.includes('pandaCoreRuntimeFields') && probe.detail?.includes('core runtime API field coverage')), 'Panda scripted QA dry-run probe detail must mention pandaCoreRuntimeFields core runtime API coverage')
assert(['passed', 'passed-with-dev-server-skipped'].includes(scriptedQaJson.status), 'Panda scripted QA must pass with or without a running dev server')

const adapterJson = runNodeJson('scripts/verify-panda-adapters.mjs', ['--json'])
assert(adapterJson.productName === 'Panda Agent', 'Panda adapters JSON must expose productName')
assert(adapterJson.status === 'passed', 'Panda adapters JSON must pass')
for (const checkName of pandaAdapterCheckNames) {
  assert(adapterJson.checks?.some((check) => check.name === checkName && check.status === 'passed'), `Panda adapter verification must pass ${checkName}`)
}

const resourceContractJson = runNodeJson('scripts/verify-panda-resource-contracts.mjs', ['--json'])
assert(resourceContractJson.productName === 'Panda Agent', 'Panda resource contracts JSON must expose productName')
assert(resourceContractJson.status === 'passed', 'Panda resource contracts JSON must pass')
assert(resourceContractJson.diffs && typeof resourceContractJson.diffs === 'object', 'Panda resource contracts JSON must expose comparison diffs')
for (const sourceName of pandaResourceContractSourceNames) {
  assert(resourceContractJson.sources?.[sourceName], `Panda resource contracts JSON must expose source: ${sourceName}`)
}
for (const checkName of pandaResourceContractCheckNames) {
  assert(resourceContractJson.checks?.some((check) => check.name === checkName && check.status === 'passed'), `Panda resource contracts must pass ${checkName}`)
  assert(Array.isArray(resourceContractJson.diffs?.[checkName]?.missingFromLeft), `Panda resource contracts must expose missingFromLeft for ${checkName}`)
  assert(Array.isArray(resourceContractJson.diffs?.[checkName]?.missingFromRight), `Panda resource contracts must expose missingFromRight for ${checkName}`)
}
assert(resourceContractJson.keys?.readinessRoutes?.includes('threads'), 'Panda resource contract probe must expose readiness route keys')
assert(resourceContractJson.keys?.readinessResourceKeys?.includes('tools'), 'Panda resource contract probe must expose readiness resource keys')
assert(resourceContractJson.keys?.readinessApiResourceKeys?.includes('workflow_nodes'), 'Panda resource contract probe must expose readiness API resource keys')
assert(resourceContractJson.keys?.readinessEndpoints?.includes('/api/v1/workbench/tools'), 'Panda resource contract probe must expose readiness endpoints')
assert(Array.isArray(resourceContractJson.keys?.readinessPendingRoutes), 'Panda resource contract probe must expose readiness pending routes')
assert(resourceContractJson.keys.readinessPendingRoutes.length === 0, 'Panda resource contract probe must show no readiness pending routes after backend alignment')
assert(Array.isArray(resourceContractJson.keys?.incompleteMockReadyContractRoutes), 'Panda resource contract probe must expose incomplete mock-ready contract routes')
assert(resourceContractJson.keys.incompleteMockReadyContractRoutes.length === 0, 'Panda mock-ready page contracts must have complete endpoint, resource, runtime, and API-need fields')
assert(
  Array.isArray(resourceContractJson.keys?.closeoutPendingRouteSignatures),
  'Panda resource contract probe must expose closeout pending route signatures',
)
assert(
  sameMembers(
    resourceContractJson.keys?.closeoutPendingRouteSignatures ?? [],
    resourceContractJson.keys?.routeRolloverPendingRouteSignatures ?? [],
  ),
  'Panda resource contract probe must prove closeout pending routes match the route rollover plan',
)
assert(resourceContractJson.keys?.moduleContentPageFields?.includes('tasks:tasks'), 'Panda resource contract probe must expose module content page field pairs')
assert(
  sameMembers(resourceContractJson.keys?.moduleContentPageFields ?? [], resourceContractJson.keys?.expectedModuleContentPageFields ?? []),
  'Panda resource contract probe must expose module content page field pairs and expected pairs without drift',
)
assert(resourceContractJson.keys?.modulePageResourceHookBindings?.includes('tasks:useTasksPageResources:TasksPageResources'), 'Panda resource contract probe must expose module page hook/type bindings')
assert(resourceContractJson.keys?.modulePageResourceTypeBindings?.includes('tasks:TasksPageResources'), 'Panda resource contract probe must expose module page resource type bindings')
assert(
  sameMembers(resourceContractJson.keys?.modulePageResourceHookBindings ?? [], resourceContractJson.keys?.expectedModulePageResourceHookBindings ?? []),
  'Panda resource contract probe must expose module page hook/type bindings without drift',
)
assert(
  sameMembers(resourceContractJson.keys?.modulePageResourceTypeBindings ?? [], resourceContractJson.keys?.expectedModulePageResourceTypeBindings ?? []),
  'Panda resource contract probe must expose module page resource type bindings without drift',
)
assert(
  manifest.nextFrontendTasks?.some(
    (task) =>
      task.id === 'resources-contract-consistency' &&
      task.description.includes('route readiness') &&
      task.description.includes('mock-ready contract field completeness'),
  ),
  'Panda manifest resource contract task must mention route readiness and mock-ready contract field completeness',
)

const resourceDryRunJson = runNodeJson('scripts/verify-panda-resource-dry-run.mjs', ['--json'])
assert(resourceDryRunJson.productName === 'Panda Agent', 'Panda resources dry-run JSON must expose productName')
assert(resourceDryRunJson.status === 'passed', 'Panda resources dry-run JSON must pass')
for (const checkName of pandaResourceDryRunCheckNames) {
  assert(resourceDryRunJson.checks?.some((check) => check.name === checkName && check.status === 'passed'), `Panda resources dry-run must pass ${checkName}`)
}
assert(manifest.nextFrontendTasks?.some((task) => task.id === 'resources-dry-run-fixture' && task.status === 'passed'), 'Panda manifest must record passing resources dry-run fixture task')
assert(manifest.nextFrontendTasks?.some((task) => task.id === 'resources-dry-run-fixture' && task.description?.includes('pandaCoreRuntimeFields') && task.description?.includes('core runtime API field coverage')), 'Panda manifest resources dry-run task must mention pandaCoreRuntimeFields core runtime API coverage')

const resourceValidationJson = runNodeJson('scripts/verify-panda-resource-validation.mjs', ['--json'])
assert(resourceValidationJson.productName === 'Panda Agent', 'Panda resources validation JSON must expose productName')
assert(resourceValidationJson.status === 'passed', 'Panda resources validation JSON must pass')
assert(resourceValidationJson.validation === 'src/panda/api/resourcesValidation.ts', 'Panda resources validation JSON must expose the validation source')
for (const checkName of pandaResourceValidationCheckNames) {
  assert(resourceValidationJson.checks?.some((check) => check.name === checkName && check.status === 'passed'), `Panda resources validation must pass ${checkName}`)
}

const app = read('src/panda/PandaAgentApp.tsx')
const hashRouteHook = read('src/panda/state/usePandaHashRoute.ts')
const homeWorkbenchHook = read('src/panda/state/usePandaHomeWorkbench.ts')
const homeWorkbenchViewModel = read('src/panda/state/homeWorkbenchViewModel.ts')
assert(app.includes('usePandaHomeWorkbench'), 'PandaAgentApp must load home data through the focused home workbench hook')
assert(app.includes('usePandaHashRoute'), 'PandaAgentApp must manage navigation through the focused hash route hook')
assert(app.includes('./api/bootstrapResources'), 'PandaAgentApp must bootstrap resource BFF settings explicitly')
assert(app.includes('./data/navigation'), 'PandaAgentApp must import navigation constants without loading mock workspace data')
assert(!app.includes("@/services/api"), 'PandaAgentApp must not import the global API client directly')
assert(app.includes('homeSource'), 'PandaAgentApp must track the home data source for degraded-state rendering')
assert(app.includes('PandaWorkspaceProvider'), 'PandaAgentApp must wrap pages with PandaWorkspaceProvider')
assert(app.includes('getPandaPageComponent'), 'PandaAgentApp must render non-home pages through the page registry')
assert(app.includes('PandaShellFrame'), 'PandaAgentApp must delegate shell layout to PandaShellFrame')
assert(!app.includes('loadPandaWorkbenchHome'), 'PandaAgentApp must not own the home BFF loading effect directly')
assert(!app.includes("addEventListener('hashchange'"), 'PandaAgentApp must not own hash route event listeners directly')
assert(!app.includes('window.history.replaceState'), 'PandaAgentApp must not own hash history updates directly')
assert(!app.includes('<Sidebar'), 'PandaAgentApp must not render Sidebar directly')
assert(!app.includes('<TopBar'), 'PandaAgentApp must not render TopBar directly')
assert(!app.includes('className="panda-shell"'), 'PandaAgentApp must not own the shell grid markup')
assert(hashRouteHook.includes('export function usePandaHashRoute()'), 'usePandaHashRoute must expose the focused route hook')
assert(hashRouteHook.includes('getInitialPandaPage'), 'usePandaHashRoute must own initial hash route resolution')
assert(hashRouteHook.includes('isPandaPage(page) ? page :'), 'usePandaHashRoute must validate hash routes through the page registry')
assert(hashRouteHook.includes("addEventListener('hashchange'"), 'usePandaHashRoute must subscribe to hash route changes')
assert(hashRouteHook.includes("removeEventListener('hashchange'"), 'usePandaHashRoute must clean up hash route listeners')
assert(hashRouteHook.includes('window.history.replaceState'), 'usePandaHashRoute must own URL hash updates')
assert(homeWorkbenchHook.includes('export function usePandaHomeWorkbench()'), 'usePandaHomeWorkbench must expose the focused home hook')
assert(homeWorkbenchHook.includes('loadPandaWorkbenchHome'), 'usePandaHomeWorkbench must load through the Panda workbench client')
assert(homeWorkbenchHook.includes('PandaWorkbenchDataSource'), 'usePandaHomeWorkbench must track home data source type')
assert(homeWorkbenchHook.includes('let cancelled = false'), 'usePandaHomeWorkbench must guard async state updates after unmount')
assert(homeWorkbenchHook.includes('buildPandaHomeWorkbenchViewModel(result)'), 'usePandaHomeWorkbench must delegate fallback state mapping to its view model')
assert(!homeWorkbenchHook.includes('本地演示数据已接管'), 'usePandaHomeWorkbench must not inline mock fallback messaging')
assert(homeWorkbenchViewModel.includes('export function buildPandaHomeWorkbenchViewModel'), 'homeWorkbenchViewModel must own the home workbench state mapper')
assert(homeWorkbenchViewModel.includes('PandaWorkbenchHomeResult'), 'homeWorkbenchViewModel must type its input with the home workbench client result')
assert(homeWorkbenchViewModel.includes('本地演示数据已接管'), 'homeWorkbenchViewModel must preserve mock fallback messaging')

const shell = read('src/panda/components/Shell.tsx')
const shellChrome = read('src/panda/components/shellChrome.tsx')
const shellBranding = read('src/panda/components/shellBranding.tsx')
const shellControls = read('src/panda/components/shellControls.tsx')
const shellActionControls = read('src/panda/components/shellActionControls.tsx')
const shellTopbar = read('src/panda/components/shellTopbar.tsx')
const shellConnectionViewModel = read('src/panda/components/shellConnectionViewModel.ts')
for (const symbol of pandaShellRequiredSymbols) {
  assert(shell.includes(symbol) || shellChrome.includes(symbol), `Panda shell missing symbol: ${symbol}`)
}
assert(shell.includes('buildShellConnectionViewModel'), 'Panda shell must delegate workbench connection labels to shellConnectionViewModel')
assert(shellConnectionViewModel.includes('export function buildShellConnectionViewModel'), 'shellConnectionViewModel must own the workbench connection label builder')
for (const connectionLabel of ['同步工作台数据中', '本地演示数据已接管', '已连接 X-Agent Core']) {
  assert(shellConnectionViewModel.includes(connectionLabel), `shellConnectionViewModel must preserve connection label: ${connectionLabel}`)
}
assert(!shell.includes('../data/navigation'), 'Panda shell layout must not import navigation chrome constants directly')
assert(shellChrome.includes('../data/navigation'), 'Panda shell chrome must import nav constants without loading mock workspace data')
assert(shellBranding.includes('../data/navigation'), 'Panda shell branding must import logo constants without loading mock workspace data')
assert(shell.includes('const { connectionLabel } = buildShellConnectionViewModel({ isLoading, error })'), 'PandaShellFrame must compute the connection label once through its view model')
assert(shellChrome.includes('export type ShellNavigationProps'), 'Panda shell navigation props must be typed once in shellChrome')
assert(shell.includes("from './shellChrome'"), 'Panda shell layout must compose focused shell chrome components')
assert(shell.includes("export type { ShellNavigationProps } from './shellChrome'"), 'Panda shell layout must preserve shell navigation type export compatibility')
assert(shellChrome.includes("from './shellBranding'"), 'Panda shell chrome must preserve compatibility exports from shellBranding')
assert(shellBranding.includes("from './shellControls'"), 'Panda shell branding must preserve compatibility exports from shellControls')
assert(shellChrome.includes("from './shellTopbar'"), 'Panda shell chrome must preserve compatibility exports from shellTopbar')
for (const layoutClass of pandaShellLayoutClasses) {
  assert(shell.includes(layoutClass), `PandaShellFrame must own layout class: ${layoutClass}`)
}
assert(shellChrome.includes('<BrandLockup />'), 'Sidebar must delegate product branding to BrandLockup')
assert(shellChrome.includes('<ShellNavigation activePage={activePage} onSelectPage={onSelectPage} />'), 'Sidebar must delegate module navigation to ShellNavigation')
assert(shellChrome.includes('<WorkspaceSwitcher />'), 'Sidebar must delegate workspace controls to WorkspaceSwitcher')
assert(shellBranding.includes('export function BrandLockup'), 'shellBranding must own BrandLockup')
assert(shellControls.includes('export function WorkspaceSwitcher'), 'shellControls must own WorkspaceSwitcher')
assert(shellControls.includes("from './shellActionControls'"), 'shellControls must preserve compatibility exports from shellActionControls')
assert(!shellControls.includes('export function TopBarActions'), 'shellControls must keep TopBarActions implementation in shellActionControls')
assert(shellActionControls.includes('export function TopBarActions'), 'shellActionControls must own TopBarActions')
for (const symbol of ['WorkspaceSwitcher', 'TopBarActions']) {
  assert(shellBranding.includes(symbol), `shellBranding must preserve shell control compatibility export: ${symbol}`)
}
assert(shell.includes('<MobileStatusRow pageLabel={pageLabel} connectionLabel={connectionLabel} />'), 'PandaShellFrame must render mobile status through MobileStatusRow')
assert(shellTopbar.includes('<TopBarStatus pageLabel={pageLabel} connectionLabel={connectionLabel} />'), 'TopBar must delegate status text to TopBarStatus')
assert(shellTopbar.includes('<TopBarActions />'), 'TopBar must delegate command and user controls to TopBarActions')
assert(shell.includes('id="panda-main-content"'), 'PandaShellFrame must expose a stable main content landmark target')
assert(shell.includes('className="panda-skip-link" href="#panda-main-content"'), 'PandaShellFrame must expose a skip link to the main workspace')
assert(!shell.includes('../data/mockWorkspace'), 'Panda shell must not depend on mock workspace data for navigation chrome')
assert(!shellChrome.includes('../data/mockWorkspace'), 'Panda shell chrome must not depend on mock workspace data for navigation chrome')
assert(!shellBranding.includes('../data/mockWorkspace'), 'Panda shell branding must not depend on mock workspace data for navigation chrome')
assert(!shellControls.includes('../data/mockWorkspace'), 'Panda shell controls must not depend on mock workspace data for navigation chrome')
assert(!shellActionControls.includes('../data/mockWorkspace'), 'Panda shell action controls must not depend on mock workspace data for navigation chrome')
assert(!shellTopbar.includes('../data/mockWorkspace'), 'Panda shell topbar must not depend on mock workspace data for navigation chrome')
assert(shell.includes('跳到主工作区'), 'Panda skip link must use a Chinese label')
assert(shell.includes('aria-label={`${pageLabel} 工作区`}'), 'Panda main content must expose the active workspace label')
assert(shellChrome.includes("aria-current={activePage === item.id ? 'page' : undefined}"), 'Panda nav must expose the active page with aria-current')
assert(shellChrome.includes('aria-label={`打开${item.label}模块`}'), 'Panda nav buttons must have explicit module labels')
assert(shellTopbar.includes('className="panda-topbar-status text-sm text-slate-400"'), 'Panda topbar status must use a dedicated no-wrap class')
assert(shellTopbar.includes('className="panda-mobile-status"'), 'PandaShellFrame must render a mobile status row')
assert(shellTopbar.includes('aria-live="polite"'), 'Panda mobile status row must announce connection changes politely')
assert(shell.includes('connectionLabel'), 'Panda TopBar must receive the shared connection label')
assert(shell.includes('rightRail: ReactNode'), 'PandaShellFrame must accept right rail content as a slot')
assert(shell.includes('children: ReactNode'), 'PandaShellFrame must accept page content as children')
assert(shellBranding.includes('Panda Agent logo'), 'Panda Sidebar must render the Panda Agent logo')
assert(shellBranding.includes('熊猫派达智能体应用管理平台'), 'Panda Sidebar must keep the Chinese product subtitle under the enlarged brand')
assert(shellConnectionViewModel.includes('已连接 X-Agent Core'), 'Panda TopBar must preserve the X-Agent Core connection label')
assert(shellActionControls.includes('role="group" aria-label="当前用户 Panda Agent，超级管理员"'), 'Panda user chip must expose the current user context')

const pageRegistry = read('src/panda/pageRegistry.tsx')
for (const symbol of pandaPageRegistryRequiredSymbols) {
  assert(pageRegistry.includes(symbol), `Missing Panda page registry symbol: ${symbol}`)
}
assert(pageRegistry.includes('navItems.map'), 'Panda page registry must derive valid page ids from navItems')
assert(pageRegistry.includes('./data/navigation'), 'Panda page registry must derive page ids from navigation constants')
assert(!pageRegistry.includes('./data/mockWorkspace'), 'Panda page registry must not load mock workspace data')
for (const pageId of pageIds.filter((id) => id !== 'home')) {
  assert(pageRegistry.includes(`${pageId}:`), `Missing registered page component for: ${pageId}`)
}
assert(!pageRegistry.includes('HomePage'), 'HomePage must stay explicitly composed by PandaAgentApp')

const client = read('src/panda/api/workbenchClient.ts')
const workbenchHomeLoadResult = read('src/panda/api/workbenchHomeLoadResult.ts')
assert(client.includes('apiClient.getWorkbenchHome'), 'workbenchClient must own current home API call')
assert(client.includes('buildPandaWorkbenchHomeApiResult(mapWorkbenchHome(response))'), 'workbenchClient must delegate home API success result construction')
assert(client.includes('buildPandaWorkbenchHomeMockResult(error)'), 'workbenchClient must delegate home mock fallback result construction')
assert(client.includes("from './workbenchHomeLoadResult'"), 'workbenchClient must import focused home load result builders')
assert(!client.includes("from '../data/mockHome'"), 'workbenchClient must not own the home fallback fixture import')
assert(!client.includes("new Error('无法加载工作台数据')"), 'workbenchClient must not inline home load fallback error copy')
assert(!client.includes("from '../data/mockWorkspace'"), 'workbenchClient must not depend on the compatibility mockWorkspace barrel')
assert(workbenchHomeLoadResult.includes('mockWorkbenchHome'), 'workbenchHomeLoadResult must provide mock fallback')
assert(workbenchHomeLoadResult.includes("source: 'api'"), 'workbenchHomeLoadResult must mark API home source')
assert(workbenchHomeLoadResult.includes("source: 'mock'"), 'workbenchHomeLoadResult must mark mock fallback source')
assert(workbenchHomeLoadResult.includes("from '../data/mockHome'"), 'workbenchHomeLoadResult must read the home fallback from mockHome')
assert(workbenchHomeLoadResult.includes('export function buildPandaWorkbenchHomeApiResult'), 'workbenchHomeLoadResult must export the API success result builder')
assert(workbenchHomeLoadResult.includes('export function buildPandaWorkbenchHomeMockResult'), 'workbenchHomeLoadResult must export the mock fallback result builder')
assert(workbenchHomeLoadResult.includes('export function normalizePandaWorkbenchHomeError'), 'workbenchHomeLoadResult must export home load error normalization')
assert(workbenchHomeLoadResult.includes("new Error('无法加载工作台数据')"), 'workbenchHomeLoadResult must own home load fallback error copy')
assert(!workbenchHomeLoadResult.includes("from '../data/mockWorkspace'"), 'workbenchHomeLoadResult must not depend on the compatibility mockWorkspace barrel')

const resourceSnapshotTypes = read('src/panda/api/resourceSnapshotTypes.ts')
const resourceFallbackSnapshot = read('src/panda/api/resourceFallbackSnapshot.ts')
const resourcesApiLoader = read('src/panda/api/resourcesApiLoader.ts')
const resourcesClient = read('src/panda/api/resourcesClient.ts')
const resourcesLoadResult = read('src/panda/api/resourcesLoadResult.ts')
assert(resourceSnapshotTypes.includes('PandaResourceSnapshot'), 'resourceSnapshotTypes must own the page resource snapshot type')
assert(resourceSnapshotTypes.includes('PandaResourceLoadResult'), 'resourceSnapshotTypes must own the resource load result type')
assert(resourceSnapshotTypes.includes('PandaResourceSource'), 'resourceSnapshotTypes must own the resource source type')
assert(resourceSnapshotTypes.includes('readonly resources: Readonly<PandaResourceSnapshot>'), 'Panda resource load result resources must be readonly')
assert(resourceSnapshotTypes.includes('readonly source: PandaResourceSource'), 'Panda resource load result source must be readonly')
assert(resourceSnapshotTypes.includes('readonly error?: Error'), 'Panda resource load result error must be readonly')
assert(resourceFallbackSnapshot.includes('getPandaResourceSnapshot'), 'resourceFallbackSnapshot must expose a page resource snapshot loader')
assert(resourceFallbackSnapshot.includes('pandaResources'), 'resourceFallbackSnapshot must expose current static page resources')
assert(resourcesClient.includes('PandaResourceSnapshot'), 'resourcesClient must re-export the page resource snapshot type for compatibility')
assert(resourcesClient.includes('PandaResourceLoadResult'), 'resourcesClient must re-export the resource load result type for compatibility')
assert(resourcesClient.includes('getPandaResourceSnapshot'), 'resourcesClient must re-export the page resource snapshot loader for compatibility')
assert(resourcesClient.includes('loadPandaResources'), 'resourcesClient must expose async resource loading')
assert(resourcesClient.includes('pandaResources'), 'resourcesClient must re-export current static page resources for compatibility')
assert(resourcesClient.includes('setPandaResourcesApiLoader'), 'resourcesClient must re-export a future API loader injection point')
assert(resourcesClient.includes('createPandaResourcesApiLoader'), 'resourcesClient must re-export a BFF loader factory')
assert(resourcesClient.includes('PandaResourcesHttpClient'), 'resourcesClient must re-export the narrow Panda resources HTTP client contract')
assert(resourcesClient.includes("from './resourcesLoadResult'"), 'resourcesClient must delegate load result construction to resourcesLoadResult')
assert(resourcesClient.includes('buildPandaApiResourceLoadResult(apiResources)'), 'resourcesClient must use resourcesLoadResult for API load success results')
assert(resourcesClient.includes('buildPandaMockResourceLoadResult()'), 'resourcesClient must use resourcesLoadResult for disabled API mock fallback')
assert(resourcesClient.includes('buildPandaMockResourceErrorResult(error)'), 'resourcesClient must use resourcesLoadResult for degraded API fallback')
assert(!resourcesClient.includes("new Error('无法加载 Panda 工作台资源')"), 'resourcesClient must not inline resource load fallback error copy')
assert(resourcesApiLoader.includes('mapPandaResourceSnapshot'), 'resourcesApiLoader must map API resources through adapters')
assert(resourcesApiLoader.includes('validatePandaResourceSnapshot'), 'resourcesApiLoader must validate BFF resource snapshots before mapping')
assert(resourcesApiLoader.includes("from './resourcesValidation'"), 'resourcesApiLoader must import resource validation from the Panda API boundary')
assert(resourcesApiLoader.includes('PandaResourcesHttpClient'), 'resourcesApiLoader must define a narrow Panda resources HTTP client contract')
assert(resourcesApiLoader.includes('setPandaResourcesApiLoader'), 'resourcesApiLoader must expose a future API loader injection point')
assert(resourcesApiLoader.includes('createPandaResourcesApiLoader'), 'resourcesApiLoader must expose a BFF loader factory')
assert(resourcesLoadResult.includes("from './resourceFallbackSnapshot'"), 'resourcesLoadResult must use the focused fallback snapshot boundary')
assert(resourcesLoadResult.includes("from './resourceSnapshotTypes'"), 'resourcesLoadResult must type load results from resourceSnapshotTypes')
assert(resourcesLoadResult.includes('export function buildPandaApiResourceLoadResult'), 'resourcesLoadResult must export the API success result builder')
assert(resourcesLoadResult.includes('export function buildPandaMockResourceLoadResult'), 'resourcesLoadResult must export the mock fallback result builder')
assert(resourcesLoadResult.includes('export function buildPandaMockResourceErrorResult'), 'resourcesLoadResult must export the degraded mock-with-error result builder')
assert(resourcesLoadResult.includes('export function normalizePandaResourceLoadError'), 'resourcesLoadResult must export resource load error normalization')
assert(resourcesLoadResult.includes("source: 'api'"), 'resourcesLoadResult must mark API resource source')
assert(resourcesLoadResult.includes("source: 'mock'"), 'resourcesLoadResult must keep mock fallback source')
assert(resourcesLoadResult.includes("new Error('无法加载 Panda 工作台资源')"), 'resourcesLoadResult must own resource load fallback error copy')

const resourcesValidation = read('src/panda/api/resourcesValidation.ts')
for (const symbol of pandaResourceValidationRequiredSymbols) {
  assert(resourcesValidation.includes(symbol), `Missing Panda resources validation symbol: ${symbol}`)
}
assert(resourcesValidation.includes("from './resourceKeys'"), 'Panda resource validation must import shared resource keys')
assert(resourcesValidation.includes('!isRecord(snapshot)'), 'Panda resources validation must reject non-object snapshots')
assert(resourcesValidation.includes('!Array.isArray(value)'), 'Panda resources validation must reject non-array resource fields')
assert(resourcesValidation.includes('findIndex((item) => !isRecord(item))'), 'Panda resources validation must reject non-object resource items')
assert(resourcesValidation.includes('must be an object'), 'Panda resources validation must explain invalid resource item shape')
assert(resourcesValidation.includes('pandaApiResourceKeySet'), 'Panda resources validation must maintain a known resource key set')
assert(resourcesValidation.includes('is not a known resource slice'), 'Panda resources validation must reject unknown resource fields')
assert(!resourcesValidation.includes('axios'), 'Panda resources validation must stay pure and not import axios')
assert(!resourcesValidation.includes('react'), 'Panda resources validation must stay pure and not import React')

const resourceKeys = read('src/panda/api/resourceKeys.ts')
for (const symbol of pandaResourceKeyBoundarySymbols) {
  assert(resourceKeys.includes(symbol), `Missing Panda resource key boundary symbol: ${symbol}`)
}
for (const [viewKey, apiKey] of pandaResourceKeyPairExpectations) {
  assert(resourceKeys.includes(`['${viewKey}', '${apiKey}']`), `Panda resource key mapping missing: ${viewKey} -> ${apiKey}`)
}
assert(!resourceKeys.includes('axios'), 'Panda resource key boundary must stay pure and not import axios')
assert(!resourceKeys.includes('react'), 'Panda resource key boundary must stay pure and not import React')

const resourcesHttpClient = read('src/panda/api/resourcesHttpClient.ts')
for (const symbol of pandaResourcesHttpClientRequiredSymbols) {
  assert(resourcesHttpClient.includes(symbol), `Missing Panda resources HTTP client symbol: ${symbol}`)
}
assert(resourcesHttpClient.includes('/api/v1/workbench/resources'), 'Panda resources fetch client must target the aggregate BFF endpoint')
assert(resourcesHttpClient.includes('const normalizedEndpoint = endpoint?.trim()'), 'Panda resources endpoint resolver must trim env endpoint values')
assert(resourcesHttpClient.includes('return normalizedEndpoint || PANDA_RESOURCES_BFF_ENDPOINT'), 'Panda resources endpoint resolver must fall back to the default endpoint')
assert(resourcesHttpClient.includes('const resolvedEndpoint = resolvePandaResourcesEndpoint(endpoint)'), 'Panda resources fetch client must resolve the endpoint once')
assert(resourcesHttpClient.includes('fetch(resolvedEndpoint'), 'Panda resources fetch client must use the resolved endpoint')
assert(resourcesHttpClient.includes('response.status} ${resolvedEndpoint}'), 'Panda resources fetch errors must include status and endpoint')
assert(resourcesHttpClient.includes('headers.Authorization'), 'Panda resources fetch client must pass the auth token when available')
assert(resourcesHttpClient.includes('PandaResourcesHttpClient'), 'Panda resources fetch client must satisfy the narrow HTTP client contract')
assert(resourcesHttpClient.includes("from './resourcesApiLoader'"), 'Panda resources fetch client must import the HTTP client contract from resourcesApiLoader')
assert(!resourcesHttpClient.includes("from './resourcesClient'"), 'Panda resources fetch client must not depend on the compatibility resourcesClient entrypoint')

const resourcesBffConfig = read('src/panda/api/resourcesBffConfig.ts')
for (const symbol of pandaResourcesBffConfigRequiredSymbols) {
  assert(resourcesBffConfig.includes(symbol), `Missing Panda resources BFF config symbol: ${symbol}`)
}
assert(resourcesBffConfig.includes("PANDA_RESOURCES_BFF_FLAG = 'true'"), 'Panda resources BFF flag constant must stay in the pure config module')
assert(resourcesBffConfig.includes('VITE_PANDA_RESOURCES_BFF'), 'Panda resources BFF config must read the opt-in env flag')
assert(resourcesBffConfig.includes('PandaResourcesBffEnv | undefined'), 'Panda resources BFF config must accept optional env for probe-safe default imports')
assert(resourcesBffConfig.includes('env?.VITE_PANDA_RESOURCES_BFF'), 'Panda resources BFF config must safely read optional env flags')
assert(resourcesBffConfig.includes('enabled: shouldUsePandaResourcesBff(env)'), 'Panda resources config must expose whether the resources BFF is enabled')
assert(resourcesBffConfig.includes('endpoint: resolvePandaResourcesEndpoint(env?.VITE_PANDA_RESOURCES_BFF_ENDPOINT)'), 'Panda resources config must safely normalize the configured endpoint')
assert(!resourcesBffConfig.includes('setPandaResourcesApiLoader'), 'Panda resources BFF config module must not mutate loader state')
assert(!resourcesBffConfig.includes('bootstrapPandaResources()'), 'Panda resources BFF config module must not run bootstrap side effects')

const bootstrapResources = read('src/panda/api/bootstrapResources.ts')
for (const symbol of pandaBootstrapResourcesRequiredSymbols) {
  assert(bootstrapResources.includes(symbol), `Missing Panda resources bootstrap symbol: ${symbol}`)
}
assert(bootstrapResources.includes("from './resourcesBffConfig'"), 'Panda resources bootstrap must read shared pure BFF config')
assert(bootstrapResources.includes("from './resourcesApiLoader'"), 'Panda resources bootstrap must import loader controls from resourcesApiLoader')
assert(!bootstrapResources.includes("from './resourcesClient'"), 'Panda resources bootstrap must not depend on the compatibility resourcesClient entrypoint')
assert(bootstrapResources.includes('setPandaResourcesApiLoader(null)'), 'Panda resources bootstrap must disable API loader when flag is off')
assert(bootstrapResources.includes('const config = getPandaResourcesBffConfig(env)'), 'Panda resources bootstrap must use the shared BFF config')
assert(bootstrapResources.includes('if (!config.enabled)'), 'Panda resources bootstrap must disable API loading when the shared config is off')
assert(bootstrapResources.includes('endpoint: config.endpoint'), 'Panda resources bootstrap must create the fetch client from the shared endpoint config')

const viteEnv = read('src/vite-env.d.ts')
for (const envName of pandaResourcesBffEnvNames) {
  assert(viteEnv.includes(envName), `Vite env typing missing: ${envName}`)
}

const envExample = read('.env.example')
assert(envExample.includes('VITE_PANDA_RESOURCES_BFF=true'), 'Panda resources BFF flag must default to true after backend alignment in .env.example')
assert(envExample.includes('VITE_PANDA_RESOURCES_BFF_ENDPOINT=/api/v1/workbench/resources'), 'Panda resources BFF endpoint must be documented in .env.example')

const resourceContracts = read('src/panda/resourceContracts.ts')
const resourceContractTypes = read('src/panda/resourceContractTypes.ts')
const resourceRuntimeFields = read('src/panda/resourceRuntimeFields.ts')
const pageResourceContractCatalog = read('src/panda/pageResourceContractCatalog.ts')
const pageResourceContracts = read('src/panda/pageResourceContracts.ts')
for (const symbol of pandaResourceContractTypeSymbols) {
  assert(resourceContractTypes.includes(symbol), `Missing Panda resource contract type symbol: ${symbol}`)
}
assert(resourceContractTypes.includes("from './api/resourceSnapshotTypes'"), 'Panda resource contract types must import snapshot types from resourceSnapshotTypes')
assert(!resourceContractTypes.includes("from './api/resourcesClient'"), 'Panda resource contract types must not depend on the compatibility resourcesClient entrypoint')
assert(resourceContractTypes.includes('resourceKeys: readonly PandaResourceKey[]'), 'Panda resource contract resource keys must be readonly')
assert(resourceContractTypes.includes('runtimeFields: readonly PandaRuntimeField[]'), 'Panda resource contract runtime fields must be readonly')
assert(resourceContractTypes.includes('apiNeeds: readonly string[]'), 'Panda resource contract API needs must be readonly')
assert(!resourceContractTypes.includes('resourceKeys: PandaResourceKey[]'), 'Panda resource contract resource keys must not be mutable arrays')
assert(!resourceContractTypes.includes('runtimeFields: PandaRuntimeField[]'), 'Panda resource contract runtime fields must not be mutable arrays')
for (const symbol of pandaResourceRuntimeFieldSymbols) {
  assert(resourceRuntimeFields.includes(symbol), `Missing Panda resource runtime field symbol: ${symbol}`)
}
assert(resourceRuntimeFields.includes('readonly PandaRuntimeField[]'), 'Panda core runtime field list must be readonly')
for (const symbol of pandaPageResourceContractSymbols) {
  assert(pageResourceContracts.includes(symbol), `Missing Panda page resource contract symbol: ${symbol}`)
}
assert(pageResourceContracts.includes("from './pageResourceContractCatalog'"), 'Panda pageResourceContracts.ts must preserve compatibility exports from pageResourceContractCatalog')
assert(!pageResourceContracts.includes('home: {'), 'Panda pageResourceContracts.ts must not own page contract catalog entries directly')
for (const symbol of pandaResourceContractBarrelSymbols) {
  assert(resourceContracts.includes(symbol), `Missing Panda resource contract symbol: ${symbol}`)
}
assert(resourceContracts.includes("from './resourceContractTypes'"), 'Panda resourceContracts.ts must re-export contract types for compatibility')
assert(resourceContracts.includes("from './resourceRuntimeFields'"), 'Panda resourceContracts.ts must re-export runtime fields for compatibility')
assert(resourceContracts.includes("from './pageResourceContracts'"), 'Panda resourceContracts.ts must re-export page contracts for compatibility')
for (const pageId of pageIds) {
  assert(pageResourceContractCatalog.includes(`${pageId}: {`), `Missing resource contract for page: ${pageId}`)
  assert(pageResourceContractCatalog.includes(`page: '${pageId}'`), `Resource contract page mismatch for: ${pageId}`)
}
for (const runtimeField of pandaCoreRuntimeFieldNames) {
  assert(resourceRuntimeFields.includes(`'${runtimeField}'`) || pageResourceContractCatalog.includes(`'${runtimeField}'`), `Resource contracts missing runtime field: ${runtimeField}`)
}
for (const resourceKey of pandaResourceSnapshotViewKeys) {
  assert(resourceSnapshotTypes.includes(`${resourceKey}:`), `PandaResourceSnapshot missing resource key: ${resourceKey}`)
  assert(resourceSnapshotTypes.includes(`${resourceKey}: readonly`), `PandaResourceSnapshot resource collection must be readonly: ${resourceKey}`)
  assert(objectLiteralIncludesKey(resourceFallbackSnapshot, resourceKey), `getPandaResourceSnapshot missing resource key: ${resourceKey}`)
  assert(pageResourceContractCatalog.includes(`'${resourceKey}'`), `No page resource contract references: ${resourceKey}`)
}
for (const endpoint of pandaPageBffEndpoints) {
  assert(pageResourceContractCatalog.includes(endpoint), `Missing Panda BFF endpoint contract: ${endpoint}`)
}

const resourceReadiness = read('src/panda/api/resourceReadiness.ts')
for (const symbol of pandaResourceReadinessRequiredSymbols) {
  assert(resourceReadiness.includes(symbol), `Missing Panda resource readiness symbol: ${symbol}`)
}
const closeoutPlan = read('scripts/panda-frontend-closeout-plan.mjs')
for (const phrase of pandaCloseoutPlanRequiredSymbols) {
  assert(closeoutPlan.includes(phrase), `Panda closeout plan script must expose ${phrase}`)
}
const closeoutPlanJson = runNodeJson('scripts/panda-frontend-closeout-plan.mjs', ['--json'])
assert(closeoutPlanJson.frontendEngineerGoal.includes('Panda Agent'), 'Panda closeout plan must state the frontend engineer goal')
assert(closeoutPlanJson.routeRolloverPlan.length === 0, 'Panda closeout plan must show no pending backend route rollovers after alignment')
assert(closeoutPlanJson.alignmentContextSource === 'frontend/scripts/panda-alignment-context.mjs', 'Panda closeout plan must expose the shared alignment context source')
assert(closeoutPlanJson.closeoutEvidenceSource === 'frontend/scripts/panda-closeout-evidence.mjs', 'Panda closeout plan must expose the shared closeout evidence source')
assert(closeoutPlanJson.routeRolloverSource === 'frontend/scripts/panda-route-rollover-plan.mjs', 'Panda closeout plan must expose the shared route rollover source')
assert(closeoutPlanJson.alignmentContextSource === alignmentReportJson.alignmentContextSource, 'Panda closeout plan and alignment report must share the alignment context source')
assert(closeoutPlanJson.closeoutEvidenceSource === alignmentReportJson.closeoutEvidenceSource, 'Panda closeout plan and alignment report must share the closeout evidence source')
assert(closeoutPlanJson.routeRolloverSource === alignmentReportJson.routeRolloverSource, 'Panda closeout plan and alignment report must share the route rollover source')
assert(closeoutPlanJson.frontendCompletionEvidence?.status === 'passed', 'Panda closeout plan must expose passed frontend completion evidence')
assert(
  JSON.stringify(closeoutPlanJson.frontendCompletionEvidence) === JSON.stringify(alignmentReportJson.frontendCompletion),
  'Panda closeout plan and alignment report must share the same frontend completion evidence payload',
)
assert(
  closeoutPlanJson.frontendCompletionEvidence?.evidence?.some((item) => item.id === 'route-api-resources-evidence' && item.status === 'passed'),
  'Panda closeout plan frontend completion evidence must include route API resources evidence',
)
assert(closeoutPlanJson.routeApiResourcesEvidence?.status === 'passed', 'Panda closeout plan must expose passed route API resources evidence')
assert(
  JSON.stringify(closeoutPlanJson.routeApiResourcesEvidence) === JSON.stringify(alignmentReportJson.routeApiResourcesEvidence),
  'Panda closeout plan and alignment report must share the same route API resources evidence payload',
)
assert(
  closeoutPlanJson.routeApiResourcesEvidence?.unknownRouteApiResources?.length === 0 &&
    closeoutPlanJson.routeApiResourcesEvidence?.missingRouteApiResources?.length === 0,
  'Panda closeout plan route API resources evidence must keep unknown and missing diffs empty',
)
assertPandaBackendAlignmentHandoff(closeoutPlanJson.backendAlignmentHandoff, 'Panda closeout plan backend alignment handoff')
assert(
  JSON.stringify(closeoutPlanJson.backendAlignmentHandoff) === JSON.stringify(alignmentReportJson.backendAlignmentHandoff),
  'Panda closeout plan and alignment report must share the same backend alignment handoff payload',
)
assert(closeoutPlanJson.resourceBffGate.flag === manifest.bff.resourcesFlag, 'Panda closeout plan must reuse the manifest resources BFF flag')
assert(closeoutPlanJson.verificationMatrix.frontendOwnedCommands.includes('npm run build'), 'Panda closeout plan must include the frontend build gate')
const expectedStrictFailure =
  alignmentReportJson.mockReadyCount > 0 || alignmentReportJson.resourcesBff.defaultValue !== 'true'
    ? `${alignmentReportJson.mockReadyCount} mock-ready routes and ${alignmentReportJson.resourcesBff.flag}=${alignmentReportJson.resourcesBff.defaultValue}`
    : 'none'
assert(
  closeoutPlanJson.verificationMatrix.expectedStrictFailure === expectedStrictFailure,
  'Panda closeout plan expected strict failure must match the alignment report strict inputs',
)
assert(
  closeoutPlanJson.modulePageStructure?.sourceScript === alignmentReportJson.modulePageStructure?.sourceScript,
  'Panda closeout plan and alignment report must share the module page structure source script',
)
assert(
  closeoutPlanJson.modulePageStructure?.content === alignmentReportJson.modulePageStructure?.content,
  'Panda closeout plan and alignment report must share the module page content boundary',
)
assert(
  closeoutPlanJson.modulePageStructure?.shell === alignmentReportJson.modulePageStructure?.shell,
  'Panda closeout plan and alignment report must share the module page shell boundary',
)
assert(
  closeoutPlanJson.modulePageStructure?.resources === alignmentReportJson.modulePageStructure?.resources,
  'Panda closeout plan and alignment report must share the module page resource hook boundary',
)
assert(
  sameMembers(
    closeoutPlanJson.modulePageStructure?.standardPages ?? [],
    alignmentReportJson.modulePageStructure?.standardPages ?? [],
  ),
  'Panda closeout plan and alignment report must expose the same standard module pages',
)
assert(
  sameMembers(
    closeoutPlanJson.modulePageStructure?.directSelectorExceptions ?? [],
    alignmentReportJson.modulePageStructure?.directSelectorExceptions ?? [],
  ),
  'Panda closeout plan and alignment report must expose the same direct selector exceptions',
)
assert(
  sameMembers(
    closeoutPlanJson.modulePageStructure?.resourceTypes?.map((binding) => `${binding.page}:${binding.resourceType}`) ?? [],
    alignmentReportJson.modulePageStructure?.resourceTypes?.map((binding) => `${binding.page}:${binding.resourceType}`) ?? [],
  ),
  'Panda closeout plan and alignment report must expose the same standard module resource type bindings',
)
assert(
  closeoutPlanJson.routeRolloverPlan.length === alignmentReportJson.backendAlignmentBlockers.pendingRoutes.length,
  'Panda closeout plan route rollover count must match alignment report pending route blockers',
)
for (const planRoute of closeoutPlanJson.routeRolloverPlan) {
  const reportRoute = alignmentReportJson.backendAlignmentBlockers.pendingRoutes.find(
    (route) => route.route === planRoute.route,
  )
  assert(reportRoute, `Panda alignment report missing pending route from closeout plan: ${planRoute.route}`)
  assert(reportRoute.endpoint === planRoute.endpoint, `Panda route rollover endpoint drift: ${planRoute.route}`)
  assert(
    sameMembers(reportRoute.resources.split(', '), planRoute.viewResources),
    `Panda route rollover resource drift: ${planRoute.route}`,
  )
  assert(
    sameMembers(reportRoute.apiResources.split(', '), planRoute.apiResources),
    `Panda route rollover API resource drift: ${planRoute.route}`,
  )
  assert(
    sameMembers(reportRoute.runtimeFields.split(', '), planRoute.runtimeFields),
    `Panda route rollover runtime field drift: ${planRoute.route}`,
  )
  assert(
    sameMembers(reportRoute.apiNeeds.split('; '), planRoute.apiNeeds),
    `Panda route rollover API need drift: ${planRoute.route}`,
  )
  assert(
    planRoute.frontendAcceptance?.some((item) => item.includes('strict report pending route count decreases')),
    `Panda route rollover acceptance must describe strict pending-route decrease: ${planRoute.route}`,
  )
}
assert(
  closeoutPlanJson.modulePageStructure?.resourceHooks?.length === Object.keys(pandaModulePageResourceHookByPage).length,
  'Panda closeout plan must expose every standard module page resource hook binding',
)
for (const [page, hook] of Object.entries(pandaModulePageResourceHookByPage)) {
  const resourceType = pandaModulePageResourceTypeByPage[page]
  assert(resourceType, `Panda verifier missing module page resource type mapping: ${page}`)
  assert(
    closeoutPlanJson.modulePageStructure.resourceHooks.some((binding) => binding.page === page && binding.hook === hook && binding.resourceType === resourceType),
    `Panda closeout plan missing module page resource hook/type binding: ${page} -> ${hook}:${resourceType}`,
  )
  assert(
    alignmentReportJson.modulePageStructure.resourceHooks.some((binding) => binding.page === page && binding.hook === hook && binding.resourceType === resourceType),
    `Panda alignment report missing module page resource hook/type binding: ${page} -> ${hook}:${resourceType}`,
  )
  assert(
    closeoutPlanJson.modulePageStructure.resourceTypes.some((binding) => binding.page === page && binding.resourceType === resourceType),
    `Panda closeout plan missing module page resource type binding: ${page} -> ${resourceType}`,
  )
  assert(
    alignmentReportJson.modulePageStructure.resourceTypes.some((binding) => binding.page === page && binding.resourceType === resourceType),
    `Panda alignment report missing module page resource type binding: ${page} -> ${resourceType}`,
  )
}
assert(resourceReadiness.includes("from '../pageResourceContracts'"), 'Panda resource readiness must derive from focused page resource contracts')
assert(resourceReadiness.includes("from '../resourceContractTypes'"), 'Panda resource readiness must import contract shape from focused contract types')
assert(resourceReadiness.includes("from './resourceKeys'"), 'Panda resource readiness must import shared resource key boundary')
assert(resourceReadiness.includes('pandaApiResourceKeyByViewKey'), 'Panda resource readiness must centralize view-to-API key mapping')
assert(resourceReadiness.includes('function resolvePandaApiResourceKey'), 'Panda resource readiness must resolve API resource keys through a focused helper')
assert(resourceReadiness.includes('Missing Panda API resource key mapping'), 'Panda resource readiness must fail fast on missing API key mappings')
assert(resourceReadiness.includes('Object.values(pandaPageResourceContracts)'), 'Panda route readiness must derive from pandaPageResourceContracts')
assert(resourceReadiness.includes("route: PandaPageResourceContract['page']"), 'Panda resource readiness must preserve the page contract route type')
assert(resourceReadiness.includes("resources: PandaPageResourceContract['resourceKeys']"), 'Panda resource readiness must preserve typed resource keys from page contracts')
assert(resourceReadiness.includes('apiResources: readonly PandaApiResourceKey[]'), 'Panda resource readiness must expose readonly backend API resource keys')
assert(resourceReadiness.includes('apiResources: contract.resourceKeys.map(resolvePandaApiResourceKey)'), 'Panda resource readiness must derive API resource keys from contract resources')
assert(resourceReadiness.includes("runtimeFields: PandaPageResourceContract['runtimeFields']"), 'Panda resource readiness must preserve typed runtime fields from page contracts')
assert(resourceReadiness.includes("needs: PandaPageResourceContract['apiNeeds']"), 'Panda resource readiness must preserve typed API needs from page contracts')
assert(!resourceReadiness.includes('runtimeFields: string[]'), 'Panda resource readiness must not weaken runtime fields to string arrays')
assert(!resourceReadiness.includes('resources: string[]'), 'Panda resource readiness must not weaken resource keys to string arrays')
assert(!resourceReadiness.includes('apiResources: string[]'), 'Panda resource readiness must not weaken API resource keys to string arrays')
assert(resourceReadiness.includes("resourcesFlag: 'VITE_PANDA_RESOURCES_BFF'"), 'Panda resource readiness must record the resources BFF flag')
assert(resourceReadiness.includes("resourcesEndpoint: '/api/v1/workbench/resources'"), 'Panda resource readiness must record the aggregate resources endpoint')
assert(resourceReadiness.includes("contract.readiness === 'mock-ready'"), 'Panda resource readiness must identify backend-owned mock-ready routes')
assert(resourceReadiness.includes('all Panda routes api-wired'), 'Panda resource readiness must record strict route readiness requirement')
assert(resourceReadiness.includes('ApiPandaResourceSnapshot validation passes'), 'Panda resource readiness must record validation-before-BFF-enable requirement')
assert(resourceReadiness.includes('approval, sandbox, auth, secret, and execution policy remain backend-owned'), 'Panda resource readiness must keep high-risk policy backend-owned')
assert(!resourceReadiness.includes('fetch('), 'Panda resource readiness must stay declarative and not fetch backend data')
assert(!resourceReadiness.includes('axios'), 'Panda resource readiness must stay pure and not import axios')

const workspaceContext = read('src/panda/state/PandaWorkspaceContext.tsx')
const workspaceTypes = read('src/panda/state/workspaceTypes.ts')
const workspaceProvider = read('src/panda/state/workspaceProvider.tsx')
const workspaceLifecycleViewModel = read('src/panda/state/workspaceLifecycleViewModel.ts')
const workspaceHooks = read('src/panda/state/workspaceHooks.ts')
const modulePageResourcesBarrel = read('src/panda/state/useModulePageResources.ts')
const modulePageResourceTypes = read('src/panda/state/modulePageResourceTypes.ts')
const countedModulePageResource = read('src/panda/state/useCountedModulePageResource.ts')
const modulePageResourceHooks = read('src/panda/state/modulePageResourceHooks.ts')
for (const symbol of pandaWorkspaceCompatibilitySymbols) {
  assert(workspaceContext.includes(symbol), `Missing Panda workspace compatibility export: ${symbol}`)
}
assert(workspaceContext.includes("from './workspaceTypes'"), 'PandaWorkspaceContext must re-export focused workspace types')
assert(workspaceContext.includes("from './workspaceProvider'"), 'PandaWorkspaceContext must re-export the focused workspace provider')
assert(workspaceContext.includes("from './workspaceHooks'"), 'PandaWorkspaceContext must re-export focused workspace hooks')
assert(!workspaceContext.includes('React.createContext'), 'PandaWorkspaceContext must stay a compatibility entrypoint without owning context runtime')
for (const symbol of pandaWorkspaceTypeSymbols) {
  assert(workspaceTypes.includes(symbol), `Missing focused Panda workspace type symbol: ${symbol}`)
}
assert(workspaceTypes.includes("from '../api/resourceSnapshotTypes'"), 'Panda workspace types must import resource types from resourceSnapshotTypes')
assert(workspaceTypes.includes('readonly resources: Readonly<PandaResourceSnapshot>'), 'Panda workspace resources must expose a readonly snapshot')
assert(workspaceTypes.includes('readonly status: PandaWorkspaceStatus'), 'Panda workspace status must be readonly context data')
assert(workspaceTypes.includes('readonly source: PandaResourceSource'), 'Panda workspace source must be readonly context data')
assert(workspaceTypes.includes('readonly error: Error | null'), 'Panda workspace error must be readonly context data')
assert(workspaceTypes.includes('readonly refresh: () => Promise<void>'), 'Panda workspace refresh handle must be readonly context data')
for (const symbol of pandaWorkspaceProviderSymbols) {
  assert(workspaceProvider.includes(symbol), `Missing focused Panda workspace provider symbol: ${symbol}`)
}
for (const symbol of pandaModulePageResourceHookSymbols) {
  assert(modulePageResourceHooks.includes(`export function ${symbol}`), `useModulePageResources must export focused module page hook: ${symbol}`)
  assert(modulePageResourcesBarrel.includes(symbol), `useModulePageResources barrel must preserve focused module page hook export: ${symbol}`)
}
for (const symbol of pandaModulePageResourceTypeSymbols) {
  assert(modulePageResourceTypes.includes(`export type ${symbol}`), `modulePageResourceTypes must export focused module page resource type: ${symbol}`)
  assert(modulePageResourceHooks.includes(`: ${symbol}`), `useModulePageResources hook return signature must use ${symbol}`)
  assert(modulePageResourcesBarrel.includes(symbol), `useModulePageResources barrel must preserve focused module page resource type export: ${symbol}`)
}
assert(modulePageResourcesBarrel.includes("from './modulePageResourceTypes'"), 'useModulePageResources must preserve compatibility exports from modulePageResourceTypes')
assert(modulePageResourcesBarrel.includes("from './useCountedModulePageResource'"), 'useModulePageResources must preserve compatibility exports from useCountedModulePageResource')
assert(modulePageResourcesBarrel.includes("from './modulePageResourceHooks'"), 'useModulePageResources must preserve compatibility exports from modulePageResourceHooks')
assert(modulePageResourceTypes.includes("import type { PandaResourceSnapshot }"), 'modulePageResourceTypes must derive hook payload types from PandaResourceSnapshot')
assert(modulePageResourceTypes.includes('export type CountedModulePageResource'), 'modulePageResourceTypes must define a shared counted resource payload helper')
assert(countedModulePageResource.includes('export function useCountedModulePageResource'), 'useCountedModulePageResource must centralize single-slice count mapping')
assert(modulePageResourceTypes.includes("PandaResourceSnapshot['tasks']"), 'TasksPageResources must derive tasks from PandaResourceSnapshot')
assert(modulePageResourceTypes.includes("PandaResourceSnapshot['workflowNodes']"), 'WorkflowsPageResources must derive workflow nodes from PandaResourceSnapshot')
assert(modulePageResourceTypes.includes("PandaResourceSnapshot['agents'][number] | undefined"), 'AgentsPageResources lead must be typed from the agent snapshot slice')
assert(!modulePageResourceTypes.includes("from '../types'"), 'modulePageResourceTypes must not duplicate resource item type imports')
assert(!modulePageResourceHooks.includes("from '../types'"), 'modulePageResourceHooks must not duplicate resource item type imports')
assert(modulePageResourceHooks.includes("import React from 'react'"), 'useModulePageResources must import React for memoized derived resources')
assert(modulePageResourceHooks.includes('React.useMemo'), 'useModulePageResources must memoize derived module resource payloads')
assert(modulePageResourceHooks.includes("useCountedModulePageResource('tools', 'toolCapabilities')"), 'ToolsPageResources must map the tools slice to the toolCapabilities view property through the shared helper')
assert(modulePageResourceHooks.includes('[workflows, workflowNodes]'), 'useWorkflowsPageResources must memoize against both workflow resource slices')
assert(
  countedModulePageResource.includes("from './PandaWorkspaceContext'") && modulePageResourceHooks.includes("from './PandaWorkspaceContext'"),
  'module page resource hooks must read through the workspace context compatibility boundary',
)
assert(
  !modulePageResourcesBarrel.includes('../api/resourcesClient')
    && !modulePageResourceTypes.includes('../api/resourcesClient')
    && !countedModulePageResource.includes('../api/resourcesClient')
    && !modulePageResourceHooks.includes('../api/resourcesClient')
    && !modulePageResourceHooks.includes('../api/adapters')
    && !modulePageResourceHooks.includes('../api/resourcesApiLoader')
    && !modulePageResourceHooks.includes('../api/workbenchClient'),
  'useModulePageResources must not import API clients, loaders, or adapters directly',
)
assert(
  !modulePageResourcesBarrel.includes('../data/mock') && !modulePageResourceTypes.includes('../data/mock') && !countedModulePageResource.includes('../data/mock') && !modulePageResourceHooks.includes('../data/mock'),
  'useModulePageResources must not import mock data directly',
)
assert(workspaceProvider.includes('refreshSeqRef'), 'Panda workspace refresh must guard against stale responses')
assert(workspaceProvider.includes('isMountedRef'), 'Panda workspace refresh must avoid state writes after unmount')
assert(workspaceProvider.includes('const isCurrentRefresh = () => isMountedRef.current && refreshSeqRef.current === refreshSeq'), 'Panda workspace refresh must verify the active refresh sequence')
assert(workspaceProvider.includes('if (!isCurrentRefresh())'), 'Panda workspace refresh must ignore stale success and error responses')
assert(workspaceProvider.includes('return () =>'), 'Panda workspace provider must clean up lifecycle refs on unmount')
assert(workspaceProvider.includes('PandaWorkspaceResourcesContext'), 'Panda workspace provider must split resource data into a dedicated context')
assert(workspaceProvider.includes('PandaWorkspaceLifecycleContext'), 'Panda workspace provider must split lifecycle data into a dedicated context')
assert(workspaceProvider.includes('const lifecycleValue = React.useMemo<PandaWorkspaceLifecycle>'), 'Panda workspace provider must memoize its lifecycle context value')
assert(workspaceProvider.includes('<PandaWorkspaceResourcesContext.Provider value={resources}>'), 'Panda workspace provider must publish resources through the resources context')
assert(workspaceProvider.includes('<PandaWorkspaceLifecycleContext.Provider value={lifecycleValue}>'), 'Panda workspace provider must publish lifecycle through the lifecycle context')
assert(workspaceProvider.includes('React.createContext<Readonly<PandaResourceSnapshot> | null>'), 'Panda resources context must expose readonly snapshots')
assert(workspaceProvider.includes("from '../api/resourcesClient'"), 'Panda workspace provider must keep resource loading behind the resourcesClient entrypoint')
assert(workspaceProvider.includes("from '../api/resourceSnapshotTypes'"), 'Panda workspace provider must import resource types from resourceSnapshotTypes')
assert(workspaceProvider.includes("from './workspaceLifecycleViewModel'"), 'Panda workspace provider must delegate refresh lifecycle display mapping to workspaceLifecycleViewModel')
assert(workspaceProvider.includes('formatPandaWorkspaceRefreshTime()'), 'Panda workspace provider must use the lifecycle view model for initial refresh timestamps')
assert(workspaceProvider.includes('const viewModel = buildPandaWorkspaceRefreshViewModel(result)'), 'Panda workspace provider must map resource load results through the lifecycle view model')
assert(workspaceProvider.includes('setResources(viewModel.resources)'), 'Panda workspace provider must apply refresh resources from the lifecycle view model')
assert(workspaceProvider.includes('setSource(viewModel.source)'), 'Panda workspace provider must apply refresh source from the lifecycle view model')
assert(workspaceProvider.includes('setError(viewModel.error)'), 'Panda workspace provider must apply refresh errors from the lifecycle view model')
assert(workspaceProvider.includes('setRefreshedAt(viewModel.refreshedAt)'), 'Panda workspace provider must apply refresh timestamps from the lifecycle view model')
assert(workspaceProvider.includes('setStatus(viewModel.status)'), 'Panda workspace provider must apply refresh status from the lifecycle view model')
assert(workspaceProvider.includes('normalizePandaWorkspaceRefreshError(refreshError)'), 'Panda workspace provider must normalize refresh exceptions through the lifecycle view model')
assert(!workspaceProvider.includes("new Date().toLocaleTimeString('zh-CN'"), 'Panda workspace provider must not inline refresh timestamp formatting')
assert(!workspaceProvider.includes("result.error ? 'error' : 'ready'"), 'Panda workspace provider must not inline refresh status derivation')
assert(!workspaceProvider.includes("new Error('无法刷新 Panda 工作台资源')"), 'Panda workspace provider must not inline refresh exception copy')
assert(workspaceLifecycleViewModel.includes("import type { PandaResourceLoadResult } from '../api/resourceSnapshotTypes'"), 'workspaceLifecycleViewModel must type resource load results from resourceSnapshotTypes')
assert(workspaceLifecycleViewModel.includes("import type { PandaWorkspaceStatus } from './workspaceTypes'"), 'workspaceLifecycleViewModel must type statuses from workspaceTypes')
assert(workspaceLifecycleViewModel.includes('export type PandaWorkspaceRefreshViewModel'), 'workspaceLifecycleViewModel must export the refresh view model shape')
assert(workspaceLifecycleViewModel.includes('export function formatPandaWorkspaceRefreshTime'), 'workspaceLifecycleViewModel must own refresh timestamp formatting')
assert(workspaceLifecycleViewModel.includes("new Date().toLocaleTimeString('zh-CN', { hour: '2-digit', minute: '2-digit' })"), 'workspaceLifecycleViewModel must preserve the zh-CN two-digit refresh time format')
assert(workspaceLifecycleViewModel.includes('export function buildPandaWorkspaceRefreshViewModel'), 'workspaceLifecycleViewModel must export the refresh result mapper')
assert(workspaceLifecycleViewModel.includes('error: result.error ?? null'), 'workspaceLifecycleViewModel must normalize optional resource load errors to nullable errors')
assert(workspaceLifecycleViewModel.includes("status: result.error ? 'error' : 'ready'"), 'workspaceLifecycleViewModel must derive ready/error status from resource load results')
assert(workspaceLifecycleViewModel.includes('export function normalizePandaWorkspaceRefreshError'), 'workspaceLifecycleViewModel must export refresh exception normalization')
assert(workspaceLifecycleViewModel.includes("new Error('无法刷新 Panda 工作台资源')"), 'workspaceLifecycleViewModel must own the fallback refresh error copy')
assert(workspaceHooks.includes('export function usePandaWorkspaceLifecycle()'), 'Panda workspace hooks must expose a lifecycle-only hook')
assert(workspaceHooks.includes('function usePandaWorkspaceResources()'), 'Panda workspace hooks must keep resource context access isolated')
assert(workspaceHooks.includes('function usePandaWorkspaceResources(): Readonly<PandaResourceSnapshot>'), 'Panda resource context hook must return a readonly snapshot')
assert(workspaceHooks.includes('return usePandaWorkspaceResources()[key]'), 'Panda resource selector must not subscribe to lifecycle context')
assert(workspaceHooks.includes('resources: usePandaWorkspaceResources()'), 'Full Panda workspace hook must preserve compatibility by composing split contexts')
assert(workspaceHooks.includes("from './workspaceProvider'"), 'Panda workspace hooks must consume focused provider contexts')
assert(workspaceHooks.includes("from './workspaceTypes'"), 'Panda workspace hooks must type lifecycle values from workspaceTypes')

const {
  common,
  metricPrimitives,
  runtimeMetaPrimitives,
  tagListPrimitives,
  progressPrimitives,
  statePanelBasePrimitives,
  statePanelPrimitives,
  runtimePrimitives,
  statusDotViewModel,
  statusPrimitives,
  workspaceCardPrimitives,
  workspaceResourceCardPrimitives,
  workspaceListCardHeaderPrimitives,
  workspaceCapabilityCardPrimitives,
  workspaceInfoPrimitives,
  workspaceTablePrimitives,
  workspaceLayoutPrimitives,
  workspaceActivityPrimitives,
  workspaceRailPrimitives,
  workspacePrimitives,
  workflowActionPrimitives,
  workflowEvidencePrimitives,
  workflowExecutionStepPrimitives,
  workflowNodePrimitives,
} = verifyPandaComponentPrimitives({ assert, read })
const runtimeMetaViewModel = read('src/panda/components/runtimeMetaViewModel.ts')
const resourceState = read('src/panda/components/resourceState.tsx')
const resourceStateViewModel = read('src/panda/components/resourceStateViewModel.ts')
assert(statePanelBasePrimitives.includes('export function PandaStatePanel'), 'statePanelBasePrimitives must own PandaStatePanel')
assert(statePanelPrimitives.includes("from './statePanelBasePrimitives'"), 'statePanelPrimitives must preserve PandaStatePanel compatibility export')
assert(!statePanelPrimitives.includes('export function PandaStatePanel'), 'statePanelPrimitives must not duplicate PandaStatePanel')
for (const symbol of ['PandaLoadingState', 'PandaEmptyState', 'PandaErrorState']) {
  assert(statePanelPrimitives.includes(`export function ${symbol}`), `statePanelPrimitives must keep semantic state component: ${symbol}`)
}
assert(resourceState.includes("from './resourceStateViewModel'"), 'PandaResourceState must import its focused lifecycle view model')
assert(resourceState.includes('buildPandaResourceStateViewModel({ count, status, error })'), 'PandaResourceState must delegate lifecycle branching to its view model')
assert(!resourceState.includes("status === 'loading' && count === 0"), 'PandaResourceState must not inline loading lifecycle branching')
for (const stateKind of ['loading', 'error', 'empty', 'ready']) {
  assert(resourceStateViewModel.includes(`'${stateKind}'`), `resourceStateViewModel must preserve lifecycle state kind: ${stateKind}`)
}
assert(resourceStateViewModel.includes("status === 'loading' && count === 0"), 'resourceStateViewModel must detect initial loading state')
assert(resourceStateViewModel.includes("status === 'error' && count === 0"), 'resourceStateViewModel must detect empty error state')
assert(resourceStateViewModel.includes('当前资源切片加载失败，等待后端接口或本地回退数据恢复。'), 'resourceStateViewModel must preserve degraded-resource fallback copy')
assert(metricPrimitives.includes('items: readonly MetricStripItem[]'), 'MetricStrip must keep readonly metric item props')
assert(metricPrimitives.includes('items: readonly SummaryMetricItem[]'), 'SummaryMetricList must keep readonly summary item props')
assert(statusPrimitives.includes('buildStatusDotViewModel'), 'StatusDot must delegate tone labels and class names to statusDotViewModel')
assert(!statusPrimitives.includes("tone === 'danger'"), 'StatusDot must not inline tone class branching')
assert(statusDotViewModel.includes('export function buildStatusDotViewModel'), 'statusDotViewModel must own the status dot view model builder')
assert(statusDotViewModel.includes('ariaLabel: label ?? `风险等级：${title}`'), 'statusDotViewModel must preserve default readable risk labels')
assert(runtimeMetaPrimitives.includes('runtime?: RuntimeMetadata'), 'RuntimeMetaStrip must keep runtime metadata props in runtimeMetaPrimitives')
assert(runtimeMetaPrimitives.includes("from './runtimeMetaViewModel'"), 'RuntimeMetaStrip must import its focused view model')
assert(runtimeMetaPrimitives.includes('buildRuntimeMetaStripItems({ runtime, owner, updatedAt, risk })'), 'RuntimeMetaStrip must delegate runtime tag construction to its view model')
assert(!runtimeMetaPrimitives.includes('owner_agent ${ownerLabel}'), 'RuntimeMetaStrip must not inline owner_agent tag construction')
for (const runtimeTag of ['owner_agent', 'updated_at', 'risk_level', 'evidence_refs']) {
  assert(runtimeMetaViewModel.includes(runtimeTag), `runtimeMetaViewModel must preserve runtime API tag label: ${runtimeTag}`)
}
for (const runtimeField of ['runtime?.ownerAgent', 'runtime?.updatedAt', 'runtime?.riskLevel', 'runtime?.evidenceRefs.length']) {
  assert(runtimeMetaViewModel.includes(runtimeField), `runtimeMetaViewModel must derive display tags from runtime field: ${runtimeField}`)
}
assert(runtimeMetaViewModel.includes('toneLabel[riskTone]'), 'runtimeMetaViewModel must render risk_level through tone labels')
assert(tagListPrimitives.includes('items: readonly KeyValueItem[]'), 'KeyValueList must keep readonly key-value item props')
assert(tagListPrimitives.includes('valueClassName?: string'), 'KeyValueList must support value-specific styling without duplicating row markup')
assert(tagListPrimitives.includes('items: readonly string[]'), 'MiniTagList must keep readonly tag props')
assert(metricPrimitives.includes("from './tagListPrimitives'"), 'metricPrimitives must preserve KeyValueList and MiniTagList compatibility exports')
assert(runtimePrimitives.includes('KeyValueList'), 'runtimePrimitives must preserve the KeyValueList compatibility export')
assert(common.includes('KeyValueList'), 'common.tsx must preserve the KeyValueList compatibility export')
assert(workspaceInfoPrimitives.includes('items: readonly InfoPairItem[]'), 'InfoPairGrid must keep readonly info item props')
assert(workspaceTablePrimitives.includes('columns: readonly string[]'), 'WorkspaceTable must keep readonly column props')
assert(workspaceCapabilityCardPrimitives.includes('metrics: readonly MetricStripItem[]'), 'CapabilityMetricCard must keep readonly metric props')
assert(workspaceLayoutPrimitives.includes('export function WorkspacePanel'), 'workspaceLayoutPrimitives must export the shared workspace panel primitive')
assert(workspaceLayoutPrimitives.includes("as?: 'section' | 'div' | 'aside'"), 'WorkspacePanel must support semantic section/div/aside containers')
assert(workspaceLayoutPrimitives.includes('title?: string'), 'WorkspacePanel must support optional panel titles')
assert(workspaceActivityPrimitives.includes('export function ActivitySummaryRow'), 'workspaceActivityPrimitives must export the shared activity summary row primitive')
assert(workspaceLayoutPrimitives.includes("from './workspaceActivityPrimitives'"), 'workspaceLayoutPrimitives must preserve ActivitySummaryRow compatibility export')
assert(workspaceRailPrimitives.includes('export function RailCard'), 'workspaceRailPrimitives must export the shared rail card primitive')
assert(workspaceLayoutPrimitives.includes("from './workspaceRailPrimitives'"), 'workspaceLayoutPrimitives must preserve RailCard compatibility export')
assert(workspaceCardPrimitives.includes('export function ResourceCardGrid'), 'workspaceCardPrimitives must export the shared resource card grid primitive')
assert(workspaceCardPrimitives.includes('renderItem: (item: Item) => React.ReactNode'), 'ResourceCardGrid must keep renderItem typed as a React node factory')
assert(workspaceCardPrimitives.includes('export function NavigationCardGrid'), 'workspaceCardPrimitives must export the shared navigation card grid primitive')
assert(workspaceCardPrimitives.includes('export function ModuleSummaryCard'), 'workspaceCardPrimitives must export the shared module summary card primitive')
assert(workspaceCardPrimitives.includes('summary: React.ReactNode'), 'ModuleSummaryCard must support composed summary content')
assert(workspaceCardPrimitives.includes("from './workspaceResourceCardPrimitives'"), 'workspaceCardPrimitives must preserve compatibility exports from workspaceResourceCardPrimitives')
assert(workspaceResourceCardPrimitives.includes("from './workspaceCapabilityCardPrimitives'"), 'workspaceResourceCardPrimitives must preserve compatibility exports from workspaceCapabilityCardPrimitives')
assert(workspaceResourceCardPrimitives.includes("from './workspaceListCardHeaderPrimitives'"), 'workspaceResourceCardPrimitives must preserve compatibility exports from workspaceListCardHeaderPrimitives')
assert(!workspaceResourceCardPrimitives.includes('export function ListCardHeader'), 'workspaceResourceCardPrimitives must keep ListCardHeader implementation in workspaceListCardHeaderPrimitives')
assert(workspaceListCardHeaderPrimitives.includes('export function ListCardHeader'), 'workspaceListCardHeaderPrimitives must export the shared list card header primitive')
assert(workspaceListCardHeaderPrimitives.includes('StatusDot'), 'workspaceListCardHeaderPrimitives must render shared status dots')
assert(workspaceResourceCardPrimitives.includes('export function ResourceRuntimeCard'), 'workspaceResourceCardPrimitives must export the shared resource runtime card primitive')
assert(workspaceResourceCardPrimitives.includes('children?: React.ReactNode'), 'ResourceRuntimeCard must support composed runtime body content')
assert(workspaceResourceCardPrimitives.includes('export function ResourceInfoCard'), 'workspaceResourceCardPrimitives must export the shared resource info card primitive')
assert(workspaceResourceCardPrimitives.includes('<ResourceRuntimeCard'), 'ResourceInfoCard must compose the shared ResourceRuntimeCard shell')
assert(workspaceResourceCardPrimitives.includes('description: React.ReactNode'), 'ResourceInfoCard must support composed descriptions')
assert(workspaceResourceCardPrimitives.includes('items: readonly InfoPairItem[]'), 'ResourceInfoCard must keep readonly info item props')
assert(workspaceCardPrimitives.includes("from './workspaceInfoPrimitives'"), 'workspaceCardPrimitives must preserve compatibility exports from workspaceInfoPrimitives')
assert(workspaceCardPrimitives.includes("from './workspaceTablePrimitives'"), 'workspaceCardPrimitives must preserve compatibility exports from workspaceTablePrimitives')
assert(workflowNodePrimitives.includes('export function FlowNodeCard'), 'workflowNodePrimitives must own FlowNodeCard')
assert(workspacePrimitives.includes('ResourceCardGrid'), 'workspacePrimitives must preserve the ResourceCardGrid compatibility export')
assert(workspacePrimitives.includes('NavigationCardGrid'), 'workspacePrimitives must preserve the NavigationCardGrid compatibility export')
assert(workspacePrimitives.includes('ModuleSummaryCard'), 'workspacePrimitives must preserve the ModuleSummaryCard compatibility export')
assert(workspacePrimitives.includes('ResourceInfoCard'), 'workspacePrimitives must preserve the ResourceInfoCard compatibility export')
assert(workspacePrimitives.includes('ResourceRuntimeCard'), 'workspacePrimitives must preserve the ResourceRuntimeCard compatibility export')
assert(workspacePrimitives.includes('WorkspacePanel'), 'workspacePrimitives must preserve the WorkspacePanel compatibility export')
assert(common.includes('ResourceCardGrid'), 'common.tsx must preserve the ResourceCardGrid compatibility export')
assert(common.includes('NavigationCardGrid'), 'common.tsx must preserve the NavigationCardGrid compatibility export')
assert(common.includes('ModuleSummaryCard'), 'common.tsx must preserve the ModuleSummaryCard compatibility export')
assert(common.includes('ResourceInfoCard'), 'common.tsx must preserve the ResourceInfoCard compatibility export')
assert(common.includes('ResourceRuntimeCard'), 'common.tsx must preserve the ResourceRuntimeCard compatibility export')
assert(common.includes('WorkspacePanel'), 'common.tsx must preserve the WorkspacePanel compatibility export')
assert(workflowActionPrimitives.includes('items: readonly string[]'), 'ActionPanel must keep readonly action item props')
assert(workflowEvidencePrimitives.includes('evidenceRefs: readonly string[]'), 'AuditEventRow must keep readonly evidence ref props')
assert(workflowExecutionStepPrimitives.includes('owner_agent: {ownerAgent}'), 'ExecutionStepRow must surface owner_agent runtime evidence')
assert(workflowExecutionStepPrimitives.includes('evidence_refs: {evidenceRef}'), 'ExecutionStepRow must surface evidence_refs runtime evidence')

const adapters = read('src/panda/api/adapters.ts')
const agentRoleAdapters = read('src/panda/api/agentRoleAdapters.ts')
const homeAdapters = read('src/panda/api/homeAdapters.ts')
const executionResourceAdapters = read('src/panda/api/executionResourceAdapters.ts')
const organizationResourceAdapters = read('src/panda/api/organizationResourceAdapters.ts')
const knowledgeResourceAdapters = read('src/panda/api/knowledgeResourceAdapters.ts')
const governanceResourceAdapters = read('src/panda/api/governanceResourceAdapters.ts')
const resourceItemAdapters = read('src/panda/api/resourceItemAdapters.ts')
const resourceSnapshotAdapter = read('src/panda/api/resourceSnapshotAdapter.ts')
for (const symbol of pandaAdapterBarrelSymbols) {
  assert(adapters.includes(symbol), `Missing adapter symbol: ${symbol}`)
}
assert(homeAdapters.includes('runtime: mapRuntimeMetadata'), 'Panda home adapters must attach runtime metadata to home view models')
assert(homeAdapters.includes('export function mapActivityItem'), 'Panda home adapters must own activity item mapping')
assert(homeAdapters.includes('tone: toStatusTone(item.tone ?? item.risk_level)'), 'Panda activity mapping must honor risk_level tone fallback')
assert(homeAdapters.includes('runtime: mapRuntimeMetadata({ ...item, status'), 'Panda activity mapping must attach runtime metadata')
const runtimeAdapterSources = {
  executionResourceAdapters,
  organizationResourceAdapters,
  knowledgeResourceAdapters,
  governanceResourceAdapters,
}
for (const name of pandaRuntimeAdapterModuleNames) {
  const source = runtimeAdapterSources[name]
  assert(source.includes('runtime: mapRuntimeMetadata'), `Panda ${name} must attach runtime metadata to resource view models`)
}
for (const symbol of pandaExecutionResourceAdapterSymbols) {
  assert(executionResourceAdapters.includes(symbol), `Execution resource adapters must own ${symbol}`)
  assert(resourceItemAdapters.includes(symbol), `Resource item adapter barrel must re-export ${symbol}`)
}
for (const symbol of pandaOrganizationResourceAdapterSymbols) {
  assert(organizationResourceAdapters.includes(symbol), `Organization resource adapters must own ${symbol}`)
  assert(resourceItemAdapters.includes(symbol), `Resource item adapter barrel must re-export ${symbol}`)
}
for (const symbol of pandaAgentRoleAdapterSymbols) {
  assert(agentRoleAdapters.includes(symbol), `Agent role adapters must own ${symbol}`)
  assert(adapters.includes(symbol), `Panda adapters barrel must re-export ${symbol}`)
}
for (const symbol of pandaKnowledgeResourceAdapterSymbols) {
  assert(knowledgeResourceAdapters.includes(symbol), `Knowledge resource adapters must own ${symbol}`)
  assert(resourceItemAdapters.includes(symbol), `Resource item adapter barrel must re-export ${symbol}`)
}
for (const symbol of pandaGovernanceResourceAdapterSymbols) {
  assert(governanceResourceAdapters.includes(symbol), `Governance resource adapters must own ${symbol}`)
  assert(resourceItemAdapters.includes(symbol), `Resource item adapter barrel must re-export ${symbol}`)
}
assert(adapters.includes("from './runtimeMapping'"), 'Panda adapters barrel must preserve shared runtime mapping exports')
assert(adapters.includes("from './apiContracts'"), 'Panda adapters barrel must preserve API DTO contract exports')
assert(adapters.includes("from './homeAdapters'"), 'Panda adapters barrel must preserve home adapter exports')
assert(adapters.includes("from './resourceItemAdapters'"), 'Panda adapters barrel must preserve resource item adapter exports')
assert(adapters.includes("from './resourceSnapshotAdapter'"), 'Panda adapters barrel must preserve resource snapshot adapter exports')
assert(resourceSnapshotAdapter.includes("from './resourceKeys'"), 'Panda resource snapshot adapter must import shared resource key types')
assert(adapters.includes("} from './apiContracts'"), 'Panda adapters must preserve compatibility re-exports for API DTO contracts')
const pureAdapterSources = {
  adapters,
  agentRoleAdapters,
  homeAdapters,
  executionResourceAdapters,
  organizationResourceAdapters,
  knowledgeResourceAdapters,
  governanceResourceAdapters,
  resourceItemAdapters,
  resourceSnapshotAdapter,
}
for (const name of pandaPureAdapterModuleNames) {
  const source = pureAdapterSources[name]
  assert(!source.includes('axios'), `Panda ${name} must stay pure and not import axios`)
  assert(!source.includes('react'), `Panda ${name} must stay pure and not import React`)
}

const apiContracts = read('src/panda/api/apiContracts.ts')
const homeApiContracts = read('src/panda/api/homeApiContracts.ts')
const executionApiContracts = read('src/panda/api/executionApiContracts.ts')
const organizationApiContracts = read('src/panda/api/organizationApiContracts.ts')
const knowledgeApiContracts = read('src/panda/api/knowledgeApiContracts.ts')
const governanceApiContracts = read('src/panda/api/governanceApiContracts.ts')
const resourceApiContracts = read('src/panda/api/resourceApiContracts.ts')
const snapshotApiContracts = read('src/panda/api/snapshotApiContracts.ts')
for (const symbol of pandaHomeApiContractSymbols) {
  assert(homeApiContracts.includes(`type ${symbol}`), `Missing Panda home API contract type: ${symbol}`)
}
assert(homeApiContracts.includes('agent_activity?: readonly ApiWorkbenchActivityItem[]'), 'ApiWorkbenchHome agent_activity must be readonly API input')
assert(homeApiContracts.includes('workflow_runs?: readonly ApiWorkbenchWorkflowRun[]'), 'ApiWorkbenchHome workflow_runs must be readonly API input')
for (const symbol of pandaExecutionApiContractSymbols) {
  assert(executionApiContracts.includes(`type ${symbol}`), `Missing Panda execution API contract type: ${symbol}`)
  assert(resourceApiContracts.includes(symbol), `Missing Panda resource API compatibility export: ${symbol}`)
}
for (const symbol of pandaOrganizationApiContractSymbols) {
  assert(organizationApiContracts.includes(`type ${symbol}`), `Missing Panda organization API contract type: ${symbol}`)
  assert(resourceApiContracts.includes(symbol), `Missing Panda resource API compatibility export: ${symbol}`)
}
assert(organizationApiContracts.includes('permissions?: readonly string[]'), 'ApiAgentProfile permissions must be readonly API input')
for (const symbol of pandaKnowledgeApiContractSymbols) {
  assert(knowledgeApiContracts.includes(`type ${symbol}`), `Missing Panda knowledge API contract type: ${symbol}`)
  assert(resourceApiContracts.includes(symbol), `Missing Panda resource API compatibility export: ${symbol}`)
}
for (const symbol of pandaGovernanceApiContractSymbols) {
  assert(governanceApiContracts.includes(`type ${symbol}`), `Missing Panda governance API contract type: ${symbol}`)
  assert(resourceApiContracts.includes(symbol), `Missing Panda resource API compatibility export: ${symbol}`)
}
for (const symbol of pandaSnapshotApiContractSymbols) {
  assert(snapshotApiContracts.includes(`type ${symbol}`), `Missing Panda snapshot API contract type: ${symbol}`)
}
for (const symbol of pandaApiContractBarrelSymbols) {
  assert(apiContracts.includes(symbol), `Missing Panda API contract compatibility export: ${symbol}`)
}
assert(apiContracts.includes("from './homeApiContracts'"), 'Panda apiContracts.ts must re-export home API contracts for compatibility')
assert(apiContracts.includes("from './resourceApiContracts'"), 'Panda apiContracts.ts must re-export resource API contracts for compatibility')
assert(apiContracts.includes("from './snapshotApiContracts'"), 'Panda apiContracts.ts must re-export snapshot API contracts for compatibility')
assert(resourceApiContracts.includes("from './executionApiContracts'"), 'Panda resourceApiContracts.ts must re-export execution API contracts for compatibility')
assert(resourceApiContracts.includes("from './organizationApiContracts'"), 'Panda resourceApiContracts.ts must re-export organization API contracts for compatibility')
assert(resourceApiContracts.includes("from './knowledgeApiContracts'"), 'Panda resourceApiContracts.ts must re-export knowledge API contracts for compatibility')
assert(resourceApiContracts.includes("from './governanceApiContracts'"), 'Panda resourceApiContracts.ts must re-export governance API contracts for compatibility')
for (const apiKey of pandaApiSnapshotResourceKeys) {
  assert(snapshotApiContracts.includes(`${apiKey}?:`), `Panda API contracts must expose resource key: ${apiKey}`)
}
assert(snapshotApiContracts.includes('tasks?: readonly ApiTaskSummary[]'), 'ApiPandaResourceSnapshot task resources must be readonly API input')
assert(snapshotApiContracts.includes('agents?: readonly ApiAgentProfile[]'), 'ApiPandaResourceSnapshot agent resources must be readonly API input')
assert(snapshotApiContracts.includes('settings_sections?: readonly ApiSettingsSection[]'), 'ApiPandaResourceSnapshot settings resources must be readonly API input')
assert(homeApiContracts.includes("from './runtimeMapping'"), 'Panda home API contracts must reuse ApiTone from runtimeMapping')
const resourceApiContractSources = {
  executionApiContracts,
  organizationApiContracts,
  knowledgeApiContracts,
  governanceApiContracts,
}
for (const name of pandaRuntimeAdapterModuleNames.map((item) => item.replace('ResourceAdapters', 'ApiContracts'))) {
  const source = resourceApiContractSources[name]
  assert(source.includes("from './runtimeMapping'"), `Panda ${name} must reuse ApiTone from runtimeMapping`)
}
const runtimeMetadataContractSources = {
  homeApiContracts,
  executionApiContracts,
  organizationApiContracts,
  knowledgeApiContracts,
  governanceApiContracts,
}
for (const [name, expectedCount] of pandaRuntimeMetadataContractSources) {
  const source = runtimeMetadataContractSources[name]
  assert(source.includes('ApiRuntimeMetadata'), `Panda ${name} must import shared ApiRuntimeMetadata`)
  const usageCount = (source.match(/& ApiRuntimeMetadata/g) ?? []).length
  assert(usageCount === expectedCount, `Panda ${name} must attach ApiRuntimeMetadata to ${expectedCount} resource contract types`)
}
assert(!apiContracts.includes('axios'), 'Panda API contracts must stay pure and not import axios')
assert(!apiContracts.includes('react'), 'Panda API contracts must stay pure and not import React')

const runtimeMapping = read('src/panda/api/runtimeMapping.ts')
for (const symbol of pandaRuntimeMappingSymbols) {
  assert(runtimeMapping.includes(symbol), `Missing Panda runtime mapping symbol: ${symbol}`)
}
for (const apiField of pandaRuntimeApiFieldNames) {
  assert(runtimeMapping.includes(apiField), `Panda runtime mapping must preserve API field: ${apiField}`)
}
assert(runtimeMapping.includes('evidence_refs?: readonly string[]'), 'ApiRuntimeMetadata evidence_refs must accept readonly evidence refs')
assert(governanceApiContracts.includes('evidence_refs?: readonly string[]'), 'ApiAuditEvent evidence_refs must accept readonly evidence refs')
assert(runtimeMapping.includes('evidenceRefs: Array.isArray(item.evidence_refs) ? [...item.evidence_refs] : []'), 'Runtime metadata mapping must copy evidence refs into display view models')
assert(governanceResourceAdapters.includes('evidenceRefs: Array.isArray(item.evidence_refs) ? [...item.evidence_refs] : []'), 'Audit event mapping must copy evidence refs into display view models')
assert(runtimeMapping.includes("tone === 'success'"), 'Panda runtime mapping must preserve known status tones')
assert(runtimeMapping.includes(": 'neutral'"), 'Panda runtime mapping must fall back unknown tones to neutral')
assert(runtimeMapping.includes('Number.isNaN(progress)'), 'Panda runtime mapping must guard NaN progress')
assert(!runtimeMapping.includes('axios'), 'Panda runtime mapping must stay pure and not import axios')
assert(!runtimeMapping.includes('react'), 'Panda runtime mapping must stay pure and not import React')

const adapterFixtures = read('src/panda/api/adapterFixtures.ts')
const adapterOutputFixtures = read('src/panda/api/adapterOutputFixtures.ts')
const resourceSnapshotFixtures = read('src/panda/api/resourceSnapshotFixtures.ts')
const resourceRuntimeFixtures = read('src/panda/api/resourceRuntimeFixtures.ts')
const resourceAdapterFixtures = read('src/panda/api/resourceAdapterFixtures.ts')
const resourceDryRunFixtures = read('src/panda/api/resourceDryRunFixtures.ts')
const homeActivityFixtures = read('src/panda/api/homeActivityFixtures.ts')
const resourceClientFixtures = read('src/panda/api/resourceClientFixtures.ts')
for (const source of pandaAdapterFixtureBarrelSources) {
  assert(adapterFixtures.includes(`from '${source}'`), `Adapter fixtures barrel must re-export ${source}`)
}
assert(!adapterFixtures.includes('export const '), 'Adapter fixtures must remain a compatibility barrel without owning fixtures')
assert(!adapterFixtures.includes("from './resourcesClient'"), 'Adapter fixtures must not depend on the compatibility resourcesClient entrypoint')
for (const symbol of pandaAdapterOutputFixtureSymbols) {
  assert(adapterOutputFixtures.includes(symbol), `Adapter output fixtures must cover adapter output mapping: ${symbol}`)
}
for (const symbol of pandaResourceSnapshotFixtureSymbols) {
  assert(resourceSnapshotFixtures.includes(symbol), `Resource snapshot fixtures must cover resource snapshot mapping: ${symbol}`)
}
assert(
  ((resourceDryRunFixtures.match(/\.\.\.runtimeFixture\(/g) ?? []).length + (homeActivityFixtures.match(/\.\.\.runtimeFixture\(/g) ?? []).length) === resourceBoundaryApiKeysForManifest.length + 1,
  'Resource snapshot fixtures must build aggregate resources and home activity runtime metadata through runtimeFixture',
)
for (const symbol of pandaResourceClientFixtureSymbols) {
  assert(resourceClientFixtures.includes(symbol), `Resource client fixtures must cover resource client mapping: ${symbol}`)
}
assert(resourceSnapshotFixtures.includes("from './resourceSnapshotTypes'"), 'Resource snapshot fixtures must import Panda resource snapshot types from resourceSnapshotTypes')
assert(resourceSnapshotFixtures.includes("from './resourcesValidation'"), 'Resource snapshot fixtures must import resource validation contracts from resourcesValidation')
assert(resourceSnapshotFixtures.includes("from './adapters'"), 'Resource snapshot fixtures must import snapshot mapping from adapters')
assert(resourceSnapshotFixtures.includes("from './resourceAdapterFixtures'"), 'Resource snapshot fixtures must preserve the adapter fixture compatibility export')
assert(resourceSnapshotFixtures.includes("from './resourceDryRunFixtures'"), 'Resource snapshot fixtures must preserve the aggregate dry-run fixture compatibility export')
assert(resourceSnapshotFixtures.includes("from './homeActivityFixtures'"), 'Resource snapshot fixtures must preserve the home activity fixture compatibility export')
assert(resourceRuntimeFixtures.includes('export function runtimeFixture'), 'Resource runtime fixtures must own the shared runtime fixture helper')
assert(resourceRuntimeFixtures.includes("NonNullable<ApiRuntimeMetadata['risk_level']>"), 'Resource runtime fixture helper must type risk levels through ApiRuntimeMetadata')
assert(resourceAdapterFixtures.includes('apiResourceSnapshotFixture: ApiPandaResourceSnapshot'), 'API resource snapshot fixture must expose the readonly DTO type')
assert(resourceDryRunFixtures.includes('aggregateResourcesBffDryRunFixture: ApiPandaResourceSnapshot'), 'Aggregate BFF dry-run fixture must expose the readonly DTO type')
assert(homeActivityFixtures.includes('satisfies ApiWorkbenchActivityItem'), 'Home activity dry-run fixture must satisfy the home activity DTO type')
assert(resourceClientFixtures.includes("from './resourceFallbackSnapshot'"), 'Resource client fixtures must import static fallback resources from resourceFallbackSnapshot')
assert(resourceClientFixtures.includes("from './resourcesApiLoader'"), 'Resource client fixtures must import resource API loader contracts from resourcesApiLoader')
assert(resourceClientFixtures.includes("from './resourcesHttpClient'"), 'Resource client fixtures must import fetch client contracts from resourcesHttpClient')
assert(!resourceClientFixtures.includes("from './resourcesClient'"), 'Resource client fixtures must not depend on the compatibility resourcesClient entrypoint')
assert(resourceClientFixtures.includes("endpoint: resolvePandaResourcesEndpoint('')"), 'Resource client fixtures must cover default endpoint normalization')
for (const apiKey of pandaApiSnapshotResourceKeys) {
  assert(resourceAdapterFixtures.includes(`${apiKey}:`) || resourceDryRunFixtures.includes(`${apiKey}:`), `Adapter resource snapshot fixtures missing API key: ${apiKey}`)
}

const types = read('src/panda/types.ts')
const routeTypes = read('src/panda/types/routeTypes.ts')
const runtimeTypes = read('src/panda/types/runtimeTypes.ts')
const agentRoleTypesForBarrel = read('src/panda/types/agentRoleTypes.ts')
const resourceTypes = read('src/panda/types/resourceTypes.ts')
const executionResourceTypes = read('src/panda/types/executionResourceTypes.ts')
const organizationResourceTypes = read('src/panda/types/organizationResourceTypes.ts')
const knowledgeResourceTypes = read('src/panda/types/knowledgeResourceTypes.ts')
const governanceResourceTypes = read('src/panda/types/governanceResourceTypes.ts')
const workbenchTypes = read('src/panda/types/workbenchTypes.ts')
for (const source of pandaTypeBarrelSources) {
  assert(types.includes(`from '${source}'`), `types.ts must preserve compatibility exports from ${source}`)
}
assert(!types.includes('export type PandaPage ='), 'types.ts must remain a compatibility barrel without owning route types')
assert(!types.includes('export type RuntimeMetadata ='), 'types.ts must remain a compatibility barrel without owning runtime types')
for (const typeName of pandaRouteTypeNames) {
  assert(routeTypes.includes(`type ${typeName}`), `Missing Panda route/UI type: ${typeName}`)
}
for (const typeName of pandaRuntimeTypeNames) {
  assert(runtimeTypes.includes(`type ${typeName}`), `Missing Panda runtime type: ${typeName}`)
}
for (const typeName of pandaAgentRoleTypeNames) {
  assert(agentRoleTypesForBarrel.includes(`type ${typeName}`), `Missing Panda agent role type: ${typeName}`)
}
const focusedResourceTypeSources = {
  executionResourceTypes,
  organizationResourceTypes,
  knowledgeResourceTypes,
  governanceResourceTypes,
}
const focusedResourceTypeOwnership = {
  executionResourceTypes: ['TaskSummary', 'ThreadItem', 'WorkflowItem', 'WorkflowNode'],
  organizationResourceTypes: ['AgentProfile', 'ProjectItem'],
  knowledgeResourceTypes: ['DataSource', 'KnowledgeSource', 'ToolCapability'],
  governanceResourceTypes: ['AuditEvent', 'AutomationRule', 'SettingsSection'],
}
for (const typeName of pandaResourceViewModelTypeNames) {
  assert(resourceTypes.includes(typeName), `resourceTypes compatibility barrel missing Panda resource view model type: ${typeName}`)
}
assert(resourceTypes.includes("from './executionResourceTypes'"), 'resourceTypes must preserve execution resource compatibility exports')
assert(resourceTypes.includes("from './organizationResourceTypes'"), 'resourceTypes must preserve organization resource compatibility exports')
assert(resourceTypes.includes("from './knowledgeResourceTypes'"), 'resourceTypes must preserve knowledge resource compatibility exports')
assert(resourceTypes.includes("from './governanceResourceTypes'"), 'resourceTypes must preserve governance resource compatibility exports')
assert(!resourceTypes.includes('import type { StatusTone'), 'resourceTypes must not own focused resource view-model implementations')
for (const [sourceName, typeNames] of Object.entries(focusedResourceTypeOwnership)) {
  const source = focusedResourceTypeSources[sourceName]
  for (const typeName of typeNames) {
    assert(source.includes(`type ${typeName}`), `${sourceName} missing Panda resource view model type: ${typeName}`)
  }
}
assert(organizationResourceTypes.includes('permissions: readonly string[]'), 'AgentProfile permissions must be readonly display data')
assert(governanceResourceTypes.includes('evidenceRefs: readonly string[]'), 'AuditEvent evidenceRefs must be readonly display data')
for (const typeName of pandaWorkbenchTypeNames) {
  assert(workbenchTypes.includes(`type ${typeName}`), `Missing Panda workbench view model type: ${typeName}`)
}
assert(workbenchTypes.includes('runtime?: RuntimeMetadata'), 'ActivityItem must carry optional runtime metadata for right rail activity evidence')
assert(workbenchTypes.includes('agentActivity: readonly ActivityItem[]'), 'PandaWorkbenchHome agentActivity must be readonly display data')
assert(workbenchTypes.includes('workflowRuns: readonly WorkflowItem[]'), 'PandaWorkbenchHome workflowRuns must be readonly display data')
for (const runtimeField of pandaRuntimeViewFieldNames) {
  assert(runtimeTypes.includes(runtimeField), `RuntimeMetadata missing field: ${runtimeField}`)
}
assert(runtimeTypes.includes('evidenceRefs: readonly string[]'), 'RuntimeMetadata evidenceRefs must be readonly for display-only evidence refs')

const navigationSource = read('src/panda/data/navigation.ts')
for (const pageId of pageIds) {
  assert(navigationSource.includes(`id: '${pageId}'`), `Missing nav item for page: ${pageId}`)
}
assert(navigationSource.includes("pandaLogoSrc = '/assets/panda-agent-logo.png'"), 'Panda navigation constants must expose the product logo asset')
assert(navigationSource.includes('navItems: readonly NavItem[]'), 'Panda navigation items must be readonly static chrome data')
assert(navigationSource.includes('toneLabel: Record<StatusTone, string>'), 'Panda navigation constants must expose status tone labels')
assert(!navigationSource.includes('mockWorkbenchHome'), 'Panda navigation constants must stay independent from mock workspace data')
assert(!navigationSource.includes('PandaWorkbenchHome'), 'Panda navigation constants must not import workbench mock view models')

const homeActionContent = read('src/panda/data/homeActionContent.ts')
const moduleFallbackContent = read('src/panda/data/moduleFallbackContent.ts')
const modulePageTypes = read('src/panda/data/modulePageTypes.ts')
const modulePageActions = read('src/panda/data/modulePageActions.tsx')
const modulePageContentCatalog = read('src/panda/data/modulePageContentCatalog.tsx')
const modulePageContent = read('src/panda/data/modulePageContent.tsx')
const homeContent = read('src/panda/data/homeContent.ts')
for (const symbol of pandaHomeContentSymbols) {
  assert(homeContent.includes(symbol), `homeContent must preserve compatibility export: ${symbol}`)
}
for (const symbol of pandaHomeActionContentSymbols) {
  assert(homeActionContent.includes(`export const ${symbol}`), `homeActionContent must own home action content: ${symbol}`)
  assert(homeActionContent.includes(`export const ${symbol}: readonly`), `homeActionContent must expose readonly content data: ${symbol}`)
}
for (const symbol of pandaModuleFallbackContentSymbols) {
  assert(moduleFallbackContent.includes(`export const ${symbol}`), `moduleFallbackContent must own module fallback content: ${symbol}`)
  assert(moduleFallbackContent.includes(`export const ${symbol}: readonly`), `moduleFallbackContent must expose readonly fallback content: ${symbol}`)
}
assert(moduleFallbackContent.includes('getModuleFallbackMeta'), 'moduleFallbackContent must own fallback metadata lookup')
assert(moduleFallbackContent.includes('new Map<PandaPage, ModuleCard>'), 'moduleFallbackContent must index module cards by page')
assert(moduleFallbackContent.includes('new Map<PandaPage, (typeof navItems)[number]>'), 'moduleFallbackContent must index navigation items by page')
assert(moduleFallbackContent.includes("from './navigation'"), 'moduleFallbackContent must own navigation fallback lookup')
for (const symbol of pandaModulePageContentSymbols) {
  assert(modulePageContent.includes(symbol), `modulePageContent must preserve module page content export: ${symbol}`)
}
assert(routeTypes.includes("PandaStandardModulePage = Exclude<PandaPage, 'home' | 'threads'>"), 'Panda route types must define the standard module page subset')
assert(modulePageContent.includes("from './modulePageTypes'"), 'modulePageContent must preserve compatibility exports from modulePageTypes')
assert(modulePageContent.includes("from './modulePageActions'"), 'modulePageContent must preserve compatibility exports from modulePageActions')
assert(modulePageContent.includes("from './modulePageContentCatalog'"), 'modulePageContent must preserve compatibility exports from modulePageContentCatalog')
assert(modulePageTypes.includes("import type { PandaStandardModulePage }"), 'modulePageTypes must import the standard module page subset')
assert(modulePageTypes.includes('page: PandaStandardModulePage'), 'ModulePageContent must bind content pages to the standard module page subset')
assert(modulePageTypes.includes('actions: readonly ModulePageAction[]'), 'ModulePageContent actions must be readonly')
assert(modulePageActions.includes('): readonly ModulePageAction[]'), 'moduleActions must return readonly action arrays')
assert(modulePageContentCatalog.includes('Record<PandaStandardModulePage, ModulePageContent>'), 'pandaModulePageContent must cover exactly the standard module page set')
assert(!modulePageContentCatalog.includes('Record<string, ModulePageContent>'), 'pandaModulePageContent must not weaken coverage to arbitrary string keys')
assert(
  (modulePageContentCatalog.match(/actions: moduleActions/g) ?? []).length === Object.keys(pandaModulePageResourceHookByPage).length,
  'modulePageContent must build every standard module action pair through moduleActions',
)
assert(homeContent.includes("from './homeActionContent'"), 'homeContent must re-export focused home action content')
assert(homeContent.includes("from './moduleFallbackContent'"), 'homeContent must re-export focused module fallback content')
assert(!homeContent.includes('export const '), 'homeContent must remain a compatibility barrel without owning content arrays')
assert(!homeContent.includes('mockWorkbenchHome'), 'homeContent must not own the home API fallback')
assert(!homeContent.includes('export const projects'), 'homeContent must stay independent from resource mock arrays')

const mockHome = read('src/panda/data/mockHome.ts')
assert(mockHome.includes('export const mockWorkbenchHome'), 'mockHome must own the home workbench fallback')
assert(mockHome.includes("from './homeContent'"), 'mockHome must compose home activity fallback from homeContent')
assert(mockHome.includes("from './mockResources'"), 'mockHome must compose workflow fallback from mockResources')
assert(!mockHome.includes('quickActions'), 'mockHome must not own home UI action content')
assert(!mockHome.includes('export const projects'), 'mockHome must not own resource mock arrays')

const navSource = read('src/panda/data/mockWorkspace.ts')
assert(navSource.includes("export { navItems, pandaLogoSrc, toneLabel } from './navigation'"), 'mockWorkspace must preserve compatibility exports for navigation constants')
assert(navSource.includes("export { activities, capabilityRows, moduleCards, promptActions, quickActions } from './homeContent'"), 'mockWorkspace must preserve compatibility exports for home content')
assert(navSource.includes("export { mockWorkbenchHome } from './mockHome'"), 'mockWorkspace must preserve compatibility exports for the home fallback')
assert(navSource.includes("} from './mockResources'"), 'mockWorkspace must preserve compatibility exports for resource mock data')
assert(navSource.includes('mockWorkbenchHome'), 'mockWorkbenchHome fallback must exist')
assert(!navSource.includes('export const '), 'mockWorkspace must remain a compatibility barrel without owning mock data')
for (const resourceSymbol of pandaMockWorkspaceResourceSymbols) {
  assert(!navSource.includes(`export const ${resourceSymbol}`), `mockWorkspace must not own resource mock data: ${resourceSymbol}`)
}

const mockResources = read('src/panda/data/mockResources.ts')
const mockExecutionResources = read('src/panda/data/mockExecutionResources.ts')
const mockKnowledgeResources = read('src/panda/data/mockKnowledgeResources.ts')
const mockOrganizationResources = read('src/panda/data/mockOrganizationResources.ts')
for (const resourceSymbol of pandaMockExecutionResourceSymbols) {
  assert(mockExecutionResources.includes(`export const ${resourceSymbol}`), `mockExecutionResources must own execution mock data: ${resourceSymbol}`)
  assert(mockExecutionResources.includes(`export const ${resourceSymbol}: readonly`), `mockExecutionResources must expose readonly execution mock data: ${resourceSymbol}`)
}
for (const resourceSymbol of pandaMockKnowledgeResourceSymbols) {
  assert(mockKnowledgeResources.includes(`export const ${resourceSymbol}`), `mockKnowledgeResources must own knowledge/tool/data mock data: ${resourceSymbol}`)
  assert(mockKnowledgeResources.includes(`export const ${resourceSymbol}: readonly`), `mockKnowledgeResources must expose readonly knowledge/tool/data mock data: ${resourceSymbol}`)
}
for (const resourceSymbol of pandaMockOrganizationResourceSymbols) {
  assert(mockOrganizationResources.includes(`export const ${resourceSymbol}`), `mockOrganizationResources must own organization mock data: ${resourceSymbol}`)
  assert(mockOrganizationResources.includes(`export const ${resourceSymbol}: readonly`), `mockOrganizationResources must expose readonly organization mock data: ${resourceSymbol}`)
}
for (const source of pandaMockResourceBarrelSources) {
  assert(mockResources.includes(`from '${source}'`), `mockResources must preserve compatibility exports from ${source}`)
}
assert(!mockResources.includes('export const '), 'mockResources must remain a compatibility barrel without owning resource arrays')
assert(!mockResources.includes('mockWorkbenchHome'), 'mockResources must not own the home workbench fallback')

assert(resourceFallbackSnapshot.includes("from '../data/mockResources'"), 'resourceFallbackSnapshot must read resource fallback data from mockResources')
assert(!resourceFallbackSnapshot.includes("from '../data/mockWorkspace'"), 'resourceFallbackSnapshot must not depend on home mock workspace data')
assert(!resourcesClient.includes("from '../data/mockWorkspace'"), 'resourcesClient must not depend on home mock workspace data')
const homePage = read('src/panda/pages/HomePage.tsx')
const homeTaskComposer = read('src/panda/components/homeTaskComposer.tsx')
const homeActionSections = read('src/panda/components/homeActionSections.tsx')
const homeNavigationSections = read('src/panda/components/homeNavigationSections.tsx')
const homeProjectSections = read('src/panda/components/homeProjectSections.tsx')
const homeProjectSectionsViewModel = read('src/panda/components/homeProjectSectionsViewModel.ts')
const homeStatusSections = read('src/panda/components/homeStatusSections.tsx')
const homeStatusSectionsViewModel = read('src/panda/components/homeStatusSectionsViewModel.ts')
const homeSections = read('src/panda/components/homeSections.tsx')
assert(homePage.includes("from '../components/homeSections'"), 'HomePage must compose stateless home UI sections from homeSections')
assert(!homePage.includes("from '../data/homeContent'"), 'HomePage must not render home content data directly')
assert(!homePage.includes("from '../data/mockWorkspace'"), 'HomePage must not depend on the compatibility mockWorkspace barrel')
assert(!homePage.includes('lucide-react'), 'HomePage must keep home action icons inside homeSections')
assert(homeSections.includes("from './homeProjectSections'"), 'homeSections must re-export home project sections for compatibility')
assert(homeSections.includes("from './homeStatusSections'"), 'homeSections must re-export home status sections for compatibility')
assert(homeSections.includes('RecentProjects'), 'homeSections must preserve compatibility export for RecentProjects')
assert(homeSections.includes('PlatformSnapshot'), 'homeSections must preserve compatibility export for PlatformSnapshot')
assert(homeProjectSections.includes('export function RecentProjects'), 'homeProjectSections must own the RecentProjects component')
assert(homeStatusSections.includes('export function PlatformSnapshot'), 'homeStatusSections must own the PlatformSnapshot component')
for (const symbol of pandaHomePageComponentSymbols) {
  assert(homePage.includes(symbol), `HomePage must compose home component: ${symbol}`)
}
for (const symbol of pandaHomeActionComponentSymbols) {
  assert(homeSections.includes(symbol), `homeSections must preserve compatibility export for home action component: ${symbol}`)
  assert(homePage.includes(symbol), `HomePage must compose home action component: ${symbol}`)
}
assert(homeTaskComposer.includes('export function TaskComposer'), 'homeTaskComposer must own the TaskComposer component')
assert(homeTaskComposer.includes('export type TaskComposerProps'), 'homeTaskComposer must own TaskComposer props')
assert(homeActionSections.includes("from './homeTaskComposer'"), 'homeActionSections must preserve compatibility exports from homeTaskComposer')
assert(homeActionSections.includes("from './homeNavigationSections'"), 'homeActionSections must preserve compatibility exports from homeNavigationSections')
assert(homeActionSections.includes('export function PromptActionRow'), 'homeActionSections must own the prompt action row')
assert(!homeActionSections.includes('export function QuickActionGrid'), 'homeActionSections must keep quick navigation grids in homeNavigationSections')
assert(!homeActionSections.includes('export function ModuleCardGrid'), 'homeActionSections must keep module navigation grids in homeNavigationSections')
for (const symbol of ['QuickActionGrid', 'ModuleCardGrid']) {
  assert(homeNavigationSections.includes(`export function ${symbol}`), `homeNavigationSections must own home navigation component: ${symbol}`)
}
assert(homeSections.includes("from './homeActionSections'"), 'homeSections must re-export home action sections for compatibility')
assert(homeSections.includes("from './homeTaskComposer'"), 'homeSections must re-export home task composer for compatibility')
assert(!homeSections.includes("from '../data/homeContent'"), 'homeSections must not own home action content imports after extraction')
assert(homeActionSections.includes("from '../data/homeActionContent'"), 'homeActionSections must import home actions from homeActionContent')
assert(!homeActionSections.includes("from '../data/homeContent'"), 'homeActionSections must not depend on the compatibility homeContent barrel')
assert(homeNavigationSections.includes("from '../data/homeActionContent'"), 'homeNavigationSections must import quick actions from homeActionContent')
assert(homeNavigationSections.includes("from '../data/moduleFallbackContent'"), 'homeNavigationSections must import module cards from moduleFallbackContent')
assert(!homeNavigationSections.includes("from '../data/homeContent'"), 'homeNavigationSections must not depend on the compatibility homeContent barrel')
assert(homeNavigationSections.includes("from '../types'"), 'homeNavigationSections must type navigation callbacks with PandaPage')
assert(homeNavigationSections.includes('NavigationCardGrid'), 'homeNavigationSections must render quick/module card grids through shared NavigationCardGrid')
assert(homeNavigationSections.includes('ModuleSummaryCard'), 'homeNavigationSections must render module card bodies through shared ModuleSummaryCard')
assert(!homeActionSections.includes('<section className="panda-module-grid">'), 'homeActionSections must not duplicate the raw module grid shell')
assert(!homeNavigationSections.includes('<section className="panda-module-grid">'), 'homeNavigationSections must not duplicate the raw module grid shell')
assert(!homeSections.includes("from '../state/PandaWorkspaceContext'"), 'homeSections must keep resource selector imports inside homeProjectSections')
assert(!homeSections.includes("from '../api/workbenchClient'"), 'homeSections must keep home BFF source typing inside homeStatusSections')
assert(homeProjectSections.includes("from '../state/PandaWorkspaceContext'"), 'homeProjectSections must own home resource selector imports')
assert(homeStatusSections.includes("from '../api/workbenchClient'"), 'homeStatusSections must own home BFF source typing')
assert(homeStatusSections.includes("from './homeStatusSectionsViewModel'"), 'homeStatusSections must import its focused metric view model')
assert(homeStatusSections.includes('buildPlatformSnapshotViewModel({ home, source, isLoading, error })'), 'PlatformSnapshot must delegate status display data to its view model')
assert(homeStatusSections.includes('snapshot.metricRows.map'), 'PlatformSnapshot must render metric rows from its view model')
assert(!homeStatusSections.includes('当前展示本地演示数据，等待后端主线收尾后切换真实资源'), 'PlatformSnapshot must not inline fallback error copy')
assert(!homeStatusSections.includes("home?.summary ?? '企业级自主智能体框架"), 'PlatformSnapshot must not inline summary fallback copy')
assert(homeStatusSectionsViewModel.includes('PandaWorkbenchMetrics'), 'home status view model must type metrics with PandaWorkbenchMetrics')
assert(homeStatusSectionsViewModel.includes('buildPlatformSnapshotViewModel'), 'home status view model must own the PlatformSnapshot display view model')
for (const metricField of ['activeAgents', 'runningWorkflows', 'pendingApprovals', 'apiCalls', 'storageUsed']) {
  assert(homeStatusSectionsViewModel.includes(metricField), `home status view model must map metric field: ${metricField}`)
}
for (const fallbackValue of ['8', '5', '3', '12428', '45.2 GB / 1 TB']) {
  assert(homeStatusSectionsViewModel.includes(fallbackValue), `home status view model must preserve mock fallback value: ${fallbackValue}`)
}
for (const statusCopy of ['正在同步工作台', '正在读取首页聚合数据和执行态势。', '当前展示本地演示数据，等待后端主线收尾后切换真实资源。', 'Powered by X-Agent Autonomous Framework', '企业级自主智能体框架，覆盖编排、记忆、工具、审计和多渠道运行。']) {
  assert(homeStatusSectionsViewModel.includes(statusCopy), `home status view model must preserve platform status copy: ${statusCopy}`)
}
assert(homeTaskComposer.includes('aria-label="输入任务"'), 'TaskComposer must preserve the task input accessible label')
assert(homeTaskComposer.includes('aria-label="启动任务"'), 'TaskComposer must preserve the task launch accessible label')
assert(homeProjectSections.includes('usePandaWorkspaceResource'), 'RecentProjects must read project resources through the typed selector')
assert(homeProjectSections.includes('RuntimeMetaStrip'), 'RecentProjects must render project runtime metadata')
assert(homeProjectSections.includes('PandaResourceState'), 'RecentProjects must guard project loading/empty/error states')
assert(homeProjectSections.includes('WorkspaceTable'), 'RecentProjects must render project rows through shared WorkspaceTable')
assert(homeProjectSections.includes("from './homeProjectSectionsViewModel'"), 'RecentProjects must import its focused view model')
assert(homeProjectSections.includes('recentProjectsHeader.title'), 'RecentProjects must render its title from the view model')
assert(homeProjectSections.includes('recentProjectsHeader.actionLabel'), 'RecentProjects must render its action label from the view model')
assert(homeProjectSections.includes('recentProjectsResourceState.emptyTitle'), 'RecentProjects must render empty title from the view model')
assert(homeProjectSections.includes('recentProjectsResourceState.loadingTitle'), 'RecentProjects must render loading title from the view model')
assert(homeProjectSections.includes('columns={recentProjectsTableColumns}'), 'RecentProjects must render table columns from the view model')
assert(homeProjectSections.includes('buildRecentProjectTableRowViewModel(project)'), 'RecentProjects must build row display data through the view model')
assert(!homeProjectSections.includes('className="panda-table"'), 'RecentProjects must keep the shared table shell inside WorkspaceTable')
assert(!homeProjectSections.includes("emptyTitle=\"暂无最近项目\""), 'RecentProjects must not inline recent project empty title')
assert(!homeProjectSections.includes("loadingTitle=\"正在同步最近项目\""), 'RecentProjects must not inline recent project loading title')
assert(!homeProjectSections.includes("columns={['名称', '类型', '运行态']}"), 'RecentProjects must not inline table columns')
assert(homeProjectSectionsViewModel.includes('ProjectItem'), 'home project view model must type rows from ProjectItem resources')
assert(homeProjectSectionsViewModel.includes('export const recentProjectsHeader'), 'home project view model must own recent project header copy')
assert(homeProjectSectionsViewModel.includes("title: '最近项目'"), 'home project view model must own recent project title')
assert(homeProjectSectionsViewModel.includes("actionLabel: '查看全部 →'"), 'home project view model must own recent project action copy')
assert(homeProjectSectionsViewModel.includes('export const recentProjectsResourceState'), 'home project view model must own resource state copy')
assert(homeProjectSectionsViewModel.includes("emptyTitle: '暂无最近项目'"), 'home project view model must own recent project empty title')
assert(homeProjectSectionsViewModel.includes("loadingTitle: '正在同步最近项目'"), 'home project view model must own recent project loading title')
assert(homeProjectSectionsViewModel.includes("export const recentProjectsTableColumns = ['名称', '类型', '运行态'] as const"), 'home project view model must own recent project table columns')
assert(homeProjectSectionsViewModel.includes('buildRecentProjectTableRowViewModel'), 'home project view model must export row display builder')
for (const projectField of ['project.name', 'project.type', 'project.runtime', 'project.ownerAgent', 'project.updatedAt', 'project.risk']) {
  assert(homeProjectSectionsViewModel.includes(projectField), `home project view model must map project field: ${projectField}`)
}
assert(homeStatusSections.includes('PandaLoadingState'), 'PlatformSnapshot must render home loading state')
assert(homeStatusSections.includes('PandaErrorState'), 'PlatformSnapshot must render home API fallback error state')
assert(homeStatusSections.includes('WorkspacePanel'), 'PlatformSnapshot must render through shared WorkspacePanel')
assert(!homeStatusSections.includes('className="panda-card p-4"'), 'PlatformSnapshot must not duplicate the raw workspace panel shell')
assert(homeStatusSectionsViewModel.includes('Powered by X-Agent Autonomous Framework'), 'PlatformSnapshot view model must preserve the X-Agent core subtitle')
assert(!homePage.includes('usePandaWorkspaceResource'), 'HomePage must keep resource selectors inside homeSections')
assert(!homePage.includes('RuntimeMetaStrip'), 'HomePage must keep project runtime metadata rendering inside homeSections')
assert(!homePage.includes('PandaResourceState'), 'HomePage must keep project resource state rendering inside homeSections')
assert(!homePage.includes('PandaLoadingState'), 'HomePage must keep platform loading state inside homeSections')
assert(!homePage.includes('PandaErrorState'), 'HomePage must keep platform error state inside homeSections')
const modulePage = read('src/panda/pages/ModulePage.tsx')
const moduleFallback = read('src/panda/components/moduleFallback.tsx')
const moduleFallbackSurface = read('src/panda/components/moduleFallbackSurface.tsx')
const moduleDeliverySurface = read('src/panda/components/moduleDeliverySurface.tsx')
const moduleDeliverySurfaceViewModel = read('src/panda/components/moduleDeliverySurfaceViewModel.ts')
const pageContractPrimitives = read('src/panda/components/pageContractPrimitives.tsx')
const pageContractViewModel = read('src/panda/components/pageContractViewModel.ts')
const modulePagePrimitives = read('src/panda/components/modulePagePrimitives.tsx')
const modulePageActionPrimitives = read('src/panda/components/modulePageActionPrimitives.tsx')
assert(modulePage.includes("from '../data/moduleFallbackContent'"), 'ModulePage must import module content from moduleFallbackContent')
assert(modulePage.includes("from '../components/moduleFallback'"), 'ModulePage must compose fallback sections from moduleFallback')
assert(modulePage.includes('<ModuleFallbackWorkspace title={title} icon={Icon} capabilityRows={capabilityRows} onNavigate={onNavigate} />'), 'ModulePage must render ModuleFallbackWorkspace with module metadata')
assert(modulePage.includes('getModuleFallbackMeta(page)'), 'ModulePage must read fallback metadata through getModuleFallbackMeta')
assert(moduleFallback.includes('capabilityRows: readonly CapabilityRow[]'), 'ModuleFallbackWorkspace must accept readonly fallback capability rows')
assert(!modulePage.includes("from '../data/mockWorkspace'"), 'ModulePage must not depend on the compatibility mockWorkspace barrel')
assert(!modulePage.includes("from '../data/navigation'"), 'ModulePage must not own navigation fallback lookup')
assert(!modulePage.includes('moduleCards.find'), 'ModulePage must not search module cards during render')
assert(!modulePage.includes('navItems.find'), 'ModulePage must not search navigation during render')
assert(!modulePage.includes('PandaEmptyState'), 'ModulePage must keep fallback empty state inside moduleFallback')
assert(!modulePage.includes('panda-command-button'), 'ModulePage must keep fallback command actions inside moduleFallback')
assert(!modulePage.includes('panda-module-grid'), 'ModulePage must keep fallback capability cards inside moduleFallback')
assert(pageContractPrimitives.includes('buildPageContractViewModel'), 'PageContractStrip must delegate visible contract labels to pageContractViewModel')
assert(pageContractPrimitives.includes('contractView.statusLabel'), 'PageContractStrip must render status labels from the page contract view model')
assert(!pageContractPrimitives.includes('contract.runtimeFields.join'), 'PageContractStrip must not own runtime field label formatting')
assert(pageContractViewModel.includes('export function buildPageContractViewModel'), 'pageContractViewModel must own the page contract view model builder')
assert(pageContractViewModel.includes("contract.readiness === 'api-wired' ? 'API 已接入' : 'Mock 待对齐'"), 'pageContractViewModel must own readiness label mapping')
assert(pageContractViewModel.includes("source === 'api' ? '实时 API' : '本地演示数据'"), 'pageContractViewModel must own workspace source label mapping')
assert(pageContractViewModel.includes('runtimeFieldsLabel: contract.runtimeFields.join'), 'pageContractViewModel must own runtime field label formatting')
assert(pageContractViewModel.includes("refreshLabel: status === 'loading' ? '同步中' : refreshedAt"), 'pageContractViewModel must own refresh label formatting')
for (const symbol of pandaModuleFallbackComponentSymbols) {
  assert(moduleFallback.includes(symbol), `moduleFallback must preserve compatibility export for fallback component: ${symbol}`)
}
assert(moduleFallback.includes('export function ModuleFallbackWorkspace'), 'moduleFallback must own the ModuleFallbackWorkspace shell component')
for (const symbol of pandaModuleFallbackSurfaceSymbols) {
  assert(moduleFallbackSurface.includes(`export function ${symbol}`), `moduleFallbackSurface must own focused fallback component: ${symbol}`)
}
for (const symbol of pandaModuleDeliverySurfaceSymbols) {
  assert(moduleDeliverySurface.includes(`export function ${symbol}`), `moduleDeliverySurface must own focused delivery component: ${symbol}`)
}
for (const symbol of pandaModulePagePrimitiveSymbols) {
  assert(modulePagePrimitives.includes(symbol), `modulePagePrimitives must preserve focused module page export: ${symbol}`)
}
assert(moduleFallback.includes("import type { CapabilityRow, PandaPage }"), 'moduleFallback must type fallback props with CapabilityRow and PandaPage')
assert(moduleFallback.includes('PandaEmptyState'), 'moduleFallback must render the shared Panda empty state')
assert(moduleFallback.includes("from './moduleFallbackSurface'"), 'moduleFallback must preserve compatibility exports from moduleFallbackSurface')
assert(moduleFallbackSurface.includes("from './moduleDeliverySurface'"), 'moduleFallbackSurface must preserve compatibility exports from moduleDeliverySurface')
assert(moduleFallbackSurface.includes('panda-command-button'), 'moduleFallbackSurface must own the fallback command action')
assert(moduleFallbackSurface.includes('NavigationCardGrid'), 'moduleFallbackSurface must render fallback capability cards through shared NavigationCardGrid')
assert(moduleFallbackSurface.includes('ModuleSummaryCard'), 'moduleFallbackSurface must render fallback capability card bodies through shared ModuleSummaryCard')
assert(!moduleFallbackSurface.includes('<section className="panda-module-grid">'), 'moduleFallbackSurface must not duplicate the raw module grid shell')
assert(!moduleFallbackSurface.includes('export function ModuleDeliverySurface'), 'moduleFallbackSurface must keep delivery surface implementation in moduleDeliverySurface')
assert(moduleDeliverySurface.includes('模块交付面'), 'moduleDeliverySurface must render the module delivery surface')
assert(moduleDeliverySurface.includes('InsetInfoBlock'), 'moduleDeliverySurface must render delivery surface items through shared InsetInfoBlock')
assert(moduleDeliverySurface.includes("from './moduleDeliverySurfaceViewModel'"), 'moduleDeliverySurface must import its focused view model')
assert(moduleDeliverySurface.includes('moduleDeliverySurfaceItems.map'), 'moduleDeliverySurface must render delivery items from its view model')
assert(moduleDeliverySurfaceViewModel.includes('export const moduleDeliverySurfaceItems'), 'moduleDeliverySurfaceViewModel must export delivery surface rows')
assert(moduleDeliverySurfaceViewModel.includes('satisfies readonly ModuleDeliverySurfaceItem[]'), 'moduleDeliverySurfaceViewModel must type delivery rows as readonly items')
for (const label of ['总览', '管理', '详情', '历史/审计']) {
  assert(moduleDeliverySurfaceViewModel.includes(label), `moduleDeliverySurfaceViewModel must preserve delivery area: ${label}`)
}
assert(moduleDeliverySurfaceViewModel.includes('支持加载、错误、空状态和权限状态。'), 'moduleDeliverySurfaceViewModel must preserve delivery state support copy')
assert(!moduleDeliverySurface.includes('rounded-lg bg-white/[0.04] p-4'), 'moduleDeliverySurface must not duplicate raw inset info block styling')
assert(modulePagePrimitives.includes("from './modulePageActionPrimitives'"), 'modulePagePrimitives must preserve module page action compatibility exports')
assert(!modulePagePrimitives.includes('export function ModulePageActions'), 'modulePagePrimitives must keep ModulePageActions implementation in modulePageActionPrimitives')
assert(modulePageActionPrimitives.includes('export function ModulePageActions'), 'modulePageActionPrimitives must own ModulePageActions')
assert(modulePageActionPrimitives.includes('export type ModulePageAction'), 'modulePageActionPrimitives must own ModulePageAction')
assert(modulePageActionPrimitives.includes('<PageActionButton'), 'ModulePageActions must render shared heading action buttons')
assert(modulePagePrimitives.includes("import { PageHeading }"), 'modulePagePrimitives must compose shared page heading primitives')
assert(modulePagePrimitives.includes("import { PandaResourceState }"), 'modulePagePrimitives must compose shared resource state primitives')
assert(modulePagePrimitives.includes("import type { PandaPage, PandaStandardModulePage }"), 'modulePagePrimitives must type the standard module page shell boundary')
assert(modulePagePrimitives.includes("import { pandaModulePageContent }"), 'modulePagePrimitives must own shared module page content binding')
assert(modulePagePrimitives.includes('actions: readonly ModulePageAction[]'), 'ModuleResourcePage content actions must be readonly')
assert(modulePagePrimitives.includes('<PageHeading'), 'ModuleResourcePage must render the shared page heading')
assert(modulePagePrimitives.includes('<PandaResourceState'), 'ModuleResourcePage must guard empty/loading/error resource states')
assert(modulePagePrimitives.includes('<ModulePageActions actions={content.actions} />'), 'ModuleResourcePage must compose ModulePageActions for shared heading action buttons')
assert(modulePagePrimitives.includes('page: PandaStandardModulePage'), 'StandardModulePageShell must only accept standard module page ids')
assert(
  modulePagePrimitives.includes('<ModuleResourcePage content={pandaModulePageContent[page]} count={count} footer={footer}>'),
  'StandardModulePageShell must bind shared module page content through ModuleResourcePage',
)

const pageFiles = pandaPageFiles
const pageFileById = pandaPageFileById
for (const file of pageFiles) {
  const source = read(file)
  assert(!source.includes('../api/resourcesClient'), `${file} must read resources through PandaWorkspaceContext`)
}

for (const file of pageFiles.filter((file) => file.includes('/pages/'))) {
  const source = read(file)
  const resourceSelectorSource = file.endsWith('HomePage.tsx')
    ? homeProjectSections
    : file.endsWith('ThreadsPage.tsx')
      ? source
      : modulePageResourceHooks
  assert(resourceSelectorSource.includes('usePandaWorkspaceResource'), `${file} must compose a typed Panda resource selector boundary`)
  assert(!source.includes('usePandaWorkspace()'), `${file} must not consume the full Panda workspace context`)
}

for (const pageId of pageIds.filter((id) => !['home', 'threads'].includes(id))) {
  const source = read(pageFileById[pageId])
  const expectedResourceHook = pandaModulePageResourceHookByPage[pageId]
  assert(expectedResourceHook, `Panda verifier missing standard module resource hook mapping for page: ${pageId}`)
  assert(source.includes("import { StandardModulePageShell }"), `${pageId} page must compose through the shared StandardModulePageShell`)
  assert(!source.includes("from '../data/modulePageContent'"), `${pageId} page must leave shared module page content binding inside StandardModulePageShell`)
  assert(source.includes("from '../state/useModulePageResources'"), `${pageId} page must import focused module page resources hook`)
  assert(source.includes(expectedResourceHook), `${pageId} page must import its focused resource hook: ${expectedResourceHook}`)
  assert(source.includes(`const resources = ${expectedResourceHook}()`), `${pageId} page must read resources through ${expectedResourceHook}()`)
  assert(source.includes(`<StandardModulePageShell page="${pageId}" count={resources.count}`), `${pageId} page must pass its page id and count into StandardModulePageShell`)
  assert(modulePageContentCatalog.includes(`${pageId}: {`), `modulePageContentCatalog must define content for ${pageId}`)
  assert(!source.includes('usePandaWorkspaceResource'), `${pageId} page must keep resource key selection inside useModulePageResources`)
  assert(!source.includes('ModuleResourcePage'), `${pageId} page must keep ModuleResourcePage composition inside StandardModulePageShell`)
  assert(!source.includes('pandaModulePageContent'), `${pageId} page must keep module content selection inside StandardModulePageShell`)
  assert(!source.includes('PageHeading'), `${pageId} page must keep heading composition inside StandardModulePageShell`)
  assert(!source.includes('PageActionButton'), `${pageId} page must keep heading action buttons inside StandardModulePageShell`)
  assert(!source.includes('PandaResourceState'), `${pageId} page must keep resource state handling inside StandardModulePageShell`)
  assert(!source.includes('emptyTitle='), `${pageId} page must keep empty title copy inside modulePageContent`)
  assert(!source.includes('emptyDescription='), `${pageId} page must keep empty description copy inside modulePageContent`)
  assert(!source.includes('title="'), `${pageId} page must keep heading title copy inside modulePageContent`)
  assert(!source.includes('description="'), `${pageId} page must keep heading description copy inside modulePageContent`)
  assert(!source.includes('<button className="panda-command-button"'), `${pageId} page must not duplicate raw heading action buttons`)
}
const threadsPage = read('src/panda/pages/ThreadsPage.tsx')
const threadWorkspace = read('src/panda/components/threadWorkspace.tsx')
const threadWorkspaceViewModel = read('src/panda/components/threadWorkspaceViewModel.ts')
const threadExecutionWorkspace = read('src/panda/components/threadExecutionWorkspace.tsx')
const threadExecutionWorkspaceViewModel = read('src/panda/components/threadExecutionWorkspaceViewModel.ts')
const threadExecutionContent = read('src/panda/data/threadExecutionContent.ts')
const agentsPage = read('src/panda/pages/AgentsPage.tsx')
const agentOrganization = read('src/panda/components/agentOrganization.tsx')
const agentOrganizationViewModel = read('src/panda/components/agentOrganizationViewModel.ts')
const agentProfileCards = read('src/panda/components/agentProfileCards.tsx')
const agentProfileCardViewModel = read('src/panda/components/agentProfileCardViewModel.ts')
const agentRolePresetCards = read('src/panda/components/agentRolePresetCards.tsx')
const agentRolePresetDetail = read('src/panda/components/agentRolePresetDetail.tsx')
const agentRolePresetViewModel = read('src/panda/components/agentRolePresetViewModel.ts')
const agentRolePresetSelector = read('src/panda/components/agentRolePresetSelector.tsx')
const agentRoleTypes = read('src/panda/types/agentRoleTypes.ts')
const agentRolePortraits = read('src/panda/data/agentRolePortraits.ts')
const agentRolePresetFixtures = read('src/panda/data/agentRolePresetFixtures.ts')
const agentRolePresets = read('src/panda/data/agentRolePresets.ts')
const workflowsPage = read('src/panda/pages/WorkflowsPage.tsx')
const workflowCanvas = read('src/panda/components/workflowCanvas.tsx')
const workflowCanvasViewModel = read('src/panda/components/workflowCanvasViewModel.ts')
const tasksPage = read('src/panda/pages/TasksPage.tsx')
const taskQueue = read('src/panda/components/taskQueue.tsx')
const taskQueueViewModel = read('src/panda/components/taskQueueViewModel.ts')
const projectsPage = read('src/panda/pages/ProjectsPage.tsx')
const projectWorkspace = read('src/panda/components/projectWorkspace.tsx')
const projectWorkspaceViewModel = read('src/panda/components/projectWorkspaceViewModel.ts')
const auditPage = read('src/panda/pages/AuditPage.tsx')
const auditReplay = read('src/panda/components/auditReplay.tsx')
const auditReplayViewModel = read('src/panda/components/auditReplayViewModel.ts')
const automationPage = read('src/panda/pages/AutomationPage.tsx')
const automationRulesPanel = read('src/panda/components/automationRules.tsx')
const automationRulesViewModel = read('src/panda/components/automationRulesViewModel.ts')
const toolsPage = read('src/panda/pages/ToolsPage.tsx')
const toolCenter = read('src/panda/components/toolCenter.tsx')
const toolCenterViewModel = read('src/panda/components/toolCenterViewModel.ts')
const dataPage = read('src/panda/pages/DataPage.tsx')
const dataCenter = read('src/panda/components/dataCenter.tsx')
const dataCenterViewModel = read('src/panda/components/dataCenterViewModel.ts')
const knowledgePage = read('src/panda/pages/KnowledgePage.tsx')
const knowledgeBase = read('src/panda/components/knowledgeBase.tsx')
const knowledgeBaseViewModel = read('src/panda/components/knowledgeBaseViewModel.ts')
const settingsPage = read('src/panda/pages/SettingsPage.tsx')
const settingsCenter = read('src/panda/components/settingsCenter.tsx')
const settingsCenterViewModel = read('src/panda/components/settingsCenterViewModel.ts')
assert(threadsPage.includes("from '../components/threadWorkspace'"), 'ThreadsPage must compose thread workspace sections from threadWorkspace')
assert(threadsPage.includes('<ThreadListPanel threads={threads} />'), 'ThreadsPage must render ThreadListPanel with workspace threads')
assert(threadsPage.includes('<ThreadWorkPanel threads={threads} activeThread={activeThread} />'), 'ThreadsPage must render ThreadWorkPanel with active thread')
assert(!threadsPage.includes('lucide-react'), 'ThreadsPage must keep thread action icons inside threadWorkspace')
assert(!threadsPage.includes('PageContractStrip'), 'ThreadsPage must not own thread contract strip rendering directly')
assert(!threadsPage.includes('ExecutionStepRow'), 'ThreadsPage must not own execution timeline row rendering directly')
for (const symbol of pandaThreadWorkspaceSymbols) {
  assert(threadWorkspace.includes(`export function ${symbol}`), `threadWorkspace must export focused thread shell component: ${symbol}`)
}
assert(threadWorkspace.includes('threads: readonly ThreadItem[]'), 'threadWorkspace must accept readonly thread resources')
assert(threadWorkspace.includes("from './threadExecutionWorkspace'"), 'threadWorkspace must preserve compatibility exports from threadExecutionWorkspace')
assert(threadWorkspace.includes('ThreadExecutionWorkspace activeThread={activeThread}'), 'ThreadWorkPanel must compose ThreadExecutionWorkspace with the active thread')
assert(threadExecutionWorkspace.includes('export function ThreadExecutionWorkspace'), 'threadExecutionWorkspace must own the thread execution workspace component')
assert(threadWorkspace.includes("import type { ThreadItem }"), 'threadWorkspace must type thread props with ThreadItem')
assert(threadWorkspace.includes("from './threadWorkspaceViewModel'"), 'threadWorkspace must import its focused view model')
assert(threadWorkspace.includes('threadWorkspaceHeader.title'), 'threadWorkspace must render its title from the view model')
assert(threadWorkspace.includes('aria-label={threadWorkspaceHeader.newThreadLabel}'), 'threadWorkspace must render the new-thread accessible label from the view model')
assert(threadWorkspace.includes('threadWorkspaceResourceState.emptyTitle'), 'threadWorkspace must render empty title from the view model')
assert(threadWorkspace.includes('threadWorkspaceResourceState.emptyDescription'), 'threadWorkspace must render empty description from the view model')
assert(threadWorkspace.includes('buildThreadListItemViewModel(thread, index)'), 'threadWorkspace must build thread list row display data through the view model')
assert(!threadWorkspace.includes('线程工作区'), 'threadWorkspace must not inline the thread workspace title')
assert(!threadWorkspace.includes('aria-label="新建线程"'), 'threadWorkspace must not inline the new-thread aria label')
assert(!threadWorkspace.includes('emptyTitle="暂无执行线程"'), 'threadWorkspace must not inline the thread empty title')
assert(!threadWorkspace.includes('后续接入线程 BFF 后'), 'threadWorkspace must not inline the thread empty description')
assert(!threadWorkspace.includes('thread.project} · {thread.ownerAgent'), 'threadWorkspace must not inline thread subtitle composition')
assert(threadWorkspaceViewModel.includes('ThreadItem'), 'threadWorkspaceViewModel must type rows from ThreadItem resources')
assert(threadWorkspaceViewModel.includes('export const threadWorkspaceHeader'), 'threadWorkspaceViewModel must own thread workspace header copy')
assert(threadWorkspaceViewModel.includes("title: '线程工作区'"), 'threadWorkspaceViewModel must own the thread workspace title')
assert(threadWorkspaceViewModel.includes("newThreadLabel: '新建线程'"), 'threadWorkspaceViewModel must own the new-thread accessible label')
assert(threadWorkspaceViewModel.includes('export const threadWorkspaceResourceState'), 'threadWorkspaceViewModel must own thread resource-state copy')
assert(threadWorkspaceViewModel.includes("emptyTitle: '暂无执行线程'"), 'threadWorkspaceViewModel must own thread empty title')
assert(threadWorkspaceViewModel.includes("emptyDescription: '后续接入线程 BFF 后，这里会展示计划、终端、文件变更、产物和审计证据。'"), 'threadWorkspaceViewModel must own thread empty description')
assert(threadWorkspaceViewModel.includes('buildThreadListItemViewModel'), 'threadWorkspaceViewModel must export the thread row display builder')
for (const threadField of ['thread.id', 'thread.title', 'thread.project', 'thread.ownerAgent', 'thread.progress']) {
  assert(threadWorkspaceViewModel.includes(threadField), `threadWorkspaceViewModel must map thread field: ${threadField}`)
}
assert(threadWorkspace.includes('PageContractStrip page="threads"'), 'threadWorkspace must show the threads Panda page contract strip')
assert(threadWorkspace.includes('PandaResourceState'), 'threadWorkspace must guard thread empty/loading/error resource states')
assert(threadWorkspace.includes('ProgressMeter'), 'threadWorkspace must render thread progress meters')
assert(threadExecutionWorkspace.includes('panda-thread-execution-grid'), 'threadExecutionWorkspace must use the stable thread execution grid')
assert(threadExecutionWorkspace.includes('panda-thread-side-actions'), 'threadExecutionWorkspace must keep side actions inside a stable column')
assert(threadExecutionWorkspace.includes('ExecutionStepRow'), 'threadExecutionWorkspace must render execution timeline rows')
assert(threadExecutionWorkspace.includes('execution.actionPanels.map'), 'threadExecutionWorkspace must render execution action panels from its view model')
assert(threadExecutionWorkspace.includes("from './threadExecutionWorkspaceViewModel'"), 'threadExecutionWorkspace must delegate execution display mapping to its focused view model')
assert(!threadExecutionWorkspace.includes("from '../data/threadExecutionContent'"), 'threadExecutionWorkspace must not load thread execution fixtures directly')
assert(threadExecutionWorkspaceViewModel.includes('export function buildThreadExecutionWorkspaceViewModel'), 'threadExecutionWorkspaceViewModel must expose the thread execution mapping function')
assert(threadExecutionWorkspaceViewModel.includes('ThreadExecutionStepViewModel'), 'threadExecutionWorkspaceViewModel must type execution step rows')
assert(threadExecutionWorkspaceViewModel.includes('ThreadExecutionActionPanelViewModel'), 'threadExecutionWorkspaceViewModel must type execution action panels')
for (const symbol of ['threadExecutionTabs', 'threadExecutionSteps', 'threadExecutionTerminalLines', 'threadExecutionControlActions', 'threadExecutionArtifactActions']) {
  assert(threadExecutionContent.includes(`export const ${symbol}`), `threadExecutionContent must export ${symbol}`)
  assert(threadExecutionWorkspaceViewModel.includes(symbol), `threadExecutionWorkspaceViewModel must consume ${symbol} from threadExecutionContent`)
}
assert(!threadExecutionWorkspace.includes("const threadTabs ="), 'threadExecutionWorkspace must not inline thread tab fixtures')
assert(!threadExecutionWorkspace.includes("const executionSteps ="), 'threadExecutionWorkspace must not inline execution step fixtures')
assert(!threadExecutionWorkspace.includes("const terminalLines ="), 'threadExecutionWorkspace must not inline terminal output fixtures')
assert(!threadExecutionWorkspace.includes('index < 2'), 'threadExecutionWorkspace must not own execution completion derivation')
assert(workflowActionPrimitives.includes('PanelActionButton'), 'ActionPanel must render shared PanelActionButton actions')
assert(workflowActionPrimitives.includes('aria-label={`${group}：${label}`}'), 'PanelActionButton must provide contextual accessible labels')
assert(tasksPage.includes("from '../components/taskQueue'"), 'TasksPage must compose task queue sections from taskQueue')
assert(tasksPage.includes('<TaskQueueWorkspace tasks={resources.tasks} />'), 'TasksPage must render TaskQueueWorkspace with workspace tasks')
assert(!tasksPage.includes('ManagementRow'), 'TasksPage must keep task management rows inside taskQueue')
assert(!tasksPage.includes('ProgressMeter'), 'TasksPage must keep task progress meters inside taskQueue')
assert(!tasksPage.includes('ActionPanel'), 'TasksPage must keep task execution actions inside taskQueue')
for (const symbol of pandaTaskQueueSymbols) {
  assert(taskQueue.includes(`export function ${symbol}`), `taskQueue must export focused task component: ${symbol}`)
}
assert(taskQueue.includes('tasks: readonly TaskSummary[]'), 'taskQueue must accept readonly task resources')
assert(taskQueue.includes("import type { TaskSummary }"), 'taskQueue must type task props with TaskSummary')
assert(taskQueue.includes("from './taskQueueViewModel'"), 'taskQueue must delegate row display derivation to taskQueueViewModel')
assert(taskQueue.includes('title={taskQueueHeader.title}'), 'TaskQueuePanel must render section title from taskQueueViewModel')
assert(taskQueue.includes('title={taskQueueExecutionPanel.title}'), 'TaskQueueWorkspace must render execution action title from taskQueueViewModel')
assert(taskQueue.includes('items={taskQueueExecutionPanel.items}'), 'TaskQueueWorkspace must render execution action items from taskQueueViewModel')
assert(taskQueue.includes('const row = buildTaskQueueRowViewModel(task)'), 'TaskQueueRow must build a row view model from task resources')
assert(taskQueue.includes('tone={row.tone}'), 'TaskQueueRow must render tone from the task row view model')
assert(taskQueue.includes('title={row.title}'), 'TaskQueueRow must render title from the task row view model')
assert(taskQueue.includes('runtime={row.runtime}'), 'TaskQueueRow must pass runtime metadata from the task row view model')
assert(taskQueue.includes('value={row.progress}'), 'TaskQueueRow must render progress from the task row view model')
assert(!taskQueue.includes('title="任务队列"'), 'taskQueue must not inline task queue section title')
assert(!taskQueue.includes("['Steer 纠偏', '转交智能体', '请求人审', '生成产物']"), 'taskQueue must not inline execution action arrays')
assert(!taskQueue.includes('ActionPanel title="执行动作"'), 'taskQueue must not inline execution action panel title')
assert(!taskQueue.includes('tone={task.tone}'), 'TaskQueueRow must not read tone directly from task resources')
assert(!taskQueue.includes('title={task.title}'), 'TaskQueueRow must not read title directly from task resources')
assert(!taskQueue.includes('runtime={task.runtime}'), 'TaskQueueRow must not read runtime metadata directly from task resources')
assert(!taskQueue.includes('value={task.progress}'), 'TaskQueueRow must not read progress directly from task resources')
assert(!taskQueue.includes('`${task.project} · ${task.ownerAgent} · ${task.status}`'), 'taskQueue must not inline task row description formatting')
assert(taskQueueViewModel.includes('export const taskQueueHeader'), 'taskQueueViewModel must own task queue header data')
assert(taskQueueViewModel.includes("title: '任务队列'"), 'taskQueueViewModel must own task queue section title')
assert(taskQueueViewModel.includes('export const taskQueueExecutionActions'), 'taskQueueViewModel must own task execution action labels')
assert(taskQueueViewModel.includes('export const taskQueueExecutionPanel'), 'taskQueueViewModel must own the task execution panel view model')
assert(taskQueueViewModel.includes("title: '执行动作'"), 'taskQueueViewModel must own task execution panel title')
assert(taskQueueViewModel.includes('items: taskQueueExecutionActions'), 'taskQueueViewModel must wire execution panel items from the shared action list')
assert(taskQueueViewModel.includes('export function buildTaskQueueRowViewModel'), 'taskQueueViewModel must export the task row view model builder')
assert(taskQueueViewModel.includes('task: TaskSummary'), 'taskQueueViewModel must build rows from TaskSummary resources')
assert(taskQueueViewModel.includes('title: task.title'), 'taskQueueViewModel must expose task titles')
assert(taskQueueViewModel.includes('tone: task.tone'), 'taskQueueViewModel must expose task tones')
assert(taskQueueViewModel.includes("[task.project, task.ownerAgent, task.status].filter(Boolean).join(' · ')"), 'taskQueueViewModel must derive task row descriptions from resource fields')
assert(taskQueueViewModel.includes('runtime: task.runtime'), 'taskQueueViewModel must expose task runtime metadata')
assert(taskQueueViewModel.includes('progress: task.progress'), 'taskQueueViewModel must expose task progress values')
assert(taskQueueViewModel.includes("progressLabel: [task.priority, `${task.progress}%`]"), 'taskQueueViewModel must derive task progress labels from resource fields')
assert(taskQueue.includes('ManagementRow'), 'taskQueue must render shared ManagementRow rows')
assert(taskQueue.includes('ProgressMeter'), 'taskQueue must render shared task progress meters')
assert(taskQueue.includes('ActionPanel'), 'taskQueue must render task execution actions')
assert(taskQueue.includes('SectionHeader'), 'taskQueue must render the task queue section heading')
assert(taskQueue.includes('WorkspacePanel'), 'taskQueue must render task queue shell through shared WorkspacePanel')
assert(!taskQueue.includes('className="panda-card p-4"'), 'taskQueue must not duplicate the raw workspace panel shell')
assert(projectsPage.includes("from '../components/projectWorkspace'"), 'ProjectsPage must compose project workspace sections from projectWorkspace')
assert(projectsPage.includes('<ProjectWorkspace projects={resources.projects} />'), 'ProjectsPage must render ProjectWorkspace with workspace projects')
assert(!projectsPage.includes('RuntimeMetaStrip'), 'ProjectsPage must keep project runtime metadata inside projectWorkspace')
assert(!projectsPage.includes('SectionHeader'), 'ProjectsPage must keep project section heading inside projectWorkspace')
for (const symbol of pandaProjectWorkspaceSymbols) {
  assert(projectWorkspace.includes(`export function ${symbol}`), `projectWorkspace must export focused project component: ${symbol}`)
}
assert(projectWorkspace.includes('projects: readonly ProjectItem[]'), 'projectWorkspace must accept readonly project resources')
assert(projectWorkspace.includes("import type { ProjectItem }"), 'projectWorkspace must type project props with ProjectItem')
assert(projectWorkspace.includes("from './projectWorkspaceViewModel'"), 'projectWorkspace must delegate table display derivation to projectWorkspaceViewModel')
assert(projectWorkspace.includes('title={projectWorkspaceHeader.title}'), 'ProjectWorkspace must render its section title from projectWorkspaceViewModel')
assert(projectWorkspace.includes('columns={projectTableColumns}'), 'ProjectTable must render columns from projectWorkspaceViewModel')
assert(projectWorkspace.includes('const row = buildProjectTableRowViewModel(project)'), 'ProjectTableRow must build a row view model from project resources')
assert(projectWorkspace.includes('owner={row.runtimeOwner}'), 'ProjectTableRow must render runtime owner from the project row view model')
assert(projectWorkspace.includes('updatedAt={row.runtimeUpdatedAt}'), 'ProjectTableRow must render updatedAt from the project row view model')
assert(projectWorkspace.includes('risk={row.runtimeRisk}'), 'ProjectTableRow must render risk from the project row view model')
assert(!projectWorkspace.includes('title="最近项目"'), 'projectWorkspace must not inline the project section title')
assert(!projectWorkspace.includes("columns={['名称', '类型', '运行态']}"), 'projectWorkspace must not inline project table columns')
assert(projectWorkspaceViewModel.includes('export const projectWorkspaceHeader'), 'projectWorkspaceViewModel must own the project workspace header')
assert(projectWorkspaceViewModel.includes("title: '最近项目'"), 'projectWorkspaceViewModel must own the project workspace section title')
assert(projectWorkspaceViewModel.includes('export const projectTableColumns'), 'projectWorkspaceViewModel must own project table columns')
assert(projectWorkspaceViewModel.includes('export function buildProjectTableRowViewModel'), 'projectWorkspaceViewModel must export the project table row view model builder')
assert(projectWorkspaceViewModel.includes('project: ProjectItem'), 'projectWorkspaceViewModel must build rows from ProjectItem resources')
assert(projectWorkspaceViewModel.includes('runtimeOwner: project.ownerAgent'), 'projectWorkspaceViewModel must expose runtime owner')
assert(projectWorkspaceViewModel.includes('runtimeUpdatedAt: project.updatedAt'), 'projectWorkspaceViewModel must expose runtime updatedAt')
assert(projectWorkspaceViewModel.includes('runtimeRisk: project.risk'), 'projectWorkspaceViewModel must expose runtime risk')
assert(projectWorkspace.includes('RuntimeMetaStrip'), 'projectWorkspace must render project runtime metadata')
assert(projectWorkspace.includes('SectionHeader'), 'projectWorkspace must render the project section heading')
assert(projectWorkspace.includes('WorkspacePanel'), 'projectWorkspace must render project shell through shared WorkspacePanel')
assert(!projectWorkspace.includes('className="panda-card p-4"'), 'projectWorkspace must not duplicate the raw workspace panel shell')
assert(projectWorkspace.includes('WorkspaceTable'), 'projectWorkspace must render project rows through shared WorkspaceTable')
assert(!projectWorkspace.includes('className="panda-table"'), 'projectWorkspace must keep the shared table shell inside WorkspaceTable')
assert(auditPage.includes("from '../components/auditReplay'"), 'AuditPage must compose audit replay sections from auditReplay')
assert(auditPage.includes('<AuditReplayWorkspace auditEvents={resources.auditEvents} />'), 'AuditPage must render AuditReplayWorkspace with audit events')
assert(!auditPage.includes('AuditEventRow'), 'AuditPage must keep audit event rows inside auditReplay')
assert(!auditPage.includes('SummaryMetricList'), 'AuditPage must keep risk summary metrics inside auditReplay')
assert(!auditPage.includes('ShieldAlert'), 'AuditPage must keep risk summary icon inside auditReplay')
for (const symbol of pandaAuditReplaySymbols) {
  assert(auditReplay.includes(`export function ${symbol}`), `auditReplay must export focused audit component: ${symbol}`)
}
assert(auditReplay.includes('auditEvents: readonly AuditEvent[]'), 'auditReplay must accept readonly audit resources')
assert(auditReplay.includes("import type { AuditEvent }"), 'auditReplay must type audit props with AuditEvent')
assert(auditReplay.includes("from './auditReplayViewModel'"), 'auditReplay must delegate audit summary derivation to auditReplayViewModel')
assert(auditReplay.includes('<AuditRiskSummary auditEvents={auditEvents} />'), 'AuditReplayWorkspace must pass audit events into AuditRiskSummary')
assert(auditReplay.includes('const summaryItems = buildAuditRiskSummaryItems(auditEvents)'), 'AuditRiskSummary must build summary items from audit events')
assert(!auditReplay.includes("value: '28 条'"), 'auditReplay must not hard-code audit replay counts')
assert(!auditReplay.includes("value: '146 条'"), 'auditReplay must not hard-code audit evidence counts')
assert(auditReplayViewModel.includes('export function buildAuditRiskSummaryItems'), 'auditReplayViewModel must export the audit risk summary builder')
assert(auditReplayViewModel.includes('auditEvents: readonly AuditEvent[]'), 'auditReplayViewModel must accept readonly audit event resources')
assert(auditReplayViewModel.includes('event.evidenceRefs.length'), 'auditReplayViewModel must derive evidence counts from audit event evidence refs')
assert(auditReplayViewModel.includes("event.riskLevel === 'danger'"), 'auditReplayViewModel must derive high-risk counts from riskLevel')
assert(auditReplayViewModel.includes('countApprovalChanges'), 'auditReplayViewModel must own approval change counting')
assert(auditReplay.includes('AuditEventRow'), 'auditReplay must render shared AuditEventRow entries')
assert(auditReplay.includes('SummaryMetricList'), 'auditReplay must render shared risk summary metrics')
assert(auditReplay.includes('WorkspacePanel'), 'auditReplay must render audit shells through shared WorkspacePanel')
assert(!auditReplay.includes('className="panda-card p-4"'), 'auditReplay must not duplicate the raw workspace panel shell')
assert(auditReplay.includes('ShieldAlert'), 'auditReplay must own the risk summary icon')
assert(auditReplay.includes('evidenceRefs={event.evidenceRefs}'), 'auditReplay must pass audit evidence refs into AuditEventRow')
assert(automationPage.includes("from '../components/automationRules'"), 'AutomationPage must compose automation rule sections from automationRules')
assert(automationPage.includes('<AutomationRulesPanel automationRules={resources.automationRules} />'), 'AutomationPage must render AutomationRulesPanel with workspace automation rules')
assert(!automationPage.includes('ManagementRow'), 'AutomationPage must keep automation management rows inside automationRules')
assert(!automationPage.includes('SectionHeader'), 'AutomationPage must keep automation section heading inside automationRules')
assert(!automationPage.includes('Timer'), 'AutomationPage must keep automation section icon inside automationRules')
for (const symbol of pandaAutomationRulesSymbols) {
  assert(automationRulesPanel.includes(`export function ${symbol}`), `automationRules must export focused automation component: ${symbol}`)
}
assert(automationRulesPanel.includes('automationRules: readonly AutomationRule[]'), 'automationRules must accept readonly automation resources')
assert(automationRulesPanel.includes("import type { AutomationRule }"), 'automationRules must type automation props with AutomationRule')
assert(automationRulesPanel.includes("from './automationRulesViewModel'"), 'automationRules must delegate row display derivation to automationRulesViewModel')
assert(automationRulesPanel.includes('title={automationRulesHeader.title}'), 'AutomationRulesPanel must render its section title from automationRulesViewModel')
assert(automationRulesPanel.includes('const row = buildAutomationRuleRowViewModel(rule)'), 'AutomationRuleRow must build a row view model from automation resources')
assert(automationRulesPanel.includes('tone={row.tone}'), 'AutomationRuleRow must render tone from the automation row view model')
assert(automationRulesPanel.includes('title={row.title}'), 'AutomationRuleRow must render title from the automation row view model')
assert(automationRulesPanel.includes('runtime={row.runtime}'), 'AutomationRuleRow must pass runtime metadata from the automation row view model')
assert(!automationRulesPanel.includes('title="自动化规则"'), 'automationRules must not inline the automation section title')
assert(!automationRulesPanel.includes('title={rule.name}'), 'AutomationRuleRow must not read title directly from automation resources')
assert(!automationRulesPanel.includes('tone={rule.tone}'), 'AutomationRuleRow must not read tone directly from automation resources')
assert(!automationRulesPanel.includes('runtime={rule.runtime}'), 'AutomationRuleRow must not read runtime metadata directly from automation resources')
assert(automationRulesViewModel.includes('export const automationRulesHeader'), 'automationRulesViewModel must own the automation section header')
assert(automationRulesViewModel.includes("title: '自动化规则'"), 'automationRulesViewModel must own the automation section title')
assert(!automationRulesPanel.includes('`${rule.trigger} · ${rule.destination}`'), 'automationRules must not inline automation row description formatting')
assert(automationRulesViewModel.includes('export function buildAutomationRuleRowViewModel'), 'automationRulesViewModel must export the automation rule row view model builder')
assert(automationRulesViewModel.includes('rule: AutomationRule'), 'automationRulesViewModel must build rows from AutomationRule resources')
assert(automationRulesViewModel.includes('title: rule.name'), 'automationRulesViewModel must expose rule titles')
assert(automationRulesViewModel.includes('tone: rule.tone'), 'automationRulesViewModel must expose rule tones')
assert(automationRulesViewModel.includes("[rule.trigger, rule.destination].filter(Boolean).join(' · ')"), 'automationRulesViewModel must derive rule descriptions from resource fields')
assert(automationRulesViewModel.includes('runtime: rule.runtime'), 'automationRulesViewModel must expose rule runtime metadata')
assert(automationRulesViewModel.includes('status: rule.status'), 'automationRulesViewModel must expose rule status display text')
assert(automationRulesViewModel.includes('lastRun: rule.lastRun'), 'automationRulesViewModel must expose last-run display text')
assert(automationRulesPanel.includes('ManagementRow'), 'automationRules must render shared ManagementRow rows')
assert(automationRulesPanel.includes('SectionHeader'), 'automationRules must render the automation section heading')
assert(automationRulesPanel.includes('WorkspacePanel'), 'automationRules must render automation shell through shared WorkspacePanel')
assert(!automationRulesPanel.includes('className="panda-card p-4"'), 'automationRules must not duplicate the raw workspace panel shell')
assert(automationRulesPanel.includes('Timer'), 'automationRules must own the automation section icon')
assert(automationRulesPanel.includes('runtime={row.runtime}'), 'automationRules must pass runtime metadata into ManagementRow')
assert(toolsPage.includes("from '../components/toolCenter'"), 'ToolsPage must compose tool center sections from toolCenter')
assert(toolsPage.includes('<ToolCapabilityGrid tools={resources.toolCapabilities} />'), 'ToolsPage must render ToolCapabilityGrid with workspace tools')
assert(toolsPage.includes('<ToolAccessBoundary />'), 'ToolsPage must render the tool access boundary section')
assert(!toolsPage.includes('MetricStrip'), 'ToolsPage must keep tool metric rendering inside toolCenter')
assert(!toolsPage.includes('ToolCardHeader'), 'ToolsPage must keep tool card headers inside toolCenter')
assert(!toolsPage.includes('Wrench'), 'ToolsPage must keep tool card icons inside toolCenter')
for (const symbol of pandaToolCenterSymbols) {
  assert(toolCenter.includes(`export function ${symbol}`), `toolCenter must export focused tool component: ${symbol}`)
}
assert(toolCenter.includes('tools: readonly ToolCapability[]'), 'toolCenter must accept readonly tool resources')
assert(toolCenter.includes("import type { ToolCapability }"), 'toolCenter must type tool props with ToolCapability')
assert(toolCenter.includes("from './toolCenterViewModel'"), 'toolCenter must delegate tool card and boundary derivation to toolCenterViewModel')
assert(toolCenter.includes('const card = buildToolCapabilityCardViewModel(tool)'), 'ToolCapabilityCard must build a card view model from tool resources')
assert(toolCenter.includes('title={card.title}'), 'ToolCapabilityCard must render title from the tool view model')
assert(toolCenter.includes('metrics={card.metrics}'), 'ToolCapabilityCard must render metrics from the tool view model')
assert(!toolCenter.includes('title={tool.name}'), 'ToolCapabilityCard must not read title directly from tool resources')
assert(toolCenter.includes('title={toolAccessBoundaryTitle}'), 'ToolAccessBoundary must render boundary title from toolCenterViewModel')
assert(toolCenter.includes('toolAccessBoundaryItems.map'), 'ToolAccessBoundary must render boundary copy from toolCenterViewModel')
assert(!toolCenter.includes('title="接入边界"'), 'ToolAccessBoundary must not inline the access boundary title')
assert(!toolCenter.includes("{ label: '状态', value: tool.status }"), 'toolCenter must not inline tool status metrics')
assert(toolCenterViewModel.includes('export const toolAccessBoundaryTitle'), 'toolCenterViewModel must own tool access boundary title')
assert(toolCenterViewModel.includes("'接入边界'"), 'toolCenterViewModel must preserve the access boundary title copy')
assert(toolCenterViewModel.includes('export const toolAccessBoundaryItems'), 'toolCenterViewModel must own tool access boundary copy')
assert(toolCenterViewModel.includes('export function buildToolCapabilityCardViewModel'), 'toolCenterViewModel must export the tool capability card view model builder')
assert(toolCenterViewModel.includes('tool: ToolCapability'), 'toolCenterViewModel must build cards from ToolCapability resources')
assert(toolCenterViewModel.includes('title: tool.name'), 'toolCenterViewModel must expose tool titles')
assert(toolCenterViewModel.includes('subtitle: tool.provider'), 'toolCenterViewModel must expose tool provider subtitle')
assert(toolCenterViewModel.includes("{ label: '状态', value: tool.status }"), 'toolCenterViewModel must expose status metric')
assert(toolCenterViewModel.includes("{ label: '权限', value: tool.permission }"), 'toolCenterViewModel must expose permission metric')
assert(toolCenterViewModel.includes("{ label: '调用', value: tool.invocations }"), 'toolCenterViewModel must expose invocation metric')
assert(toolCenter.includes('ResourceCardGrid'), 'toolCenter must render tool cards through the shared ResourceCardGrid')
assert(toolCenter.includes('CapabilityMetricCard'), 'toolCenter must render shared CapabilityMetricCard')
assert(toolCenter.includes('InsetInfoBlock'), 'toolCenter must render access boundary items through shared InsetInfoBlock')
assert(toolCenter.includes('WorkspacePanel'), 'toolCenter must render access boundary shell through shared WorkspacePanel')
assert(!toolCenter.includes('<section className="panda-tools-grid">'), 'toolCenter must not duplicate the raw resource card grid shell')
assert(!toolCenter.includes('className="panda-card p-4"'), 'toolCenter must not duplicate the raw workspace panel shell')
assert(!toolCenter.includes('MetricStrip'), 'toolCenter must keep metric strip rendering inside CapabilityMetricCard')
assert(!toolCenter.includes('ToolCardHeader'), 'toolCenter must keep tool-card header rendering inside CapabilityMetricCard')
assert(!toolCenter.includes('rounded-lg bg-white/[0.04] p-4'), 'toolCenter must not duplicate raw inset info block styling')
assert(toolCenter.includes('Wrench'), 'toolCenter must own the tool capability icon')
assert(toolCenterViewModel.includes('工具发现由 MCP 管理器提供'), 'toolCenterViewModel must own the MCP discovery access boundary')
assert(toolCenterViewModel.includes('权限与审批由后端策略返回'), 'toolCenterViewModel must own the backend policy access boundary')
assert(toolCenterViewModel.includes('前端只展示状态、证据和可用动作'), 'toolCenterViewModel must keep frontend policy ownership explicit')
assert(dataPage.includes("from '../components/dataCenter'"), 'DataPage must compose data source sections from dataCenter')
assert(dataPage.includes('<DataSourceGrid dataSources={resources.dataSources} />'), 'DataPage must render DataSourceGrid with workspace data sources')
assert(!dataPage.includes('MetricStrip'), 'DataPage must keep data source metrics inside dataCenter')
assert(!dataPage.includes('ToolCardHeader'), 'DataPage must keep data source card headers inside dataCenter')
assert(!dataPage.includes('Database'), 'DataPage must keep data source icons inside dataCenter')
for (const symbol of pandaDataCenterSymbols) {
  assert(dataCenter.includes(`export function ${symbol}`), `dataCenter must export focused data component: ${symbol}`)
}
assert(dataCenter.includes('dataSources: readonly DataSource[]'), 'dataCenter must accept readonly data resources')
assert(dataCenter.includes("import type { DataSource }"), 'dataCenter must type data props with DataSource')
assert(dataCenter.includes("from './dataCenterViewModel'"), 'dataCenter must delegate card display derivation to dataCenterViewModel')
assert(dataCenter.includes('const card = buildDataSourceCardViewModel(source)'), 'DataSourceCard must build a card view model from data source resources')
assert(dataCenter.includes('title={card.title}'), 'DataSourceCard must render title from the data source view model')
assert(dataCenter.includes('metrics={card.metrics}'), 'DataSourceCard must render metrics from the data source view model')
assert(!dataCenter.includes('title={source.name}'), 'DataSourceCard must not read title directly from data source resources')
assert(!dataCenter.includes("{ label: '状态', value: source.status }"), 'dataCenter must not inline data source status metrics')
assert(dataCenterViewModel.includes('export function buildDataSourceCardViewModel'), 'dataCenterViewModel must export the data source card view model builder')
assert(dataCenterViewModel.includes('source: DataSource'), 'dataCenterViewModel must build cards from DataSource resources')
assert(dataCenterViewModel.includes('title: source.name'), 'dataCenterViewModel must expose data source titles')
assert(dataCenterViewModel.includes('subtitle: source.source'), 'dataCenterViewModel must expose data source subtitle')
assert(dataCenterViewModel.includes("{ label: '状态', value: source.status }"), 'dataCenterViewModel must expose status metric')
assert(dataCenterViewModel.includes("{ label: '记录', value: source.records }"), 'dataCenterViewModel must expose records metric')
assert(dataCenterViewModel.includes("{ label: '同步', value: source.syncState }"), 'dataCenterViewModel must expose sync-state metric')
assert(dataCenter.includes('ResourceCardGrid'), 'dataCenter must render data cards through the shared ResourceCardGrid')
assert(dataCenter.includes('CapabilityMetricCard'), 'dataCenter must render shared CapabilityMetricCard')
assert(!dataCenter.includes('<section className="panda-tools-grid">'), 'dataCenter must not duplicate the raw resource card grid shell')
assert(!dataCenter.includes('MetricStrip'), 'dataCenter must keep metric strip rendering inside CapabilityMetricCard')
assert(!dataCenter.includes('ToolCardHeader'), 'dataCenter must keep tool-card header rendering inside CapabilityMetricCard')
assert(dataCenter.includes('Database'), 'dataCenter must own the data source icon')
assert(knowledgePage.includes("from '../components/knowledgeBase'"), 'KnowledgePage must compose knowledge source sections from knowledgeBase')
assert(knowledgePage.includes('<KnowledgeSourceGrid knowledgeSources={resources.knowledgeSources} />'), 'KnowledgePage must render KnowledgeSourceGrid with workspace knowledge sources')
assert(!knowledgePage.includes('ListCardHeader'), 'KnowledgePage must keep knowledge card headers inside knowledgeBase')
assert(!knowledgePage.includes('InfoPairGrid'), 'KnowledgePage must keep knowledge info pairs inside knowledgeBase')
assert(!knowledgePage.includes('Brain'), 'KnowledgePage must keep knowledge icons inside knowledgeBase')
for (const symbol of pandaKnowledgeBaseSymbols) {
  assert(knowledgeBase.includes(`export function ${symbol}`), `knowledgeBase must export focused knowledge component: ${symbol}`)
}
assert(knowledgeBase.includes('knowledgeSources: readonly KnowledgeSource[]'), 'knowledgeBase must accept readonly knowledge resources')
assert(knowledgeBase.includes("import type { KnowledgeSource }"), 'knowledgeBase must type knowledge props with KnowledgeSource')
assert(knowledgeBase.includes("from './knowledgeBaseViewModel'"), 'knowledgeBase must delegate card display derivation to knowledgeBaseViewModel')
assert(knowledgeBase.includes('const card = buildKnowledgeSourceCardViewModel(source)'), 'KnowledgeSourceCard must build a card view model from knowledge resources')
assert(knowledgeBase.includes('title={card.title}'), 'KnowledgeSourceCard must render title from the knowledge source view model')
assert(!knowledgeBase.includes('title={source.name}'), 'KnowledgeSourceCard must not read title directly from knowledge source resources')
assert(!knowledgeBase.includes('`${source.kind} · ${source.status}`'), 'knowledgeBase must not inline knowledge source description formatting')
assert(knowledgeBaseViewModel.includes('export function buildKnowledgeSourceCardViewModel'), 'knowledgeBaseViewModel must export the knowledge source card view model builder')
assert(knowledgeBaseViewModel.includes('source: KnowledgeSource'), 'knowledgeBaseViewModel must build cards from KnowledgeSource resources')
assert(knowledgeBaseViewModel.includes('title: source.name'), 'knowledgeBaseViewModel must expose knowledge source titles')
assert(knowledgeBaseViewModel.includes("[source.kind, source.status].filter(Boolean).join(' · ')"), 'knowledgeBaseViewModel must derive descriptions from knowledge source fields')
assert(knowledgeBaseViewModel.includes("{ label: '文档', value: source.documents }"), 'knowledgeBaseViewModel must expose document count display item')
assert(knowledgeBaseViewModel.includes("{ label: '同步', value: source.lastSync }"), 'knowledgeBaseViewModel must expose last-sync display item')
assert(knowledgeBase.includes('ResourceCardGrid'), 'knowledgeBase must render knowledge cards through the shared ResourceCardGrid')
assert(knowledgeBase.includes('ResourceInfoCard'), 'knowledgeBase must render knowledge card bodies through the shared ResourceInfoCard')
assert(!knowledgeBase.includes('<section className="panda-list-grid">'), 'knowledgeBase must not duplicate the raw resource card grid shell')
assert(!knowledgeBase.includes('<div className="panda-card panda-list-card">'), 'knowledgeBase must not duplicate the raw resource info card shell')
assert(knowledgeBase.includes('Brain'), 'knowledgeBase must own the knowledge source icon')
assert(settingsPage.includes("from '../components/settingsCenter'"), 'SettingsPage must compose settings sections from settingsCenter')
assert(settingsPage.includes('<SettingsSectionGrid settingsSections={resources.settingsSections} />'), 'SettingsPage must render SettingsSectionGrid with workspace settings sections')
assert(!settingsPage.includes('ListCardHeader'), 'SettingsPage must keep setting card headers inside settingsCenter')
assert(!settingsPage.includes('InfoPairGrid'), 'SettingsPage must keep setting info pairs inside settingsCenter')
assert(!settingsPage.includes('Settings,'), 'SettingsPage must keep settings section icons inside settingsCenter')
for (const symbol of pandaSettingsCenterSymbols) {
  assert(settingsCenter.includes(`export function ${symbol}`), `settingsCenter must export focused settings component: ${symbol}`)
}
assert(settingsCenter.includes('settingsSections: readonly SettingsSection[]'), 'settingsCenter must accept readonly settings resources')
assert(settingsCenter.includes("import type { SettingsSection }"), 'settingsCenter must type settings props with SettingsSection')
assert(settingsCenter.includes("from './settingsCenterViewModel'"), 'settingsCenter must delegate card display derivation to settingsCenterViewModel')
assert(settingsCenter.includes('const card = buildSettingsSectionCardViewModel(section)'), 'SettingsSectionCard must build a card view model from settings resources')
assert(settingsCenter.includes('title={card.title}'), 'SettingsSectionCard must render title from the settings view model')
assert(settingsCenter.includes('items={card.items}'), 'SettingsSectionCard must render info items from the settings view model')
assert(!settingsCenter.includes('title={section.title}'), 'SettingsSectionCard must not read title directly from settings resources')
assert(!settingsCenter.includes("{ label: '策略', value: 'X-Agent Core' }"), 'settingsCenter must not inline the technical core policy item')
assert(settingsCenterViewModel.includes('export const xAgentCorePolicyLabel'), 'settingsCenterViewModel must own the technical core policy label')
assert(settingsCenterViewModel.includes('export function buildSettingsSectionCardViewModel'), 'settingsCenterViewModel must export the settings card view model builder')
assert(settingsCenterViewModel.includes('section: SettingsSection'), 'settingsCenterViewModel must build cards from SettingsSection resources')
assert(settingsCenterViewModel.includes('title: section.title'), 'settingsCenterViewModel must expose settings section titles')
assert(settingsCenterViewModel.includes('description: section.description'), 'settingsCenterViewModel must expose settings section descriptions')
assert(settingsCenterViewModel.includes("{ label: '状态', value: section.status }"), 'settingsCenterViewModel must expose settings status item')
assert(settingsCenterViewModel.includes("{ label: '策略', value: xAgentCorePolicyLabel }"), 'settingsCenterViewModel must expose technical core policy item')
assert(settingsCenter.includes('ResourceCardGrid'), 'settingsCenter must render settings cards through the shared ResourceCardGrid')
assert(settingsCenter.includes('ResourceInfoCard'), 'settingsCenter must render settings card bodies through the shared ResourceInfoCard')
assert(!settingsCenter.includes('<section className="panda-list-grid">'), 'settingsCenter must not duplicate the raw resource card grid shell')
assert(!settingsCenter.includes('<div className="panda-card panda-list-card">'), 'settingsCenter must not duplicate the raw resource info card shell')
assert(settingsCenterViewModel.includes('X-Agent Core'), 'settingsCenterViewModel must preserve the technical core policy label')
assert(workflowsPage.includes("from '../components/workflowCanvas'"), 'WorkflowsPage must compose workflow canvas sections from workflowCanvas')
assert(workflowsPage.includes('<WorkflowCanvas workflowNodes={resources.workflowNodes} />'), 'WorkflowsPage must render WorkflowCanvas with workspace workflow nodes')
assert(workflowsPage.includes('<WorkflowRunGrid workflows={resources.workflows} />'), 'WorkflowsPage must render WorkflowRunGrid with workspace workflows')
assert(!workflowsPage.includes('FlowNodeCard'), 'WorkflowsPage must keep workflow node rendering inside workflowCanvas')
assert(!workflowsPage.includes('ProgressSummary'), 'WorkflowsPage must keep workflow progress rendering inside workflowCanvas')
assert(!workflowsPage.includes('RuntimeMetaStrip'), 'WorkflowsPage must keep workflow runtime metadata inside workflowCanvas')
for (const symbol of pandaWorkflowCanvasSymbols) {
  assert(workflowCanvas.includes(`export function ${symbol}`), `workflowCanvas must export focused workflow component: ${symbol}`)
}
assert(workflowCanvas.includes('workflowNodes: readonly WorkflowNode[]'), 'WorkflowCanvas must accept readonly workflow node resources')
assert(workflowCanvas.includes('workflows: readonly WorkflowItem[]'), 'WorkflowRunGrid must accept readonly workflow resources')
assert(workflowCanvas.includes("import type { WorkflowItem, WorkflowNode }"), 'workflowCanvas must type workflow props with WorkflowItem and WorkflowNode')
assert(workflowCanvas.includes("from './workflowCanvasViewModel'"), 'workflowCanvas must delegate workflow canvas summary derivation to workflowCanvasViewModel')
assert(workflowCanvas.includes('const summary = buildWorkflowCanvasSummary(workflowNodes)'), 'WorkflowCanvas must build a workflow canvas view model from workflow nodes')
assert(workflowCanvas.includes('const card = buildWorkflowRunCardViewModel(workflow)'), 'WorkflowRunCard must build a workflow run card view model from workflow resources')
assert(workflowCanvas.includes('title={card.title}'), 'WorkflowRunCard must render title from its view model')
assert(workflowCanvas.includes('description={card.description}'), 'WorkflowRunCard must render description from its view model')
assert(workflowCanvas.includes('value={card.progress}'), 'WorkflowRunCard must render progress from its view model')
assert(workflowCanvas.includes('owner={card.runtimeOwner}'), 'WorkflowRunCard must render runtime owner from its view model')
assert(workflowCanvas.includes('risk={card.runtimeRisk}'), 'WorkflowRunCard must render runtime risk from its view model')
assert(!workflowCanvas.includes('description={`${workflow.owner} · ${workflow.state}`}'), 'WorkflowRunCard must not inline workflow owner/state description formatting')
assert(!workflowCanvas.includes('7 个节点'), 'WorkflowCanvas must not hard-code workflow node counts')
assert(!workflowCanvas.includes('1 个待审批网关'), 'WorkflowCanvas must not hard-code workflow approval counts')
assert(workflowCanvasViewModel.includes('export function buildWorkflowCanvasSummary'), 'workflowCanvasViewModel must export the workflow canvas summary builder')
assert(workflowCanvasViewModel.includes('export function buildWorkflowRunCardViewModel'), 'workflowCanvasViewModel must export the workflow run card view model builder')
assert(workflowCanvasViewModel.includes('workflowNodes: readonly WorkflowNode[]'), 'workflowCanvasViewModel must accept readonly workflow node resources')
assert(workflowCanvasViewModel.includes('workflow: WorkflowItem'), 'workflowCanvasViewModel must build workflow run cards from WorkflowItem resources')
assert(workflowCanvasViewModel.includes('runtime?.evidenceRefs.length'), 'workflowCanvasViewModel must derive evidence counts from runtime evidence refs')
assert(workflowCanvasViewModel.includes('countApprovalGateways'), 'workflowCanvasViewModel must own approval gateway counting')
assert(workflowCanvasViewModel.includes('emptyWorkflowSubtitle'), 'workflowCanvasViewModel must own empty workflow canvas fallback copy')
assert(workflowCanvasViewModel.includes("[workflow.owner, workflow.state].filter(Boolean).join(' · ')"), 'workflowCanvasViewModel must own workflow run description formatting')
assert(workflowCanvas.includes('FlowNodeCard'), 'workflowCanvas must render shared FlowNodeCard nodes')
assert(workflowCanvas.includes('ResourceCardGrid'), 'workflowCanvas must render workflow run cards through the shared ResourceCardGrid')
assert(workflowCanvas.includes('ResourceRuntimeCard'), 'workflowCanvas must render workflow run bodies through the shared ResourceRuntimeCard')
assert(!workflowCanvas.includes('<section className="panda-list-grid">'), 'workflowCanvas must not duplicate the raw resource card grid shell')
assert(!workflowCanvas.includes('<div className="panda-card panda-list-card">'), 'workflowCanvas must not duplicate the raw resource runtime card shell')
assert(workflowCanvas.includes('ProgressSummary'), 'workflowCanvas must render shared workflow progress summaries')
assert(workflowCanvas.includes('RuntimeMetaStrip'), 'workflowCanvas must render shared workflow runtime metadata')
assert(workspaceListCardHeaderPrimitives.includes('StatusDot'), 'workflow run status indicators must be rendered through shared list-card header primitives')
assert(workflowCanvas.includes('ShieldCheck'), 'workflowCanvas must own the workflow policy chip icon')
assert(agentsPage.includes("from '../components/agentOrganization'"), 'AgentsPage must compose agent organization sections from agentOrganization')
assert(agentsPage.includes('<AgentRolePresetSelector />'), 'AgentsPage must expose built-in role card selection before organization overview')
assert(agentsPage.includes('<AgentOrganizationOverview agentProfiles={resources.agentProfiles} lead={resources.lead} />'), 'AgentsPage must render AgentOrganizationOverview with the lead agent')
assert(agentsPage.includes('<AgentProfileGrid agentProfiles={resources.agentProfiles} />'), 'AgentsPage must render AgentProfileGrid with workspace agents')
assert(!agentsPage.includes('ProgressSummary'), 'AgentsPage must keep agent progress rendering inside agentOrganization')
assert(!agentsPage.includes('MiniTagList'), 'AgentsPage must keep agent permission tags inside agentOrganization')
assert(!agentsPage.includes('RuntimeMetaStrip'), 'AgentsPage must keep agent runtime metadata inside agentOrganization')
for (const symbol of pandaAgentOrganizationSymbols) {
  assert(agentOrganization.includes(`export function ${symbol}`), `agentOrganization must export focused agent component: ${symbol}`)
}
for (const symbol of pandaAgentProfileCardSymbols) {
  assert(agentProfileCards.includes(`export function ${symbol}`), `agentProfileCards must own focused agent profile component: ${symbol}`)
}
assert(agentProfileCards.includes("from './agentProfileCardViewModel'"), 'agentProfileCards must delegate card display derivation to agentProfileCardViewModel')
assert(agentProfileCards.includes('const card = buildAgentProfileCardViewModel(agent)'), 'AgentProfileCard must build a card view model from agent resources')
assert(agentProfileCards.includes('title={card.title}'), 'AgentProfileCard must render title from the agent profile view model')
assert(agentProfileCards.includes('description={card.description}'), 'AgentProfileCard must render description from the agent profile view model')
assert(agentProfileCards.includes('value={card.progress}'), 'AgentProfileCard must render progress from the agent profile view model')
assert(agentProfileCards.includes('owner={card.runtimeOwner}'), 'AgentProfileCard must render runtime owner from the agent profile view model')
assert(agentProfileCards.includes('risk={card.runtimeRisk}'), 'AgentProfileCard must render runtime risk from the agent profile view model')
assert(agentProfileCards.includes('items={card.permissions}'), 'AgentProfileCard must render permission tags from the agent profile view model')
assert(!agentProfileCards.includes('title={agent.name}'), 'AgentProfileCard must not read title directly from agent resources')
assert(!agentProfileCards.includes('value={agent.load}'), 'AgentProfileCard must not read progress directly from agent resources')
assert(!agentProfileCards.includes('items={agent.permissions}'), 'AgentProfileCard must not read permission tags directly from agent resources')
assert(!agentProfileCards.includes('`${agent.role} · ${agent.model} · ${agent.status}`'), 'agentProfileCards must not inline agent profile description formatting')
assert(agentProfileCardViewModel.includes('export function buildAgentProfileCardViewModel'), 'agentProfileCardViewModel must export the agent profile card view model builder')
assert(agentProfileCardViewModel.includes('agent: AgentProfile'), 'agentProfileCardViewModel must build cards from AgentProfile resources')
assert(agentProfileCardViewModel.includes('title: agent.name'), 'agentProfileCardViewModel must expose the agent card title')
assert(agentProfileCardViewModel.includes("[agent.role, agent.model, agent.status].filter(Boolean).join(' · ')"), 'agentProfileCardViewModel must derive agent descriptions from profile fields')
assert(agentProfileCardViewModel.includes('progress: agent.load'), 'agentProfileCardViewModel must expose agent progress')
assert(agentProfileCardViewModel.includes('permissions: agent.permissions'), 'agentProfileCardViewModel must expose agent permission tags')
assert(agentProfileCardViewModel.includes('runtimeOwner: agent.name'), 'agentProfileCardViewModel must expose the runtime owner')
assert(agentProfileCardViewModel.includes('runtimeRisk: agent.tone'), 'agentProfileCardViewModel must expose the runtime risk')
assert(agentOrganization.includes('agentProfiles: readonly AgentProfile[]'), 'agentOrganization must accept readonly agent resources')
assert(agentOrganization.includes("import type { AgentProfile }"), 'agentOrganization must type agent props with AgentProfile')
assert(agentOrganization.includes("from './agentOrganizationViewModel'"), 'agentOrganization must import its focused view model helpers')
assert(agentOrganization.includes('agentOrganizationOverviewHeader'), 'agentOrganization must render its overview header from the view model')
assert(agentOrganization.includes('<h2>{agentOrganizationOverviewHeader.title}</h2>'), 'agentOrganization must render overview title from the view model')
assert(agentOrganization.includes('<p>{agentOrganizationOverviewHeader.summary}</p>'), 'agentOrganization must render overview summary from the view model')
assert(agentOrganization.includes('title={agentOrganizationTeamActionPanel.title}'), 'agentOrganization must render team action title from its view model')
assert(agentOrganization.includes('items={agentOrganizationTeamActionPanel.items}'), 'agentOrganization must render team actions from its view model')
assert(agentOrganization.includes('const leadControlPanel = buildLeadAgentControlPanel(lead)'), 'agentOrganization must build lead control panel data through its view model')
assert(agentOrganization.includes('title={leadControlPanel.title}'), 'agentOrganization must render lead control title from its view model')
assert(agentOrganization.includes('items={leadControlPanel.items}'), 'agentOrganization must render lead controls from its view model')
assert(agentOrganization.includes("from './agentProfileCards'"), 'agentOrganization must preserve compatibility exports from agentProfileCards')
assert(agentOrganization.includes("from './agentRolePresetSelector'"), 'agentOrganization must preserve compatibility exports from agentRolePresetSelector')
assert(!agentOrganization.includes("from '../data/agentRolePresets'"), 'agentOrganization must keep create-agent role card internals in agentRolePresetSelector')
assert(!agentOrganization.includes('aria-pressed={selected}'), 'agentOrganization must not duplicate agent role card selection internals')
for (const symbol of pandaAgentRolePresetSelectorSymbols) {
  assert(agentRolePresetSelector.includes(symbol), `agentRolePresetSelector must preserve compatibility export for role-card component: ${symbol}`)
}
assert(agentRolePresetSelector.includes('export function AgentRolePresetSelector'), 'agentRolePresetSelector must own the role preset selector state component')
assert(agentRolePresetCards.includes('export function AgentRolePresetCard'), 'agentRolePresetCards must own focused role-card component: AgentRolePresetCard')
assert(agentRolePresetCards.includes("from './agentRolePresetDetail'"), 'agentRolePresetCards must preserve AgentRolePresetDetail compatibility export')
assert(!agentRolePresetCards.includes('export function AgentRolePresetDetail'), 'agentRolePresetCards must keep AgentRolePresetDetail implementation in agentRolePresetDetail')
assert(agentRolePresetDetail.includes('export function AgentRolePresetDetail'), 'agentRolePresetDetail must own focused role-card detail panel')
assert(agentRolePresetCards.includes("from './agentRolePresetViewModel'"), 'agentRolePresetCards must delegate role card display derivation to agentRolePresetViewModel')
assert(agentRolePresetDetail.includes("from './agentRolePresetViewModel'"), 'agentRolePresetDetail must delegate role detail display derivation to agentRolePresetViewModel')
assert(agentRolePresetCards.includes('const card = buildAgentRolePresetViewModel(preset)'), 'AgentRolePresetCard must build a view model from role presets')
assert(agentRolePresetDetail.includes('const detail = buildAgentRolePresetViewModel(preset)'), 'AgentRolePresetDetail must build a view model from role presets')
assert(agentRolePresetCards.includes('alt={card.portraitAlt}'), 'agent role card portraits must render alt text from the view model')
assert(agentRolePresetDetail.includes('alt={detail.portraitAlt}'), 'agent role detail portraits must render alt text from the view model')
assert(agentRolePresetDetail.includes('detail.detailBlocks.map'), 'agent role detail must render detail blocks from the view model')
assert(agentRolePresetViewModel.includes('export function buildAgentRolePresetViewModel'), 'agentRolePresetViewModel must export the role preset view model builder')
assert(agentRolePresetViewModel.includes('preset: AgentRolePreset'), 'agentRolePresetViewModel must build display data from AgentRolePreset')
assert(agentRolePresetViewModel.includes('portraitAlt: `${preset.name}角色形象`'), 'agentRolePresetViewModel must own role-specific portrait alt text')
assert(agentRolePresetViewModel.includes("{ label: '核心能力', items: preset.abilities }"), 'agentRolePresetViewModel must own ability detail block mapping')
assert(agentRolePresetViewModel.includes("{ label: '默认工具', items: preset.tools }"), 'agentRolePresetViewModel must own tool detail block mapping')
assert(agentRolePresetViewModel.includes("{ label: '权限边界', items: preset.defaultPermissions }"), 'agentRolePresetViewModel must own permission detail block mapping')
assert(agentRolePresetSelector.includes("from '../data/agentRolePresets'"), 'agentRolePresetSelector must load built-in role cards from the preset data module')
assert(agentRolePresetSelector.includes("from './agentRolePresetCards'"), 'agentRolePresetSelector must compose focused role card/detail components')
assert(agentRolePresetCards.includes('aria-pressed={selected}'), 'agent role cards must expose selected state for assistive tech')
assert(agentRolePresetCards.includes('panda-role-portrait'), 'agent role cards must render a visual role portrait, not only text or numeric metadata')
assert(agentRolePresetCards.includes('src={preset.portraitSrc}'), 'agent role cards must render the configured reference portrait image')
assert(agentRolePresetCards.includes('className="panda-role-portrait-image"'), 'agent role cards must render user-reference portraits as real images, not abstract avatar placeholders')
assert(!agentRolePresetCards.includes('alt={`${preset.name}角色形象`}'), 'agent role cards must not inline portrait alt text')
assert(agentRolePresetDetail.includes('panda-role-portrait is-large'), 'agent role preset detail must render the large role portrait')
assert(agentRolePresetDetail.includes('src={preset.portraitSrc}'), 'agent role preset detail must render the configured reference portrait image')
assert(agentRolePresetDetail.includes('className="panda-role-portrait-image"'), 'agent role detail panel must render user-reference portraits as real images, not abstract avatar placeholders')
assert(agentRolePresetDetail.includes('MiniTagList'), 'agent role preset detail must render abilities, tools, and permission tags')
assert(!agentOrganization.includes('ActionPanel title="团队动作"'), 'agentOrganization must not inline team action panel title')
assert(!agentOrganization.includes('ActionPanel title="当前主控"'), 'agentOrganization must not inline lead control panel title')
assert(agentOrganizationViewModel.includes("export const agentOrganizationTeamActions"), 'agentOrganizationViewModel must export team action rows')
assert(agentOrganizationViewModel.includes('export type AgentOrganizationHeaderViewModel'), 'agentOrganizationViewModel must type the overview header display model')
assert(agentOrganizationViewModel.includes('export const agentOrganizationOverviewHeader'), 'agentOrganizationViewModel must export overview header display data')
assert(agentOrganizationViewModel.includes("title: 'Panda Agent 企业团队'"), 'agentOrganizationViewModel must own the overview header title')
assert(agentOrganizationViewModel.includes("summary: '5 个在线角色 · 3 条并行任务 · 1 个待审批交接'"), 'agentOrganizationViewModel must own the overview header summary')
assert(!agentOrganization.includes('Panda Agent 企业团队'), 'agentOrganization must not inline the organization overview title')
assert(!agentOrganization.includes('5 个在线角色 · 3 条并行任务 · 1 个待审批交接'), 'agentOrganization must not inline the organization overview summary')
assert(agentOrganizationViewModel.includes('export const agentOrganizationTeamActionPanel'), 'agentOrganizationViewModel must export team action panel data')
assert(agentOrganizationViewModel.includes("title: '团队动作'"), 'agentOrganizationViewModel must own the team action panel title')
for (const action of ['转交任务', '召开智能体会议', '调整权限', '查看运行证据']) {
  assert(agentOrganizationViewModel.includes(action), `agentOrganizationViewModel must preserve team action: ${action}`)
}
assert(agentOrganizationViewModel.includes('buildLeadAgentControlItems'), 'agentOrganizationViewModel must export lead control row builder')
assert(agentOrganizationViewModel.includes('buildLeadAgentControlPanel'), 'agentOrganizationViewModel must export lead control panel builder')
assert(agentOrganizationViewModel.includes("title: '当前主控'"), 'agentOrganizationViewModel must own the lead control panel title')
for (const leadField of ['lead.name', 'lead.model', 'lead.load', 'lead.status']) {
  assert(agentOrganizationViewModel.includes(leadField), `agentOrganizationViewModel must map lead field: ${leadField}`)
}
assert(agentOrganization.includes('ResourceCardGrid'), 'agentOrganization must render agent profile cards through the shared ResourceCardGrid')
assert(agentProfileCards.includes('ResourceRuntimeCard'), 'agentProfileCards must render agent profile bodies through the shared ResourceRuntimeCard')
assert(!agentOrganization.includes('<section className="panda-list-grid">'), 'agentOrganization must not duplicate the raw resource card grid shell')
assert(!agentProfileCards.includes('<div className="panda-card panda-list-card">'), 'agentProfileCards must not duplicate the raw resource runtime card shell')
assert(agentProfileCards.includes('ProgressSummary'), 'agentProfileCards must render agent progress summaries')
assert(agentProfileCards.includes('RuntimeMetaStrip'), 'agentProfileCards must render agent runtime metadata')
assert(agentProfileCards.includes('MiniTagList'), 'agentProfileCards must render agent permission tags')
assert(agentOrganization.includes('StatusDot'), 'agentOrganization must render agent status indicators')
assert(agentRoleTypes.includes('export type AgentRolePreset'), 'agent role preset view type must live in the Panda type layer')
assert(agentRoleTypes.includes('readonly portraitSrc: string'), 'agent role preset type must include a role portrait image source')
assert(agentRoleTypes.includes('readonly defaultPermissions: readonly string[]'), 'agent role preset type must keep default permissions in the view model')
assert(agentRolePresetFixtures.includes('export const apiAgentRolePresetFixtures: readonly ApiAgentRolePreset[]'), 'agent role fixtures must use the API DTO shape for backend alignment')
assert(agentRolePresets.includes("from './agentRolePresetFixtures'"), 'agent role presets must import backend-shaped fixtures from the focused fixture module')
assert(agentRolePresets.includes("export { apiAgentRolePresetFixtures } from './agentRolePresetFixtures'"), 'agentRolePresets must preserve fixture compatibility exports')
assert(agentRolePresets.includes('mapAgentRolePresets(apiAgentRolePresetFixtures)'), 'agent role presets must be generated through the API-alignment mapper')
assert(agentRolePresets.includes('export const agentRolePresets ='), 'agent role presets must export the mapped preset library')
assert(agentRolePresets.includes('satisfies readonly AgentRolePreset[]'), 'agent role presets must satisfy the readonly view-model preset type')
for (const roleName of ['总经理', '平面设计师', '编程大牛', '财务总监', '导演', '编剧', '采购总监', '法务总监', '自媒体运营', '客服专员']) {
  assert(agentRolePresetFixtures.includes(`name: '${roleName}'`), `agent role fixtures missing built-in role: ${roleName}`)
}
for (const portraitName of ['ceoPortrait', 'designerPortrait', 'engineerPortrait', 'financePortrait', 'directorPortrait', 'screenwriterPortrait', 'procurementPortrait', 'legalPortrait', 'mediaOperatorPortrait', 'supportPortrait']) {
  assert(agentRolePortraits.includes(portraitName), `agent role portrait registry missing reference portrait import: ${portraitName}`)
}
for (const referenceAsset of ['direct-reference-ceo.png', 'direct-reference-designer.png', 'direct-reference-engineer.png', 'direct-reference-finance.png', 'direct-reference-director.png', 'direct-reference-screenwriter.png', 'direct-reference-procurement.png', 'direct-reference-legal.png', 'direct-reference-media-operator.png', 'direct-reference-support.png']) {
  assert(agentRolePortraits.includes(referenceAsset), `agent role portrait registry must use the user reference character asset: ${referenceAsset}`)
  assert(existsSync(resolve(root, `src/panda/assets/roles/${referenceAsset}`)), `agent role reference portrait asset must exist: ${referenceAsset}`)
}
assert(agentRolePresetCards.includes('src={preset.portraitSrc}'), 'agent role cards must render the mapped reference portrait image')
assert(agentRolePresetDetail.includes('src={preset.portraitSrc}'), 'agent role detail panel must render the mapped reference portrait image')
assert(!agentRolePresetCards.includes('preset.icon'), 'agent role cards must not fall back to generic icon placeholders')
assert(!agentRolePresetDetail.includes('preset.icon'), 'agent role detail panel must not fall back to generic icon placeholders')
for (const apiField of ['default_permissions', 'portrait_key', 'abilities', 'tools']) {
  assert(agentRolePresetFixtures.includes(apiField), `agent role fixtures must keep backend-aligned field: ${apiField}`)
}
assert(!agentRolePresets.includes('apiClient'), 'agent role presets must not call backend clients until creation API alignment')
assert(!agentRolePresets.includes('fetch('), 'agent role presets must not fetch backend data until creation API alignment')
for (const pageId of pageIds.filter((id) => id !== 'home')) {
  const source = read(pageFileById[pageId])
  const resourceGuardSource = pageId === 'threads' ? threadWorkspace : modulePagePrimitives
  assert(resourceGuardSource.includes('PandaResourceState'), `${pageId} page must guard empty/loading/error resource states`)
  if (pageId !== 'threads') {
    assert(source.includes('StandardModulePageShell'), `${pageId} page must receive resource state handling through StandardModulePageShell`)
  }
}
for (const pageId of pandaManagementRowPageIds) {
  const source = read(pageFileById[pageId])
  const managementRowSource = pageId === 'tasks' ? taskQueue : pageId === 'automation' ? automationRulesPanel : source
  assert(managementRowSource.includes('ManagementRow'), `${pageId} page must use shared ManagementRow`)
  assert(managementRowSource.includes('runtime='), `${pageId} page must pass runtime metadata into ManagementRow`)
}
assert(workflowActionPrimitives.includes('RuntimeMetaStrip'), 'ManagementRow must use shared RuntimeMetaStrip for runtime evidence')
assert(!workflowActionPrimitives.includes('MiniTagList'), 'ManagementRow must not duplicate runtime evidence tag rendering')
assert(threadWorkspace.includes('ProgressMeter'), 'threads page must use shared ProgressMeter through threadWorkspace')
assert(taskQueue.includes('ProgressMeter'), 'tasks page must use shared ProgressMeter through taskQueue')
assert(projectWorkspace.includes('RuntimeMetaStrip'), 'projects page must use shared RuntimeMetaStrip through projectWorkspace')
assert(workflowCanvas.includes('RuntimeMetaStrip'), 'workflows page must use shared RuntimeMetaStrip through workflowCanvas')
assert(agentProfileCards.includes('RuntimeMetaStrip'), 'agents page must use shared RuntimeMetaStrip through agentProfileCards')
assert(homeProjectSections.includes('RuntimeMetaStrip'), 'home page recent projects must use shared RuntimeMetaStrip through homeProjectSections')
assert(homeProjectSections.includes('PandaResourceState'), 'home page recent projects must use shared PandaResourceState through homeProjectSections')
assert(!read(pageFileById.home).includes('PandaEmptyState'), 'home page recent projects must not bypass PandaResourceState with a direct empty state')
assert(homeProjectSectionsViewModel.includes("loadingTitle: '正在同步最近项目'"), 'home page recent project view model must expose a module-specific loading state')
assert(homeProjectSectionsViewModel.includes("emptyTitle: '暂无最近项目'"), 'home page recent project view model must expose a module-specific empty state')
assert(moduleFallbackContent.includes('./navigation'), 'Module fallback metadata must import nav labels from navigation constants')
assert(workflowCanvas.includes('ProgressSummary'), 'workflows page must use shared ProgressSummary through workflowCanvas')
assert(agentProfileCards.includes('ProgressSummary'), 'agents page must use shared ProgressSummary through agentProfileCards')
assert(workflowCanvas.includes('FlowNodeCard'), 'workflows page must use shared FlowNodeCard through workflowCanvas')
assert(progressPrimitives.includes('ProgressSummary'), 'ProgressSummary must provide workflow card progress display')
assert(threadExecutionWorkspace.includes('ExecutionStepRow'), 'threads page must use shared ExecutionStepRow through threadExecutionWorkspace')
const rightRail = read('src/panda/components/RightRail.tsx')
assert(rightRail.includes('usePandaWorkspaceLifecycle'), 'RightRail must read lifecycle data through the lifecycle hook')
assert(!rightRail.includes('usePandaWorkspace()'), 'RightRail must not consume the full workspace context directly')
for (const symbol of pandaRightRailFocusedCardSymbols) {
  assert(rightRail.includes(symbol), `RightRail missing focused card import or usage: ${symbol}`)
}
assert(rightRail.includes('getPandaResourcesBffConfig'), 'RightRail must surface the current Panda resources BFF config')
assert(rightRail.includes('../api/resourcesBffConfig'), 'RightRail must import pure BFF config without bootstrap side effects')
assert(!rightRail.includes('../api/bootstrapResources'), 'RightRail must not import the bootstrap side-effect module')
assert(rightRail.includes('const resourcesBffConfig = getPandaResourcesBffConfig()'), 'RightRail must read the shared resources BFF config')
assert(rightRail.includes("from './rightRailFallbacks'"), 'RightRail must delegate fallback resource mapping to rightRailFallbacks')
assert(rightRail.includes('resolveRightRailAgentActivities'), 'RightRail must resolve agent activity fallback through a focused helper')
assert(rightRail.includes('resolveRightRailWorkflowRuns'), 'RightRail must resolve workflow fallback through a focused helper')
assert(!rightRail.includes('agents.map((agent)'), 'RightRail must not inline agent-to-activity fallback mapping')
assert(rightRail.includes('<ResourceSnapshotCard'), 'RightRail must delegate resource snapshot rendering')
assert(rightRail.includes('<AgentActivityCard'), 'RightRail must delegate agent activity rendering')
assert(rightRail.includes('<WorkflowRunsCard'), 'RightRail must delegate workflow run rendering')
assert(rightRail.includes('<ApprovalRiskCard />'), 'RightRail must delegate approval and risk rendering')
assert(rightRail.includes('<SystemStatusCard />'), 'RightRail must delegate system status rendering')
assert(rightRail.includes('onRefresh={refresh}'), 'RightRail must pass refresh into the resource snapshot card')

const rightRailCards = read('src/panda/components/rightRailCards.tsx')
const rightRailActivityCard = read('src/panda/components/rightRailActivityCard.tsx')
const rightRailActivityCardViewModel = read('src/panda/components/rightRailActivityCardViewModel.ts')
const rightRailWorkflowCard = read('src/panda/components/rightRailWorkflowCard.tsx')
const rightRailWorkflowCardViewModel = read('src/panda/components/rightRailWorkflowCardViewModel.ts')
const rightRailResourceCard = read('src/panda/components/rightRailResourceCard.tsx')
const rightRailResourceCardViewModel = read('src/panda/components/rightRailResourceCardViewModel.ts')
const rightRailStatusCards = read('src/panda/components/rightRailStatusCards.tsx')
const rightRailStatusCardsViewModel = read('src/panda/components/rightRailStatusCardsViewModel.tsx')
const rightRailFallbacks = read('src/panda/components/rightRailFallbacks.ts')
for (const symbol of pandaRightRailCardSymbols) {
  assert(rightRailCards.includes(symbol), `rightRailCards must preserve compatibility export for focused card component: ${symbol}`)
}
assert(rightRailActivityCard.includes('export function AgentActivityCard'), 'rightRailActivityCard must own AgentActivityCard')
assert(rightRailWorkflowCard.includes('export function WorkflowRunsCard'), 'rightRailWorkflowCard must own WorkflowRunsCard')
assert(rightRailActivityCard.includes('activities: readonly ActivityItem[]'), 'AgentActivityCard must accept readonly activity resources')
assert(rightRailActivityCard.includes("from './rightRailActivityCardViewModel'"), 'RightRail activity card must import its focused view model')
assert(rightRailActivityCard.includes('buildRightRailActivityRowViewModels(activities)'), 'RightRail activity card must delegate row display derivation to its view model')
assert(rightRailActivityCard.includes('rightRailActivityCardHeader.title'), 'RightRail activity card must render title from its view model')
assert(rightRailActivityCard.includes('rightRailActivityCardHeader.action'), 'RightRail activity card must render action from its view model')
assert(rightRailActivityCard.includes('rightRailActivityEmptyState.title'), 'RightRail activity card must render empty title from its view model')
assert(rightRailActivityCard.includes('rightRailActivityEmptyState.description'), 'RightRail activity card must render empty description from its view model')
assert(!rightRailActivityCard.includes('title="智能体活动"'), 'RightRail activity card must not inline its card title')
assert(!rightRailActivityCard.includes('action="查看全部"'), 'RightRail activity card must not inline its card action')
assert(!rightRailActivityCard.includes('title="暂无智能体活动"'), 'RightRail activity card must not inline its empty title')
assert(!rightRailActivityCard.includes('启动任务后会在这里显示智能体运行、等待审批和失败事件。'), 'RightRail activity card must not inline its empty description')
assert(!rightRailActivityCard.includes('updatedAt={item.time}'), 'RightRail activity card must not directly map activity time in the component')
assert(rightRailActivityCardViewModel.includes('ActivityItem'), 'RightRail activity view model must type rows from ActivityItem resources')
assert(rightRailActivityCardViewModel.includes('export const rightRailActivityCardHeader'), 'RightRail activity view model must own card header copy')
assert(rightRailActivityCardViewModel.includes("title: '智能体活动'"), 'RightRail activity view model must own card title')
assert(rightRailActivityCardViewModel.includes("action: '查看全部'"), 'RightRail activity view model must own card action')
assert(rightRailActivityCardViewModel.includes('export const rightRailActivityEmptyState'), 'RightRail activity view model must own empty-state copy')
assert(rightRailActivityCardViewModel.includes("title: '暂无智能体活动'"), 'RightRail activity view model must own empty title')
assert(rightRailActivityCardViewModel.includes("description: '启动任务后会在这里显示智能体运行、等待审批和失败事件。'"), 'RightRail activity view model must own empty description')
assert(rightRailActivityCardViewModel.includes('buildRightRailActivityRowViewModel'), 'RightRail activity view model must export a single-row builder')
assert(rightRailActivityCardViewModel.includes('buildRightRailActivityRowViewModels'), 'RightRail activity view model must export a list builder')
for (const activityField of ['item.id', 'item.title', 'item.subtitle', 'item.tone', 'item.runtime', 'item.time']) {
  assert(rightRailActivityCardViewModel.includes(activityField), `RightRail activity view model must map activity field: ${activityField}`)
}
assert(rightRailWorkflowCard.includes('workflows: readonly WorkflowItem[]'), 'WorkflowRunsCard must accept readonly workflow resources')
assert(rightRailFallbacks.includes('buildRightRailAgentActivityFallback'), 'rightRailFallbacks must own agent-to-activity fallback mapping')
assert(rightRailFallbacks.includes('resolveRightRailAgentActivities'), 'rightRailFallbacks must expose home-or-resource activity resolution')
assert(rightRailFallbacks.includes('resolveRightRailWorkflowRuns'), 'rightRailFallbacks must expose home-or-resource workflow resolution')
assert(rightRailFallbacks.includes('runtime: agent.runtime'), 'rightRailFallbacks agent activity fallback must preserve agent runtime metadata')
assert(rightRailFallbacks.includes("time: agent.runtime?.updatedAt ?? '现在'"), 'rightRailFallbacks must prefer runtime updatedAt for fallback activity time')
for (const symbol of pandaRightRailResourceCardSymbols) {
  assert(rightRailResourceCard.includes(`export function ${symbol}`) || rightRailResourceCard.includes(`export type ${symbol}`), `rightRailResourceCard must own resource snapshot component: ${symbol}`)
}
assert(rightRailCards.includes("from './rightRailResourceCard'"), 'rightRailCards must preserve compatibility exports from rightRailResourceCard')
assert(rightRailCards.includes("from './rightRailStatusCards'"), 'rightRailCards must preserve compatibility exports from rightRailStatusCards')
assert(rightRailCards.includes("from './rightRailActivityCard'"), 'rightRailCards must preserve compatibility exports from rightRailActivityCard')
assert(rightRailCards.includes("from './rightRailWorkflowCard'"), 'rightRailCards must preserve compatibility exports from rightRailWorkflowCard')
for (const symbol of pandaRightRailStatusCardSymbols) {
  assert(rightRailStatusCards.includes(`export function ${symbol}`), `rightRailStatusCards must own status card component: ${symbol}`)
}
assert(rightRailActivityCard.includes('ActivitySummaryRow'), 'RightRail activity card must use shared ActivitySummaryRow')
assert(rightRailActivityCard.includes('RuntimeMetaStrip'), 'RightRail activity card must render activity runtime metadata')
assert(rightRailActivityCard.includes('runtime={item.runtime}'), 'RightRail activity card must pass activity runtime metadata into RuntimeMetaStrip')
assert(rightRailActivityCard.includes('updatedAt={item.updatedAt}'), 'RightRail activity card must pass view-model updatedAt into RuntimeMetaStrip')
assert(rightRailWorkflowCard.includes('ProgressSummary'), 'RightRail workflow card must use shared ProgressSummary')
assert(rightRailWorkflowCard.includes("from './rightRailWorkflowCardViewModel'"), 'RightRail workflow card must import its focused view model')
assert(rightRailWorkflowCard.includes('buildRightRailWorkflowRunViewModels(workflows)'), 'RightRail workflow card must delegate run display derivation to its view model')
assert(rightRailActivityCard.includes('pandaLogoSrc'), 'RightRail activity card must render the Panda Agent logo avatar')
assert(rightRailActivityCard.includes('../data/navigation'), 'RightRail activity card must import Panda logo from navigation constants')
assert(rightRailStatusCards.includes('KeyValueList'), 'RightRail status cards must render key-value rows through shared KeyValueList')
assert(!rightRailStatusCards.includes('flex items-center justify-between'), 'RightRail status cards must not duplicate raw key-value row layout')
assert(rightRailStatusCards.includes("from './rightRailStatusCardsViewModel'"), 'RightRail status cards must import their focused view model')
assert(rightRailStatusCards.includes('title={rightRailApprovalRiskHeader.title}'), 'RightRail approval card must render title from its view model')
assert(rightRailStatusCards.includes('title={rightRailSystemStatusHeader.title}'), 'RightRail system status card must render title from its view model')
assert(!rightRailStatusCards.includes('title="审批与风险"'), 'RightRail status cards must not inline approval/risk card title')
assert(!rightRailStatusCards.includes('title="系统状态"'), 'RightRail status cards must not inline system status card title')
assert(rightRailStatusCards.includes('buildRightRailApprovalRiskRows()'), 'RightRail approval card must delegate row construction to its view model')
assert(rightRailStatusCards.includes('buildRightRailSystemStatusRows()'), 'RightRail system card must delegate row construction to its view model')
assert(rightRailResourceCard.includes('onClick={() => { void onRefresh() }}'), 'ResourceSnapshotCard must trigger refresh through its prop')
assert(rightRailResourceCard.includes('aria-label="重新同步 Panda 资源快照"'), 'ResourceSnapshotCard refresh button must expose a contextual accessible label')
assert(rightRailResourceCard.includes('KeyValueList'), 'RightRail resource snapshot must render key-value rows through shared KeyValueList')
assert(!rightRailResourceCard.includes('flex items-center justify-between'), 'RightRail resource snapshot must not duplicate raw key-value row layout')
assert(rightRailWorkflowCard.includes('ariaLabel={workflow.progressAriaLabel}'), 'RightRail workflow progress must render the workflow-specific accessible label from its view model')
assert(rightRailWorkflowCardViewModel.includes('export function buildRightRailWorkflowRunViewModel'), 'RightRail workflow view model must export a single-run builder')
assert(rightRailWorkflowCardViewModel.includes('export function buildRightRailWorkflowRunViewModels'), 'RightRail workflow view model must export a list builder')
assert(rightRailWorkflowCardViewModel.includes('workflow: WorkflowItem'), 'RightRail workflow view model must derive display data from WorkflowItem resources')
assert(rightRailWorkflowCardViewModel.includes('progressLabel: `${workflow.progress}%`'), 'RightRail workflow view model must own progress percent label formatting')
assert(rightRailWorkflowCardViewModel.includes('progressAriaLabel: `${workflow.name} 工作流进度`'), 'RightRail workflow view model must own workflow-specific progress aria labels')
assert(rightRailResourceCard.includes("from './rightRailResourceCardViewModel'"), 'RightRail resource snapshot must import its focused view model')
assert(rightRailResourceCard.includes('buildRightRailResourceSnapshotRows({ source, status, refreshedAt, resourcesBffConfig })'), 'RightRail resource snapshot must delegate row construction to its view model')
assert(rightRailResourceCardViewModel.includes('Resources BFF'), 'RightRail resource snapshot view model must show the resources BFF flag state')
assert(rightRailResourceCardViewModel.includes('BFF Endpoint'), 'RightRail resource snapshot view model must show the resources BFF endpoint')
assert(rightRailResourceCardViewModel.includes('resourcesBffConfig.enabled ?'), 'RightRail resource snapshot view model must render the resources BFF enabled state from shared config')
assert(rightRailResourceCardViewModel.includes('resourcesBffConfig.endpoint'), 'RightRail resource snapshot view model must render the resources BFF endpoint from shared config')
assert(rightRailStatusCardsViewModel.includes('StatusDot'), 'RightRail system status view model must use the shared status dot')
assert(rightRailStatusCardsViewModel.includes('export const rightRailApprovalRiskHeader'), 'RightRail status card view model must own approval/risk card header')
assert(rightRailStatusCardsViewModel.includes("title: '审批与风险'"), 'RightRail status card view model must own approval/risk card title')
assert(rightRailStatusCardsViewModel.includes('export const rightRailSystemStatusHeader'), 'RightRail status card view model must own system status card header')
assert(rightRailStatusCardsViewModel.includes("title: '系统状态'"), 'RightRail status card view model must own system status card title')
assert(rightRailStatusCardsViewModel.includes('待审批变更'), 'RightRail status card view model must render approval summary')
assert(rightRailStatusCardsViewModel.includes('高风险工具调用'), 'RightRail status card view model must render high-risk tool call summary')
assert(rightRailStatusCardsViewModel.includes('服务状态正常'), 'RightRail status card view model must render system health status')
assert(rightRailStatusCardsViewModel.includes('buildRightRailApprovalRiskRows'), 'RightRail status card view model must expose approval/risk rows')
assert(rightRailStatusCardsViewModel.includes('buildRightRailSystemStatusRows'), 'RightRail status card view model must expose system status rows')
assert(toolCenter.includes('CapabilityMetricCard'), 'tools page must use shared CapabilityMetricCard through toolCenter')
assert(toolCenter.includes('InsetInfoBlock'), 'tools page must use shared InsetInfoBlock through toolCenter')
assert(dataCenter.includes('CapabilityMetricCard'), 'data page must use shared CapabilityMetricCard through dataCenter')
assert(agentProfileCards.includes('MiniTagList'), 'agents page must use shared MiniTagList through agentProfileCards')
assert(workflowEvidencePrimitives.includes('MiniTagList items={evidenceRefs} prefix="#"'), 'AuditEventRow must render audit evidence refs through MiniTagList')
assert(workflowNodePrimitives.includes('panda-flow-node'), 'workflow node primitives must own FlowNodeCard visual shell')
assert(auditReplay.includes('AuditEventRow'), 'audit page must use shared AuditEventRow through auditReplay')
assert(auditReplay.includes('SummaryMetricList'), 'audit page must use shared SummaryMetricList through auditReplay')
assert(knowledgeBase.includes('ResourceInfoCard'), 'knowledge page must use shared ResourceInfoCard through knowledgeBase')
assert(settingsCenter.includes('ResourceInfoCard'), 'settings page must use shared ResourceInfoCard through settingsCenter')
assert(workflowCanvas.includes('ResourceRuntimeCard'), 'workflows page must use shared ResourceRuntimeCard through workflowCanvas')
assert(agentProfileCards.includes('ResourceRuntimeCard'), 'agents page must use shared ResourceRuntimeCard through agentProfileCards')
for (const pageId of pandaSectionHeaderPageIds) {
  const source = read(pageFileById[pageId])
  const sectionHeaderSource = pageId === 'tasks' ? taskQueue : pageId === 'projects' ? projectWorkspace : pageId === 'automation' ? automationRulesPanel : source
  assert(sectionHeaderSource.includes('SectionHeader'), `${pageId} page must use shared SectionHeader`)
}
assert(read('src/panda/components/rightRailWorkflowCard.tsx').includes('ProgressSummary'), 'RightRail workflow card must use shared ProgressSummary')

const css = read('src/panda/PandaAgentApp.css')
assert(css.includes('.panda-contract-strip'), 'Panda CSS must style the page contract strip')
assert(css.includes('.panda-contract-fields'), 'Panda CSS must allow runtime contract fields to wrap')
assert(css.includes('.panda-mobile-status'), 'Panda CSS must style the mobile shell status row')
assert(css.includes('.panda-agent-app :where(button, input, textarea, select, [tabindex]):focus-visible'), 'Panda CSS must expose a scoped focus-visible ring')
assert(css.includes('outline: 2px solid rgba(248, 113, 113, 0.95)'), 'Panda focus ring must be visibly branded')
assert(css.includes('outline-offset: 3px'), 'Panda focus ring must keep spacing around focused controls')
assert(css.includes(':focus:not(:focus-visible)'), 'Panda CSS must avoid noisy mouse focus outlines while preserving keyboard focus')
assert(css.includes('.panda-skip-link'), 'Panda CSS must style the skip link')
assert(css.includes('.panda-skip-link:focus-visible'), 'Panda skip link must become visible on keyboard focus')
assert(css.includes('pointer-events: none'), 'Panda skip link must stay inactive while visually hidden')
assert(css.includes('pointer-events: auto'), 'Panda skip link must become interactive when focused')
assert(css.includes('grid-template-columns: minmax(280px, 520px) minmax(180px, 1fr) max-content'), 'Panda topbar must reserve stable columns for search, status, and actions')
assert(css.includes('.panda-role-presets'), 'Panda CSS must style the built-in agent role preset selector')
assert(css.includes('.panda-role-card-grid'), 'Panda CSS must provide a stable grid for built-in agent role cards')
assert(css.includes('grid-template-columns: repeat(auto-fit, minmax(238px, 1fr))'), 'Panda role cards must auto-fit with enough width for reference character portraits')
assert(css.includes('.panda-role-portrait'), 'Panda CSS must style visual role portraits for agent cards')
assert(css.includes('.panda-role-portrait img'), 'Panda CSS must render imported role images inside portrait frames')
assert(css.includes('.panda-role-portrait-image'), 'Panda CSS must explicitly style real role portrait images')
assert(css.includes('object-fit: contain'), 'Panda role portrait images must keep their full character visible')
assert(css.includes('padding: 0'), 'Panda role portrait images must not shrink into abstract avatar placeholders')
assert(css.includes('grid-template-columns: minmax(0, 1fr) minmax(300px, 360px)'), 'Panda role preset detail must be a real grid column instead of overlaying cards')
assert(css.includes('.panda-thread-execution-grid'), 'Panda CSS must style a stable thread execution grid')
assert(css.includes('grid-template-columns: minmax(0, 1fr) minmax(240px, 300px)'), 'Panda thread execution grid must reserve a side action column')
assert(css.includes('overflow-wrap: anywhere'), 'Panda terminal must wrap long command text instead of pushing side panels')
assert(css.includes('width: clamp(176px, 14vw, 210px)'), 'Panda workflow nodes must use responsive clamped widths to avoid canvas overlap')
assert(css.includes('padding: 22px'), 'Panda workflow canvas stage must keep node padding away from clipped edges')
assert(css.includes('max-height: 620px'), 'Panda thread list must cap height and scroll instead of pushing the work panel')
assert(css.includes('overflow-x: auto'), 'Panda tab and terminal rows must allow horizontal overflow without layout breakage')
assert(css.includes('.panda-topbar-status'), 'Panda CSS must style the topbar status text')
assert(css.includes('text-overflow: ellipsis'), 'Panda topbar status must ellipsize instead of vertical wrapping')
assert(css.includes('white-space: nowrap'), 'Panda topbar status must stay on one line')
assert(css.includes('min-width: max-content'), 'Panda toolbar must avoid squeezing the status text into vertical wrapping')
assert(css.includes('@media (max-width: 860px)'), 'Panda CSS must keep the mobile breakpoint')
assert(css.includes('.panda-mobile-status span:first-child'), 'Panda mobile status must distinguish the current page label')
assert(css.includes('.panda-state-action'), 'Panda CSS must style the resource retry action')

const docs = read('docs/PANDA_FRONTEND_BACKEND_ALIGNMENT.md')
for (const phrase of pandaAlignmentDocRequiredPhrases) {
  assert(docs.includes(phrase), `Alignment doc missing section: ${phrase}`)
}
assert(docs.includes('frontend/src/panda/types/agentRoleTypes.ts'), 'Alignment doc must name the agent role type boundary')
assert(docs.includes('frontend/src/panda/data/agentRolePortraits.ts'), 'Alignment doc must name the agent role portrait registry')
assert(docs.includes('frontend/src/panda/api/agentRoleAdapters.ts'), 'Alignment doc must name the agent role adapter boundary')
assert(docs.includes('ApiAgentRolePreset'), 'Alignment doc must document the agent role API DTO')
assert(docs.includes('portrait_key'), 'Alignment doc must document the agent role portrait key field')
assert(docs.includes('default_permissions'), 'Alignment doc must document the agent role default permission field')
assert(docs.includes('role-template endpoint'), 'Alignment doc must identify the future role-template backend alignment point')

const statuses = []
for (const pageId of pageIds) {
  const url = pageId === 'home' ? 'http://127.0.0.1:3000/' : `http://127.0.0.1:3000/#${pageId}`
  statuses.push([pageId, await requestStatus(url)])
}

const reachable = statuses.filter(([, status]) => status === 200)
if (reachable.length > 0) {
  assert(reachable.length === pageIds.length, `Only ${reachable.length}/${pageIds.length} Panda routes returned 200`)
  console.log(`Panda workbench verified: ${requiredFiles.length} files, ${pageIds.length} routes reachable.`)
} else {
  console.log(`Panda workbench static checks passed: ${requiredFiles.length} files. Dev server route check skipped.`)
}
