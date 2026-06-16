import { Network } from 'lucide-react'
import type { AgentProfile } from '../types'
import { ActionPanel, ResourceCardGrid, StatusDot } from './common'
import { AgentProfileCard } from './agentProfileCards'
import {
  agentOrganizationOverviewHeader,
  agentOrganizationTeamActionPanel,
  buildLeadAgentControlPanel,
} from './agentOrganizationViewModel'

export { AgentRolePresetCard, AgentRolePresetDetail, AgentRolePresetSelector } from './agentRolePresetSelector'
export { AgentProfileCard } from './agentProfileCards'

export function AgentOrganizationOverview({
  agentProfiles,
  lead,
}: {
  agentProfiles: readonly AgentProfile[]
  lead: AgentProfile
}) {
  const leadControlPanel = buildLeadAgentControlPanel(lead)

  return (
    <section className="panda-agent-grid">
      <div className="panda-card panda-org-panel">
        <div className="panda-org-core">
          <Network size={30} aria-hidden="true" />
          <div>
            <h2>{agentOrganizationOverviewHeader.title}</h2>
            <p>{agentOrganizationOverviewHeader.summary}</p>
          </div>
        </div>
        <div className="panda-org-spokes">
          {agentProfiles.map((agent) => (
            <div key={agent.id} className="panda-org-agent">
              <StatusDot tone={agent.tone} />
              <span>{agent.name}</span>
            </div>
          ))}
        </div>
      </div>
      <div className="space-y-3">
        <ActionPanel title={agentOrganizationTeamActionPanel.title} items={agentOrganizationTeamActionPanel.items} />
        <ActionPanel title={leadControlPanel.title} items={leadControlPanel.items} />
      </div>
    </section>
  )
}

export function AgentProfileGrid({ agentProfiles }: { agentProfiles: readonly AgentProfile[] }) {
  return (
    <ResourceCardGrid
      items={agentProfiles}
      className="panda-list-grid"
      renderItem={(agent) => <AgentProfileCard key={agent.id} agent={agent} />}
    />
  )
}
