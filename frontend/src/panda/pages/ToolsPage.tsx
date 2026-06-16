import { StandardModulePageShell } from '../components/common'
import { ToolAccessBoundary, ToolCapabilityGrid } from '../components/toolCenter'
import { useToolsPageResources } from '../state/useModulePageResources'

export function ToolsPage() {
  const resources = useToolsPageResources()

  return (
    <StandardModulePageShell page="tools" count={resources.count} footer={<ToolAccessBoundary />}>
      <ToolCapabilityGrid tools={resources.toolCapabilities} />
    </StandardModulePageShell>
  )
}
