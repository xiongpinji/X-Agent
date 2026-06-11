import type { RuntimeMetadata, StatusTone } from './runtimeTypes'
import type { WorkflowItem } from './resourceTypes'

export type ActivityItem = {
  id: string
  title: string
  subtitle: string
  status: string
  tone: StatusTone
  time: string
  runtime?: RuntimeMetadata
}

export type PandaWorkbenchMetrics = {
  activeAgents: number
  runningWorkflows: number
  pendingApprovals: number
  apiCalls: number
  storageUsed: string
}

export type PandaWorkbenchHome = {
  brand: {
    productName: string
    platformName: string
    subtitle: string
  }
  summary: string
  metrics: PandaWorkbenchMetrics
  agentActivity: readonly ActivityItem[]
  workflowRuns: readonly WorkflowItem[]
}
