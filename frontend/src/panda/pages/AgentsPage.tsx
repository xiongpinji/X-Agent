import { StandardModulePageShell } from '../components/common'
import { AgentOrganizationOverview, AgentProfileGrid, AgentRolePresetSelector } from '../components/agentOrganization'
import { useAgentsPageResources } from '../state/useModulePageResources'

export function AgentsPage() {
  const resources = useAgentsPageResources()

  return (
    <StandardModulePageShell page="agents" count={resources.count}>
      {resources.lead ? (
        <>
          <AgentRolePresetSelector />
          <AgentOrganizationOverview agentProfiles={resources.agentProfiles} lead={resources.lead} />
          <AgentProfileGrid agentProfiles={resources.agentProfiles} />
        </>
      ) : null}
    </StandardModulePageShell>
  )
}
