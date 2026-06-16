import { ShieldCheck } from 'lucide-react'
import type { WorkflowItem, WorkflowNode } from '../types'
import { FlowNodeCard, ProgressSummary, ResourceCardGrid, ResourceRuntimeCard, RuntimeMetaStrip } from './common'
import { buildWorkflowCanvasSummary, buildWorkflowRunCardViewModel } from './workflowCanvasViewModel'

export function WorkflowCanvas({ workflowNodes }: { workflowNodes: readonly WorkflowNode[] }) {
  const summary = buildWorkflowCanvasSummary(workflowNodes)

  return (
    <section className="panda-card panda-workflow-canvas">
      <div className="panda-canvas-toolbar">
        <div>
          <h2>{summary.title}</h2>
          <p>{summary.subtitle}</p>
        </div>
        <div className="panda-risk-chip"><ShieldCheck size={16} aria-hidden="true" />{summary.policyLabel}</div>
      </div>
      <div className="panda-canvas-stage">
        {summary.nodes.map((node) => (
          <FlowNodeCard
            key={node.id}
            title={node.title}
            role={node.role}
            status={node.status}
            tone={node.tone}
            x={node.x}
            y={node.y}
          />
        ))}
      </div>
    </section>
  )
}

export function WorkflowRunGrid({ workflows }: { workflows: readonly WorkflowItem[] }) {
  return (
    <ResourceCardGrid
      items={workflows}
      className="panda-list-grid"
      renderItem={(workflow) => <WorkflowRunCard key={workflow.id} workflow={workflow} />}
    />
  )
}

export function WorkflowRunCard({ workflow }: { workflow: WorkflowItem }) {
  const card = buildWorkflowRunCardViewModel(workflow)

  return (
    <ResourceRuntimeCard title={card.title} tone={workflow.tone} description={card.description}>
      <ProgressSummary value={card.progress} />
      <RuntimeMetaStrip runtime={workflow.runtime} owner={card.runtimeOwner} risk={card.runtimeRisk} />
    </ResourceRuntimeCard>
  )
}
