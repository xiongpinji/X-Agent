import { StandardModulePageShell } from '../components/common'
import { WorkflowCanvas, WorkflowRunGrid } from '../components/workflowCanvas'
import { useWorkflowsPageResources } from '../state/useModulePageResources'

export function WorkflowsPage() {
  const resources = useWorkflowsPageResources()

  return (
    <StandardModulePageShell page="workflows" count={resources.count}>
      <WorkflowCanvas workflowNodes={resources.workflowNodes} />
      <WorkflowRunGrid workflows={resources.workflows} />
    </StandardModulePageShell>
  )
}
