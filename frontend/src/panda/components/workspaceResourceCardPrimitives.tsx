import React from 'react'
import type { StatusTone } from '../types'
import { InfoPairGrid, type InfoPairItem } from './workspaceInfoPrimitives'
import { ListCardHeader } from './workspaceListCardHeaderPrimitives'

export { CapabilityMetricCard, ToolCardHeader } from './workspaceCapabilityCardPrimitives'
export { ListCardHeader } from './workspaceListCardHeaderPrimitives'

export function ResourceRuntimeCard({
  icon,
  title,
  tone,
  description,
  children,
}: {
  icon?: React.ReactNode
  title: string
  tone: StatusTone
  description: React.ReactNode
  children?: React.ReactNode
}) {
  return (
    <div className="panda-card panda-list-card">
      <ListCardHeader icon={icon} title={title} tone={tone} />
      <p>{description}</p>
      {children}
    </div>
  )
}

export function ResourceInfoCard({
  icon,
  title,
  tone,
  description,
  items,
}: {
  icon?: React.ReactNode
  title: string
  tone: StatusTone
  description: React.ReactNode
  items: readonly InfoPairItem[]
}) {
  return (
    <ResourceRuntimeCard icon={icon} title={title} tone={tone} description={description}>
      <InfoPairGrid items={items} />
    </ResourceRuntimeCard>
  )
}
