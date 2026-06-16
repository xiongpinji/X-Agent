import { KeyValueList, RailCard } from './common'
import {
  buildRightRailApprovalRiskRows,
  buildRightRailSystemStatusRows,
  rightRailApprovalRiskHeader,
  rightRailSystemStatusHeader,
} from './rightRailStatusCardsViewModel'

export function ApprovalRiskCard() {
  return (
    <RailCard title={rightRailApprovalRiskHeader.title}>
      <KeyValueList items={buildRightRailApprovalRiskRows()} />
    </RailCard>
  )
}

export function SystemStatusCard() {
  return (
    <RailCard title={rightRailSystemStatusHeader.title}>
      <KeyValueList items={buildRightRailSystemStatusRows()} />
    </RailCard>
  )
}
