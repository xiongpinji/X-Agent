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

export type PandaControlSummary = {
  source: string
  status: string
  readOnly: boolean
  executeEnabled: boolean
  countScope: string
  limit: number
  planCount: number
  goalCount: number
  latestUpdatedAt: string | null
  boundary: string
}

export type PandaRuntimeCapabilitySummary = {
  source: string
  sourceStatus: string
  status: string
  readOnly: boolean
  executeEnabled: boolean
  ok: boolean
  mainlineWiredCount: number
  apiCliEvidenceCount: number
  frontendVerifiedCount: number
  detachedCandidateCount: number
  staleEvidenceCount: number
  overclaimFindingCount: number
  readyCount: number
  needsReviewCount: number
  blockedCount: number
  missingEvidenceCount: number
  issueCodes: readonly string[]
  nextActions: readonly string[]
  boundary: string
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
  controlSummary: PandaControlSummary
  runtimeCapabilitySummary: PandaRuntimeCapabilitySummary
}
