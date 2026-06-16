import type { ApiPandaResourceSnapshot } from './adapters'

export const apiResourceSnapshotFixture: ApiPandaResourceSnapshot = {
  tasks: [{ id: 'task-api', title: 'API 任务', owner_agent: '任务智能体', progress: 44, risk_level: 'warning' }],
  projects: [{ id: 'project-api', name: 'API 项目', updated_at: 'today', owner_agent: '项目智能体', risk_level: 'success' }],
  threads: [{ id: 'thread-api', title: 'API 线程', owner_agent: '线程智能体', progress: 52 }],
  workflows: [{ id: 'wf-api', name: 'API 工作流', owner_agent: '编排智能体', progress: 110, tone: 'success' }],
  workflow_nodes: [{ id: 'node-api', title: 'API 节点', status: 'queued', x: 12, y: 34 }],
  agents: [{ id: 'agent-api', name: 'API 智能体', permissions: ['repo:read'], load: 48 }],
  knowledge_sources: [{ id: 'kb-api', name: 'API 知识源', documents: 12, last_sync: 'today' }],
  tools: [{ id: 'tool-api', name: 'API 工具', invocations: 5 }],
  data_sources: [{ id: 'data-api', name: 'API 数据源', records: 42, sync_state: 'realtime' }],
  audit_events: [{ id: 'audit-api', title: 'API 审计', risk_level: 'warning', evidence_refs: ['ev-1'] }],
  automation_rules: [{ id: 'auto-api', name: 'API 自动化', last_run: 'today' }],
  settings_sections: [{ id: 'settings-api', title: 'API 设置', description: 'tenant', status: 'ready' }],
}
