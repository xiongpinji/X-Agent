import type { ApiRuntimeMetadata, ApiTone } from './runtimeMapping'
import type { AgentRoleIcon } from '../types/agentRoleTypes'

export type ApiProjectItem = {
  id?: string
  name?: string
  type?: string
  risk?: ApiTone
  risk_level?: ApiTone
} & ApiRuntimeMetadata

export type ApiAgentProfile = {
  id?: string
  name?: string
  role?: string
  status?: string
  model?: string
  load?: number
  permissions?: readonly string[]
  tone?: ApiTone
} & ApiRuntimeMetadata

export type ApiAgentRolePreset = {
  id?: string
  name?: string
  tagline?: string
  description?: string
  abilities?: readonly string[]
  tools?: readonly string[]
  default_permissions?: readonly string[]
  icon?: AgentRoleIcon
  portrait_key?: string
  tone?: ApiTone
} & ApiRuntimeMetadata
