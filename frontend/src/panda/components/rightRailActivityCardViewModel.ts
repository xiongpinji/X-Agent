import type { ActivityItem, RuntimeMetadata, StatusTone } from '../types'

export type RightRailActivityCardHeaderViewModel = {
  readonly title: string
  readonly action: string
}

export type RightRailActivityEmptyStateViewModel = {
  readonly title: string
  readonly description: string
}

export type RightRailActivityRowViewModel = {
  readonly id: string
  readonly title: string
  readonly subtitle: string
  readonly tone: StatusTone
  readonly runtime?: RuntimeMetadata
  readonly updatedAt: string
}

export const rightRailActivityCardHeader: RightRailActivityCardHeaderViewModel = {
  title: '智能体活动',
  action: '查看全部',
}

export const rightRailActivityEmptyState: RightRailActivityEmptyStateViewModel = {
  title: '暂无智能体活动',
  description: '启动任务后会在这里显示智能体运行、等待审批和失败事件。',
}

export function buildRightRailActivityRowViewModel(item: ActivityItem): RightRailActivityRowViewModel {
  return {
    id: item.id,
    title: item.title,
    subtitle: item.subtitle,
    tone: item.tone,
    runtime: item.runtime,
    updatedAt: item.time,
  }
}

export function buildRightRailActivityRowViewModels(
  activities: readonly ActivityItem[],
): readonly RightRailActivityRowViewModel[] {
  return activities.map(buildRightRailActivityRowViewModel)
}
