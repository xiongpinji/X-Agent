import {
  Bot,
  Brain,
  ClipboardCheck,
  Database,
  FolderGit2,
  Home,
  MessageSquare,
  Settings,
  ShieldCheck,
  Timer,
  Workflow,
  Wrench,
} from 'lucide-react'
import type { NavItem, StatusTone } from '../types'

export const pandaLogoSrc = '/assets/panda-agent-logo.png'

export const navItems: readonly NavItem[] = [
  { id: 'home', label: '首页', icon: Home },
  { id: 'threads', label: '线程', icon: MessageSquare },
  { id: 'tasks', label: '任务', icon: ClipboardCheck },
  { id: 'projects', label: '项目', icon: FolderGit2 },
  { id: 'workflows', label: '工作流', icon: Workflow },
  { id: 'agents', label: '智能体', icon: Bot },
  { id: 'knowledge', label: '知识库', icon: Brain },
  { id: 'tools', label: '工具/MCP', icon: Wrench },
  { id: 'data', label: '数据', icon: Database },
  { id: 'audit', label: '审计', icon: ShieldCheck },
  { id: 'automation', label: '自动化', icon: Timer },
  { id: 'settings', label: '设置', icon: Settings },
]

export const toneLabel: Record<StatusTone, string> = {
  success: '正常',
  warning: '关注',
  danger: '异常',
  neutral: '稳定',
}
