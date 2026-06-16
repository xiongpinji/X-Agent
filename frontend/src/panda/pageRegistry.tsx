import type { ComponentType } from 'react'
import { navItems } from './data/navigation'
import { AgentsPage } from './pages/AgentsPage'
import { AuditPage } from './pages/AuditPage'
import { AutomationPage } from './pages/AutomationPage'
import { DataPage } from './pages/DataPage'
import { KnowledgePage } from './pages/KnowledgePage'
import { ProjectsPage } from './pages/ProjectsPage'
import { SettingsPage } from './pages/SettingsPage'
import { TasksPage } from './pages/TasksPage'
import { ThreadsPage } from './pages/ThreadsPage'
import { ToolsPage } from './pages/ToolsPage'
import { WorkflowsPage } from './pages/WorkflowsPage'
import type { PandaPage } from './types'

export const pandaPageIds = new Set<PandaPage>(navItems.map((item) => item.id))

export const pandaPageComponents: Partial<Record<PandaPage, ComponentType>> = {
  threads: ThreadsPage,
  tasks: TasksPage,
  projects: ProjectsPage,
  workflows: WorkflowsPage,
  agents: AgentsPage,
  knowledge: KnowledgePage,
  tools: ToolsPage,
  data: DataPage,
  audit: AuditPage,
  automation: AutomationPage,
  settings: SettingsPage,
}

export function isPandaPage(page: string): page is PandaPage {
  return pandaPageIds.has(page as PandaPage)
}

export function getPandaPageComponent(page: PandaPage): ComponentType | null {
  return pandaPageComponents[page] ?? null
}
