import type { PandaWorkbenchHome } from '../types'
import { activities } from './homeContent'
import { workflows } from './mockResources'

export const mockWorkbenchHome: PandaWorkbenchHome = {
  brand: {
    productName: 'Panda Agent',
    platformName: '熊猫派达智能体应用管理平台',
    subtitle: 'Powered by X-Agent Autonomous Framework',
  },
  summary: 'Codex 桌面端工作方式与 X-Agent 企业智能体框架融合的应用管理工作台。',
  metrics: {
    activeAgents: 8,
    runningWorkflows: 5,
    pendingApprovals: 3,
    apiCalls: 12428,
    storageUsed: '45.2 GB / 1 TB',
  },
  agentActivity: activities,
  workflowRuns: workflows,
  controlSummary: {
    source: 'mock',
    status: 'unavailable',
    readOnly: true,
    executeEnabled: false,
    countScope: 'mock',
    limit: 0,
    planCount: 0,
    goalCount: 0,
    latestUpdatedAt: null,
    boundary: '本地演示数据未连接 ControlModeStore；此处不提供执行入口。',
  },
  runtimeCapabilitySummary: {
    source: 'mock',
    sourceStatus: 'unavailable',
    status: 'unknown',
    readOnly: true,
    executeEnabled: false,
    ok: false,
    mainlineWiredCount: 0,
    apiCliEvidenceCount: 0,
    frontendVerifiedCount: 0,
    detachedCandidateCount: 0,
    staleEvidenceCount: 0,
    overclaimFindingCount: 0,
    readyCount: 0,
    needsReviewCount: 0,
    blockedCount: 0,
    missingEvidenceCount: 0,
    issueCodes: ['runtime_capability_mock_data'],
    nextActions: ['connect_backend_runtime_capability_boundary_report'],
    boundary: '本地演示数据不代表主线运行能力；detached candidate 不展示为已交付。',
  },
}
