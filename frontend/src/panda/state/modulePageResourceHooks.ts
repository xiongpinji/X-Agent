import React from 'react'
import { usePandaWorkspaceResource } from './PandaWorkspaceContext'
import { useCountedModulePageResource } from './useCountedModulePageResource'
import type {
  AgentsPageResources,
  AuditPageResources,
  AutomationPageResources,
  DataPageResources,
  KnowledgePageResources,
  ProjectsPageResources,
  SettingsPageResources,
  TasksPageResources,
  ToolsPageResources,
  WorkflowsPageResources,
} from './modulePageResourceTypes'

export function useTasksPageResources(): TasksPageResources {
  return useCountedModulePageResource('tasks', 'tasks')
}

export function useProjectsPageResources(): ProjectsPageResources {
  return useCountedModulePageResource('projects', 'projects')
}

export function useWorkflowsPageResources(): WorkflowsPageResources {
  const workflows = usePandaWorkspaceResource('workflows')
  const workflowNodes = usePandaWorkspaceResource('workflowNodes')
  return React.useMemo(
    () => ({ workflows, workflowNodes, count: workflows.length + workflowNodes.length }),
    [workflows, workflowNodes],
  )
}

export function useAgentsPageResources(): AgentsPageResources {
  const agentProfiles = usePandaWorkspaceResource('agents')
  return React.useMemo(
    () => ({ agentProfiles, lead: agentProfiles[0], count: agentProfiles.length }),
    [agentProfiles],
  )
}

export function useKnowledgePageResources(): KnowledgePageResources {
  return useCountedModulePageResource('knowledgeSources', 'knowledgeSources')
}

export function useToolsPageResources(): ToolsPageResources {
  return useCountedModulePageResource('tools', 'toolCapabilities')
}

export function useDataPageResources(): DataPageResources {
  return useCountedModulePageResource('dataSources', 'dataSources')
}

export function useAuditPageResources(): AuditPageResources {
  return useCountedModulePageResource('auditEvents', 'auditEvents')
}

export function useAutomationPageResources(): AutomationPageResources {
  return useCountedModulePageResource('automationRules', 'automationRules')
}

export function useSettingsPageResources(): SettingsPageResources {
  return useCountedModulePageResource('settingsSections', 'settingsSections')
}
