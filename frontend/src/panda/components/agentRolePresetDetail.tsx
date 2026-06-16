import type { AgentRolePreset } from '../data/agentRolePresets'
import { MiniTagList } from './common'
import { buildAgentRolePresetViewModel } from './agentRolePresetViewModel'

export function AgentRolePresetDetail({ preset }: { preset: AgentRolePreset }) {
  const detail = buildAgentRolePresetViewModel(preset)

  return (
    <aside className="panda-role-detail">
      <div className="panda-role-detail-title">
        <span className="panda-role-portrait is-large" data-role-id={preset.id} data-reference-source="x-agent-role-sheet">
          <img
            className="panda-role-portrait-image"
            src={preset.portraitSrc}
            alt={detail.portraitAlt}
            loading="lazy"
            decoding="async"
          />
        </span>
        <div>
          <h3>{preset.name}</h3>
          <p>{preset.description}</p>
        </div>
      </div>
      {detail.detailBlocks.map((block) => (
        <div className="panda-role-detail-block" key={block.label}>
          <span>{block.label}</span>
          <MiniTagList items={block.items} />
        </div>
      ))}
    </aside>
  )
}
