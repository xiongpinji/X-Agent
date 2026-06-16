import React from 'react'
import { toneLabel } from '../data/navigation'
import type { StatusTone } from '../types'
import { MetricStrip, StatusDot, type MetricStripItem } from './runtimePrimitives'

export function ToolCardHeader({
  icon,
  title,
  subtitle,
  tone,
}: {
  icon: React.ReactNode
  title: string
  subtitle: string
  tone: StatusTone
}) {
  return (
    <div className="flex items-start justify-between gap-3">
      <div className="flex items-center gap-3">
        <div className="panda-tool-icon">{icon}</div>
        <div>
          <h3>{title}</h3>
          <p>{subtitle}</p>
        </div>
      </div>
      <StatusDot tone={tone} label={`${title} 风险等级：${toneLabel[tone]}`} />
    </div>
  )
}

export function CapabilityMetricCard({
  icon,
  title,
  subtitle,
  tone,
  metrics,
}: {
  icon: React.ReactNode
  title: string
  subtitle: string
  tone: StatusTone
  metrics: readonly MetricStripItem[]
}) {
  return (
    <div className="panda-card panda-tool-card">
      <ToolCardHeader icon={icon} title={title} subtitle={subtitle} tone={tone} />
      <MetricStrip items={metrics} />
    </div>
  )
}
