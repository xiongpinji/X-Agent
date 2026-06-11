import React from 'react'
import type { PandaPage, PandaStandardModulePage } from '../types'
import { pandaModulePageContent } from '../data/modulePageContent'
import type { ModulePageAction } from './modulePageActionPrimitives'
import { ModulePageActions } from './modulePageActionPrimitives'
import { PageHeading } from './pageChromePrimitives'
import { PandaResourceState } from './resourceState'

export type { ModulePageAction } from './modulePageActionPrimitives'
export { ModulePageActions } from './modulePageActionPrimitives'

export function ModuleResourcePage({
  content,
  count,
  children,
  footer,
}: {
  content: {
    page: PandaPage
    title: string
    description: string
    actions: readonly ModulePageAction[]
    emptyTitle: string
    emptyDescription: string
  }
  count: number
  children: React.ReactNode
  footer?: React.ReactNode
}) {
  return (
    <div className="space-y-5">
      <PageHeading
        page={content.page}
        title={content.title}
        description={content.description}
        actions={<ModulePageActions actions={content.actions} />}
      />

      <PandaResourceState count={count} emptyTitle={content.emptyTitle} emptyDescription={content.emptyDescription}>
        {children}
      </PandaResourceState>

      {footer}
    </div>
  )
}

export function StandardModulePageShell({
  page,
  count,
  children,
  footer,
}: {
  page: PandaStandardModulePage
  count: number
  children: React.ReactNode
  footer?: React.ReactNode
}) {
  return (
    <ModuleResourcePage content={pandaModulePageContent[page]} count={count} footer={footer}>
      {children}
    </ModuleResourcePage>
  )
}
