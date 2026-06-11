import type { ActivityItem, PandaWorkbenchHome, WorkflowItem } from '../types'
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
  }
}
