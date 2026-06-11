import { ShieldCheck } from 'lucide-react'
import type { WorkflowItem, WorkflowNode } from '../types'
import { FlowNodeCard, ProgressSummary, ResourceCardGrid, ResourceRuntimeCard, RuntimeMetaStrip } from './common'

export function WorkflowCanvas({ workflowNodes }: { workflowNodes: readonly WorkflowNode[] }) {
  return (
    <section className="panda-card panda-workflow-canvas">
      <div className="panda-canvas-toolbar">
        <div>
          <h2>客户反馈处理流程</h2>
          <p>运行中 · 7 个节点 · 1 个待审批网关 · evidence_refs 自动记录</p>
        </div>
        <div className="panda-risk-chip"><ShieldCheck size={16} aria-hidden="true" />策略由后端返回</div>
      </div>
      <div className="panda-canvas-stage">
        {workflowNodes.map((node) => (
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
  return (
    <ResourceRuntimeCard title={workflow.name} tone={workflow.tone} description={`${workflow.owner} · ${workflow.state}`}>
      <ProgressSummary value={workflow.progress} />
      <RuntimeMetaStrip runtime={workflow.runtime} owner={workflow.owner} risk={workflow.tone} />
    </ResourceRuntimeCard>
  )
}
