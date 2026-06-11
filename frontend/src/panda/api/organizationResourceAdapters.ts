import type { AgentProfile, ProjectItem } from '../types'
import type { ApiAgentProfile, ApiProjectItem } from './apiContracts'
import { clampProgress, mapRuntimeMetadata, stringValue, toStatusTone } from './runtimeMapping'

export function mapProjectItem(item: ApiProjectItem): ProjectItem {
  const updatedAt = stringValue(item.updated_at, '未知')
  const ownerAgent = stringValue(item.owner_agent, '未分配')
  return {
    id: stringValue(item.id, 'project-local'),
    name: stringValue(item.name, '未命名项目'),
    type: stringValue(item.type, '项目'),
    updatedAt,
    ownerAgent,
    risk: toStatusTone(item.risk ?? item.risk_level),
    runtime: mapRuntimeMetadata({ ...item, updated_at: updatedAt, owner_agent: ownerAgent }),
  }
}

export function mapAgentProfile(item: ApiAgentProfile): AgentProfile {
  const status = stringValue(item.status, '未知')
  return {
    id: stringValue(item.id, 'agent-local'),
    name: stringValue(item.name, '未命名智能体'),
    role: stringValue(item.role, '通用智能体'),
    status,
    model: stringValue(item.model, 'X-Agent Router'),
    load: clampProgress(item.load),
    permissions: Array.isArray(item.permissions) ? [...item.permissions] : [],
    tone: toStatusTone(item.tone ?? item.risk_level),
    runtime: mapRuntimeMetadata({ ...item, status, progress: item.progress ?? item.load }),
  }
}
