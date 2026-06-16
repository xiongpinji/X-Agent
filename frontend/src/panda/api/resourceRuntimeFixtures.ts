import type { ApiRuntimeMetadata } from './runtimeMapping'

export function runtimeFixture({
  status,
  riskLevel,
  progress,
  ownerAgent,
  updatedAt,
  evidenceRef,
}: {
  status?: string
  riskLevel: NonNullable<ApiRuntimeMetadata['risk_level']>
  progress: number
  ownerAgent: string
  updatedAt: string
  evidenceRef: string
}): ApiRuntimeMetadata {
  return {
    ...(status ? { status } : {}),
    risk_level: riskLevel,
    progress,
    owner_agent: ownerAgent,
    updated_at: updatedAt,
    evidence_refs: [evidenceRef],
  }
}
