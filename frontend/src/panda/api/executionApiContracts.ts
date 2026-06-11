import type { ApiRuntimeMetadata, ApiTone } from './runtimeMapping'

export type ApiTaskSummary = {
  id?: string
  title?: string
  project?: string
  priority?: string
  tone?: ApiTone
} & ApiRuntimeMetadata

export type ApiThreadItem = {
  id?: string
  title?: string
  project?: string
} & ApiRuntimeMetadata

export type ApiWorkflowNode = {
  id?: string
  title?: string
  role?: string
  tone?: ApiTone
  x?: number
  y?: number
} & ApiRuntimeMetadata
