import type { ToolCapability } from '../types'
import type { MetricStripItem } from './common'

export type ToolCapabilityCardViewModel = {
  readonly title: string
  readonly subtitle: string
  readonly metrics: readonly MetricStripItem[]
}

export const toolAccessBoundaryTitle = '接入边界'

export const toolAccessBoundaryItems = [
  '工具发现由 MCP 管理器提供',
  '权限与审批由后端策略返回',
  '前端只展示状态、证据和可用动作',
] as const

export function buildToolCapabilityCardViewModel(tool: ToolCapability): ToolCapabilityCardViewModel {
  return {
    title: tool.name,
    subtitle: tool.provider,
    metrics: [
      { label: '状态', value: tool.status },
      { label: '权限', value: tool.permission },
      { label: '调用', value: tool.invocations },
    ],
  }
}
