import { ClipboardCheck } from 'lucide-react'
import type { TaskSummary } from '../types'
import { ActionPanel, ManagementRow, ProgressMeter, SectionHeader, WorkspacePanel } from './common'

export function TaskQueueWorkspace({ tasks }: { tasks: readonly TaskSummary[] }) {
  return (
    <section className="panda-split-layout">
      <TaskQueuePanel tasks={tasks} />
      <ActionPanel title="执行动作" items={['Steer 纠偏', '转交智能体', '请求人审', '生成产物']} />
    </section>
  )
}

export function TaskQueuePanel({ tasks }: { tasks: readonly TaskSummary[] }) {
  return (
    <WorkspacePanel as="div">
      <SectionHeader icon={<ClipboardCheck className="text-rose-300" size={22} />} title="任务队列" />
      <div className="space-y-3">
        {tasks.map((task) => (
          <TaskQueueRow key={task.id} task={task} />
        ))}
      </div>
    </WorkspacePanel>
  )
}

export function TaskQueueRow({ task }: { task: TaskSummary }) {
  return (
    <ManagementRow
      tone={task.tone}
      title={task.title}
      description={`${task.project} · ${task.ownerAgent} · ${task.status}`}
      runtime={task.runtime}
    >
      <div className="w-44">
        <ProgressMeter
          value={task.progress}
          label={<><span>{task.priority}</span><span>{task.progress}%</span></>}
        />
      </div>
    </ManagementRow>
  )
}
