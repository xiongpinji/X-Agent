import type { AuditEvent } from '../types'
import type { SummaryMetricItem } from './common'

const approvalPattern = /审批|待审|approval|review/i

function countApprovalChanges(auditEvents: readonly AuditEvent[]): number {
  return auditEvents.filter((event) => approvalPattern.test(`${event.title} ${event.summary}`)).length
}

function countDangerEvents(auditEvents: readonly AuditEvent[]): number {
  return auditEvents.filter((event) => event.riskLevel === 'danger').length
}

function countEvidenceRefs(auditEvents: readonly AuditEvent[]): number {
  return auditEvents.reduce((total, event) => total + event.evidenceRefs.length, 0)
}

export function buildAuditRiskSummaryItems(auditEvents: readonly AuditEvent[]): readonly SummaryMetricItem[] {
  const approvalChanges = countApprovalChanges(auditEvents)
  const dangerEvents = countDangerEvents(auditEvents)
  const evidenceRefs = countEvidenceRefs(auditEvents)

  return [
    { label: '待审批变更', value: `${approvalChanges} 项`, tone: approvalChanges > 0 ? 'warning' : 'neutral' },
    { label: '高风险工具调用', value: `${dangerEvents} 项`, tone: dangerEvents > 0 ? 'danger' : 'neutral' },
    { label: '审计回放', value: `${auditEvents.length} 条` },
    { label: '证据引用', value: `${evidenceRefs} 条` },
  ]
}
