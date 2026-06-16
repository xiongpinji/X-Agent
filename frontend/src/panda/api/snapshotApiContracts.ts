import type { ApiWorkbenchWorkflowRun } from './homeApiContracts'
import type {
  ApiAgentProfile,
  ApiAuditEvent,
  ApiAutomationRule,
  ApiDataSource,
  ApiKnowledgeSource,
  ApiProjectItem,
  ApiSettingsSection,
  ApiTaskSummary,
  ApiThreadItem,
  ApiToolCapability,
  ApiWorkflowNode,
} from './resourceApiContracts'

export type ApiPandaResourceSnapshot = {
  tasks?: readonly ApiTaskSummary[]
  projects?: readonly ApiProjectItem[]
  threads?: readonly ApiThreadItem[]
  workflows?: readonly ApiWorkbenchWorkflowRun[]
  workflow_nodes?: readonly ApiWorkflowNode[]
  agents?: readonly ApiAgentProfile[]
  knowledge_sources?: readonly ApiKnowledgeSource[]
  tools?: readonly ApiToolCapability[]
  data_sources?: readonly ApiDataSource[]
  audit_events?: readonly ApiAuditEvent[]
  automation_rules?: readonly ApiAutomationRule[]
  settings_sections?: readonly ApiSettingsSection[]
}
