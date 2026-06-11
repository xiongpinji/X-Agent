import { Boxes, Brain, Network, ShieldCheck, SplitSquareHorizontal, Workflow } from 'lucide-react'
import { navItems } from './navigation'
import type { CapabilityRow, ModuleCard, PandaPage } from '../types'

export const moduleCards: readonly ModuleCard[] = [
  { id: 'threads', title: 'Codex 线程工作区', summary: '任务线程、计划、终端、文件变更、Git diff 与 PR 审查。', metric: '12 条活跃线程', icon: SplitSquareHorizontal },
  { id: 'agents', title: '多智能体组织', summary: '企业角色、智能体团队、会议室协作和跨角色交接。', metric: '8 个在线智能体', icon: Network },
  { id: 'workflows', title: '工作流编排画布', summary: '可视化节点、审批网关、补偿策略、失败恢复。', metric: '5 条运行中', icon: Workflow },
  { id: 'knowledge', title: '长期记忆与知识库', summary: '会话记忆、知识检索、上下文压缩和引用证据。', metric: '1,248 条记忆', icon: Brain },
  { id: 'tools', title: '工具 / MCP 中心', summary: 'MCP、浏览器、文件、搜索、代码执行和插件能力。', metric: '42 个能力', icon: Boxes },
  { id: 'audit', title: '企业审计回放', summary: '工具调用证据、审批轨迹、风险事件与可观测性。', metric: '3 个待审项', icon: ShieldCheck },
]

export const capabilityRows: readonly CapabilityRow[] = [
  { label: 'Codex 基础', value: '线程、项目、终端、文件、Git diff、PR、Skills、Automations' },
  { label: 'X-Agent 超越', value: '多智能体、工作流编排、长期记忆、企业审计、多渠道、模型路由' },
  { label: '执行边界', value: '人审、权限、沙箱、证据引用、失败恢复、成本观测' },
]

const moduleCardByPage = new Map<PandaPage, ModuleCard>(moduleCards.map((item) => [item.id, item]))
const navItemByPage = new Map<PandaPage, (typeof navItems)[number]>(navItems.map((item) => [item.id, item]))

export function getModuleFallbackMeta(page: PandaPage) {
  const current = moduleCardByPage.get(page)
  const nav = navItemByPage.get(page)

  return {
    title: current?.title ?? nav?.label ?? '模块',
    icon: current?.icon ?? nav?.icon ?? Boxes,
  }
}
