import { toneLabel } from '../data/navigation'
import type { StatusTone } from '../types'
import { StatusDot } from './runtimePrimitives'

export function FlowNodeCard({
  title,
  role,
  status,
  tone,
  x,
  y,
}: {
  title: string
  role: string
  status: string
  tone: StatusTone
  x: number
  y: number
}) {
  return (
    <div className="panda-flow-node" style={{ left: `${x}%`, top: `${y}%` }}>
      <div className="flex items-center justify-between gap-3">
        <span className="text-sm font-semibold">{title}</span>
        <StatusDot tone={tone} label={`${title} 状态：${status}，风险等级：${toneLabel[tone]}`} />
      </div>
      <div className="mt-2 text-xs text-slate-400">{role}</div>
      <div className="mt-3 text-xs text-slate-300">{status}</div>
    </div>
  )
}
