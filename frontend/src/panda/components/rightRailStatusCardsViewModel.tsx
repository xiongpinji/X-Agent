import { StatusDot } from './common'
import type { KeyValueItem } from './common'

export type RightRailStatusCardHeaderViewModel = {
  readonly title: string
}

export const rightRailApprovalRiskHeader: RightRailStatusCardHeaderViewModel = {
  title: '审批与风险',
}

export const rightRailSystemStatusHeader: RightRailStatusCardHeaderViewModel = {
  title: '系统状态',
}

export function buildRightRailApprovalRiskRows(): readonly KeyValueItem[] {
  return [
    { label: '待审批变更', value: '3 项' },
    { label: '高风险工具调用', value: '1 项', valueClassName: 'text-rose-300' },
    { label: '审计回放', value: '28 条' },
  ]
}

export function buildRightRailSystemStatusRows(): readonly KeyValueItem[] {
  return [
    { label: '服务状态', value: <><StatusDot tone="success" label="服务状态正常" /> 正常</> },
    { label: '模型路由', value: '均衡' },
    { label: '活跃用户', value: '128 人' },
  ]
}
