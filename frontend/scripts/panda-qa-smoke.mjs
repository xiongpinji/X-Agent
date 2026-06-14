import { existsSync, mkdirSync, writeFileSync } from 'node:fs'
import os from 'node:os'
import { resolve } from 'node:path'
import { pandaScriptRoot, read, readJson, requestStatus } from './panda-script-utils.mjs'

const root = pandaScriptRoot
const manifest = readJson('src/panda/pandaFrontendManifest.json')
const useBrowser = process.argv.includes('--browser')
const requireBrowser = process.argv.includes('--require-browser')
const outputJson = process.argv.includes('--json')
const devServer = process.env.PANDA_QA_URL ?? manifest.visualReviewEvidence?.devServer ?? 'http://127.0.0.1:3000'
const screenshotDir =
  process.env.PANDA_QA_SCREENSHOT_DIR ?? resolve(os.tmpdir(), `panda-scripted-qa-${Date.now()}`)

const routes = manifest.visualReviewTargets.map((target) => ({
  ...target,
  url: target.route === 'home' ? devServer : `${devServer}/#${target.route}`,
}))

function probeStaticContracts() {
  const shell = read('src/panda/components/Shell.tsx')
  const shellChrome = read('src/panda/components/shellChrome.tsx')
  const css = read('src/panda/PandaAgentApp.css')
  const common = read('src/panda/components/common.tsx')
  const statusPrimitives = read('src/panda/components/statusPrimitives.tsx')
  const statusDotViewModel = read('src/panda/components/statusDotViewModel.ts')
  const progressPrimitives = read('src/panda/components/progressPrimitives.tsx')
  const report = read('scripts/panda-alignment-report.mjs')
  const packageJson = JSON.parse(read('package.json'))
  const adapterScript = read('scripts/verify-panda-adapters.mjs')
  const resourceDryRunScript = read('scripts/verify-panda-resource-dry-run.mjs')
  const resourceContractScript = read('scripts/verify-panda-resource-contracts.mjs')
  const resourceValidationScript = read('scripts/verify-panda-resource-validation.mjs')
  const closeoutEvidenceScript = read('scripts/panda-closeout-evidence.mjs')
  const closeoutPlanScript = read('scripts/panda-frontend-closeout-plan.mjs')
  const scriptUtils = read('scripts/panda-script-utils.mjs')
  const resourcesClient = read('src/panda/api/resourcesClient.ts')
  const resourcesApiLoader = read('src/panda/api/resourcesApiLoader.ts')
  const resourcesValidation = read('src/panda/api/resourcesValidation.ts')
  const resourceKeys = read('src/panda/api/resourceKeys.ts')
  const agentRoleTypes = read('src/panda/types/agentRoleTypes.ts')
  const agentRolePresetFixtures = read('src/panda/data/agentRolePresetFixtures.ts')
  const agentRolePresets = read('src/panda/data/agentRolePresets.ts')
  const agentRolePortraits = read('src/panda/data/agentRolePortraits.ts')
  const agentRoleAdapters = read('src/panda/api/agentRoleAdapters.ts')
  const organizationApiContracts = read('src/panda/api/organizationApiContracts.ts')

  return [
    {
      id: 'skip-link',
      passed: shell.includes('className="panda-skip-link" href="#panda-main-content"') && shell.includes('id="panda-main-content"'),
      detail: 'Shell exposes a skip link targeting the main Panda workspace.',
    },
    {
      id: 'main-landmark',
      passed: shell.includes('aria-label={`${pageLabel} 工作区`}'),
      detail: 'Main content landmark follows the active Panda module label.',
    },
    {
      id: 'active-navigation',
      passed: shellChrome.includes("aria-current={activePage === item.id ? 'page' : undefined}"),
      detail: 'Navigation exposes aria-current for the active module.',
    },
    {
      id: 'focus-visible',
      passed:
        css.includes('.panda-agent-app :where(button, input, textarea, select, [tabindex]):focus-visible') &&
        css.includes('.panda-skip-link:focus-visible'),
      detail: 'Panda-scoped keyboard focus styling and skip-link visibility are present.',
    },
    {
      id: 'progress-semantics',
      passed:
        progressPrimitives.includes('role="progressbar"') &&
        progressPrimitives.includes('aria-label={ariaLabel}') &&
        progressPrimitives.includes('aria-valuetext={`${clampedValue}%`}'),
      detail: 'Progress meters expose accessible progress semantics.',
    },
    {
      id: 'status-semantics',
      passed:
        statusPrimitives.includes('role="img"') &&
        statusPrimitives.includes('aria-label={statusDot.ariaLabel}') &&
        statusDotViewModel.includes('ariaLabel: label ?? `风险等级：${title}`'),
      detail: 'Status dots expose readable labels for non-visual users.',
    },
    {
      id: 'alignment-report-evidence',
      passed:
        report.includes('Visual review evidence') &&
        report.includes('Accessibility evidence') &&
        report.includes('Next frontend tasks') &&
        report.includes('resourcesValidationEvidence'),
      detail: 'Alignment report surfaces visual, accessibility, and closeout evidence.',
    },
    {
      id: 'resources-bff-validation',
      passed:
        resourcesClient.includes('loadPandaResources') &&
        resourcesApiLoader.includes('validatePandaResourceSnapshot') &&
        resourcesApiLoader.includes('mapPandaResourceSnapshot') &&
        resourcesValidation.includes('PandaResourceValidationError') &&
        resourcesValidation.includes('!isRecord(snapshot)') &&
        resourcesValidation.includes('!Array.isArray(value)') &&
        resourcesValidation.includes('must be an object') &&
        resourcesValidation.includes('is not a known resource slice'),
      detail: 'Resources BFF snapshots are validated before adapter mapping and reject unknown keys, non-array fields, and non-object resource items.',
    },
    {
      id: 'resources-validation-executable',
      passed:
        packageJson.scripts?.['verify:panda:resources'] === 'node scripts/verify-panda-resource-validation.mjs' &&
        resourceValidationScript.includes('valid-array-fields') &&
        resourceValidationScript.includes('non-array-resource-field') &&
        resourceValidationScript.includes('non-object-resource-item') &&
        resourceValidationScript.includes('unknown-resource-field') &&
        resourceValidationScript.includes('PANDA_RESOURCE_VALIDATION_RESULT_PATH'),
      detail: 'Resources BFF validation has an executable positive and negative contract probe.',
    },
    {
      id: 'resources-contract-consistency',
      passed:
        packageJson.scripts?.['verify:panda:contracts'] === 'node scripts/verify-panda-resource-contracts.mjs' &&
        resourceKeys.includes('pandaResourceKeyPairs') &&
        resourceKeys.includes('pandaApiResourceKeys') &&
        resourceKeys.includes('pandaViewResourceKeys') &&
        resourceContractScript.includes('manifest-api-vs-resource-boundary-api') &&
        resourceContractScript.includes('manifest-view-vs-resource-boundary-view') &&
        resourceContractScript.includes('resource-boundary-api-vs-api-snapshot') &&
        resourceContractScript.includes('resource-boundary-view-vs-view-snapshot') &&
        resourceContractScript.includes('validation-vs-api-snapshot') &&
        resourceContractScript.includes('mapper-vs-api-snapshot') &&
        resourceContractScript.includes('view-snapshot-vs-fallback') &&
        resourceContractScript.includes('contracts-vs-view-snapshot') &&
        resourceContractScript.includes('closeout-pending-routes-vs-route-rollover') &&
        resourceContractScript.includes('module-resource-hooks-vs-type-bindings') &&
        resourceContractScript.includes('module-resource-types-vs-type-map') &&
        resourceContractScript.includes('expectedModulePageResourceHookBindings') &&
        resourceContractScript.includes('expectedModulePageResourceTypeBindings') &&
        resourceContractScript.includes('diffMembers') &&
        resourceContractScript.includes('missingFromLeft') &&
        resourceContractScript.includes('missingFromRight') &&
        resourceContractScript.includes('PANDA_RESOURCE_CONTRACT_RESULT_PATH'),
      detail: 'Resource contract keys, mock-ready contract fields, closeout pending route handoff fields, standard module page content keys/page fields, and page -> hook -> PageResources type bindings are checked across the manifest, shared resource key pairs, validation, adapters, fallback snapshots, page contracts, and module page structure with explicit drift diffs.',
    },
    {
      id: 'route-api-resources-evidence',
      passed:
        report.includes('routeApiResourcesEvidence') &&
        closeoutEvidenceScript.includes('route-api-resources-evidence') &&
        closeoutEvidenceScript.includes('frontendCompletion') &&
        closeoutEvidenceScript.includes('buildRouteApiResourcesEvidence') &&
        closeoutPlanScript.includes('routeApiResourcesEvidence') &&
        closeoutPlanScript.includes('frontendCompletionEvidence') &&
        closeoutPlanScript.includes('Frontend Completion Evidence') &&
        report.includes('routeApiResources') &&
        scriptUtils.includes('boundaryApiResources') &&
        scriptUtils.includes('unknownRouteApiResources') &&
        scriptUtils.includes('missingRouteApiResources') &&
        scriptUtils.includes('resourceKeys.ts') &&
        scriptUtils.includes('backend API resource boundary'),
      detail: 'Alignment report exposes route API resource boundary evidence with route, boundary, unknown, and missing API resource key diffs for backend handoff.',
    },
    {
      id: 'adapter-behavior-executable',
      passed:
        packageJson.scripts?.['verify:panda:adapters'] === 'node scripts/verify-panda-adapters.mjs' &&
        adapterScript.includes('tone-fallback') &&
        adapterScript.includes('progress-clamp') &&
        adapterScript.includes('runtime-snake-case-mapping') &&
        adapterScript.includes('activity-runtime-mapping') &&
        adapterScript.includes('evidence-refs-copy') &&
        adapterScript.includes('agent-permissions-copy') &&
        adapterScript.includes('agent-role-preset-mapping') &&
        adapterScript.includes('resource-snapshot-mapping') &&
        adapterScript.includes('PANDA_ADAPTER_RESULT_PATH'),
      detail: 'Adapter behavior has executable checks for tone fallback, progress clamping, task/activity runtime metadata, evidence refs and agent permissions copy semantics, agent role preset mapping, and resource snapshot mapping.',
    },
    {
      id: 'agent-role-card-contract',
      passed:
        organizationApiContracts.includes('type ApiAgentRolePreset') &&
        agentRoleTypes.includes('type AgentRolePreset') &&
        agentRoleTypes.includes('readonly portraitSrc: string') &&
        agentRolePresetFixtures.includes('apiAgentRolePresetFixtures') &&
        agentRolePresetFixtures.includes('readonly ApiAgentRolePreset[]') &&
        agentRolePresets.includes('mapAgentRolePresets(apiAgentRolePresetFixtures)') &&
        agentRolePresets.includes("from './agentRolePresetFixtures'") &&
        agentRolePresetFixtures.includes('default_permissions') &&
        agentRolePresetFixtures.includes('portrait_key') &&
        agentRolePortraits.includes('resolveAgentRolePortrait') &&
        agentRoleAdapters.includes('mapAgentRolePreset') &&
        agentRoleAdapters.includes('resolveAgentRolePortrait(item.portrait_key ?? id)'),
      detail: 'Create-agent role cards keep a backend-aligned ApiAgentRolePreset fixture shape, AgentRolePreset view model, portrait key registry, and mapper boundary without calling backend clients.',
    },
    {
      id: 'resource-dry-run-fixture',
      passed:
        packageJson.scripts?.['verify:panda:dry-run'] === 'node scripts/verify-panda-resource-dry-run.mjs' &&
        resourceDryRunScript.includes('aggregate resources BFF dry-run') &&
        resourceDryRunScript.includes('aggregate-fixture-core-runtime-fields') &&
        resourceDryRunScript.includes('pandaCoreRuntimeFields') &&
        resourceDryRunScript.includes('task-runtime-fields') &&
        resourceDryRunScript.includes('workflow-node-runtime-fields') &&
        resourceDryRunScript.includes('audit-evidence-fields') &&
        resourceDryRunScript.includes('resources-bootstrap-import-safe-default-env') &&
        resourceDryRunScript.includes('resources-bff-explicit-disabled') &&
        resourceDryRunScript.includes('resources-bff-explicit-enabled') &&
        resourceDryRunScript.includes('resources-bootstrap-disabled-clears-loader') &&
        resourceDryRunScript.includes('resources-bootstrap-enabled-registers-loader') &&
        resourceDryRunScript.includes('resources-client-mock-fallback') &&
        resourceDryRunScript.includes('resources-client-api-success') &&
        resourceDryRunScript.includes('resources-client-invalid-api-fallback') &&
        resourceDryRunScript.includes('aggregateResourcesBffDryRunFixture') &&
        resourceDryRunScript.includes('PANDA_RESOURCE_DRY_RUN_RESULT_PATH'),
      detail: 'Aggregate resources BFF dry-run fixture is shared from the API fixture layer and validates cross-resource runtime fields, shared pandaCoreRuntimeFields core runtime API field coverage, runtime shape stability, home activity runtime metadata, default import safety, explicit disable/enable config, bootstrap loader behavior, and loadPandaResources mock/api/error fallback behavior.',
    },
  ]
}

