import { ClipboardCheck } from 'lucide-react'
import type { TaskSummary } from '../types'
import { ActionPanel, ManagementRow, ProgressMeter, SectionHeader, WorkspacePanel } from './common'
import { buildTaskQueueRowViewModel, taskQueueExecutionPanel, taskQueueHeader } from './taskQueueViewModel'

export function TaskQueueWorkspace({ tasks }: { tasks: readonly TaskSummary[] }) {
  return (
    <section className="panda-split-layout">
      <TaskQueuePanel tasks={tasks} />
      <ActionPanel title={taskQueueExecutionPanel.title} items={taskQueueExecutionPanel.items} />
    </section>
  )
}

export function TaskQueuePanel({ tasks }: { tasks: readonly TaskSummary[] }) {
  return (
    <WorkspacePanel as="div">
      <SectionHeader icon={<ClipboardCheck className="text-rose-300" size={22} />} title={taskQueueHeader.title} />
      <div className="space-y-3">
        {tasks.map((task) => (
          <TaskQueueRow key={task.id} task={task} />
        ))}
      </div>
    </WorkspacePanel>
  )
}

export function TaskQueueRow({ task }: { task: TaskSummary }) {
  const row = buildTaskQueueRowViewModel(task)

  return (
    <ManagementRow
      tone={row.tone}
      title={row.title}
      description={row.description}
      runtime={row.runtime}
    >
      <div className="w-44">
        <ProgressMeter
          value={row.progress}
          label={<><span>{row.progressLabel[0]}</span><span>{row.progressLabel[1]}</span></>}
        />
      </div>
    </ManagementRow>
  )
}
