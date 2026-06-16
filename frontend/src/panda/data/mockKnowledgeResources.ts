import type { DataSource, KnowledgeSource, ToolCapability } from '../types'

export const toolCapabilities: readonly ToolCapability[] = [
  { id: 'tool-mcp-git', name: 'Git MCP Server', provider: 'MCP', status: '在线', permission: '项目级授权', invocations: '1,284', tone: 'success' },
  { id: 'tool-browser', name: '浏览器预览', provider: 'Playwright', status: '在线', permission: '沙箱执行', invocations: '412', tone: 'success' },
  { id: 'tool-files', name: '文件与补丁工具', provider: 'X-Agent Core', status: '受控', permission: '人审策略', invocations: '3,908', tone: 'warning' },
  { id: 'tool-search', name: '联网检索', provider: 'MCP / Search', status: '降级', permission: '按任务授权', invocations: '205', tone: 'warning' },
  { id: 'tool-feishu', name: '飞书渠道适配器', provider: 'Channel Adapter', status: '待审批', permission: '组织级审批', invocations: '89', tone: 'warning' },
]

export const knowledgeSources: readonly KnowledgeSource[] = [
  { id: 'kb-1', name: 'X-Agent 项目文档', kind: 'Markdown / Docs', status: '已索引', documents: '428', lastSync: '刚刚', tone: 'success' },
  { id: 'kb-2', name: '企业客户反馈库', kind: '工单 / CRM', status: '同步中', documents: '18,204', lastSync: '12 分钟前', tone: 'warning' },
  { id: 'kb-3', name: '审计证据索引', kind: 'Audit Evidence', status: '已索引', documents: '1,462', lastSync: '1 小时前', tone: 'success' },
  { id: 'kb-4', name: '渠道运营知识', kind: '飞书 / Slack', status: '等待授权', documents: '96', lastSync: '昨天', tone: 'warning' },
]

export const dataSources: readonly DataSource[] = [
  { id: 'data-1', name: '任务运行事件', source: 'X-Agent Core', status: '在线', records: '128K', syncState: '实时', tone: 'success' },
  { id: 'data-2', name: '模型调用成本', source: 'Model Router', status: '在线', records: '42K', syncState: '5 分钟延迟', tone: 'success' },
  { id: 'data-3', name: '客户反馈样本', source: 'CRM Adapter', status: '同步中', records: '18K', syncState: '增量同步', tone: 'warning' },
  { id: 'data-4', name: '沙箱执行记录', source: 'Execution Sandbox', status: '受控', records: '8K', syncState: '审计保留', tone: 'warning' },
]
