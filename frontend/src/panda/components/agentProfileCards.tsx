import type { AgentProfile } from '../types'
import { MiniTagList, ProgressSummary, ResourceRuntimeCard, RuntimeMetaStrip } from './common'

export function AgentProfileCard({ agent }: { agent: AgentProfile }) {
  return (
    <ResourceRuntimeCard
      title={agent.name}
      tone={agent.tone}
      description={`${agent.role} · ${agent.model} · ${agent.status}`}
    >
      <ProgressSummary value={agent.load} />
      <RuntimeMetaStrip runtime={agent.runtime} owner={agent.name} risk={agent.tone} />
      <MiniTagList items={agent.permissions} />
    </ResourceRuntimeCard>
  )
}
