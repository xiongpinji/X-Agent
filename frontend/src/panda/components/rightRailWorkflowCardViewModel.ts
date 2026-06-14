import type { WorkflowItem } from '../types'

export type RightRailWorkflowRunViewModel = {
  readonly id: string
  readonly name: string
  readonly state: string
  readonly progress: number
  readonly progressLabel: string
  readonly progressAriaLabel: string
}

export function buildRightRailWorkflowRunViewModel(workflow: WorkflowItem): RightRailWorkflowRunViewModel {
  return {
    id: workflow.id,
    name: workflow.name,
    state: workflow.state,
    progress: workflow.progress,
    progressLabel: `${workflow.progress}%`,
    progressAriaLabel: `${workflow.name} 工作流进度`,
  }
}

export function buildRightRailWorkflowRunViewModels(
  workflows: readonly WorkflowItem[],
): readonly RightRailWorkflowRunViewModel[] {
  return workflows.map(buildRightRailWorkflowRunViewModel)
}
