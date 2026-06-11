import { CheckCircle2 } from 'lucide-react'
import { toneLabel } from '../data/navigation'
import type { StatusTone } from '../types'
import { MiniTagList, StatusDot } from './runtimePrimitives'

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

export function ExecutionStepRow({
  title,
  ownerAgent,
  evidenceRef,
  complete,
}: {
  title: string
  ownerAgent: string
  evidenceRef: string
  complete: boolean
}) {
  return (
    <div className="flex gap-3 rounded-lg bg-white/[0.04] p-3">
      <CheckCircle2 className={complete ? 'text-green-400' : 'text-slate-500'} size={18} aria-hidden="true" />
      <div>
        <div className="text-sm font-medium">{title}</div>
        <div className="mt-1 text-xs text-slate-400">owner_agent: {ownerAgent} · evidence_refs: {evidenceRef}</div>
      </div>
    </div>
  )
}
