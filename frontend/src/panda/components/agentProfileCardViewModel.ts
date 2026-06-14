import type { AgentProfile, StatusTone } from '../types'

export type AgentProfileCardViewModel = {
  readonly title: string
  readonly description: string
  readonly progress: number
  readonly permissions: readonly string[]
  readonly runtimeOwner: string
  readonly runtimeRisk: StatusTone
}

export function buildAgentProfileCardViewModel(agent: AgentProfile): AgentProfileCardViewModel {
  return {
    title: agent.name,
    description: [agent.role, agent.model, agent.status].filter(Boolean).join(' · '),
    progress: agent.load,
    permissions: agent.permissions,
    runtimeOwner: agent.name,
    runtimeRisk: agent.tone,
  }
}
