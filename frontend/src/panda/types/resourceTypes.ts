import type { StatusTone, WithRuntimeMetadata } from './runtimeTypes'

export type WorkflowItem = {
  id: string
  name: string
  state: string
  progress: number
  owner: string
  tone: StatusTone
} & WithRuntimeMetadata

export type ProjectItem = {
  id: string
  name: string
  type: string
  updatedAt: string
  ownerAgent: string
  risk: StatusTone
} & WithRuntimeMetadata

export type ThreadItem = {
  id: string
  title: string
  project: string
  status: string
  ownerAgent: string
  progress: number
} & WithRuntimeMetadata

export type WorkflowNode = {
  id: string
  title: string
  role: string
  status: string
  tone: StatusTone
  x: number
  y: number
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

export type AuditEvent = {
  id: string
  title: string
  actor: string
  riskLevel: StatusTone
  evidenceRefs: readonly string[]
  time: string
  summary: string
} & WithRuntimeMetadata

export type ToolCapability = {
  id: string
  name: string
  provider: string
  status: string
  permission: string
  invocations: string
  tone: StatusTone
} & WithRuntimeMetadata

export type TaskSummary = {
  id: string
  title: string
  ownerAgent: string
  project: string
  status: string
  priority: string
  progress: number
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

export type AutomationRule = {
  id: string
  name: string
  trigger: string
  destination: string
  status: string
  lastRun: string
  tone: StatusTone
} & WithRuntimeMetadata

export type SettingsSection = {
  id: string
  title: string
  description: string
  status: string
  tone: StatusTone
} & WithRuntimeMetadata
