import type {
  AgentProfile,
  AuditEvent,
  AutomationRule,
  DataSource,
  KnowledgeSource,
  ProjectItem,
  SettingsSection,
  TaskSummary,
  ThreadItem,
  ToolCapability,
  WorkflowItem,
  WorkflowNode,
} from '../types'

export type PandaResourceSource = 'mock' | 'api'

export type PandaResourceSnapshot = {
  tasks: readonly TaskSummary[]
  projects: readonly ProjectItem[]
  threads: readonly ThreadItem[]
  workflows: readonly WorkflowItem[]
  workflowNodes: readonly WorkflowNode[]
  agents: readonly AgentProfile[]
  knowledgeSources: readonly KnowledgeSource[]
  tools: readonly ToolCapability[]
  dataSources: readonly DataSource[]
  auditEvents: readonly AuditEvent[]
  automationRules: readonly AutomationRule[]
  settingsSections: readonly SettingsSection[]
}

export type PandaResourceLoadResult = {
  readonly resources: Readonly<PandaResourceSnapshot>
  readonly source: PandaResourceSource
  readonly error?: Error
}