async function probeRoutes() {
  const statuses = []
  for (const route of routes) {
    statuses.push({
      route: route.route,
      url: route.url,
      viewport: route.viewport,
      status: await requestStatus(route.url),
    })
  }
  return statuses
}

async function probeBrowser() {
  try {
    const { chromium } = await import('playwright')
    mkdirSync(screenshotDir, { recursive: true })
    const browser = await chromium.launch()
    const page = await browser.newPage()
    const browserRoutes = []
    const consoleMessages = []

    page.on('console', (message) => {
      if (['error', 'warning'].includes(message.type())) {
        consoleMessages.push(`${message.type()}: ${message.text()}`)
      }
    })

    for (const route of routes) {
      const [width, height] = route.viewport.split('x').map(Number)
      await page.setViewportSize({ width, height })
      await page.goto(route.url, { waitUntil: 'networkidle' })
      const screenshotPath = resolve(screenshotDir, `${route.route}-${route.viewport}.png`)
      await page.screenshot({ path: screenshotPath, fullPage: false })
      const mainLabel = await page.locator('#panda-main-content').getAttribute('aria-label')
      const activeNav = await page.locator('[aria-current="page"]').first().getAttribute('aria-label')
      browserRoutes.push({
        route: route.route,
        url: page.url(),
        title: await page.title(),
        mainLabel,
        activeNav,
        screenshotPath,
      })
    }

    await page.goto(`${devServer}/`, { waitUntil: 'networkidle' })
    await page.getByLabel('创建 Panda Agent 任务').fill('验证 Panda 工作台脚本化 QA')
    await page.getByLabel('打开工作流模块').click()
    const interaction = {
      url: page.url(),
      activeNav: await page.locator('[aria-current="page"]').first().getAttribute('aria-label'),
      mainLabel: await page.locator('#panda-main-content').getAttribute('aria-label'),
    }

    await browser.close()

    return {
      status: 'passed',
      screenshotDir,
      routes: browserRoutes,
      interaction,
      consoleMessages,
    }
  } catch (error) {
    if (requireBrowser) {
      throw error
    }
    return {
      status: 'skipped',
      reason: error instanceof Error ? error.message : 'Playwright browser QA is unavailable.',
      screenshotDir: null,
      routes: [],
      interaction: null,
      consoleMessages: [],
    }
  }
}

