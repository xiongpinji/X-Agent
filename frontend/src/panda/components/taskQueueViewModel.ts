import type { ReactNode } from 'react'
import type { RuntimeMetadata, StatusTone, TaskSummary } from '../types'

export type TaskQueueRowViewModel = {
  readonly title: string
  readonly tone: StatusTone
  readonly description: string
  readonly runtime?: RuntimeMetadata
  readonly progress: number
  readonly progressLabel: readonly [ReactNode, ReactNode]
}

export type TaskQueueHeaderViewModel = {
  readonly title: string
}

export type TaskQueueExecutionPanelViewModel = {
  readonly title: string
  readonly items: readonly string[]
}

export const taskQueueHeader: TaskQueueHeaderViewModel = {
  title: '任务队列',
}

export const taskQueueExecutionActions = ['Steer 纠偏', '转交智能体', '请求人审', '生成产物'] as const
export const taskQueueExecutionPanel: TaskQueueExecutionPanelViewModel = {
  title: '执行动作',
  items: taskQueueExecutionActions,
}

export function buildTaskQueueRowViewModel(task: TaskSummary): TaskQueueRowViewModel {
  return {
    title: task.title,
    tone: task.tone,
    description: [task.project, task.ownerAgent, task.status].filter(Boolean).join(' · '),
    runtime: task.runtime,
    progress: task.progress,
    progressLabel: [task.priority, `${task.progress}%`],
  }
}
