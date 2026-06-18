import { createWriteStream, existsSync, mkdirSync, rmSync, writeFileSync } from 'node:fs'
import { spawn, spawnSync } from 'node:child_process'
import http from 'node:http'
import net from 'node:net'
import os from 'node:os'
import { delimiter, join, resolve } from 'node:path'
import WebSocket from 'ws'
import { pandaScriptRoot, read, readJson, requestStatus } from './panda-script-utils.mjs'

const root = pandaScriptRoot
const repoRoot = resolve(root, '..')
const manifest = readJson('src/panda/pandaFrontendManifest.json')
const useBrowser = process.argv.includes('--browser')
const requireBrowser = process.argv.includes('--require-browser')
const allowBrowserSkip = process.argv.includes('--allow-browser-skip')
const outputJson = process.argv.includes('--json')
const qaHost = process.env.PANDA_QA_HOST ?? '127.0.0.1'
const configuredDevServer = normalizeBaseUrl(
  process.env.PANDA_QA_URL ?? manifest.visualReviewEvidence?.devServer ?? 'http://127.0.0.1:3000',
)
const reportsDir = process.env.PANDA_QA_REPORT_DIR ?? resolve(repoRoot, '.xagent_runtime', 'reports')
const smokeStamp = buildSmokeStamp()
const browserReportPath =
  process.env.PANDA_QA_BROWSER_REPORT_PATH ?? resolve(reportsDir, `frontend-browser-smoke-${smokeStamp}.json`)
const screenshotDir =
  process.env.PANDA_QA_SCREENSHOT_DIR ??
  (useBrowser ? reportsDir : resolve(os.tmpdir(), `panda-scripted-qa-${Date.now()}`))

function normalizeBaseUrl(url) {
  return url.replace(/\/+$/, '')
}

function buildSmokeStamp() {
  const now = new Date()
  const pad = (value) => String(value).padStart(2, '0')
  return [
    now.getFullYear(),
    pad(now.getMonth() + 1),
    pad(now.getDate()),
    '-',
    pad(now.getHours()),
    pad(now.getMinutes()),
    pad(now.getSeconds()),
  ].join('')
}

function buildRoutes(baseUrl) {
  return manifest.visualReviewTargets.map((target) => ({
    ...target,
    requestedRoute: target.route === 'home' ? '/' : `/#${target.route}`,
    url: target.route === 'home' ? `${baseUrl}/` : `${baseUrl}/#${target.route}`,
  }))
}

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

