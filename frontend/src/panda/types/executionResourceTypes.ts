import type { StatusTone, WithRuntimeMetadata } from './runtimeTypes'

export type WorkflowItem = {
  id: string
  name: string
  state: string
  progress: number
  owner: string
  tone: StatusTone
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
