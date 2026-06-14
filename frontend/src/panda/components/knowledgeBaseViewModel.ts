import type { KnowledgeSource } from '../types'
import type { KeyValueItem } from './common'

export type KnowledgeSourceCardViewModel = {
  readonly title: string
  readonly description: string
  readonly items: readonly KeyValueItem[]
}

export function buildKnowledgeSourceCardViewModel(source: KnowledgeSource): KnowledgeSourceCardViewModel {
  return {
    title: source.name,
    description: [source.kind, source.status].filter(Boolean).join(' · '),
    items: [
      { label: '文档', value: source.documents },
      { label: '同步', value: source.lastSync },
    ],
  }
}
