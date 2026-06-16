import type { AgentProfile } from '../types'
import { MiniTagList, ProgressSummary, ResourceRuntimeCard, RuntimeMetaStrip } from './common'
import { buildAgentProfileCardViewModel } from './agentProfileCardViewModel'

export function AgentProfileCard({ agent }: { agent: AgentProfile }) {
  const card = buildAgentProfileCardViewModel(agent)

  return (
    <ResourceRuntimeCard
      title={card.title}
      tone={agent.tone}
      description={card.description}
    >
      <ProgressSummary value={card.progress} />
      <RuntimeMetaStrip runtime={agent.runtime} owner={card.runtimeOwner} risk={card.runtimeRisk} />
      <MiniTagList items={card.permissions} />
    </ResourceRuntimeCard>
  )
}
