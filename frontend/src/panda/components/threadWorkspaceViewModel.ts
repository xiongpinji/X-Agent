import type { ThreadItem } from '../types'

export type ThreadWorkspaceHeaderViewModel = {
  readonly title: string
  readonly newThreadLabel: string
}

export type ThreadWorkspaceResourceStateViewModel = {
  readonly emptyTitle: string
  readonly emptyDescription: string
}

export type ThreadListItemViewModel = {
  readonly id: string
  readonly title: string
  readonly subtitle: string
  readonly progress: number
  readonly active: boolean
}

export const threadWorkspaceHeader: ThreadWorkspaceHeaderViewModel = {
  title: '线程工作区',
  newThreadLabel: '新建线程',
}

export const threadWorkspaceResourceState: ThreadWorkspaceResourceStateViewModel = {
  emptyTitle: '暂无执行线程',
  emptyDescription: '后续接入线程 BFF 后，这里会展示计划、终端、文件变更、产物和审计证据。',
}

export function buildThreadListItemViewModel(thread: ThreadItem, index: number): ThreadListItemViewModel {
  return {
    id: thread.id,
    title: thread.title,
    subtitle: `${thread.project} · ${thread.ownerAgent}`,
    progress: thread.progress,
    active: index === 0,
  }
}
