import type { StatusTone } from '../types'
import { buildStatusDotViewModel } from './statusDotViewModel'

export function StatusDot({ tone, label }: { tone: StatusTone; label?: string }) {
  const statusDot = buildStatusDotViewModel({ tone, label })

  return <span title={statusDot.title} aria-label={statusDot.ariaLabel} role="img" className={statusDot.className} />
}
