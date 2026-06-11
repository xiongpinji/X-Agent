import { KeyValueList, RailCard, StatusDot } from './common'

export function ApprovalRiskCard() {
  return (
    <RailCard title="审批与风险">
      <KeyValueList
        items={[
          { label: '待审批变更', value: '3 项' },
          { label: '高风险工具调用', value: '1 项', valueClassName: 'text-rose-300' },
          { label: '审计回放', value: '28 条' },
        ]}
      />
    </RailCard>
  )
}

export function SystemStatusCard() {
  return (
    <RailCard title="系统状态">
      <KeyValueList
        items={[
          { label: '服务状态', value: <><StatusDot tone="success" label="服务状态正常" /> 正常</> },
          { label: '模型路由', value: '均衡' },
          { label: '活跃用户', value: '128 人' },
        ]}
      />
    </RailCard>
  )
}
