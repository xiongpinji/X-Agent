import type { AgentRolePreset } from '../data/agentRolePresets'

export type AgentRolePresetDetailBlock = {
  readonly label: string
  readonly items: readonly string[]
}

export type AgentRolePresetViewModel = {
  readonly portraitAlt: string
  readonly detailBlocks: readonly AgentRolePresetDetailBlock[]
}

export function buildAgentRolePresetViewModel(preset: AgentRolePreset): AgentRolePresetViewModel {
  return {
    portraitAlt: `${preset.name}角色形象`,
    detailBlocks: [
      { label: '核心能力', items: preset.abilities },
      { label: '默认工具', items: preset.tools },
      { label: '权限边界', items: preset.defaultPermissions },
    ],
  }
}
