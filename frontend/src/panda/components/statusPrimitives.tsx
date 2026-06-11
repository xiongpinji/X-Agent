import { toneLabel } from '../data/navigation'
import type { StatusTone } from '../types'

export function StatusDot({ tone, label }: { tone: StatusTone; label?: string }) {
  const className = tone === 'danger' ? 'danger' : tone === 'warning' ? 'warn' : ''
  const readableLabel = label ?? `风险等级：${toneLabel[tone]}`

  return <span title={toneLabel[tone]} aria-label={readableLabel} role="img" className={`panda-status-dot ${className}`} />
}
