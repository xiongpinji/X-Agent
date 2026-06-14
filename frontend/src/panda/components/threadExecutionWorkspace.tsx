import type { ThreadItem } from '../types'
import { ActionPanel, ExecutionStepRow } from './common'
import { buildThreadExecutionWorkspaceViewModel } from './threadExecutionWorkspaceViewModel'

export function ThreadExecutionWorkspace({ activeThread }: { activeThread: ThreadItem }) {
  const execution = buildThreadExecutionWorkspaceViewModel(activeThread)

  return (
    <>
      <div className="panda-tab-row">
        {execution.tabs.map((tab) => (
          <button key={tab} className={`panda-tab ${tab === execution.activeTab ? 'is-active' : ''}`} type="button">{tab}</button>
        ))}
      </div>
      <div className="panda-thread-execution-grid">
        <div className="min-w-0">
          <div className="mb-4">
            <h2 className="text-xl font-semibold">{activeThread.title}</h2>
            <p className="mt-2 text-sm text-slate-400">{execution.subtitle}</p>
          </div>
          <div className="space-y-3">
            {execution.steps.map((step) => (
              <ExecutionStepRow
                key={step.title}
                title={step.title}
                ownerAgent={step.ownerAgent}
                evidenceRef={step.evidenceRef}
                complete={step.complete}
              />
            ))}
          </div>
          <div className="mt-4 panda-terminal">
            {execution.terminalLines.map((line) => (
              <div key={line}>{line}</div>
            ))}
          </div>
        </div>
        <div className="panda-thread-side-actions">
          {execution.actionPanels.map((panel) => (
            <ActionPanel key={panel.title} title={panel.title} items={panel.items} />
          ))}
        </div>
      </div>
    </>
  )
}
