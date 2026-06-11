import React from 'react'

export { ActivitySummaryRow } from './workspaceActivityPrimitives'
export { RailCard } from './workspaceRailPrimitives'

export function WorkspacePanel({
  as: Component = 'section',
  title,
  className = '',
  children,
}: {
  as?: 'section' | 'div' | 'aside'
  title?: string
  className?: string
  children: React.ReactNode
}) {
  const panelClassName = `panda-card p-4${className ? ` ${className}` : ''}`

  return (
    <Component className={panelClassName}>
      {title ? <h2 className="font-semibold">{title}</h2> : null}
      {children}
    </Component>
  )
}

export function SectionHeader({ icon, title }: { icon: React.ReactNode; title: string }) {
  return (
    <div className="mb-4 flex items-center gap-3">
      {icon}
      <h2 className="font-semibold">{title}</h2>
    </div>
  )
}
