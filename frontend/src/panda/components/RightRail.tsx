import { usePandaWorkspaceLifecycle, usePandaWorkspaceResource } from '../state/PandaWorkspaceContext'
import { getPandaResourcesBffConfig } from '../api/resourcesBffConfig'
import type { PandaWorkbenchHome } from '../types'
import { PandaErrorState, PandaLoadingState, RailCard } from './common'
import { AgentActivityCard, ApprovalRiskCard, ResourceSnapshotCard, SystemStatusCard, WorkflowRunsCard } from './rightRailCards'
import { resolveRightRailAgentActivities, resolveRightRailWorkflowRuns } from './rightRailFallbacks'

export function RightRail({ home, isLoading, error }: { home: PandaWorkbenchHome | null; isLoading: boolean; error: string | null }) {
  const { status, source, refreshedAt, refresh, error: resourceError } = usePandaWorkspaceLifecycle()
  const resourcesBffConfig = getPandaResourcesBffConfig()
  const agents = usePandaWorkspaceResource('agents')
  const workflowFallback = usePandaWorkspaceResource('workflows')
  const activities = resolveRightRailAgentActivities({ homeActivities: home?.agentActivity, agents })
  const workflows = resolveRightRailWorkflowRuns({ homeWorkflows: home?.workflowRuns, fallbackWorkflows: workflowFallback })

  return (
    <aside className="panda-right-rail">
      {isLoading ? <RailCard title="同步状态"><PandaLoadingState title="正在同步运行态势" description="加载智能体活动、工作流执行和审批状态。" /></RailCard> : null}
      {!isLoading && error ? <RailCard title="数据源"><PandaErrorState description="首页聚合接口暂不可用，右侧态势栏正在使用本地快照。" /></RailCard> : null}
      <ResourceSnapshotCard
        source={source}
        status={status}
        refreshedAt={refreshedAt}
        resourceError={resourceError}
        resourcesBffConfig={resourcesBffConfig}
        onRefresh={refresh}
      />
      <AgentActivityCard activities={activities} />
      <WorkflowRunsCard workflows={workflows} />
      <ApprovalRiskCard />
      <SystemStatusCard />
    </aside>
  )
}
