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
  control_summary?: {
    source?: string
    status?: string
    read_only?: boolean
    execute_enabled?: boolean
    count_scope?: string
    limit?: number
    plan_count?: number
    goal_count?: number
    status_counts?: Record<string, Record<string, number>>
    latest_updated_at?: string | null
    boundary?: string
  }
  runtime_capability_summary?: {
    source?: string
    source_status?: string
    status?: string
    read_only?: boolean
    execute_enabled?: boolean
    ok?: boolean
    summary?: Record<string, number>
    issue_codes?: readonly string[]
    next_actions?: readonly string[]
    boundary?: string
  }
}
