import { toneLabel } from '../data/navigation'
import type { StatusTone } from '../types'
import { StatusDot } from './runtimePrimitives'

export function ActivitySummaryRow({
  avatarSrc,
  title,
  subtitle,
  tone,
}: {
  avatarSrc?: string
  title: string
  subtitle: string
  tone: StatusTone
}) {
  return (
    <div className="flex items-center gap-3">
      {avatarSrc ? <img className="panda-avatar h-9 w-9" src={avatarSrc} alt="" /> : null}
      <div className="min-w-0 flex-1">
        <div className="truncate text-sm font-medium">{title}</div>
        <div className="truncate text-xs text-slate-400">{subtitle}</div>
      </div>
      <StatusDot tone={tone} label={`${title} 状态：${subtitle}，风险等级：${toneLabel[tone]}`} />
    </div>
  )
}
