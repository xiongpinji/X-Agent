import type { StatusTone, WithRuntimeMetadata } from './runtimeTypes'

export type ToolCapability = {
  id: string
  name: string
  provider: string
  status: string
  permission: string
  invocations: string
  tone: StatusTone
} & WithRuntimeMetadata

export type KnowledgeSource = {
  id: string
  name: string
  kind: string
  status: string
  documents: string
  lastSync: string
  tone: StatusTone
} & WithRuntimeMetadata

export type DataSource = {
  id: string
  name: string
  source: string
  status: string
  records: string
  syncState: string
  tone: StatusTone
} & WithRuntimeMetadata
