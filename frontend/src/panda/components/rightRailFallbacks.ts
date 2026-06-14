import type { ActivityItem, AgentProfile, WorkflowItem } from '../types'

export function buildRightRailAgentActivityFallback(agents: readonly AgentProfile[]): readonly ActivityItem[] {
  return agents.map((agent) => ({
    id: agent.id,
    title: agent.name,
    subtitle: agent.status,
    status: agent.status,
    tone: agent.tone,
    time: agent.runtime?.updatedAt ?? '现在',
    runtime: agent.runtime,
  }))
}

export function resolveRightRailAgentActivities({
  homeActivities,
  agents,
}: {
  homeActivities: readonly ActivityItem[] | undefined
  agents: readonly AgentProfile[]
}): readonly ActivityItem[] {
  return homeActivities?.length ? homeActivities : buildRightRailAgentActivityFallback(agents)
}

export function resolveRightRailWorkflowRuns({
  homeWorkflows,
  fallbackWorkflows,
}: {
  homeWorkflows: readonly WorkflowItem[] | undefined
  fallbackWorkflows: readonly WorkflowItem[]
}): readonly WorkflowItem[] {
  return homeWorkflows?.length ? homeWorkflows : fallbackWorkflows
}
