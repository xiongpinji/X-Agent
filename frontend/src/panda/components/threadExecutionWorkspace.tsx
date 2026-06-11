import type { ThreadItem } from '../types'
import {
  threadExecutionArtifactActions,
  threadExecutionControlActions,
  threadExecutionSteps,
  threadExecutionTabs,
  threadExecutionTerminalLines,
} from '../data/threadExecutionContent'
import { ActionPanel, ExecutionStepRow } from './common'

export function ThreadExecutionWorkspace({ activeThread }: { activeThread: ThreadItem }) {
  return (
    <>
      <div className="panda-tab-row">
        {threadExecutionTabs.map((tab, index) => (
          <button key={tab} className={`panda-tab ${index === 0 ? 'is-active' : ''}`} type="button">{tab}</button>
        ))}
      </div>
      <div className="panda-thread-execution-grid">
        <div className="min-w-0">
          <div className="mb-4">
            <h2 className="text-xl font-semibold">{activeThread.title}</h2>
            <p className="mt-2 text-sm text-slate-400">用户可在这里 Steer 纠偏、暂停执行、转交智能体、请求人审、生成 PR。</p>
          </div>
          <div className="space-y-3">
            {threadExecutionSteps.map((step, index) => (
              <ExecutionStepRow
                key={step}
                title={step}
                ownerAgent={activeThread.ownerAgent}
                evidenceRef={`#${index + 1}`}
                complete={index < 2}
              />
            ))}
          </div>
          <div className="mt-4 panda-terminal">
            {threadExecutionTerminalLines.map((line) => (
              <div key={line}>{line}</div>
            ))}
          </div>
        </div>
        <div className="panda-thread-side-actions">
          <ActionPanel title="执行控制" items={threadExecutionControlActions} />
          <ActionPanel title="产物" items={threadExecutionArtifactActions} />
        </div>
      </div>
    </>
  )
}