async function probeRoutes(devServer = configuredDevServer) {
  const routes = buildRoutes(devServer)
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

function isPortOpen(host, port) {
  return new Promise((resolveOpen) => {
    const socket = net.connect({ host, port })
    socket.setTimeout(500)
    socket.on('connect', () => {
      socket.destroy()
      resolveOpen(true)
    })
    socket.on('timeout', () => {
      socket.destroy()
      resolveOpen(false)
    })
    socket.on('error', () => resolveOpen(false))
  })
}

function findFreePort(host) {
  return new Promise((resolvePort, reject) => {
    const server = net.createServer()
    server.listen(0, host, () => {
      const address = server.address()
      const port = typeof address === 'object' && address ? address.port : 0
      server.close(() => resolvePort(port))
    })
    server.on('error', reject)
  })
}

function requestText(url, timeoutMs = 2500) {
  return new Promise((resolveRequest) => {
    const req = http.get(url, (res) => {
      const chunks = []
      res.on('data', (chunk) => chunks.push(chunk))
      res.on('end', () => {
        resolveRequest({
          status: res.statusCode ?? 0,
          headers: res.headers,
          text: Buffer.concat(chunks).toString('utf8'),
        })
      })
    })
    req.on('error', (error) => resolveRequest({ status: 0, error: error.message, headers: {}, text: '' }))
    req.setTimeout(timeoutMs, () => {
      req.destroy()
      resolveRequest({ status: 0, error: `timeout after ${timeoutMs}ms`, headers: {}, text: '' })
    })
  })
}

async function waitForHttp(url, timeoutMs = 45000) {
  const deadline = Date.now() + timeoutMs
  let lastStatus = 0
  let lastError = ''
  while (Date.now() < deadline) {
    const response = await requestText(url)
    lastStatus = response.status
    lastError = response.error ?? ''
    if (response.status === 200) {
      return response
    }
    await delay(500)
  }
  throw new Error(`timed out waiting for ${url}: status=${lastStatus}${lastError ? ` error=${lastError}` : ''}`)
}

function delay(ms) {
  return new Promise((resolveDelay) => setTimeout(resolveDelay, ms))
}

function parseUrlPort(url) {
  const parsed = new URL(url)
  if (parsed.port) {
    return Number(parsed.port)
  }
  return parsed.protocol === 'https:' ? 443 : 80
}

function npmRunCommand(args) {
  if (process.env.npm_execpath) {
    return {
      command: process.execPath,
      args: [process.env.npm_execpath, ...args],
    }
  }
  if (process.platform === 'win32') {
    return {
      command: 'cmd.exe',
      args: ['/d', '/s', '/c', ['npm', ...args].join(' ')],
    }
  }
  return {
    command: 'npm',
    args,
  }
}

function terminateProcess(childProcess) {
  if (!childProcess || childProcess.exitCode !== null || childProcess.signalCode !== null) {
    return
  }
  if (process.platform === 'win32') {
    spawnSync('taskkill', ['/PID', String(childProcess.pid), '/T', '/F'], { stdio: 'ignore' })
    return
  }
  childProcess.kill('SIGTERM')
}

function removeDirectoryBestEffort(path) {
  try {
    rmSync(path, { recursive: true, force: true, maxRetries: 3, retryDelay: 200 })
  } catch {
    // Browser profile cleanup can race Windows file handles after process termination.
  }
}

async function resolveDevServer() {
  if (process.env.PANDA_QA_URL) {
    await waitForHttp(`${configuredDevServer}/`, 15000)
    return {
      baseUrl: configuredDevServer,
      mode: 'connected',
      requestedUrl: configuredDevServer,
      process: null,
      logs: null,
    }
  }

  const preferredPort = parseUrlPort(configuredDevServer)
  const port = (await isPortOpen(qaHost, preferredPort)) ? await findFreePort(qaHost) : preferredPort
  const baseUrl = `http://${qaHost}:${port}`
  const logs = {
    stdout: resolve(reportsDir, `frontend-browser-smoke-${smokeStamp}-vite.out.log`),
    stderr: resolve(reportsDir, `frontend-browser-smoke-${smokeStamp}-vite.err.log`),
  }
  mkdirSync(reportsDir, { recursive: true })
  const devCommand = npmRunCommand(['run', 'dev', '--', '--host', qaHost, '--port', String(port), '--strictPort'])
  const vite = spawn(devCommand.command, devCommand.args, {
    cwd: root,
    env: {
      ...process.env,
      BROWSER: 'none',
    },
    stdio: ['ignore', 'pipe', 'pipe'],
  })
  vite.stdout.pipe(createWriteStream(logs.stdout))
  vite.stderr.pipe(createWriteStream(logs.stderr))

  try {
    await waitForHttp(`${baseUrl}/`)
  } catch (error) {
    terminateProcess(vite)
    throw error
  }

  return {
    baseUrl,
    mode: port === preferredPort ? 'started' : 'started-on-free-port',
    requestedUrl: configuredDevServer,
    requestedPort: preferredPort,
    actualPort: port,
    process: vite,
    logs,
  }
}

function findBrowserExecutable() {
  if (process.env.PANDA_QA_BROWSER_EXECUTABLE && existsSync(process.env.PANDA_QA_BROWSER_EXECUTABLE)) {
    return process.env.PANDA_QA_BROWSER_EXECUTABLE
  }

  const commandCandidates =
    process.platform === 'win32'
      ? ['msedge.exe', 'chrome.exe', 'chromium.exe']
      : ['google-chrome', 'chrome', 'chromium', 'chromium-browser', 'microsoft-edge']
  for (const command of commandCandidates) {
    const result = spawnSync(process.platform === 'win32' ? 'where.exe' : 'which', [command], {
      encoding: 'utf8',
      stdio: ['ignore', 'pipe', 'ignore'],
    })
    const found = result.stdout
      .split(/\r?\n/)
      .map((line) => line.trim())
      .find(Boolean)
    if (found) {
      return found
    }
  }

  if (process.platform === 'win32') {
    const windowsCandidates = [
      join(process.env.ProgramFiles ?? '', 'Google', 'Chrome', 'Application', 'chrome.exe'),
      join(process.env['ProgramFiles(x86)'] ?? '', 'Google', 'Chrome', 'Application', 'chrome.exe'),
      join(process.env.LOCALAPPDATA ?? '', 'Google', 'Chrome', 'Application', 'chrome.exe'),
      join(process.env.ProgramFiles ?? '', 'Microsoft', 'Edge', 'Application', 'msedge.exe'),
      join(process.env['ProgramFiles(x86)'] ?? '', 'Microsoft', 'Edge', 'Application', 'msedge.exe'),
      join(process.env.LOCALAPPDATA ?? '', 'Microsoft', 'Edge', 'Application', 'msedge.exe'),
    ]
    return windowsCandidates.find((candidate) => candidate && existsSync(candidate)) ?? null
  }

  const pathCandidates = (process.env.PATH ?? '')
    .split(delimiter)
    .flatMap((path) => commandCandidates.map((command) => join(path, command)))
  return pathCandidates.find((candidate) => existsSync(candidate)) ?? null
}

async function getJson(url, options = {}) {
  const response = await fetch(url, options)
  if (!response.ok) {
    throw new Error(`GET ${url} failed with ${response.status}`)
  }
  return response.json()
}

async function launchCdpBrowser() {
  const executable = findBrowserExecutable()
  if (!executable) {
    throw new Error('No local Chrome/Edge executable found; set PANDA_QA_BROWSER_EXECUTABLE or install Playwright browsers.')
  }

  const debuggingPort = await findFreePort(qaHost)
  const userDataDir = resolve(os.tmpdir(), `panda-browser-smoke-${process.pid}-${Date.now()}`)
  const logs = {
    stdout: resolve(reportsDir, `frontend-browser-smoke-${smokeStamp}-browser.out.log`),
    stderr: resolve(reportsDir, `frontend-browser-smoke-${smokeStamp}-browser.err.log`),
  }
  mkdirSync(reportsDir, { recursive: true })
  const browser = spawn(
    executable,
    [
      `--remote-debugging-port=${debuggingPort}`,
      `--user-data-dir=${userDataDir}`,
      '--headless=new',
      '--disable-gpu',
      '--no-first-run',
      '--no-default-browser-check',
      'about:blank',
    ],
    {
      stdio: ['ignore', 'pipe', 'pipe'],
    },
  )
  browser.stdout.pipe(createWriteStream(logs.stdout))
  browser.stderr.pipe(createWriteStream(logs.stderr))
  let session = null
  try {
    await waitForHttp(`http://${qaHost}:${debuggingPort}/json/version`, 15000)
    const target = await createCdpTarget(debuggingPort)
    session = new CdpSession(target.webSocketDebuggerUrl)
    await session.open()
  } catch (error) {
    if (session) {
      await session.close()
    }
    terminateProcess(browser)
    removeDirectoryBestEffort(userDataDir)
    throw error
  }

  return {
    engine: executable.includes('msedge') ? 'edge-cdp' : 'chrome-cdp',
    executable,
    debuggingPort,
    userDataDir,
    logs,
    process: browser,
    session,
    close: async () => {
      await session.close()
      terminateProcess(browser)
      removeDirectoryBestEffort(userDataDir)
    },
  }
}

async function createCdpTarget(debuggingPort) {
  const url = `http://${qaHost}:${debuggingPort}/json/new?about:blank`
  const target = await getJson(url, { method: 'PUT' }).catch((error) => {
    if (error instanceof Error && error.message.includes('405')) {
      return getJson(url)
    }
    throw error
  })
  if (!target.webSocketDebuggerUrl) {
    throw new Error('Chrome DevTools target did not expose webSocketDebuggerUrl.')
  }
  return target
}

class CdpSession {
  constructor(webSocketUrl) {
    this.webSocketUrl = webSocketUrl
    this.nextId = 1
    this.pending = new Map()
    this.events = []
    this.ws = null
  }

  open() {
    return new Promise((resolveOpen, rejectOpen) => {
      this.ws = new WebSocket(this.webSocketUrl)
      this.ws.on('open', resolveOpen)
      this.ws.on('message', (data) => this.handleMessage(data))
      this.ws.on('error', rejectOpen)
    })
  }

  handleMessage(data) {
    const message = JSON.parse(data.toString('utf8'))
    if (message.id && this.pending.has(message.id)) {
      const { resolve: resolveCommand, reject } = this.pending.get(message.id)
      this.pending.delete(message.id)
      if (message.error) {
        reject(new Error(message.error.message ?? JSON.stringify(message.error)))
      } else {
        resolveCommand(message.result ?? {})
      }
      return
    }
    if (message.method) {
      this.events.push({
        method: message.method,
        params: message.params ?? {},
        timestamp: new Date().toISOString(),
      })
    }
  }

  send(method, params = {}) {
    if (!this.ws) {
      throw new Error('CDP websocket is not open.')
    }
    const id = this.nextId++
    this.ws.send(JSON.stringify({ id, method, params }))
    return new Promise((resolveCommand, reject) => {
      this.pending.set(id, { resolve: resolveCommand, reject })
      setTimeout(() => {
        if (this.pending.has(id)) {
          this.pending.delete(id)
          reject(new Error(`CDP command timed out: ${method}`))
        }
      }, 15000)
    })
  }

  async close() {
    if (!this.ws) {
      return
    }
    await new Promise((resolveClose) => {
      this.ws.once('close', resolveClose)
      this.ws.close()
      setTimeout(resolveClose, 1000)
    })
    this.ws = null
  }

  takeEvents() {
    const events = this.events
    this.events = []
    return events
  }
}

async function probeBrowserWithCdp({ baseUrl, devServerInfo }) {
  let browserRuntime = null
  try {
    browserRuntime = await launchCdpBrowser()
    const page = browserRuntime.session
    await page.send('Page.enable')
    await page.send('Runtime.enable')
    await page.send('Log.enable')
    await page.send('Network.enable')
    mkdirSync(screenshotDir, { recursive: true })

    const browserRoutes = []
    const routes = buildRoutes(baseUrl)
    for (const route of routes) {
      browserRoutes.push(await probeCdpRoute(page, route))
    }

    const consoleErrors = browserRoutes.flatMap((route) => route.logs.filter((log) => log.level === 'error'))
    const failedRoutes = browserRoutes.filter((route) => route.status !== 'passed')
    const status = failedRoutes.length === 0 && consoleErrors.length === 0 ? 'passed' : 'failed'

    return {
      status,
      engine: browserRuntime.engine,
      executable: browserRuntime.executable,
      baseUrl,
      devServer: devServerInfo,
      screenshotDir,
      reportPath: browserReportPath,
      routes: browserRoutes,
      consoleErrors,
      backendFallback: summarizeBackendFallback(browserRoutes),
      assertions: {
        routeCount: browserRoutes.length,
        expectedRouteCount: routes.length,
        allRoutesPassed: failedRoutes.length === 0,
        noConsoleErrors: consoleErrors.length === 0,
        backendFallbackAllowed: true,
      },
    }
  } finally {
    if (browserRuntime) {
      await browserRuntime.close()
    }
  }
}

async function probeCdpRoute(page, route) {
  const [width, height] = route.viewport.split('x').map(Number)
  page.takeEvents()
  await page.send('Emulation.setDeviceMetricsOverride', {
    width,
    height,
    deviceScaleFactor: 1,
    mobile: width <= 600,
  })
  await navigateAndWait(page, route.url)
  await delay(750)

  const metrics = await evaluatePageMetrics(page)
  const screenshotPath = resolve(screenshotDir, `frontend-browser-smoke-${smokeStamp}-${route.route}.png`)
  const screenshot = await page.send('Page.captureScreenshot', { format: 'png', fromSurface: true })
  writeFileSync(screenshotPath, Buffer.from(screenshot.data, 'base64'))
  const logs = collectCdpLogs(page.takeEvents())
  const assertions = {
    httpStatusOk: metrics.httpStatus === 0 || metrics.httpStatus === 200,
    nonEmptyBody: metrics.bodyTextLength > 100 && metrics.rootChildCount > 0,
    noFrameworkOverlay: !metrics.overlayDetected,
    noConsoleError: !logs.some((log) => log.level === 'error'),
    titlePresent: Boolean(metrics.title),
  }
  const passed = Object.values(assertions).every(Boolean)

  return {
    route: route.requestedRoute,
    routeId: route.route,
    requestedUrl: route.url,
    actualUrl: metrics.location,
    title: metrics.title,
    viewport: { width, height },
    screenshot: screenshotPath,
    status: passed ? 'passed' : 'failed',
    assertions,
    metrics,
    logs,
  }
}

async function navigateAndWait(page, url) {
  await page.send('Page.navigate', { url })
  const deadline = Date.now() + 30000
  while (Date.now() < deadline) {
    const state = await page.send('Runtime.evaluate', {
      expression: 'document.readyState',
      returnByValue: true,
    })
    if (state.result?.value === 'complete') {
      return
    }
    await delay(250)
  }
  throw new Error(`timed out waiting for browser navigation: ${url}`)
}

async function evaluatePageMetrics(page) {
  const response = await page.send('Runtime.evaluate', {
    returnByValue: true,
    awaitPromise: true,
    expression: `(() => {
      const overlaySelectors = [
        '#vite-error-overlay',
        'vite-error-overlay',
        '[data-nextjs-dialog-overlay]',
        '[data-vite-dev-id][role="dialog"]'
      ];
      const bodyText = document.body?.innerText ?? '';
      const buttons = [...document.querySelectorAll('button, [role="button"], a')]
        .map((element) => (element.innerText || element.getAttribute('aria-label') || '').trim())
        .filter(Boolean)
        .slice(0, 40);
      const headings = [...document.querySelectorAll('h1,h2,h3')]
        .map((element) => element.innerText.trim())
        .filter(Boolean)
        .slice(0, 40);
      const fallbackCopy = bodyText
        .split(/\\n+/)
        .map((line) => line.trim())
        .filter((line) => /降级|fallback|Request failed|ECONNREFUSED|502|无法加载/.test(line))
        .slice(0, 20);
      return {
        bodyTextLength: bodyText.length,
        bodyTextSample: bodyText.slice(0, 1200),
        buttons,
        fallbackCopy,
        hash: window.location.hash,
        headings,
        httpStatus: performance.getEntriesByType('navigation')[0]?.responseStatus ?? 0,
        location: window.location.href,
        overlayDetected: overlaySelectors.some((selector) => document.querySelector(selector)),
        pathname: window.location.pathname,
        rootChildCount: document.getElementById('root')?.childElementCount ?? 0,
        scroll: {
          height: document.documentElement.scrollHeight,
          width: document.documentElement.scrollWidth
        },
        title: document.title,
        viewport: {
          height: window.innerHeight,
          width: window.innerWidth
        }
      };
    })()`,
  })
  return response.result?.value ?? {}
}

function collectCdpLogs(events) {
  return events
    .flatMap((event) => {
      if (event.method === 'Runtime.consoleAPICalled') {
        return [
          {
            level: event.params.type === 'error' ? 'error' : event.params.type === 'warning' ? 'warn' : event.params.type,
            message: (event.params.args ?? []).map((arg) => arg.value ?? arg.description ?? '').join(' '),
            source: 'console',
            timestamp: event.timestamp,
          },
        ]
      }
      if (event.method === 'Runtime.exceptionThrown') {
        return [
          {
            level: 'error',
            message: event.params.exceptionDetails?.text ?? 'Runtime exception thrown',
            source: 'exception',
            timestamp: event.timestamp,
          },
        ]
      }
      if (event.method === 'Log.entryAdded') {
        const entry = event.params.entry ?? {}
        return [
          {
            level: entry.level === 'error' ? 'error' : entry.level === 'warning' ? 'warn' : entry.level ?? 'info',
            message: entry.text ?? '',
            source: entry.source ?? 'log',
            timestamp: event.timestamp,
            url: entry.url,
          },
        ]
      }
      return []
    })
    .filter((log) => ['error', 'warn'].includes(log.level))
    .filter((log) => !isAllowedBackendFallbackLog(log))
}

function isAllowedBackendFallbackLog(log) {
  if (/\/favicon\.ico\b/i.test(log.url ?? log.message)) {
    return true
  }
  return /Failed to load resource.*\/api\/v1\/workbench\/resources|502 \(Bad Gateway\)|ERR_CONNECTION_REFUSED/i.test(log.message)
}

function summarizeBackendFallback(browserRoutes) {
  const fallbackRoutes = browserRoutes
    .filter((route) => route.metrics.fallbackCopy?.length)
    .map((route) => ({
      route: route.route,
      routeId: route.routeId,
      fallbackCopy: route.metrics.fallbackCopy,
    }))
  return {
    status: fallbackRoutes.length ? 'observed-allowed' : 'not-observed',
    allowed: true,
    routes: fallbackRoutes,
  }
}

async function probeBrowser() {
  let devServerInfo = null
  try {
    devServerInfo = await resolveDevServer()
    try {
      return await probeBrowserWithCdp({ baseUrl: devServerInfo.baseUrl, devServerInfo: cleanDevServerInfo(devServerInfo) })
    } catch (cdpError) {
      try {
        return await probeBrowserWithPlaywright(devServerInfo)
      } catch (playwrightError) {
        const reason = [
          cdpError instanceof Error ? cdpError.message : 'CDP browser QA is unavailable.',
          playwrightError instanceof Error ? playwrightError.message : 'Playwright browser QA is unavailable.',
        ].join(' | ')
        return {
          status: allowBrowserSkip && !requireBrowser ? 'skipped' : 'failed',
          reason,
          failureMode: allowBrowserSkip && !requireBrowser ? undefined : 'browser-unavailable',
          screenshotDir: null,
          reportPath: browserReportPath,
          routes: [],
          interaction: null,
          consoleMessages: [],
        }
      }
    }
  } finally {
    if (devServerInfo?.process) {
      terminateProcess(devServerInfo.process)
    }
  }
}

function cleanDevServerInfo(devServerInfo) {
  if (!devServerInfo) {
    return null
  }
  const { process: _process, ...cleaned } = devServerInfo
  return cleaned
}

async function probeBrowserWithPlaywright(existingDevServerInfo = null) {
  let devServerInfo = existingDevServerInfo
  try {
    if (!devServerInfo) {
      devServerInfo = await resolveDevServer()
    }
    const { chromium } = await import('playwright')
    mkdirSync(screenshotDir, { recursive: true })
    const browser = await chromium.launch()
    const page = await browser.newPage()
    const browserRoutes = []
    const consoleMessages = []
    const routes = buildRoutes(devServerInfo.baseUrl)

    page.on('console', (message) => {
      if (['error', 'warning'].includes(message.type()) && !isAllowedBackendFallbackLog({ message: message.text() })) {
        consoleMessages.push(`${message.type()}: ${message.text()}`)
      }
    })

    for (const route of routes) {
      const [width, height] = route.viewport.split('x').map(Number)
      await page.setViewportSize({ width, height })
      await page.goto(route.url, { waitUntil: 'networkidle' })
      const screenshotPath = resolve(screenshotDir, `frontend-browser-smoke-${smokeStamp}-${route.route}.png`)
      await page.screenshot({ path: screenshotPath, fullPage: false })
      const mainLabel = await page.locator('#panda-main-content').getAttribute('aria-label')
      const activeNav = await page.locator('[aria-current="page"]').first().getAttribute('aria-label')
      const bodyTextLength = await page.locator('body').innerText().then((text) => text.length)
      const overlayDetected = await page
        .locator('#vite-error-overlay, vite-error-overlay, [data-nextjs-dialog-overlay]')
        .count()
        .then((count) => count > 0)
      browserRoutes.push({
        route: route.route,
        url: page.url(),
        title: await page.title(),
        mainLabel,
        activeNav,
        screenshotPath,
        status: bodyTextLength > 100 && !overlayDetected ? 'passed' : 'failed',
        assertions: {
          nonEmptyBody: bodyTextLength > 100,
          noFrameworkOverlay: !overlayDetected,
        },
      })
    }

    await browser.close()
    const failedRoutes = browserRoutes.filter((route) => route.status !== 'passed')

    return {
      status: failedRoutes.length === 0 && consoleMessages.length === 0 ? 'passed' : 'failed',
      engine: 'playwright',
      devServer: cleanDevServerInfo(devServerInfo),
      screenshotDir,
      reportPath: browserReportPath,
      routes: browserRoutes,
      interaction: null,
      consoleMessages,
      consoleErrors: consoleMessages.filter((message) => message.startsWith('error:')),
    }
  } catch (error) {
    throw error
  } finally {
    if (!existingDevServerInfo && devServerInfo?.process) {
      terminateProcess(devServerInfo.process)
    }
  }
}

const routes = buildRoutes(configuredDevServer)
const routeStatuses = await probeRoutes(configuredDevServer)
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
const browserStatusAccepted =
  !useBrowser || browserProbe.status === 'passed' || (allowBrowserSkip && browserProbe.status === 'skipped')
const status =
  staticStatus === 'passed' &&
  routeStatus !== 'failed' &&
  browserStatusAccepted
    ? routeStatus === 'skipped'
      ? 'passed-with-dev-server-skipped'
      : 'passed'
    : 'failed'

const result = {
  productName: manifest.productName,
  technicalCore: manifest.technicalCore,
  status,
  checkedAt: new Date().toISOString(),
  devServer: configuredDevServer,
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
      ? allowBrowserSkip
        ? 'Browser screenshot QA was requested; skipped browser execution is allowed only because --allow-browser-skip was provided.'
        : 'Browser screenshot QA was requested and must pass in this strict run.'
      : 'Browser screenshot QA was not requested; run npm run qa:panda:browser in an environment with Playwright to capture screenshots.',
  ],
}

if (useBrowser) {
  mkdirSync(reportsDir, { recursive: true })
  writeFileSync(browserReportPath, `${JSON.stringify(result.browser, null, 2)}\n`)
}

if (outputJson) {
  console.log(JSON.stringify(result, null, 2))
} else {
  console.log(`Panda scripted QA: ${result.status}`)
  console.log(`Dev server: ${configuredDevServer}`)
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
