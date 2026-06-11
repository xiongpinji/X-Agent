import type { AuditEvent, TaskSummary, ThreadItem, WorkflowItem, WorkflowNode } from '../types'

export const workflows: readonly WorkflowItem[] = [
  { id: 'wf-1', name: '客户反馈处理流程', state: '执行中', progress: 75, owner: '客服智能体组', tone: 'warning' },
  { id: 'wf-2', name: '数据同步工作流', state: '执行中', progress: 45, owner: '数据分析助手', tone: 'warning' },
  { id: 'wf-3', name: '日报生成流程', state: '已完成', progress: 100, owner: '运营智能体', tone: 'success' },
  { id: 'wf-4', name: '周报汇总流程', state: '已完成', progress: 100, owner: '文档总结专家', tone: 'success' },
  { id: 'wf-5', name: '异常监控流程', state: '失败', progress: 0, owner: '审计智能体', tone: 'danger' },
]

export const threads: readonly ThreadItem[] = [
  { id: 'thr-1', title: '修复 MCP 工具执行链路', project: 'X-Agent Core', status: '运行中', ownerAgent: '代码审查智能体', progress: 68 },
  { id: 'thr-2', title: '设计 Feishu 渠道商业试点', project: '商业化试点', status: '等待审批', ownerAgent: '渠道发布智能体', progress: 82 },
  { id: 'thr-3', title: '生成客户反馈周报', project: '客户成功', status: '已完成', ownerAgent: '文档总结专家', progress: 100 },
]

export const workflowNodes: readonly WorkflowNode[] = [
  { id: 'trigger', title: '客户反馈触发器', role: 'Webhook / 飞书事件', status: '已接收', tone: 'success', x: 14, y: 24 },
  { id: 'classify', title: '意图分类', role: '客服智能体', status: '执行中', tone: 'warning', x: 35, y: 24 },
  { id: 'memory', title: '知识检索', role: 'RAG / 长期记忆', status: '命中 18 条', tone: 'success', x: 56, y: 24 },
  { id: 'approval', title: '人审网关', role: '审批中心', status: '待审批', tone: 'warning', x: 77, y: 24 },
  { id: 'publish', title: '多渠道发布', role: '渠道发布智能体', status: '排队中', tone: 'neutral', x: 77, y: 64 },
  { id: 'audit', title: '审计回放', role: 'X-Agent Core', status: '持续记录', tone: 'success', x: 56, y: 64 },
  { id: 'recover', title: '失败补偿', role: '异常监控流程', status: '未触发', tone: 'neutral', x: 35, y: 64 },
]

export const auditEvents: readonly AuditEvent[] = [
  { id: 'audit-1', title: '高风险工具调用等待审批', actor: '渠道发布智能体', riskLevel: 'warning', evidenceRefs: ['ev-tool-221', 'ev-approval-019'], time: '17:21', summary: '准备向外部飞书群发送客户反馈摘要，后端策略返回人审要求。' },
  { id: 'audit-2', title: 'MCP 工具链执行完成', actor: '代码审查智能体', riskLevel: 'success', evidenceRefs: ['ev-mcp-118', 'ev-test-404'], time: '16:48', summary: '读取仓库、生成 diff 摘要、运行定向测试，证据链已归档。' },
  { id: 'audit-3', title: '知识库检索命中敏感片段', actor: '文档总结专家', riskLevel: 'danger', evidenceRefs: ['ev-kb-771', 'ev-redact-022'], time: '15:05', summary: '输出前触发脱敏提示，前端只呈现状态与证据引用，不内置策略。' },
  { id: 'audit-4', title: '工作流失败补偿未触发', actor: '异常监控流程', riskLevel: 'neutral', evidenceRefs: ['ev-flow-334'], time: '昨天', summary: '节点执行未达到补偿条件，保留回放记录用于运营复盘。' },
]

export const taskSummaries: readonly TaskSummary[] = [
  { id: 'task-1', title: '补齐 Panda 前端工作台模块', ownerAgent: 'UI 设计助手', project: 'Panda Agent Console', status: '执行中', priority: 'P0', progress: 82, tone: 'warning' },
  { id: 'task-2', title: '后端主线交付标准复核', ownerAgent: '审计智能体', project: 'X-Agent Core', status: '等待后端主线', priority: 'P0', progress: 64, tone: 'warning' },
  { id: 'task-3', title: '生成 MCP 工具中心对齐清单', ownerAgent: '代码审查智能体', project: '工具/MCP', status: '已完成', priority: 'P1', progress: 100, tone: 'success' },
  { id: 'task-4', title: '整理多渠道发布审批态', ownerAgent: '渠道发布智能体', project: '商业化试点', status: '待审批', priority: 'P1', progress: 58, tone: 'warning' },
]
