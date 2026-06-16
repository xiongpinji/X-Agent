import type { AgentRolePreset } from '../data/agentRolePresets'
import { buildAgentRolePresetViewModel } from './agentRolePresetViewModel'

export { AgentRolePresetDetail } from './agentRolePresetDetail'

export function AgentRolePresetCard({
  preset,
  selected,
  onSelect,
}: {
  preset: AgentRolePreset
  selected: boolean
  onSelect: () => void
}) {
  const card = buildAgentRolePresetViewModel(preset)

  return (
    <button
      className={`panda-role-card ${selected ? 'is-selected' : ''}`}
      type="button"
      aria-pressed={selected}
      onClick={onSelect}
    >
      <span className="panda-role-portrait" data-role-id={preset.id} data-reference-source="x-agent-role-sheet">
        <img
          className="panda-role-portrait-image"
          src={preset.portraitSrc}
          alt={card.portraitAlt}
          loading="lazy"
          decoding="async"
        />
      </span>
      <span className="panda-role-card-copy">
        <strong>{preset.name}</strong>
        <span>{preset.tagline}</span>
      </span>
    </button>
  )
}
