import type { ApiRuntimeMetadata, ApiTone } from './runtimeMapping'

export type ApiAuditEvent = {
  id?: string
  title?: string
  actor?: string
  risk_level?: ApiTone
  evidence_refs?: readonly string[]
  time?: string
  summary?: string
} & ApiRuntimeMetadata

export type ApiAutomationRule = {
  id?: string
  name?: string
  trigger?: string
  destination?: string
  status?: string
  last_run?: string
  tone?: ApiTone
} & ApiRuntimeMetadata

export type ApiSettingsSection = {
  id?: string
  title?: string
  description?: string
  status?: string
  tone?: ApiTone
} & ApiRuntimeMetadata