const routeStatuses = await probeRoutes()
const staticProbes = probeStaticContracts()
const browserProbe = useBrowser ? await probeBrowser() : { status: 'not-requested' }

const reachableRoutes = routeStatuses.filter((route) => route.status === 200)
const routeStatus =
  reachableRoutes.length === routes.length
    ? 'passed'
    : reachableRoutes.length === 0
      ? 'skipped'
      : 'failed'
const staticStatus = staticProbes.every((probe) => probe.passed) ? 'passed' : 'failed'
const status =
  staticStatus === 'passed' &&
  routeStatus !== 'failed' &&
  (!useBrowser || browserProbe.status === 'passed' || browserProbe.status === 'skipped')
    ? routeStatus === 'skipped'
      ? 'passed-with-dev-server-skipped'
      : 'passed'
    : 'failed'

const result = {
  productName: manifest.productName,
  technicalCore: manifest.technicalCore,
  status,
  checkedAt: new Date().toISOString(),
  devServer,
  routeStatus,
  routeStatuses,
  staticStatus,
  staticProbes,
  browser: browserProbe,
  notes: [
    routeStatus === 'skipped'
      ? 'Dev server route checks were skipped because no Panda dev server responded.'
      : `Dev server route checks covered ${reachableRoutes.length}/${routes.length} visual review targets.`,
    useBrowser
      ? 'Browser screenshot QA was requested through optional Playwright mode.'
      : 'Browser screenshot QA was not requested; run npm run qa:panda:browser in an environment with Playwright to capture screenshots.',
  ],
}

if (outputJson) {
  console.log(JSON.stringify(result, null, 2))
} else {
  console.log(`Panda scripted QA: ${result.status}`)
  console.log(`Dev server: ${devServer}`)
  console.log(`Routes: ${reachableRoutes.length}/${routes.length} reachable (${routeStatus})`)
  console.log(`Static probes: ${staticProbes.filter((probe) => probe.passed).length}/${staticProbes.length} passed`)
  if (useBrowser) {
    console.log(`Browser QA: ${browserProbe.status}`)
    if (browserProbe.screenshotDir) {
      console.log(`Screenshots: ${browserProbe.screenshotDir}`)
    }
    if (browserProbe.reason) {
      console.log(`Browser skip reason: ${browserProbe.reason}`)
    }
  }
}

if (process.env.PANDA_QA_RESULT_PATH) {
  writeFileSync(process.env.PANDA_QA_RESULT_PATH, `${JSON.stringify(result, null, 2)}\n`)
}

if (status === 'failed') {
  process.exit(1)
}
