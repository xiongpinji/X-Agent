import { Wrench } from 'lucide-react'
import type { ToolCapability } from '../types'
import { CapabilityMetricCard, InsetInfoBlock, ResourceCardGrid, WorkspacePanel } from './common'
import { buildToolCapabilityCardViewModel, toolAccessBoundaryItems, toolAccessBoundaryTitle } from './toolCenterViewModel'

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
  const card = buildToolCapabilityCardViewModel(tool)

  return (
    <CapabilityMetricCard
      icon={<Wrench size={18} />}
      title={card.title}
      subtitle={card.subtitle}
      tone={tool.tone}
      metrics={card.metrics}
    />
  )
}

export function ToolAccessBoundary() {
  return (
    <WorkspacePanel title={toolAccessBoundaryTitle}>
      <div className="mt-4 grid gap-3 md:grid-cols-3">
        {toolAccessBoundaryItems.map((item) => (
          <InsetInfoBlock key={item} dense>{item}</InsetInfoBlock>
        ))}
      </div>
    </WorkspacePanel>
  )
}
