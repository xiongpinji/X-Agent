import { Wrench } from 'lucide-react'
import type { ToolCapability } from '../types'
import { CapabilityMetricCard, InsetInfoBlock, ResourceCardGrid, WorkspacePanel } from './common'

export function ToolCapabilityGrid({ tools }: { tools: readonly ToolCapability[] }) {
  return (
    <ResourceCardGrid
      items={tools}
      className="panda-tools-grid"
      renderItem={(tool) => <ToolCapabilityCard key={tool.id} tool={tool} />}
    />
  )
}

export function ToolCapabilityCard({ tool }: { tool: ToolCapability }) {
  return (
    <CapabilityMetricCard
      icon={<Wrench size={18} />}
      title={tool.name}
      subtitle={tool.provider}
      tone={tool.tone}
      metrics={[
        { label: '状态', value: tool.status },
        { label: '权限', value: tool.permission },
        { label: '调用', value: tool.invocations },
      ]}
    />
  )
}

export function ToolAccessBoundary() {
  return (
    <WorkspacePanel title="接入边界">
      <div className="mt-4 grid gap-3 md:grid-cols-3">
        {['工具发现由 MCP 管理器提供', '权限与审批由后端策略返回', '前端只展示状态、证据和可用动作'].map((item) => (
          <InsetInfoBlock key={item} dense>{item}</InsetInfoBlock>
        ))}
      </div>
    </WorkspacePanel>
  )
}
