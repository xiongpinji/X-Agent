import { Plus } from 'lucide-react'
import type { ThreadItem } from '../types'
import { PageContractStrip, PandaResourceState, ProgressMeter } from './common'
import { ThreadExecutionWorkspace } from './threadExecutionWorkspace'
import {
  buildThreadListItemViewModel,
  threadWorkspaceHeader,
  threadWorkspaceResourceState,
} from './threadWorkspaceViewModel'
export { ThreadExecutionWorkspace } from './threadExecutionWorkspace'

export function ThreadListPanel({ threads }: { threads: readonly ThreadItem[] }) {
  return (
    <div className="panda-card p-3">
      <div className="mb-3 flex items-center justify-between">
        <h1 className="font-semibold">{threadWorkspaceHeader.title}</h1>
        <button className="panda-icon-button" type="button" aria-label={threadWorkspaceHeader.newThreadLabel}><Plus size={17} /></button>
      </div>
      <div className="panda-thread-list">
        {threads.map((thread, index) => {
          const row = buildThreadListItemViewModel(thread, index)

          return (
            <button key={row.id} className={`panda-thread-item ${row.active ? 'is-active' : ''}`} type="button">
              <div className="font-medium">{row.title}</div>
              <div className="mt-2 text-xs text-slate-400">{row.subtitle}</div>
              <div className="mt-3">
                <ProgressMeter value={row.progress} />
              </div>
            </button>
          )
        })}
      </div>
    </div>
  )
}

export function ThreadWorkPanel({ threads, activeThread }: { threads: readonly ThreadItem[]; activeThread?: ThreadItem }) {
  return (
    <div className="panda-card panda-work-panel">
      <div className="p-4 pb-0">
        <PageContractStrip page="threads" />
      </div>
      <PandaResourceState
        count={threads.length}
        emptyTitle={threadWorkspaceResourceState.emptyTitle}
        emptyDescription={threadWorkspaceResourceState.emptyDescription}
      >
        {activeThread ? <ThreadExecutionWorkspace activeThread={activeThread} /> : null}
      </PandaResourceState>
    </div>
  )
}
