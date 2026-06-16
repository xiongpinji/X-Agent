import { Brain } from 'lucide-react'
import type { KnowledgeSource } from '../types'
import { ResourceCardGrid, ResourceInfoCard } from './common'
import { buildKnowledgeSourceCardViewModel } from './knowledgeBaseViewModel'

export function KnowledgeSourceGrid({ knowledgeSources }: { knowledgeSources: readonly KnowledgeSource[] }) {
  return (
    <ResourceCardGrid
      items={knowledgeSources}
      className="panda-list-grid"
      renderItem={(source) => <KnowledgeSourceCard key={source.id} source={source} />}
    />
  )
}

export function KnowledgeSourceCard({ source }: { source: KnowledgeSource }) {
  const card = buildKnowledgeSourceCardViewModel(source)

  return (
    <ResourceInfoCard
      icon={<Brain className="text-rose-300" size={19} />}
      title={card.title}
      tone={source.tone}
      description={card.description}
      items={card.items}
    />
  )
}
