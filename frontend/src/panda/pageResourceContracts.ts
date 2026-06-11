import type { PandaPage } from './types'
import type { PandaPageResourceContract } from './resourceContractTypes'
import { pandaCoreRuntimeFields } from './resourceRuntimeFields'

export const pandaPageResourceContracts: Record<PandaPage, PandaPageResourceContract> = {
  home: {
    page: 'home',
    resourceKeys: ['projects'],
    bffEndpoint: '/api/v1/workbench/home',
    readiness: 'api-wired',
    runtimeFields: ['status', 'risk_level', 'progress', 'owner_agent', 'updated_at'],
    apiNeeds: ['home metrics', 'agent activity', 'workflow run summaries', 'recent projects'],
  },
  threads: {
    page: 'threads',
    resourceKeys: ['threads'],
    bffEndpoint: '/api/v1/workbench/threads',
    readiness: 'mock-ready',
    runtimeFields: pandaCoreRuntimeFields,
    apiNeeds: ['thread list', 'active run detail', 'plan steps', 'terminal events', 'file changes', 'audit evidence'],
  },
  tasks: {
    page: 'tasks',
    resourceKeys: ['tasks'],
    bffEndpoint: '/api/v1/workbench/tasks',
    readiness: 'mock-ready',
    runtimeFields: pandaCoreRuntimeFields,
    apiNeeds: ['task queue', 'owner agent', 'priority', 'progress', 'execution actions'],
  },
  projects: {
    page: 'projects',
    resourceKeys: ['projects'],
    bffEndpoint: '/api/v1/workbench/projects',
    readiness: 'mock-ready',
    runtimeFields: ['status', 'risk_level', 'progress', 'owner_agent', 'updated_at'],
    apiNeeds: ['project list', 'Git/worktree state', 'recent files', 'linked runs', 'PR status'],
  },
  workflows: {
    page: 'workflows',
    resourceKeys: ['workflows', 'workflowNodes'],
    bffEndpoint: '/api/v1/workbench/workflows',
    readiness: 'mock-ready',
    runtimeFields: pandaCoreRuntimeFields,
    apiNeeds: ['workflow definitions', 'run graph', 'node status', 'approval gateway', 'failure state'],
  },
  agents: {
    page: 'agents',
    resourceKeys: ['agents'],
    bffEndpoint: '/api/v1/workbench/agents',
    readiness: 'mock-ready',
    runtimeFields: ['status', 'risk_level', 'progress', 'owner_agent', 'updated_at'],
    apiNeeds: ['agent profiles', 'team topology', 'permissions', 'handoff state', 'load state'],
  },
  knowledge: {
    page: 'knowledge',
    resourceKeys: ['knowledgeSources'],
    bffEndpoint: '/api/v1/workbench/knowledge',
    readiness: 'mock-ready',
    runtimeFields: ['status', 'risk_level', 'progress', 'owner_agent', 'updated_at', 'evidence_refs'],
    apiNeeds: ['knowledge sources', 'indexing state', 'retrieval summary', 'memory references'],
  },
  tools: {
    page: 'tools',
    resourceKeys: ['tools'],
    bffEndpoint: '/api/v1/workbench/tools',
    readiness: 'mock-ready',
    runtimeFields: pandaCoreRuntimeFields,
    apiNeeds: ['tool catalog', 'MCP server state', 'permissions', 'invocation history'],
  },
  data: {
    page: 'data',
    resourceKeys: ['dataSources'],
    bffEndpoint: '/api/v1/workbench/data',
    readiness: 'mock-ready',
    runtimeFields: ['status', 'risk_level', 'progress', 'owner_agent', 'updated_at'],
    apiNeeds: ['data source inventory', 'sync jobs', 'record counts', 'cost and storage metrics'],
  },
  audit: {
    page: 'audit',
    resourceKeys: ['auditEvents'],
    bffEndpoint: '/api/v1/workbench/audit',
    readiness: 'mock-ready',
    runtimeFields: ['status', 'risk_level', 'progress', 'owner_agent', 'updated_at', 'evidence_refs'],
    apiNeeds: ['audit events', 'risk levels', 'evidence references', 'replay payloads'],
  },
  automation: {
    page: 'automation',
    resourceKeys: ['automationRules'],
    bffEndpoint: '/api/v1/workbench/automation',
    readiness: 'mock-ready',
    runtimeFields: pandaCoreRuntimeFields,
    apiNeeds: ['automation rules', 'schedule state', 'monitor status', 'last run'],
  },
  settings: {
    page: 'settings',
    resourceKeys: ['settingsSections'],
    bffEndpoint: '/api/v1/workbench/settings',
    readiness: 'mock-ready',
    runtimeFields: ['status', 'risk_level', 'updated_at'],
    apiNeeds: ['tenant settings', 'model routing', 'permissions', 'branding', 'readonly policy status'],
  },
}

export const pandaResourceContractKeys = Object.values(pandaPageResourceContracts).flatMap(
  (contract) => contract.resourceKeys,
)
