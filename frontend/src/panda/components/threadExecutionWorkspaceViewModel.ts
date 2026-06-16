import type { ThreadItem } from '../types'
import {
  threadExecutionArtifactActions,
  threadExecutionControlActions,
  threadExecutionSteps,
  threadExecutionTabs,
  threadExecutionTerminalLines,
} from '../data/threadExecutionContent'

export type ThreadExecutionStepViewModel = {
  readonly title: string
  readonly ownerAgent: string
  readonly evidenceRef: string
  readonly complete: boolean
}

export type ThreadExecutionActionPanelViewModel = {
  readonly title: string
  readonly items: readonly string[]
}

export type ThreadExecutionWorkspaceViewModel = {
  readonly tabs: readonly string[]
  readonly activeTab: string
  readonly subtitle: string
  readonly steps: readonly ThreadExecutionStepViewModel[]
  readonly terminalLines: readonly string[]
  readonly actionPanels: readonly ThreadExecutionActionPanelViewModel[]
}

export function buildThreadExecutionWorkspaceViewModel(activeThread: ThreadItem): ThreadExecutionWorkspaceViewModel {
  return {
    tabs: threadExecutionTabs,
    activeTab: threadExecutionTabs[0],
    subtitle: '用户可在这里 Steer 纠偏、暂停执行、转交智能体、请求人审、生成 PR。',
    steps: threadExecutionSteps.map((step, index) => ({
      title: step,
      ownerAgent: activeThread.ownerAgent,
      evidenceRef: `#${index + 1}`,
      complete: index < 2,
    })),
    terminalLines: threadExecutionTerminalLines,
    actionPanels: [
      { title: '执行控制', items: threadExecutionControlActions },
      { title: '产物', items: threadExecutionArtifactActions },
    ],
  }
}
