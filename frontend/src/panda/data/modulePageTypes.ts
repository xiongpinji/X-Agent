import type { PandaStandardModulePage } from '../types'
import type { ModulePageAction } from '../components/common'

export type ModulePageContent = {
  page: PandaStandardModulePage
  title: string
  description: string
  actions: readonly ModulePageAction[]
  emptyTitle: string
  emptyDescription: string
}
