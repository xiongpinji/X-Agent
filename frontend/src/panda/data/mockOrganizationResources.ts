import type { AgentProfile, AutomationRule, ProjectItem, SettingsSection } from '../types'

export const projects: readonly ProjectItem[] = [
  { id: 'p-1', name: '智能客服优化项目', type: '项目', updatedAt: '刚刚', ownerAgent: '客户成功组', risk: 'success' },
  { id: 'p-2', name: '数据分析报告生成器', type: '智能体', updatedAt: '2小时前', ownerAgent: '数据分析助手', risk: 'warning' },
  { id: 'p-3', name: '客户反馈处理工作流', type: '工作流', updatedAt: '昨天', ownerAgent: '客服智能体组', risk: 'success' },
  { id: 'p-4', name: '市场调研自动化', type: '项目', updatedAt: '2天前', ownerAgent: '研究智能体', risk: 'neutral' },
  { id: 'p-5', name: '竞品分析智能体', type: '智能体', updatedAt: '3天前', ownerAgent: '策略智能体', risk: 'neutral' },
]

export const agentProfiles: readonly AgentProfile[] = [
  { id: 'agent-code', name: '代码审查智能体', role: '工程质量', status: '运行中', model: 'Panda Agent-4', load: 78, permissions: ['repo:read', 'diff:write', 'tests:run'], tone: 'warning' },
  { id: 'agent-data', name: '数据分析助手', role: '洞察生成', status: '运行中', model: 'X-Agent Router', load: 62, permissions: ['dataset:read', 'chart:create'], tone: 'warning' },
  { id: 'agent-docs', name: '文档总结专家', role: '知识沉淀', status: '空闲', model: 'Panda Agent-4-mini', load: 22, permissions: ['memory:write', 'kb:read'], tone: 'success' },
  { id: 'agent-channel', name: '渠道发布智能体', role: '多渠道交付', status: '待审批', model: 'X-Agent Router', load: 48, permissions: ['feishu:send', 'approval:request'], tone: 'warning' },
  { id: 'agent-audit', name: '审计智能体', role: '风险与证据', status: '在线', model: 'Panda Agent-4', load: 35, permissions: ['audit:read', 'evidence:sign'], tone: 'success' },
]

export const automationRules: readonly AutomationRule[] = [
  { id: 'auto-1', name: '每日运行质量报告', trigger: '每天 09:00', destination: '运营智能体', status: '启用', lastRun: '今天 09:00', tone: 'success' },
  { id: 'auto-2', name: '高风险审批提醒', trigger: 'risk_level=warning', destination: '审批中心', status: '启用', lastRun: '17:21', tone: 'warning' },
  { id: 'auto-3', name: 'MCP 服务健康监控', trigger: '每 15 分钟', destination: '工具/MCP 中心', status: '启用', lastRun: '刚刚', tone: 'success' },
  { id: 'auto-4', name: '多渠道发布复盘', trigger: '每周一', destination: '渠道发布智能体', status: '暂停', lastRun: '上周', tone: 'neutral' },
]

export const settingsSections: readonly SettingsSection[] = [
  { id: 'set-tenant', title: '组织与租户', description: '企业空间、团队、成员、角色和多租户边界。', status: '企业版已启用', tone: 'success' },
  { id: 'set-routing', title: '模型路由', description: 'Panda Agent 与 X-Agent Core 的模型选择、降级和成本策略。', status: '本地演示配置', tone: 'warning' },
  { id: 'set-permission', title: '权限与审批', description: '人审、沙箱、密钥、工具调用策略的只读状态入口。', status: '由后端策略控制', tone: 'warning' },
  { id: 'set-brand', title: '品牌与开发者区域', description: '产品品牌 Panda Agent，技术内核 X-Agent Core。', status: '已配置', tone: 'success' },
]
