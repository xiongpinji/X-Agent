import { writeFileSync } from 'node:fs'
import { getPandaAlignmentContext } from './panda-alignment-context.mjs'
import { buildPandaCloseoutEvidence } from './panda-closeout-evidence.mjs'
import { getPandaExpectedStrictFailure } from './panda-route-rollover-plan.mjs'
import { buildResourceKeyBoundary, read } from './panda-script-utils.mjs'

const outputJson = process.argv.includes('--json')

function toMarkdownList(items) {
  return items.map((item) => `- ${item}`).join('\n')
}

function toMarkdownTable(headers, rows) {
  const header = `| ${headers.join(' | ')} |`
  const divider = `| ${headers.map(() => '---').join(' | ')} |`
  const body = rows.map((row) => `| ${row.map((cell) => String(cell).replaceAll('\n', '<br>')).join(' | ')} |`)
  return [header, divider, ...body].join('\n')
}

const pandaAlignmentContext = getPandaAlignmentContext()
const { manifest, routeRollover, modulePageStructure } = pandaAlignmentContext
const resourceKeyBoundary = buildResourceKeyBoundary(read('src/panda/api/resourceKeys.ts'))
const closeoutEvidence = buildPandaCloseoutEvidence({ manifest, routeRollover, resourceKeyBoundary })
const frontendCommands = manifest.frontendHandoffGates?.frontendOwnedCommands ?? [
  'npm run verify:panda',
  'npm run verify:panda:components',
  'npm run verify:panda:adapters',
  'npm run verify:panda:contracts',
  'npm run verify:panda:resources',
  'npm run report:panda:json',
  'npm run qa:panda:json',
  'npm run type-check',
  'npm run build',
]

const plan = {
  productName: manifest.productName,
  technicalCore: manifest.technicalCore,
  status: manifest.status,
  currentPhase: manifest.frontendCloseout.currentPhase,
  frontendEngineerGoal:
    '在后端主线收尾期间，保持 Panda Agent 前端完整可演示、可验证、可对齐；所有后端等待项必须有路由、资源、字段和验收命令。',
  safeScope: manifest.frontendCloseout.safeScope,
  blockedScope: manifest.frontendCloseout.blockedScope,
  frontendCompletion: closeoutEvidence.frontendBoundary,
  frontendCompletionEvidence: closeoutEvidence.frontendCompletion,
  modulePageStructure,
  resourceBffGate: {
    endpoint: manifest.bff.resourcesEndpoint,
    flag: manifest.bff.resourcesFlag,
    defaultValue: manifest.bff.resourcesFlagDefault,
    enableRule:
      'Only enable this flag after the resources endpoint returns a validated ApiPandaResourceSnapshot and frontend resource probes pass.',
  },
  verificationMatrix: {
    frontendOwnedCommands: frontendCommands,
    expectedStrictFailure: getPandaExpectedStrictFailure({
      pendingRoutes: routeRollover.pendingRoutes,
      resourcesFlag: manifest.bff.resourcesFlag,
      resourcesFlagDefault: manifest.bff.resourcesFlagDefault,
    }),
  },
  alignmentContextSource: pandaAlignmentContext.sourceScript,
  closeoutEvidenceSource: closeoutEvidence.sourceScript,
  routeRolloverSource: routeRollover.sourceScript,
  routeApiResourcesEvidence: closeoutEvidence.routeApiResourcesEvidence,
  routeRolloverPlan: routeRollover.routeRolloverPlan,
  currentApiWiredRoutes: routeRollover.currentApiWiredRoutes,
  backendAlignmentHandoff: closeoutEvidence.backendAlignmentHandoff,
  backendAlignmentPending: manifest.backendAlignmentPending,
}

