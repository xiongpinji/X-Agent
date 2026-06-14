import type { StatusTone, WithRuntimeMetadata } from './runtimeTypes'

export type AuditEvent = {
  id: string
  title: string
  actor: string
  riskLevel: StatusTone
  evidenceRefs: readonly string[]
  time: string
  summary: string
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
