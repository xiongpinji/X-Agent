import type { WorkflowItem } from '../types'
import { PandaEmptyState, ProgressSummary, RailCard } from './common'
import { buildRightRailWorkflowRunViewModels } from './rightRailWorkflowCardViewModel'

export function WorkflowRunsCard({ workflows }: { workflows: readonly WorkflowItem[] }) {
  const workflowRuns = buildRightRailWorkflowRunViewModels(workflows)

  return (
    <RailCard title="工作流执行" action="查看全部">
      {workflowRuns.length ? (
        <div className="space-y-4">
          {workflowRuns.map((workflow) => (
            <div key={workflow.id}>
              <div className="mb-2 flex items-center justify-between gap-3">
                <div className="min-w-0">
                  <div className="truncate text-sm font-medium">{workflow.name}</div>
                  <div className="text-xs text-slate-400">{workflow.state}</div>
                </div>
                <div className="text-sm text-slate-300">{workflow.progressLabel}</div>
              </div>
              <ProgressSummary value={workflow.progress} ariaLabel={workflow.progressAriaLabel} />
            </div>
          ))}
        </div>
      ) : <PandaEmptyState title="暂无工作流执行" description="工作流 BFF 接入后会显示运行图、进度和失败补偿状态。" />}
    </RailCard>
  )
}
