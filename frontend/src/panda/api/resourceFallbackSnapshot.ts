import {
  agentProfiles,
  auditEvents,
  automationRules,
  dataSources,
  knowledgeSources,
  projects,
  settingsSections,
  taskSummaries,
  threads,
  toolCapabilities,
  workflowNodes,
  workflows,
} from '../data/mockResources'
import type { PandaResourceSnapshot } from './resourceSnapshotTypes'

export function getPandaResourceSnapshot(): PandaResourceSnapshot {
  return {
    tasks: taskSummaries,
    projects,
    threads,
    workflows,
    workflowNodes,
    agents: agentProfiles,
    knowledgeSources,
    tools: toolCapabilities,
    dataSources,
    auditEvents,
    automationRules,
    settingsSections,
  }
}

export const pandaResources = getPandaResourceSnapshot()
