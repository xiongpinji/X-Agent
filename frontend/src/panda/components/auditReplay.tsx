import { ShieldAlert } from 'lucide-react'
import type { AuditEvent } from '../types'
import { AuditEventRow, SummaryMetricList, WorkspacePanel } from './common'
import { buildAuditRiskSummaryItems } from './auditReplayViewModel'

export function AuditReplayWorkspace({ auditEvents }: { auditEvents: readonly AuditEvent[] }) {
  return (
    <section className="panda-audit-layout">
      <AuditTimeline auditEvents={auditEvents} />
      <AuditRiskSummary auditEvents={auditEvents} />
    </section>
  )
}

export function AuditTimeline({ auditEvents }: { auditEvents: readonly AuditEvent[] }) {
  return (
    <WorkspacePanel as="div" title="事件时间线">
      <div className="mt-4 space-y-3">
        {auditEvents.map((event) => (
          <AuditEventRow
            key={event.id}
            title={event.title}
            time={event.time}
            summary={event.summary}
            evidenceRefs={event.evidenceRefs}
            riskLevel={event.riskLevel}
          />
        ))}
      </div>
    </WorkspacePanel>
  )
}

export function AuditRiskSummary({ auditEvents }: { auditEvents: readonly AuditEvent[] }) {
  const summaryItems = buildAuditRiskSummaryItems(auditEvents)

  return (
    <WorkspacePanel as="aside">
      <div className="flex items-center gap-3">
        <ShieldAlert className="text-rose-300" size={22} />
        <h2 className="font-semibold">风险摘要</h2>
      </div>
      <SummaryMetricList items={summaryItems} />
    </WorkspacePanel>
  )
}
