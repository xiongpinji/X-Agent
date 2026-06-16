import { writeFileSync } from 'node:fs'
import {
  cleanupPandaTsProbeTempDir,
  createPandaTsProbeTempDir,
  importProbeModule,
  rewritePandaApiProbeImports,
  transpilePandaApiProbeFiles,
} from './panda-ts-probe-utils.mjs'

const outputJson = process.argv.includes('--json')

function loadAdaptersModule() {
  const tempDir = createPandaTsProbeTempDir('panda-adapter-probe')

  transpilePandaApiProbeFiles(tempDir)
  rewritePandaApiProbeImports(tempDir)

  return importProbeModule(tempDir, 'adapters.mjs').finally(() => {
    cleanupPandaTsProbeTempDir(tempDir)
  })
}

function expect(name, run) {
  try {
    run()
    return { name, status: 'passed' }
  } catch (error) {
    return {
      name,
      status: 'failed',
      error: error instanceof Error ? error.message : String(error),
    }
  }
}

function assertEqual(actual, expected, message) {
  if (actual !== expected) {
    throw new Error(`${message}: expected ${JSON.stringify(expected)}, got ${JSON.stringify(actual)}`)
  }
}

const adapters = await loadAdaptersModule()
const checks = [
  expect('tone-fallback', () => {
    assertEqual(adapters.toStatusTone('critical'), 'neutral', 'unknown tone should map to neutral')
    assertEqual(adapters.toStatusTone('warning'), 'warning', 'known tone should be preserved')
  }),
  expect('progress-clamp', () => {
    assertEqual(adapters.clampProgress(140), 100, 'progress above 100 should clamp')
    assertEqual(adapters.clampProgress(-8), 0, 'progress below 0 should clamp')
    assertEqual(adapters.clampProgress(Number.NaN), 0, 'NaN progress should fallback to 0')
  }),
  expect('runtime-snake-case-mapping', () => {
    const runtime = adapters.mapRuntimeMetadata({
      status: 'running',
      risk_level: 'danger',
      progress: 64.6,
      owner_agent: '执行智能体',
      updated_at: 'today',
      evidence_refs: ['ev-1'],
    })
    assertEqual(runtime.riskLevel, 'danger', 'risk_level should map to riskLevel')
    assertEqual(runtime.progress, 65, 'progress should be rounded')
    assertEqual(runtime.ownerAgent, '执行智能体', 'owner_agent should map to ownerAgent')
    assertEqual(runtime.updatedAt, 'today', 'updated_at should map to updatedAt')
    assertEqual(runtime.evidenceRefs.length, 1, 'evidence_refs should map to evidenceRefs')
  }),
  expect('task-runtime-mapping', () => {
    const task = adapters.mapTaskSummary({
      id: 'task-api',
      title: 'API 任务',
      owner_agent: '任务智能体',
      project: 'Panda',
      status: 'running',
      progress: -10,
      risk_level: 'danger',
      evidence_refs: ['task-ev'],
    })
    assertEqual(task.progress, 0, 'task progress should clamp through adapter')
    assertEqual(task.tone, 'danger', 'task risk_level should map to tone')
    assertEqual(task.runtime.ownerAgent, '任务智能体', 'task runtime should keep owner_agent')
    assertEqual(task.runtime.evidenceRefs[0], 'task-ev', 'task runtime should keep evidence refs')
  }),
  expect('activity-runtime-mapping', () => {
    const activity = adapters.mapActivityItem({
      id: 'activity-api',
      title: '右栏活动',
      status: 'running',
      risk_level: 'warning',
      progress: 42,
      owner_agent: '活动智能体',
      updated_at: 'now',
      evidence_refs: ['activity-ev'],
    })
    assertEqual(activity.tone, 'warning', 'activity risk_level should map to tone')
    assertEqual(activity.runtime?.ownerAgent, '活动智能体', 'activity runtime should keep owner_agent')
    assertEqual(activity.runtime?.progress, 42, 'activity runtime should keep progress')
    assertEqual(activity.runtime?.evidenceRefs[0], 'activity-ev', 'activity runtime should keep evidence refs')
  }),
  expect('evidence-refs-copy', () => {
    const evidenceRefs = ['ev-original']
    const runtime = adapters.mapRuntimeMetadata({ evidence_refs: evidenceRefs })
    const audit = adapters.mapAuditEvent({
      id: 'audit-copy',
      title: '审计拷贝',
      evidence_refs: evidenceRefs,
    })
    evidenceRefs.push('ev-mutated')
    assertEqual(runtime.evidenceRefs.length, 1, 'runtime evidence refs should not share the API array reference')
    assertEqual(runtime.evidenceRefs[0], 'ev-original', 'runtime evidence refs should preserve original values')
    assertEqual(audit.evidenceRefs.length, 1, 'audit evidence refs should not share the API array reference')
    assertEqual(audit.evidenceRefs[0], 'ev-original', 'audit evidence refs should preserve original values')
  }),
  expect('agent-permissions-copy', () => {
    const permissions = ['tools.invoke']
    const agent = adapters.mapAgentProfile({
      id: 'agent-copy',
      name: '权限智能体',
      permissions,
    })
    permissions.push('admin.mutated')
    assertEqual(agent.permissions.length, 1, 'agent permissions should not share the API array reference')
    assertEqual(agent.permissions[0], 'tools.invoke', 'agent permissions should preserve original values')
  }),
  expect('agent-role-preset-mapping', () => {
    const abilities = ['角色规划']
    const permissions = ['role:create']
    const role = adapters.mapAgentRolePreset({
      id: 'director',
      name: '导演',
      abilities,
      default_permissions: permissions,
      portrait_key: 'director',
      tone: 'critical',
    })
    abilities.push('mutated')
    permissions.push('admin.mutated')
    assertEqual(role.id, 'director', 'agent role preset id should map from API DTO')
    assertEqual(role.abilities.length, 1, 'agent role abilities should not share the API array reference')
    assertEqual(role.defaultPermissions[0], 'role:create', 'default_permissions should map to defaultPermissions')
    assertEqual(role.portraitSrc, 'portrait:director', 'portrait_key should resolve through the portrait registry')
    assertEqual(role.tone, 'neutral', 'unknown role tone should map to neutral')
  }),
  expect('resource-snapshot-mapping', () => {
    const snapshot = adapters.mapPandaResourceSnapshot({
      tasks: [{ id: 'task-api', title: 'API 任务', owner_agent: '任务智能体', progress: 44, risk_level: 'warning' }],
      workflows: [{ id: 'wf-api', name: 'API 工作流', owner_agent: '编排智能体', progress: 110, tone: 'success' }],
      workflow_nodes: [{ id: 'node-api', title: 'API 节点', status: 'queued', x: 12, y: 34 }],
      audit_events: [{ id: 'audit-api', title: 'API 审计', risk_level: 'warning', evidence_refs: ['ev-1'] }],
    })
    assertEqual(snapshot.tasks.length, 1, 'tasks should map from API snapshot')
    assertEqual(snapshot.workflows[0].progress, 100, 'workflow progress should clamp through snapshot mapping')
    assertEqual(snapshot.workflowNodes[0].x, 12, 'workflow_nodes should map to workflowNodes')
    assertEqual(snapshot.auditEvents[0].evidenceRefs[0], 'ev-1', 'audit_events should map to auditEvents evidence refs')
    assertEqual(snapshot.projects.length, 0, 'missing resource arrays should map to empty view arrays')
  }),
]

const failedChecks = checks.filter((check) => check.status !== 'passed')
const result = {
  productName: 'Panda Agent',
  technicalCore: 'X-Agent Autonomous Framework',
  status: failedChecks.length === 0 ? 'passed' : 'failed',
  checkedAt: new Date().toISOString(),
  adapter: 'src/panda/api/adapters.ts',
  checks,
}

if (outputJson) {
  console.log(JSON.stringify(result, null, 2))
} else {
  console.log(`Panda adapters: ${result.status}`)
  console.log(`Checks: ${checks.filter((check) => check.status === 'passed').length}/${checks.length} passed`)
  for (const check of failedChecks) {
    console.log(`- [failed] ${check.name}: ${check.error}`)
  }
}

if (process.env.PANDA_ADAPTER_RESULT_PATH) {
  writeFileSync(process.env.PANDA_ADAPTER_RESULT_PATH, `${JSON.stringify(result, null, 2)}\n`)
}

if (failedChecks.length > 0) {
  process.exit(1)
}
