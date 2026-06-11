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
import type { ApiPandaResourceSnapshot } from './apiContracts'
import { mapWorkflowRun } from './homeAdapters'
import type { PandaViewResourceKey } from './resourceKeys'
import {
  mapAgentProfile,
  mapAuditEvent,
  mapAutomationRule,
  mapDataSource,
  mapKnowledgeSource,
  mapProjectItem,
  mapSettingsSection,
  mapTaskSummary,
  mapThreadItem,
  mapToolCapability,
  mapWorkflowNode,
} from './resourceItemAdapters'

export type PandaMappedResourceSnapshot = Record<PandaViewResourceKey, unknown[]> & {
  tasks: TaskSummary[]
  projects: ProjectItem[]
  threads: ThreadItem[]
  workflows: WorkflowItem[]
  workflowNodes: WorkflowNode[]
  agents: AgentProfile[]
  knowledgeSources: KnowledgeSource[]
  tools: ToolCapability[]
  dataSources: DataSource[]
  auditEvents: AuditEvent[]
  automationRules: AutomationRule[]
  settingsSections: SettingsSection[]
}

export function mapPandaResourceSnapshot(snapshot: ApiPandaResourceSnapshot): PandaMappedResourceSnapshot {
  return {
    tasks: Array.isArray(snapshot.tasks) ? snapshot.tasks.map(mapTaskSummary) : [],
    projects: Array.isArray(snapshot.projects) ? snapshot.projects.map(mapProjectItem) : [],
    threads: Array.isArray(snapshot.threads) ? snapshot.threads.map(mapThreadItem) : [],
    workflows: Array.isArray(snapshot.workflows) ? snapshot.workflows.map(mapWorkflowRun) : [],
    workflowNodes: Array.isArray(snapshot.workflow_nodes) ? snapshot.workflow_nodes.map(mapWorkflowNode) : [],
    agents: Array.isArray(snapshot.agents) ? snapshot.agents.map(mapAgentProfile) : [],
    knowledgeSources: Array.isArray(snapshot.knowledge_sources) ? snapshot.knowledge_sources.map(mapKnowledgeSource) : [],
    tools: Array.isArray(snapshot.tools) ? snapshot.tools.map(mapToolCapability) : [],
    dataSources: Array.isArray(snapshot.data_sources) ? snapshot.data_sources.map(mapDataSource) : [],
    auditEvents: Array.isArray(snapshot.audit_events) ? snapshot.audit_events.map(mapAuditEvent) : [],
    automationRules: Array.isArray(snapshot.automation_rules) ? snapshot.automation_rules.map(mapAutomationRule) : [],
    settingsSections: Array.isArray(snapshot.settings_sections) ? snapshot.settings_sections.map(mapSettingsSection) : [],
  }
}
