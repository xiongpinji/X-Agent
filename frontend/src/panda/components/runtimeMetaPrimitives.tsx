import { toneLabel } from '../data/navigation'
import type { RuntimeMetadata, StatusTone } from '../types'
import { MiniTagList } from './tagListPrimitives'

export function RuntimeMetaStrip({
  runtime,
  owner,
  updatedAt,
  risk,
}: {
  runtime?: RuntimeMetadata
  owner?: string
  updatedAt?: string
  risk?: StatusTone
}) {
  const ownerLabel = runtime?.ownerAgent ?? owner
  const updatedLabel = runtime?.updatedAt ?? updatedAt
  const riskTone = runtime?.riskLevel ?? risk
  const items = [
    ownerLabel ? `owner_agent ${ownerLabel}` : null,
    updatedLabel ? `updated_at ${updatedLabel}` : null,
    riskTone ? `risk_level ${toneLabel[riskTone]}` : null,
    runtime?.evidenceRefs.length ? `evidence_refs ${runtime.evidenceRefs.length}` : null,
  ].filter((item): item is string => Boolean(item))

  return <MiniTagList items={items} />
}
