import { toneLabel } from '../data/navigation'
import type { StatusTone } from '../types'

export type StatusDotViewModel = {
  readonly title: string
  readonly ariaLabel: string
  readonly className: string
}

export function buildStatusDotViewModel({
  tone,
  label,
}: {
  readonly tone: StatusTone
  readonly label?: string
}): StatusDotViewModel {
  const toneClassName = tone === 'danger' ? 'danger' : tone === 'warning' ? 'warn' : ''
  const title = toneLabel[tone]

  return {
    title,
    ariaLabel: label ?? `风险等级：${title}`,
    className: `panda-status-dot ${toneClassName}`,
  }
}
