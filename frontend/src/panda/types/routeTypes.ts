import type { LucideIcon } from 'lucide-react'

export type PandaPage =
  | 'home'
  | 'threads'
  | 'tasks'
  | 'projects'
  | 'workflows'
  | 'agents'
  | 'knowledge'
  | 'tools'
  | 'data'
  | 'audit'
  | 'automation'
  | 'settings'

export type PandaStandardModulePage = Exclude<PandaPage, 'home' | 'threads'>

export type NavItem = {
  id: PandaPage
  label: string
  icon: LucideIcon
}

export type ModuleCard = {
  id: PandaPage
  title: string
  summary: string
  metric: string
  icon: LucideIcon
}

export type QuickAction = {
  title: string
  description: string
  action: string
  targetPage: PandaPage
  icon: LucideIcon
}

export type PromptAction = {
  label: string
  icon: LucideIcon
}

export type CapabilityRow = {
  label: string
  value: string
}
