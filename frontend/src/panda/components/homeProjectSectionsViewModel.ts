import type { ProjectItem, RuntimeMetadata, StatusTone } from '../types'

export type RecentProjectsHeaderViewModel = {
  readonly title: string
  readonly actionLabel: string
}

export type RecentProjectsResourceStateViewModel = {
  readonly emptyTitle: string
  readonly emptyDescription: string
  readonly loadingTitle: string
  readonly loadingDescription: string
}

export type RecentProjectTableRowViewModel = {
  readonly name: string
  readonly type: string
  readonly runtime?: RuntimeMetadata
  readonly runtimeOwner?: string
  readonly runtimeUpdatedAt?: string
  readonly runtimeRisk?: StatusTone
}

export const recentProjectsHeader: RecentProjectsHeaderViewModel = {
  title: '最近项目',
  actionLabel: '查看全部 →',
}

export const recentProjectsResourceState: RecentProjectsResourceStateViewModel = {
  emptyTitle: '暂无最近项目',
  emptyDescription: '后续接入项目 BFF 后，这里会展示工作区、智能体应用和工作流的最近更新。',
  loadingTitle: '正在同步最近项目',
  loadingDescription: '正在读取项目、智能体应用和工作流的最近更新。',
}

export const recentProjectsTableColumns = ['名称', '类型', '运行态'] as const

export function buildRecentProjectTableRowViewModel(project: ProjectItem): RecentProjectTableRowViewModel {
  return {
    name: project.name,
    type: project.type,
    runtime: project.runtime,
    runtimeOwner: project.ownerAgent,
    runtimeUpdatedAt: project.updatedAt,
    runtimeRisk: project.risk,
  }
}
