import type { AgentProfile } from '../types'

export type AgentOrganizationHeaderViewModel = {
  readonly title: string
  readonly summary: string
}

export type AgentOrganizationActionPanelViewModel = {
  readonly title: string
  readonly items: readonly string[]
}

export const agentOrganizationOverviewHeader: AgentOrganizationHeaderViewModel = {
  title: 'Panda Agent 企业团队',
  summary: '5 个在线角色 · 3 条并行任务 · 1 个待审批交接',
}

export const agentOrganizationTeamActions = ['转交任务', '召开智能体会议', '调整权限', '查看运行证据'] as const
export const agentOrganizationTeamActionPanel: AgentOrganizationActionPanelViewModel = {
  title: '团队动作',
  items: agentOrganizationTeamActions,
}

export function buildLeadAgentControlItems(lead: AgentProfile): readonly string[] {
  return [lead.name, lead.model, `${lead.load}% 负载`, lead.status]
}

export function buildLeadAgentControlPanel(lead: AgentProfile): AgentOrganizationActionPanelViewModel {
  return {
    title: '当前主控',
    items: buildLeadAgentControlItems(lead),
  }
}
