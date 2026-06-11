import React from 'react'
import { PageActionButton } from './pageChromePrimitives'

export type ModulePageAction = {
  label: string
  icon: React.ReactElement<{ size?: number; 'aria-hidden'?: string }>
  primary?: boolean
}

export function ModulePageActions({ actions }: { actions: readonly ModulePageAction[] }) {
  return (
    <>
      {actions.map((action) => (
        <PageActionButton key={action.label} icon={action.icon} primary={action.primary}>
          {action.label}
        </PageActionButton>
      ))}
    </>
  )
}
