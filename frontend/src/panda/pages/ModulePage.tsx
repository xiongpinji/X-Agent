import { capabilityRows, getModuleFallbackMeta } from '../data/moduleFallbackContent'
import type { PandaPage } from '../types'
import { ModuleFallbackWorkspace } from '../components/moduleFallback'

export function ModulePage({ page, onNavigate }: { page: PandaPage; onNavigate: (page: PandaPage) => void }) {
  const { title, icon: Icon } = getModuleFallbackMeta(page)

  return <ModuleFallbackWorkspace title={title} icon={Icon} capabilityRows={capabilityRows} onNavigate={onNavigate} />
}
