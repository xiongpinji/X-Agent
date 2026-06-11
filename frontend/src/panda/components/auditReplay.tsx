import { ShieldAlert } from 'lucide-react'
import type { AuditEvent } from '../types'
import { AuditEventRow, SummaryMetricList, WorkspacePanel } from './common'

export function AuditReplayWorkspace({ auditEvents }: { auditEvents: readonly AuditEvent[] }) {
  return (
    <section className="panda-audit-layout">
      <AuditTimeline auditEvents={auditEvents} />
      <AuditRiskSummary />
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

export function AuditRiskSummary() {
  return (
    <WorkspacePanel as="aside">
      <div className="flex items-center gap-3">
        <ShieldAlert className="text-rose-300" size={22} />
        <h2 className="font-semibold">风险摘要</h2>
      </div>
      <SummaryMetricList
        items={[
          { label: '待审批变更', value: '3 项' },
          { label: '高风险工具调用', value: '1 项', tone: 'danger' },
          { label: '审计回放', value: '28 条' },
          { label: '证据引用', value: '146 条' },
        ]}
      />
    </WorkspacePanel>
  )
}
