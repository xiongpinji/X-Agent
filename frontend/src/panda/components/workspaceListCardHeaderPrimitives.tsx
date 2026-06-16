import React from 'react'
import { toneLabel } from '../data/navigation'
import type { StatusTone } from '../types'
import { StatusDot } from './runtimePrimitives'

export function ListCardHeader({
  icon,
  title,
  tone,
}: {
  icon?: React.ReactNode
  title: string
  tone: StatusTone
}) {
  return (
    <div className="flex items-center justify-between">
      <div className="flex items-center gap-3">
        {icon}
        <h3>{title}</h3>
      </div>
      <StatusDot tone={tone} label={`${title} 风险等级：${toneLabel[tone]}`} />
    </div>
  )
}
