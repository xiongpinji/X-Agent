import { CheckCircle2 } from 'lucide-react'

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
