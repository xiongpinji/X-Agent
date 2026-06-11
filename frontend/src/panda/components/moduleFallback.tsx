import type { LucideIcon } from 'lucide-react'
import type { CapabilityRow, PandaPage } from '../types'
import { PandaEmptyState } from './common'
import { ModuleCapabilityGrid, ModuleDeliverySurface, ModuleFallbackHero } from './moduleFallbackSurface'

export { ModuleCapabilityGrid, ModuleDeliverySurface, ModuleFallbackHero } from './moduleFallbackSurface'

export function ModuleFallbackWorkspace({
  title,
  icon: Icon,
  capabilityRows,
  onNavigate,
}: {
  title: string
  icon: LucideIcon
  capabilityRows: readonly CapabilityRow[]
  onNavigate: (page: PandaPage) => void
}) {
  return (
    <div className="space-y-5">
      <ModuleFallbackHero title={title} icon={Icon} onNavigate={onNavigate} />
      <ModuleCapabilityGrid capabilityRows={capabilityRows} />
      <ModuleDeliverySurface />
      <PandaEmptyState
        title="等待真实资源接入"
        description="该兜底页会在后续对齐中被具体模块页面替换；当前保留统一的空状态、错误状态和执行入口规范。"
      />
    </div>
  )
}
