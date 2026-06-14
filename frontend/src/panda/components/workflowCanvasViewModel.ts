import type { StatusTone, WorkflowItem, WorkflowNode } from '../types'

export type WorkflowCanvasSummary = {
  readonly title: string
  readonly subtitle: string
  readonly policyLabel: string
  readonly nodes: readonly WorkflowNode[]
}

export type WorkflowRunCardViewModel = {
  readonly title: string
  readonly description: string
  readonly progress: number
  readonly runtimeOwner: string
  readonly runtimeRisk: StatusTone
}

const awaitingApprovalPattern = /审批|待审|approval|review/i
const defaultWorkflowTitle = '客户反馈处理流程'
const emptyWorkflowSubtitle = '等待工作流节点 · evidence_refs 将随运行结果记录'
const workflowPolicyLabel = '策略由后端返回'

function formatNodeCount(count: number): string {
  return `${count} 个节点`
}

function countApprovalGateways(workflowNodes: readonly WorkflowNode[]): number {
  return workflowNodes.filter((node) => awaitingApprovalPattern.test(`${node.status} ${node.title} ${node.role}`)).length
}

function countEvidenceRefs(workflowNodes: readonly WorkflowNode[]): number {
  return workflowNodes.reduce((total, node) => total + (node.runtime?.evidenceRefs.length ?? 0), 0)
}

export function buildWorkflowCanvasSummary(workflowNodes: readonly WorkflowNode[]): WorkflowCanvasSummary {
  if (workflowNodes.length === 0) {
    return {
      title: defaultWorkflowTitle,
      subtitle: emptyWorkflowSubtitle,
      policyLabel: workflowPolicyLabel,
      nodes: workflowNodes,
    }
  }

  const approvalGateways = countApprovalGateways(workflowNodes)
  const evidenceRefs = countEvidenceRefs(workflowNodes)
  const primaryStatus = workflowNodes[0]?.runtime?.status ?? workflowNodes[0]?.status ?? '运行中'

  return {
    title: defaultWorkflowTitle,
    subtitle: [
      primaryStatus,
      formatNodeCount(workflowNodes.length),
      `${approvalGateways} 个待审批网关`,
      evidenceRefs > 0 ? `${evidenceRefs} 条 evidence_refs` : 'evidence_refs 自动记录',
    ].join(' · '),
    policyLabel: workflowPolicyLabel,
    nodes: workflowNodes,
  }
}

export function buildWorkflowRunCardViewModel(workflow: WorkflowItem): WorkflowRunCardViewModel {
  return {
    title: workflow.name,
    description: [workflow.owner, workflow.state].filter(Boolean).join(' · '),
    progress: workflow.progress,
    runtimeOwner: workflow.owner,
    runtimeRisk: workflow.tone,
  }
}
