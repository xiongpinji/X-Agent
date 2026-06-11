import { Brain } from 'lucide-react'
import type { KnowledgeSource } from '../types'
import { ResourceCardGrid, ResourceInfoCard } from './common'

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
  return (
    <ResourceInfoCard
      icon={<Brain className="text-rose-300" size={19} />}
      title={source.name}
      tone={source.tone}
      description={`${source.kind} · ${source.status}`}
      items={[
        { label: '文档', value: source.documents },
        { label: '同步', value: source.lastSync },
      ]}
    />
  )
}
