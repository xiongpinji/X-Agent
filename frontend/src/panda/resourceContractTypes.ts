import type { PandaResourceSnapshot } from './api/resourceSnapshotTypes'
import type { PandaPage } from './types'

export type PandaResourceKey = keyof PandaResourceSnapshot
export type PandaRuntimeField = 'status' | 'risk_level' | 'progress' | 'owner_agent' | 'updated_at' | 'evidence_refs'

export type PandaPageResourceContract = {
  page: PandaPage
  resourceKeys: readonly PandaResourceKey[]
  bffEndpoint: string
  readiness: 'mock-ready' | 'api-wired'
  runtimeFields: readonly PandaRuntimeField[]
  apiNeeds: readonly string[]
}
