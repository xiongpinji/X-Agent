import type { AgentRolePreset } from '../types'
import { resolveAgentRolePortrait } from '../data/agentRolePortraits'
import type { ApiAgentRolePreset } from './apiContracts'
import { stringValue, toStatusTone } from './runtimeMapping'

const defaultAgentRoleAbilities = ['任务拆解', '工具调用', '结果复核'] as const

function stringList(value: readonly string[] | undefined, fallback: readonly string[]): readonly string[] {
  return Array.isArray(value) && value.length > 0 ? [...value] : fallback
}

export function mapAgentRolePreset(item: ApiAgentRolePreset): AgentRolePreset {
  const id = stringValue(item.id, 'custom-role')
  return {
    id,
    name: stringValue(item.name, '通用智能体'),
    tagline: stringValue(item.tagline, '企业角色 · 自主执行'),
    description: stringValue(item.description, '面向企业任务编排的通用角色卡。'),
    abilities: stringList(item.abilities, defaultAgentRoleAbilities),
    tools: stringList(item.tools, ['工作台', '知识库', 'MCP 工具']),
    defaultPermissions: stringList(item.default_permissions, ['task:read', 'artifact:write']),
    icon: item.icon ?? 'briefcase',
    portraitSrc: resolveAgentRolePortrait(item.portrait_key ?? id),
    tone: toStatusTone(item.tone ?? item.risk_level),
  }
}

export function mapAgentRolePresets(items: readonly ApiAgentRolePreset[]): readonly AgentRolePreset[] {
  return items.map(mapAgentRolePreset)
}
