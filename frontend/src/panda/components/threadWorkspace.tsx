import { Plus } from 'lucide-react'
import type { ThreadItem } from '../types'
import { PageContractStrip, PandaResourceState, ProgressMeter } from './common'
import { ThreadExecutionWorkspace } from './threadExecutionWorkspace'
export { ThreadExecutionWorkspace } from './threadExecutionWorkspace'

export function ThreadListPanel({ threads }: { threads: readonly ThreadItem[] }) {
  return (
    <div className="panda-card p-3">
      <div className="mb-3 flex items-center justify-between">
        <h1 className="font-semibold">线程工作区</h1>
        <button className="panda-icon-button" type="button" aria-label="新建线程"><Plus size={17} /></button>
      </div>
      <div className="panda-thread-list">
        {threads.map((thread, index) => (
          <button key={thread.id} className={`panda-thread-item ${index === 0 ? 'is-active' : ''}`} type="button">
            <div className="font-medium">{thread.title}</div>
            <div className="mt-2 text-xs text-slate-400">{thread.project} · {thread.ownerAgent}</div>
            <div className="mt-3">
              <ProgressMeter value={thread.progress} />
            </div>
          </button>
        ))}
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
        emptyTitle="暂无执行线程"
        emptyDescription="后续接入线程 BFF 后，这里会展示计划、终端、文件变更、产物和审计证据。"
      >
        {activeThread ? <ThreadExecutionWorkspace activeThread={activeThread} /> : null}
      </PandaResourceState>
    </div>
  )
}
