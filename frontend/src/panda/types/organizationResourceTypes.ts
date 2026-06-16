import type { StatusTone, WithRuntimeMetadata } from './runtimeTypes'

export type ProjectItem = {
  id: string
  name: string
  type: string
  updatedAt: string
  ownerAgent: string
  risk: StatusTone
} & WithRuntimeMetadata

export type AgentProfile = {
  id: string
  name: string
  role: string
  status: string
  model: string
  load: number
  permissions: readonly string[]
  tone: StatusTone
} & WithRuntimeMetadata
