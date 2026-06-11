import type { PandaWorkbenchDataSource } from '../api/workbenchClient'
import type { PandaWorkbenchHome } from '../types'
import { PandaErrorState, PandaLoadingState, WorkspacePanel } from './common'

export function PlatformSnapshot({
  home,
  source,
  isLoading,
  error,
}: {
  home: PandaWorkbenchHome | null
  source: PandaWorkbenchDataSource
  isLoading: boolean
  error: string | null
}) {
  const metrics = home?.metrics
  const rows = [
    ['活跃智能体', metrics?.activeAgents ?? 8, '个'],
    ['运行工作流', metrics?.runningWorkflows ?? 5, '条'],
    ['待审批', metrics?.pendingApprovals ?? 3, '项'],
    ['API 调用', metrics?.apiCalls ?? 12428, '次'],
    ['存储使用', metrics?.storageUsed ?? '45.2 GB / 1 TB', ''],
  ] as const

  return (
    <WorkspacePanel title="系统状态">
      {isLoading ? <div className="mt-4"><PandaLoadingState title="正在同步工作台" description="正在读取首页聚合数据和执行态势。" /></div> : null}
      {!isLoading && source === 'mock' && error ? (
        <div className="mt-4">
          <PandaErrorState description={`${error}。当前展示本地演示数据，等待后端主线收尾后切换真实资源。`} />
        </div>
      ) : null}
      <div className="mt-4 space-y-4">
        {rows.map(([label, value, unit]) => (
          <div key={label} className="flex items-center justify-between text-sm">
            <span className="text-slate-400">{label}</span>
            <span className="text-slate-100">{value}{unit}</span>
          </div>
        ))}
      </div>
      <div className="mt-5 rounded-lg bg-white/[0.04] p-3">
        <div className="text-sm font-medium">Powered by X-Agent Autonomous Framework</div>
        <p className="mt-2 text-xs leading-5 text-slate-400">{home?.summary ?? '企业级自主智能体框架，覆盖编排、记忆、工具、审计和多渠道运行。'}</p>
      </div>
    </WorkspacePanel>
  )
}