if (outputJson) {
  const output = `${JSON.stringify(plan, null, 2)}\n`
  console.log(output.trimEnd())
  if (process.env.PANDA_CLOSEOUT_PLAN_PATH) {
    writeFileSync(process.env.PANDA_CLOSEOUT_PLAN_PATH, output)
  }
} else {
  const lines = [
    '# Panda Agent Frontend Closeout Plan',
    '',
    `Product: ${plan.productName}`,
    `Core: ${plan.technicalCore}`,
    `Phase: ${plan.currentPhase}`,
    '',
    '## Frontend Engineer Goal',
    '',
    plan.frontendEngineerGoal,
    '',
    '## Current Boundary',
    '',
    toMarkdownTable(
      ['Area', 'State'],
      Object.entries(plan.frontendCompletion).map(([area, state]) => [area, state]),
    ),
    '',
    '## Frontend Completion Evidence',
    '',
    `Status: ${plan.frontendCompletionEvidence.status}`,
    `Owner: ${plan.frontendCompletionEvidence.owner}`,
    '',
    toMarkdownTable(
      ['Evidence', 'Status', 'Detail'],
      plan.frontendCompletionEvidence.evidence.map((item) => [item.id, item.status, item.detail]),
    ),
    '',
    '## Module Page Structure',
    '',
    toMarkdownTable(
      ['Layer', 'Owner'],
      [
        ['Content', plan.modulePageStructure.content],
        ['Shell', plan.modulePageStructure.shell],
        ['Resources', plan.modulePageStructure.resources],
        ['Standard pages', plan.modulePageStructure.standardPages.join(', ')],
        ['Direct-selector exceptions', plan.modulePageStructure.directSelectorExceptions.join(', ')],
      ],
    ),
    '',
    plan.modulePageStructure.rule,
    '',
    `Alignment context source: ${plan.alignmentContextSource}`,
    `Closeout evidence source: ${plan.closeoutEvidenceSource}`,
    '',
    `Route API resources evidence: ${plan.routeApiResourcesEvidence.status}`,
    `- unknownRouteApiResources: ${plan.routeApiResourcesEvidence.unknownRouteApiResources.join(', ') || '(none)'}`,
    `- missingRouteApiResources: ${plan.routeApiResourcesEvidence.missingRouteApiResources.join(', ') || '(none)'}`,
    '',
    '### Module Resource Hooks',
    '',
    toMarkdownTable(
      ['Page', 'Hook', 'Resource type', 'Source'],
      plan.modulePageStructure.resourceHooks.map((binding) => [binding.page, binding.hook, binding.resourceType, binding.source]),
    ),
    '',
    '## Safe Scope',
    '',
    toMarkdownList(plan.safeScope),
    '',
    '## Blocked Scope',
    '',
    toMarkdownList(plan.blockedScope),
    '',
    '## Resource BFF Gate',
    '',
    toMarkdownTable(
      ['Endpoint', 'Flag', 'Default', 'Enable rule'],
      [[plan.resourceBffGate.endpoint, plan.resourceBffGate.flag, plan.resourceBffGate.defaultValue, plan.resourceBffGate.enableRule]],
    ),
    '',
    '## Route Rollover Plan',
    '',
    toMarkdownTable(
      ['Route', 'Endpoint', 'API resources', 'Runtime fields', 'Needs'],
      plan.routeRolloverPlan.map((route) => [
        route.route,
        route.endpoint,
        route.apiResources.join(', '),
        route.runtimeFields.join(', '),
        route.apiNeeds.join('; '),
      ]),
    ),
    '',
    '## Verification Matrix',
    '',
    toMarkdownList(plan.verificationMatrix.frontendOwnedCommands),
    '',
    `Expected strict status before backend alignment: ${plan.verificationMatrix.expectedStrictFailure}`,
    '',
    '## Backend Alignment Pending',
    '',
    toMarkdownList(plan.backendAlignmentPending),
    '',
    '## Backend Alignment Handoff',
    '',
    toMarkdownTable(
      ['Item', 'Value'],
      [
        ['Resources BFF flag', plan.backendAlignmentHandoff.resourcesBffFlag],
        ['Resources BFF endpoint', plan.backendAlignmentHandoff.resourcesBffEndpoint],
        ['Pending route count', plan.backendAlignmentHandoff.pendingRouteCount],
        ['Pending routes', plan.backendAlignmentHandoff.pendingRouteIds.join(', ')],
        ['Handoff rule', plan.backendAlignmentHandoff.handoffRule],
      ],
    ),
    '',
    'Frontend-owned commands:',
    '',
    toMarkdownList(plan.backendAlignmentHandoff.frontendOwnedCommands),
    '',
    'Backend-owned commands:',
    '',
    toMarkdownList(plan.backendAlignmentHandoff.backendOwnedCommands),
  ]
  const output = `${lines.join('\n')}\n`
  console.log(output)
  if (process.env.PANDA_CLOSEOUT_PLAN_PATH) {
    writeFileSync(process.env.PANDA_CLOSEOUT_PLAN_PATH, output)
  }
}
