import { Network } from 'lucide-react'
import type { AgentProfile } from '../types'
import { ActionPanel, ResourceCardGrid, StatusDot } from './common'
import { AgentProfileCard } from './agentProfileCards'

export { AgentRolePresetCard, AgentRolePresetDetail, AgentRolePresetSelector } from './agentRolePresetSelector'
export { AgentProfileCard } from './agentProfileCards'

export function AgentOrganizationOverview({
  agentProfiles,
  lead,
}: {
  agentProfiles: readonly AgentProfile[]
  lead: AgentProfile
}) {
  return (
    <section className="panda-agent-grid">
      <div className="panda-card panda-org-panel">
        <div className="panda-org-core">
          <Network size={30} aria-hidden="true" />
          <div>
            <h2>Panda Agent 企业团队</h2>
            <p>5 个在线角色 · 3 条并行任务 · 1 个待审批交接</p>
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
        <ActionPanel title="团队动作" items={['转交任务', '召开智能体会议', '调整权限', '查看运行证据']} />
        <ActionPanel title="当前主控" items={[lead.name, lead.model, `${lead.load}% 负载`, lead.status]} />
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
