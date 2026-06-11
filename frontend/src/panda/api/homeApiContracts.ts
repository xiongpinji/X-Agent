import type { ApiRuntimeMetadata, ApiTone } from './runtimeMapping'

export type ApiWorkbenchActivityItem = {
  id?: string
  title?: string
  subtitle?: string
  tone?: ApiTone
  time?: string
} & ApiRuntimeMetadata

export type ApiWorkbenchWorkflowRun = {
  id?: string
  name?: string
  state?: string
  owner?: string
  tone?: ApiTone
} & ApiRuntimeMetadata

export type ApiWorkbenchHome = {
  brand?: {
    product_name?: string
    platform_name?: string
    subtitle?: string
  }
  summary?: string
  metrics?: {
    active_agents?: number
    running_workflows?: number
    pending_approvals?: number
    api_calls?: number
    storage_used?: string
  }
  agent_activity?: readonly ApiWorkbenchActivityItem[]
  workflow_runs?: readonly ApiWorkbenchWorkflowRun[]
}
