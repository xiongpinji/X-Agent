import type {
  ActivityItem,
  PandaControlSummary,
  PandaRuntimeCapabilitySummary,
  PandaWorkbenchHome,
  WorkflowItem,
} from '../types'
import type {
  ApiWorkbenchActivityItem,
  ApiWorkbenchHome,
  ApiWorkbenchWorkflowRun,
} from './apiContracts'
import { clampProgress, mapRuntimeMetadata, stringValue, toStatusTone } from './runtimeMapping'

export function mapActivityItem(item: ApiWorkbenchActivityItem): ActivityItem {
  const status = stringValue(item.status, 'unknown')
  const time = stringValue(item.time ?? item.updated_at, '刚刚')
  return {
    id: stringValue(item.id, 'activity-local'),
    title: stringValue(item.title, '未命名活动'),
    subtitle: stringValue(item.subtitle ?? status, '状态未知'),
    status,
    tone: toStatusTone(item.tone ?? item.risk_level),
    time,
    runtime: mapRuntimeMetadata({ ...item, status, updated_at: item.updated_at ?? time }),
  }
}

export function mapWorkflowRun(item: ApiWorkbenchWorkflowRun): WorkflowItem {
  const state = stringValue(item.state ?? item.status, '未知')
  const owner = stringValue(item.owner ?? item.owner_agent, '未分配')
  return {
    id: stringValue(item.id, 'workflow-local'),
    name: stringValue(item.name, '未命名工作流'),
    state,
    progress: clampProgress(item.progress),
    owner,
    tone: toStatusTone(item.tone ?? item.risk_level),
    runtime: mapRuntimeMetadata({ ...item, status: state, owner }),
  }
}

export function mapControlSummary(summary: ApiWorkbenchHome['control_summary']): PandaControlSummary {
  return {
    source: stringValue(summary?.source, 'missing'),
    status: stringValue(summary?.status, 'unknown'),
    readOnly: summary?.read_only !== false,
    executeEnabled: summary?.execute_enabled === true,
    countScope: stringValue(summary?.count_scope, 'unknown'),
    limit: summary?.limit ?? 0,
    planCount: summary?.plan_count ?? 0,
    goalCount: summary?.goal_count ?? 0,
    latestUpdatedAt: summary?.latest_updated_at ?? null,
    boundary: stringValue(
      summary?.boundary,
      'Control plan/goal state is unavailable in this view; no execution controls are exposed.',
    ),
  }
}

export function mapRuntimeCapabilitySummary(
  summary: ApiWorkbenchHome['runtime_capability_summary'],
): PandaRuntimeCapabilitySummary {
  const counts = summary?.summary ?? {}
  return {
    source: stringValue(summary?.source, 'missing'),
    sourceStatus: stringValue(summary?.source_status, 'unknown'),
    status: stringValue(summary?.status, 'unknown'),
    readOnly: summary?.read_only !== false,
    executeEnabled: summary?.execute_enabled === true,
    ok: summary?.ok === true,
    mainlineWiredCount: counts.mainline_wired_count ?? 0,
    apiCliEvidenceCount: counts.api_cli_evidence_count ?? 0,
    frontendVerifiedCount: counts.frontend_verified_count ?? 0,
    detachedCandidateCount: counts.detached_candidate_count ?? 0,
    staleEvidenceCount: counts.stale_evidence_count ?? 0,
    overclaimFindingCount: counts.overclaim_finding_count ?? 0,
    readyCount: 0,
    needsReviewCount: counts.needs_review_count ?? 0,
    blockedCount: counts.blocked_count ?? 0,
    missingEvidenceCount: counts.missing_evidence_count ?? 0,
    issueCodes: Array.isArray(summary?.issue_codes) ? summary.issue_codes : [],
    nextActions: Array.isArray(summary?.next_actions) ? summary.next_actions : [],
    boundary: stringValue(
      summary?.boundary,
      'Runtime capability status is not available from the backend; detached candidates are not treated as delivered mainline capability.',
    ),
  }
}

export function mapWorkbenchHome(home: ApiWorkbenchHome): PandaWorkbenchHome {
  return {
    brand: {
      productName: stringValue(home.brand?.product_name, 'Panda Agent'),
      platformName: stringValue(home.brand?.platform_name, '熊猫派达智能体应用管理平台'),
      subtitle: stringValue(home.brand?.subtitle, 'Powered by X-Agent Autonomous Framework'),
    },
    summary: stringValue(home.summary, '企业级自主智能体框架，覆盖编排、记忆、工具、审计和多渠道运行。'),
    metrics: {
      activeAgents: home.metrics?.active_agents ?? 8,
      runningWorkflows: home.metrics?.running_workflows ?? 5,
      pendingApprovals: home.metrics?.pending_approvals ?? 3,
      apiCalls: home.metrics?.api_calls ?? 12428,
      storageUsed: stringValue(home.metrics?.storage_used, '45.2 GB / 1 TB'),
    },
    agentActivity: Array.isArray(home.agent_activity) ? home.agent_activity.map(mapActivityItem) : [],
    workflowRuns: Array.isArray(home.workflow_runs) ? home.workflow_runs.map(mapWorkflowRun) : [],
    controlSummary: mapControlSummary(home.control_summary),
    runtimeCapabilitySummary: mapRuntimeCapabilitySummary(home.runtime_capability_summary),
  }
}
