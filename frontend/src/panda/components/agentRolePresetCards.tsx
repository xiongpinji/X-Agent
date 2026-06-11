import type { AgentRolePreset } from '../data/agentRolePresets'
import { MiniTagList } from './common'

export function AgentRolePresetCard({
  preset,
  selected,
  onSelect,
}: {
  preset: AgentRolePreset
  selected: boolean
  onSelect: () => void
}) {
  return (
    <button
      className={`panda-role-card ${selected ? 'is-selected' : ''}`}
      type="button"
      aria-pressed={selected}
      onClick={onSelect}
    >
      <span className="panda-role-portrait" data-role-id={preset.id}>
        <img src={preset.portraitSrc} alt={`${preset.name}角色形象`} loading="lazy" />
      </span>
      <span className="panda-role-card-copy">
        <strong>{preset.name}</strong>
        <span>{preset.tagline}</span>
      </span>
    </button>
  )
}

export function AgentRolePresetDetail({ preset }: { preset: AgentRolePreset }) {
  return (
    <aside className="panda-role-detail">
      <div className="panda-role-detail-title">
        <span className="panda-role-portrait is-large" data-role-id={preset.id}>
          <img src={preset.portraitSrc} alt={`${preset.name}角色形象`} loading="lazy" />
        </span>
        <div>
          <h3>{preset.name}</h3>
          <p>{preset.description}</p>
        </div>
      </div>
      <div className="panda-role-detail-block">
        <span>核心能力</span>
        <MiniTagList items={preset.abilities} />
      </div>
      <div className="panda-role-detail-block">
        <span>默认工具</span>
        <MiniTagList items={preset.tools} />
      </div>
      <div className="panda-role-detail-block">
        <span>权限边界</span>
        <MiniTagList items={preset.defaultPermissions} />
      </div>
    </aside>
  )
}
