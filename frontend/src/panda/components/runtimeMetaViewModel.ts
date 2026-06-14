import { toneLabel } from '../data/navigation'
import type { RuntimeMetadata, StatusTone } from '../types'

export type RuntimeMetaStripInput = {
  readonly runtime?: RuntimeMetadata
  readonly owner?: string
  readonly updatedAt?: string
  readonly risk?: StatusTone
}

export function buildRuntimeMetaStripItems({
  runtime,
  owner,
  updatedAt,
  risk,
}: RuntimeMetaStripInput): readonly string[] {
  const ownerLabel = runtime?.ownerAgent ?? owner
  const updatedLabel = runtime?.updatedAt ?? updatedAt
  const riskTone = runtime?.riskLevel ?? risk

  return [
    ownerLabel ? `owner_agent ${ownerLabel}` : null,
    updatedLabel ? `updated_at ${updatedLabel}` : null,
    riskTone ? `risk_level ${toneLabel[riskTone]}` : null,
    runtime?.evidenceRefs.length ? `evidence_refs ${runtime.evidenceRefs.length}` : null,
  ].filter((item): item is string => Boolean(item))
}
