import { toneLabel } from '../data/navigation'
import type { StatusTone } from '../types'
import { MiniTagList, StatusDot } from './runtimePrimitives'

export { ExecutionStepRow } from './workflowExecutionStepPrimitives'
export { FlowNodeCard } from './workflowNodePrimitives'

export function AuditEventRow({
  title,
  time,
  summary,
  evidenceRefs,
  riskLevel,
}: {
  title: string
  time: string
  summary: string
  evidenceRefs: readonly string[]
  riskLevel: StatusTone
}) {
  return (
    <article className="panda-audit-event">
      <div className="flex items-start gap-3">
        <StatusDot tone={riskLevel} label={`${title} 风险等级：${toneLabel[riskLevel]}`} />
        <div className="min-w-0 flex-1">
          <div className="flex items-center justify-between gap-3">
            <h3>{title}</h3>
            <span className="text-xs text-slate-500">{time}</span>
          </div>
          <p>{summary}</p>
          <MiniTagList items={evidenceRefs} prefix="#" />
        </div>
      </div>
    </article>
  )
}
