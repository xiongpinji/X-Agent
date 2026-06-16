import { Activity, Archive, Bot, Code2, Database, FolderGit2, Layers3, Sparkles, Workflow } from 'lucide-react'
import type { ActivityItem, PromptAction, QuickAction } from '../types'

export const quickActions: readonly QuickAction[] = [
  { title: '创建智能体', description: '定制专属智能体并接入角色权限', action: '创建', targetPage: 'agents', icon: Bot },
  { title: '创建工作流', description: '通过可视化编排完成复杂任务自动化', action: '创建', targetPage: 'workflows', icon: Workflow },
  { title: '导入项目', description: '从 Git 仓库导入项目到工作区', action: '导入', targetPage: 'projects', icon: FolderGit2 },
  { title: '探索模板', description: '从能力市场快速启动你的项目', action: '浏览模板', targetPage: 'automation', icon: Sparkles },
]

export const promptActions: readonly PromptAction[] = [
  { label: '代码分析', icon: Code2 },
  { label: '文档总结', icon: Archive },
  { label: '数据分析', icon: Activity },
  { label: '生成图表', icon: Database },
  { label: '头脑风暴', icon: Sparkles },
  { label: '更多', icon: Layers3 },
]

export const activities: readonly ActivityItem[] = [
  {
    id: 'act-1',
    title: '代码审查智能体',
    subtitle: '正在运行',
    status: 'running',
    tone: 'warning',
    time: '现在',
    runtime: { status: 'running', riskLevel: 'warning', progress: 68, ownerAgent: '代码审查智能体', updatedAt: '现在', evidenceRefs: ['ev-mcp-118'] },
  },
  {
    id: 'act-2',
    title: '数据分析助手',
    subtitle: '正在生成洞察报告',
    status: 'running',
    tone: 'warning',
    time: '12:30',
    runtime: { status: 'running', riskLevel: 'warning', progress: 74, ownerAgent: '数据分析助手', updatedAt: '12:30', evidenceRefs: ['ev-data-042'] },
  },
  {
    id: 'act-3',
    title: '文档总结专家',
    subtitle: '已完成',
    status: 'done',
    tone: 'success',
    time: '09:15',
    runtime: { status: 'done', riskLevel: 'success', progress: 100, ownerAgent: '文档总结专家', updatedAt: '09:15', evidenceRefs: ['ev-doc-203'] },
  },
  {
    id: 'act-4',
    title: '渠道发布智能体',
    subtitle: '等待审批',
    status: 'review',
    tone: 'warning',
    time: '昨天',
    runtime: { status: 'review', riskLevel: 'warning', progress: 58, ownerAgent: '渠道发布智能体', updatedAt: '昨天', evidenceRefs: ['ev-approval-019'] },
  },
  {
    id: 'act-5',
    title: 'UI 设计助手',
    subtitle: '运行失败',
    status: 'failed',
    tone: 'danger',
    time: '昨天',
    runtime: { status: 'failed', riskLevel: 'danger', progress: 0, ownerAgent: 'UI 设计助手', updatedAt: '昨天', evidenceRefs: ['ev-ui-500'] },
  },
]
