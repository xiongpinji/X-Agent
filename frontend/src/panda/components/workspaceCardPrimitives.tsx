import React from 'react'

export { InfoPairGrid, InsetInfoBlock, type InfoPairItem } from './workspaceInfoPrimitives'
export {
  CapabilityMetricCard,
  ListCardHeader,
  ResourceInfoCard,
  ResourceRuntimeCard,
  ToolCardHeader,
} from './workspaceResourceCardPrimitives'
export { WorkspaceTable, WorkspaceTableHeader } from './workspaceTablePrimitives'

export function ResourceCardGrid<Item>({
  items,
  className,
  renderItem,
}: {
  items: readonly Item[]
  className: string
  renderItem: (item: Item) => React.ReactNode
}) {
  return (
    <section className={className}>
      {items.map(renderItem)}
    </section>
  )
}

export function NavigationCardGrid<Item>({
  items,
  className,
  renderItem,
}: {
  items: readonly Item[]
  className: string
  renderItem: (item: Item) => React.ReactNode
}) {
  return (
    <section className={className}>
      {items.map(renderItem)}
    </section>
  )
}

export function ModuleSummaryCard({
  icon,
  title,
  summary,
  metric,
}: {
  icon?: React.ReactNode
  title: string
  summary: React.ReactNode
  metric?: React.ReactNode
}) {
  return (
    <>
      {icon}
      <h3 className={icon ? 'mt-4 font-semibold' : 'font-semibold'}>{title}</h3>
      <p className="mt-2 text-sm leading-6 text-slate-400">{summary}</p>
      {metric ? <div className="mt-4 text-sm text-slate-200">{metric}</div> : null}
    </>
  )
}
