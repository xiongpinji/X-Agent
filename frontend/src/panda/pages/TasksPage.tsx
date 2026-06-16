import { StandardModulePageShell } from '../components/common'
import { TaskQueueWorkspace } from '../components/taskQueue'
import { useTasksPageResources } from '../state/useModulePageResources'

export function TasksPage() {
  const resources = useTasksPageResources()

  return (
    <StandardModulePageShell page="tasks" count={resources.count}>
      <TaskQueueWorkspace tasks={resources.tasks} />
    </StandardModulePageShell>
  )
}
