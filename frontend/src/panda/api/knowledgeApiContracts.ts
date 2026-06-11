import type { ApiRuntimeMetadata, ApiTone } from './runtimeMapping'

export type ApiKnowledgeSource = {
  id?: string
  name?: string
  kind?: string
  status?: string
  documents?: string | number
  last_sync?: string
  tone?: ApiTone
} & ApiRuntimeMetadata

export type ApiDataSource = {
  id?: string
  name?: string
  source?: string
  status?: string
  records?: string | number
  sync_state?: string
  tone?: ApiTone
} & ApiRuntimeMetadata

export type ApiToolCapability = {
  id?: string
  name?: string
  provider?: string
  status?: string
  permission?: string
  invocations?: string | number
  tone?: ApiTone
} & ApiRuntimeMetadata
