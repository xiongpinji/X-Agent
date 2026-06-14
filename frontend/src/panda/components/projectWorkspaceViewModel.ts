import type { ProjectItem, StatusTone, RuntimeMetadata } from '../types'

export type ProjectWorkspaceHeaderViewModel = {
  readonly title: string
}

export type ProjectTableRowViewModel = {
  readonly name: string
  readonly type: string
  readonly runtime?: RuntimeMetadata
  readonly runtimeOwner: string
  readonly runtimeUpdatedAt: string
  readonly runtimeRisk: StatusTone
}

export const projectWorkspaceHeader: ProjectWorkspaceHeaderViewModel = {
  title: '最近项目',
}

export const projectTableColumns = ['名称', '类型', '运行态'] as const

export function buildProjectTableRowViewModel(project: ProjectItem): ProjectTableRowViewModel {
  return {
    name: project.name,
    type: project.type,
    runtime: project.runtime,
    runtimeOwner: project.ownerAgent,
    runtimeUpdatedAt: project.updatedAt,
    runtimeRisk: project.risk,
  }
}
