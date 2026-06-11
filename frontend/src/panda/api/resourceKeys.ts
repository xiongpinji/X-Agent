export const pandaResourceKeyPairs = [
  ['tasks', 'tasks'],
  ['projects', 'projects'],
  ['threads', 'threads'],
  ['workflows', 'workflows'],
  ['workflowNodes', 'workflow_nodes'],
  ['agents', 'agents'],
  ['knowledgeSources', 'knowledge_sources'],
  ['tools', 'tools'],
  ['dataSources', 'data_sources'],
  ['auditEvents', 'audit_events'],
  ['automationRules', 'automation_rules'],
  ['settingsSections', 'settings_sections'],
] as const

export type PandaViewResourceKey = (typeof pandaResourceKeyPairs)[number][0]
export type PandaApiResourceKey = (typeof pandaResourceKeyPairs)[number][1]

export const pandaViewResourceKeys = pandaResourceKeyPairs.map(([viewKey]) => viewKey)
export const pandaApiResourceKeys = pandaResourceKeyPairs.map(([, apiKey]) => apiKey)

export const pandaApiResourceKeySet = new Set<string>(pandaApiResourceKeys)
