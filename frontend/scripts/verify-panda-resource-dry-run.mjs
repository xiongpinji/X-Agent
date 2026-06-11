import { writeFileSync } from 'node:fs'
import {
  cleanupPandaTsProbeTempDir,
  createPandaTsProbeTempDir,
  importProbeModule,
  rewritePandaApiProbeImports,
  rewriteProbeImports,
  transpilePandaApiProbeFiles,
  transpilePandaTsFile,
} from './panda-ts-probe-utils.mjs'

const outputJson = process.argv.includes('--json')

async function loadDryRunModules() {
  const tempDir = createPandaTsProbeTempDir('panda-resource-dry-run')
  transpilePandaApiProbeFiles(tempDir, [
    'resourceKeys.ts',
    'runtimeMapping.ts',
    'homeApiContracts.ts',
    'executionApiContracts.ts',
    'organizationApiContracts.ts',
    'knowledgeApiContracts.ts',
    'governanceApiContracts.ts',
    'resourceApiContracts.ts',
    'snapshotApiContracts.ts',
    'resourceSnapshotTypes.ts',
    'apiContracts.ts',
    'agentRoleAdapters.ts',
    'homeAdapters.ts',
    'executionResourceAdapters.ts',
    'organizationResourceAdapters.ts',
    'knowledgeResourceAdapters.ts',
    'governanceResourceAdapters.ts',
    'resourceItemAdapters.ts',
    'resourceSnapshotAdapter.ts',
    'resourceSnapshotFixtures.ts',
    'resourceRuntimeFixtures.ts',
    'resourceAdapterFixtures.ts',
    'resourceDryRunFixtures.ts',
    'homeActivityFixtures.ts',
    'resourcesValidation.ts',
    'adapters.ts',
    'resourcesBffConfig.ts',
    'resourcesHttpClient.ts',
    'resourcesApiLoader.ts',
    'resourceFallbackSnapshot.ts',
    'resourcesClient.ts',
    'bootstrapResources.ts',
  ])
  for (const fileName of [
    'mockExecutionResources.ts',
    'mockKnowledgeResources.ts',
    'mockOrganizationResources.ts',
    'mockResources.ts',
  ]) {
    transpilePandaTsFile(tempDir, `src/panda/data/${fileName}`, fileName.replace(/\.ts$/, '.mjs'))
  }
  transpilePandaTsFile(tempDir, 'src/panda/resourceRuntimeFields.ts', 'resourceRuntimeFields.mjs')
  rewritePandaApiProbeImports(tempDir)
  rewriteProbeImports(tempDir, 'mockResources.mjs', [
    [/from ['"]\.\/mockExecutionResources['"]/g, "from './mockExecutionResources.mjs'"],
    [/from ['"]\.\/mockKnowledgeResources['"]/g, "from './mockKnowledgeResources.mjs'"],
    [/from ['"]\.\/mockOrganizationResources['"]/g, "from './mockOrganizationResources.mjs'"],
  ])
  rewriteProbeImports(tempDir, 'resourceFallbackSnapshot.mjs', [
    [/from ['"]\.\.\/data\/mockResources['"]/g, "from './mockResources.mjs'"],
  ])
  rewriteProbeImports(tempDir, 'resourceSnapshotFixtures.mjs', [
    [/from ['"]\.\/adapters['"]/g, "from './adapters.mjs'"],
    [/from ['"]\.\/resourceAdapterFixtures['"]/g, "from './resourceAdapterFixtures.mjs'"],
    [/from ['"]\.\/resourceDryRunFixtures['"]/g, "from './resourceDryRunFixtures.mjs'"],
    [/from ['"]\.\/homeActivityFixtures['"]/g, "from './homeActivityFixtures.mjs'"],
    [/from ['"]\.\/resourceRuntimeFixtures['"]/g, "from './resourceRuntimeFixtures.mjs'"],
    [/from ['"]\.\/resourcesValidation['"]/g, "from './resourcesValidation.mjs'"],
  ])
  rewriteProbeImports(tempDir, 'resourceAdapterFixtures.mjs', [
    [/from ['"]\.\/adapters['"]/g, "from './adapters.mjs'"],
  ])
  rewriteProbeImports(tempDir, 'resourceDryRunFixtures.mjs', [
    [/from ['"]\.\/adapters['"]/g, "from './adapters.mjs'"],
    [/from ['"]\.\/resourceRuntimeFixtures['"]/g, "from './resourceRuntimeFixtures.mjs'"],
  ])
  rewriteProbeImports(tempDir, 'homeActivityFixtures.mjs', [
    [/from ['"]\.\/resourceRuntimeFixtures['"]/g, "from './resourceRuntimeFixtures.mjs'"],
  ])
  rewriteProbeImports(tempDir, 'resourcesBffConfig.mjs', [
    [/from ['"]\.\/resourcesHttpClient['"]/g, "from './resourcesHttpClient.mjs'"],
  ])
  rewriteProbeImports(tempDir, 'resourcesApiLoader.mjs', [
    [/from ['"]\.\/adapters['"]/g, "from './adapters.mjs'"],
    [/from ['"]\.\/resourcesValidation['"]/g, "from './resourcesValidation.mjs'"],
  ])
  rewriteProbeImports(tempDir, 'resourcesClient.mjs', [
    [/from ['"]\.\/resourceFallbackSnapshot['"]/g, "from './resourceFallbackSnapshot.mjs'"],
    [/from ['"]\.\/resourcesApiLoader['"]/g, "from './resourcesApiLoader.mjs'"],
  ])
  rewriteProbeImports(tempDir, 'bootstrapResources.mjs', [
    [/from ['"]\.\/resourcesBffConfig['"]/g, "from './resourcesBffConfig.mjs'"],
    [/from ['"]\.\/resourcesHttpClient['"]/g, "from './resourcesHttpClient.mjs'"],
    [/from ['"]\.\/resourcesApiLoader['"]/g, "from './resourcesApiLoader.mjs'"],
  ])

  try {
    const validationModule = await importProbeModule(tempDir, 'resourcesValidation.mjs')
    const adaptersModule = await importProbeModule(tempDir, 'adapters.mjs')
    const fixtureModule = await importProbeModule(tempDir, 'resourceSnapshotFixtures.mjs')
    const bffConfigModule = await importProbeModule(tempDir, 'resourcesBffConfig.mjs')
    const apiLoaderModule = await importProbeModule(tempDir, 'resourcesApiLoader.mjs')
    const resourcesClientModule = await importProbeModule(tempDir, 'resourcesClient.mjs')
    const bootstrapModule = await importProbeModule(tempDir, 'bootstrapResources.mjs')
    const runtimeFieldsModule = await importProbeModule(tempDir, 'resourceRuntimeFields.mjs')
    return {
      validatePandaResourceSnapshot: validationModule.validatePandaResourceSnapshot,
      mapPandaResourceSnapshot: adaptersModule.mapPandaResourceSnapshot,
      mapActivityItem: adaptersModule.mapActivityItem,
      pandaCoreRuntimeFields: runtimeFieldsModule.pandaCoreRuntimeFields,
      aggregateResourcesBffDryRunFixture: fixtureModule.aggregateResourcesBffDryRunFixture,
      workbenchActivityDryRunFixture: fixtureModule.workbenchActivityDryRunFixture,
      shouldUsePandaResourcesBff: bffConfigModule.shouldUsePandaResourcesBff,
      getPandaResourcesBffConfig: bffConfigModule.getPandaResourcesBffConfig,
      createPandaResourcesApiLoader: apiLoaderModule.createPandaResourcesApiLoader,
      setPandaResourcesApiLoader: apiLoaderModule.setPandaResourcesApiLoader,
      loadPandaResourcesFromApi: apiLoaderModule.loadPandaResourcesFromApi,
      getPandaResourceSnapshot: resourcesClientModule.getPandaResourceSnapshot,
      loadPandaResources: resourcesClientModule.loadPandaResources,
      bootstrapPandaResources: bootstrapModule.bootstrapPandaResources,
      cleanup: () => cleanupPandaTsProbeTempDir(tempDir),
    }
  } catch (error) {
    cleanupPandaTsProbeTempDir(tempDir)
    throw error
  }
}

async function check(name, run) {
  try {
    await run()
    return { name, status: 'passed' }
  } catch (error) {
    return {
      name,
      status: 'failed',
      error: error instanceof Error ? error.message : String(error),
    }
  }
}

function assertRuntimeShape(runtime, label) {
  if (!runtime || typeof runtime !== 'object') {
    throw new Error(`${label} runtime metadata must be an object.`)
  }
  const validRiskLevels = new Set(['success', 'warning', 'danger', 'neutral'])
  if (typeof runtime.status !== 'string' || !validRiskLevels.has(runtime.riskLevel)) {
    throw new Error(`${label} runtime metadata must expose string status and valid riskLevel.`)
  }
  if (typeof runtime.progress !== 'number' || runtime.progress < 0 || runtime.progress > 100) {
    throw new Error(`${label} runtime metadata must expose clamped numeric progress.`)
  }
  if (typeof runtime.ownerAgent !== 'string' || typeof runtime.updatedAt !== 'string' || !Array.isArray(runtime.evidenceRefs)) {
    throw new Error(`${label} runtime metadata must expose ownerAgent, updatedAt, and evidenceRefs array.`)
  }
}

function assertApiRuntimeFields(item, fields, label) {
  for (const field of fields) {
    if (!(field in item)) {
      throw new Error(`${label} fixture item must include core API runtime field: ${field}.`)
    }
  }
}

const modules = await loadDryRunModules()
const fixture = modules.aggregateResourcesBffDryRunFixture
const activityFixture = modules.workbenchActivityDryRunFixture
let mapped
let mappedActivity
try {
  const validated = modules.validatePandaResourceSnapshot(fixture)
  mapped = modules.mapPandaResourceSnapshot(validated)
  mappedActivity = modules.mapActivityItem(activityFixture)
} finally {
  modules.cleanup()
}

const checkRuns = [
  ['resources-bootstrap-import-safe-default-env', () => {
    if (typeof modules.bootstrapPandaResources !== 'function') {
      throw new Error('Resources bootstrap module did not import safely with default env handling.')
    }
  }],
  ['resources-bff-default-disabled', () => {
    const config = modules.getPandaResourcesBffConfig({
      VITE_PANDA_RESOURCES_BFF: 'false',
      VITE_PANDA_RESOURCES_BFF_ENDPOINT: '',
    })
    if (config.enabled || config.endpoint !== '/api/v1/workbench/resources') {
      throw new Error('Resources BFF must stay disabled by default and use the aggregate endpoint fallback.')
    }
  }],
  ['resources-bff-explicit-enabled', () => {
    const env = {
      VITE_PANDA_RESOURCES_BFF: 'true',
      VITE_PANDA_RESOURCES_BFF_ENDPOINT: '/api/v1/workbench/resources/probe',
    }
    if (!modules.shouldUsePandaResourcesBff(env) || modules.getPandaResourcesBffConfig(env).endpoint !== env.VITE_PANDA_RESOURCES_BFF_ENDPOINT) {
      throw new Error('Resources BFF config did not honor the explicit opt-in flag and endpoint.')
    }
  }],
  ['resources-bootstrap-disabled-clears-loader', async () => {
    modules.setPandaResourcesApiLoader(async () => fixture)
    modules.bootstrapPandaResources({ VITE_PANDA_RESOURCES_BFF: 'false' })
    const snapshot = await modules.loadPandaResourcesFromApi()
    if (snapshot !== null) {
      throw new Error('Disabled resources BFF bootstrap must clear the API loader.')
    }
  }],
  ['resources-bootstrap-enabled-registers-loader', async () => {
    const calls = []
    const previousFetch = globalThis.fetch
    const previousLocalStorage = globalThis.localStorage
    globalThis.localStorage = { getItem: () => 'probe-token' }
    globalThis.fetch = async (url, options = {}) => {
      calls.push({ url: String(url), authorization: options.headers?.Authorization })
      return {
        ok: true,
        json: async () => fixture,
      }
    }
    try {
      modules.bootstrapPandaResources({
        VITE_PANDA_RESOURCES_BFF: 'true',
        VITE_PANDA_RESOURCES_BFF_ENDPOINT: '/api/v1/workbench/resources/probe',
      })
      const snapshot = await modules.loadPandaResourcesFromApi()
      if (!snapshot || snapshot.tasks[0].runtime?.ownerAgent !== 'Panda Planner') {
        throw new Error('Enabled resources BFF bootstrap did not validate and map the API snapshot.')
      }
      if (calls[0]?.url !== '/api/v1/workbench/resources/probe' || calls[0]?.authorization !== 'Bearer probe-token') {
        throw new Error('Enabled resources BFF bootstrap did not use the configured endpoint and auth token.')
      }
    } finally {
      modules.setPandaResourcesApiLoader(null)
      globalThis.fetch = previousFetch
      if (previousLocalStorage === undefined) {
        delete globalThis.localStorage
      } else {
        globalThis.localStorage = previousLocalStorage
      }
    }
  }],
  ['resources-client-mock-fallback', async () => {
    modules.setPandaResourcesApiLoader(null)
    const result = await modules.loadPandaResources()
    const fallback = modules.getPandaResourceSnapshot()
    if (result.source !== 'mock' || result.error || result.resources.tasks[0]?.id !== fallback.tasks[0]?.id) {
      throw new Error('loadPandaResources must return the fallback snapshot when no API loader is registered.')
    }
  }],
  ['resources-client-api-success', async () => {
    modules.setPandaResourcesApiLoader(async () => fixture)
    try {
      const result = await modules.loadPandaResources()
      if (result.source !== 'api' || result.error || result.resources.tasks[0]?.runtime?.ownerAgent !== 'Panda Planner') {
        throw new Error('loadPandaResources must return mapped API resources when the loader succeeds.')
      }
    } finally {
      modules.setPandaResourcesApiLoader(null)
    }
  }],
  ['resources-client-invalid-api-fallback', async () => {
    modules.setPandaResourcesApiLoader(modules.createPandaResourcesApiLoader({
      getPandaResources: async () => ({ tasks: [null] }),
    }))
    try {
      const result = await modules.loadPandaResources()
      if (result.source !== 'mock' || !result.error || result.resources.tasks[0]?.id !== modules.getPandaResourceSnapshot().tasks[0]?.id) {
        throw new Error('loadPandaResources must degrade invalid API shapes to mock-with-error.')
      }
    } finally {
      modules.setPandaResourcesApiLoader(null)
    }
  }],
  ['all-view-slices-present', () => {
    for (const [key, value] of Object.entries(mapped)) {
      if (!Array.isArray(value) || value.length !== 1) {
        throw new Error(`${key} should map to a single-item array.`)
      }
    }
  }],
  ['all-runtime-metadata-shapes', () => {
    for (const [key, value] of Object.entries(mapped)) {
      assertRuntimeShape(value[0]?.runtime, key)
    }
    assertRuntimeShape(mappedActivity.runtime, 'homeActivity')
  }],
  ['aggregate-fixture-core-runtime-fields', () => {
    for (const [key, value] of Object.entries(fixture)) {
      const item = value?.[0]
      if (!item || typeof item !== 'object') {
        throw new Error(`${key} fixture must expose a representative object item.`)
      }
      assertApiRuntimeFields(item, modules.pandaCoreRuntimeFields, key)
    }
    assertApiRuntimeFields(activityFixture, modules.pandaCoreRuntimeFields, 'homeActivity')
  }],
  ['task-runtime-fields', () => {
    const runtime = mapped.tasks[0].runtime
    if (mapped.tasks[0].progress !== 88 || runtime?.ownerAgent !== 'Panda Planner' || runtime.riskLevel !== 'warning') {
      throw new Error('Task runtime metadata did not map owner_agent, progress, or risk_level.')
    }
    if (runtime.updatedAt !== '2026-06-10T06:00:00+08:00' || runtime.evidenceRefs[0] !== 'ev-task-1') {
      throw new Error('Task runtime metadata did not map updated_at or evidence_refs.')
    }
  }],
  ['home-activity-runtime-fields', () => {
    const runtime = mappedActivity.runtime
    if (mappedActivity.tone !== 'neutral' || runtime?.ownerAgent !== 'Activity Agent' || runtime.riskLevel !== 'warning') {
      throw new Error('Home activity runtime metadata did not map owner_agent or risk_level while preserving explicit tone.')
    }
    if (runtime.progress !== 76 || runtime.updatedAt !== '2026-06-10T07:05:00+08:00' || runtime.evidenceRefs[0] !== 'ev-activity-1') {
      throw new Error('Home activity runtime metadata did not map progress, updated_at, or evidence_refs.')
    }
  }],
  ['workflow-node-runtime-fields', () => {
    const node = mapped.workflowNodes[0]
    if (node.x !== 25 || node.y !== 35 || node.runtime?.progress !== 100 || node.runtime?.ownerAgent !== 'Gate Agent') {
      throw new Error('Workflow node geometry or runtime metadata did not map.')
    }
  }],
  ['cross-resource-runtime-fields', () => {
    const expectations = [
      ['projects', 'Panda Builder', 'success', 'ev-project-1'],
      ['agents', 'Platform', 'success', 'ev-agent-1'],
      ['knowledgeSources', 'Memory Agent', 'success', 'ev-knowledge-1'],
      ['tools', 'Tool Agent', 'warning', 'ev-tool-1'],
      ['dataSources', 'Data Agent', 'neutral', 'ev-data-1'],
      ['automationRules', 'Automation Agent', 'warning', 'ev-automation-1'],
    ]
    for (const [key, ownerAgent, riskLevel, evidenceRef] of expectations) {
      const item = mapped[key]?.[0]
      const runtime = item?.runtime
      if (runtime?.ownerAgent !== ownerAgent || runtime?.riskLevel !== riskLevel || runtime?.evidenceRefs?.[0] !== evidenceRef) {
        throw new Error(`${key} runtime metadata did not map owner_agent, risk_level, or evidence_refs.`)
      }
    }
  }],
  ['audit-evidence-fields', () => {
    const audit = mapped.auditEvents[0]
    if (audit.riskLevel !== 'success' || audit.evidenceRefs[0] !== 'ev-audit-1' || audit.runtime?.ownerAgent !== 'Audit Agent') {
      throw new Error('Audit risk/evidence/runtime fields did not map.')
    }
  }],
  ['settings-readonly-runtime', () => {
    const settings = mapped.settingsSections[0]
    if (settings.status !== 'readonly' || settings.runtime?.updatedAt !== '2026-06-10T06:55:00+08:00') {
      throw new Error('Settings readonly status or updated_at did not map.')
    }
  }],
]

const checks = []
for (const [name, run] of checkRuns) {
  checks.push(await check(name, run))
}

const failedChecks = checks.filter((item) => item.status !== 'passed')
const result = {
  productName: 'Panda Agent',
  technicalCore: 'X-Agent Autonomous Framework',
  status: failedChecks.length === 0 ? 'passed' : 'failed',
  checkedAt: new Date().toISOString(),
  fixture: 'aggregate resources BFF dry-run',
  validation: 'src/panda/api/resourcesValidation.ts',
  adapter: 'src/panda/api/adapters.ts',
  checks,
}

if (outputJson) {
  console.log(JSON.stringify(result, null, 2))
} else {
  console.log(`Panda resources dry-run: ${result.status}`)
  console.log(`Checks: ${checks.filter((item) => item.status === 'passed').length}/${checks.length} passed`)
  for (const item of failedChecks) {
    console.log(`- [failed] ${item.name}: ${item.error}`)
  }
}

if (process.env.PANDA_RESOURCE_DRY_RUN_RESULT_PATH) {
  writeFileSync(process.env.PANDA_RESOURCE_DRY_RUN_RESULT_PATH, `${JSON.stringify(result, null, 2)}\n`)
}

if (failedChecks.length > 0) {
  process.exit(1)
}
