import { mapAgentRolePresets } from '../api/agentRoleAdapters'
import type { AgentRolePreset } from '../types'
import { apiAgentRolePresetFixtures } from './agentRolePresetFixtures'

export type { AgentRolePreset } from '../types'
export { apiAgentRolePresetFixtures } from './agentRolePresetFixtures'

export const agentRolePresets = mapAgentRolePresets(apiAgentRolePresetFixtures) satisfies readonly AgentRolePreset[]
