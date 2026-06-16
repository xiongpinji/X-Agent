import { StandardModulePageShell } from '../components/common'
import { KnowledgeSourceGrid } from '../components/knowledgeBase'
import { useKnowledgePageResources } from '../state/useModulePageResources'

export function KnowledgePage() {
  const resources = useKnowledgePageResources()

  return (
    <StandardModulePageShell page="knowledge" count={resources.count}>
      <KnowledgeSourceGrid knowledgeSources={resources.knowledgeSources} />
    </StandardModulePageShell>
  )
}
