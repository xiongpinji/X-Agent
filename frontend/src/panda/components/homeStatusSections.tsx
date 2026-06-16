import type { PandaWorkbenchDataSource } from '../api/workbenchClient'
import type { PandaWorkbenchHome } from '../types'
import { PandaErrorState, PandaLoadingState, WorkspacePanel } from './common'
import { buildPlatformSnapshotViewModel } from './homeStatusSectionsViewModel'

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
  const snapshot = buildPlatformSnapshotViewModel({ home, source, isLoading, error })

  return (
    <WorkspacePanel title="系统状态">
      {isLoading ? <div className="mt-4"><PandaLoadingState title={snapshot.loadingTitle} description={snapshot.loadingDescription} /></div> : null}
      {snapshot.errorDescription ? (
        <div className="mt-4">
          <PandaErrorState description={snapshot.errorDescription} />
        </div>
      ) : null}
      <div className="mt-4 space-y-4">
        {snapshot.metricRows.map(([label, value, unit]) => (
          <div key={label} className="flex items-center justify-between text-sm">
            <span className="text-slate-400">{label}</span>
            <span className="text-slate-100">{value}{unit}</span>
          </div>
        ))}
      </div>
      <div className="mt-5 rounded-lg bg-white/[0.04] p-3">
        <div className="text-sm font-medium">{snapshot.coreLabel}</div>
        <p className="mt-2 text-xs leading-5 text-slate-400">{snapshot.summary}</p>
      </div>
      <div className="mt-4 rounded-lg border border-white/10 bg-white/[0.03] p-3">
        <div className="text-sm font-medium text-slate-100">Plan / Goal 状态</div>
        <div className="mt-3 space-y-2">
          {snapshot.controlRows.map(([label, value, unit]) => (
            <div key={label} className="flex items-center justify-between text-xs">
              <span className="text-slate-400">{label}</span>
              <span className="text-slate-100">{value}{unit}</span>
            </div>
          ))}
        </div>
        <p className="mt-3 text-xs leading-5 text-slate-400">{snapshot.controlBoundary}</p>
      </div>
      <div className="mt-4 rounded-lg border border-white/10 bg-white/[0.03] p-3">
        <div className="text-sm font-medium text-slate-100">主线能力边界</div>
        <div className="mt-3 space-y-2">
          {snapshot.runtimeRows.map(([label, value, unit]) => (
            <div key={label} className="flex items-center justify-between text-xs">
              <span className="text-slate-400">{label}</span>
              <span className="text-slate-100">{value}{unit}</span>
            </div>
          ))}
        </div>
        <p className="mt-3 text-xs leading-5 text-slate-400">{snapshot.runtimeBoundary}</p>
      </div>
    </WorkspacePanel>
  )
}
