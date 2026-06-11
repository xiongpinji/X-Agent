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
}
