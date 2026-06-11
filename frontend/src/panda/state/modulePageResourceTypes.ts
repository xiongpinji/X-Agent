import type { PandaResourceSnapshot } from '../api/resourceSnapshotTypes'

export type CountedModulePageResource<
  ResourceName extends string,
  ResourceItems extends readonly unknown[],
> = Readonly<Record<ResourceName, ResourceItems>> & {
  readonly count: number
}

export type TasksPageResources = {
  readonly tasks: PandaResourceSnapshot['tasks']
  readonly count: number
}

export type ProjectsPageResources = {
  readonly projects: PandaResourceSnapshot['projects']
  readonly count: number
}

export type WorkflowsPageResources = {
  readonly workflows: PandaResourceSnapshot['workflows']
  readonly workflowNodes: PandaResourceSnapshot['workflowNodes']
  readonly count: number
}

export type AgentsPageResources = {
  readonly agentProfiles: PandaResourceSnapshot['agents']
  readonly lead: PandaResourceSnapshot['agents'][number] | undefined
  readonly count: number
}

export type KnowledgePageResources = {
  readonly knowledgeSources: PandaResourceSnapshot['knowledgeSources']
  readonly count: number
}

export type ToolsPageResources = {
  readonly toolCapabilities: PandaResourceSnapshot['tools']
  readonly count: number
}

export type DataPageResources = {
  readonly dataSources: PandaResourceSnapshot['dataSources']
  readonly count: number
}

export type AuditPageResources = {
  readonly auditEvents: PandaResourceSnapshot['auditEvents']
  readonly count: number
}

export type AutomationPageResources = {
  readonly automationRules: PandaResourceSnapshot['automationRules']
  readonly count: number
}

export type SettingsPageResources = {
  readonly settingsSections: PandaResourceSnapshot['settingsSections']
  readonly count: number
}
