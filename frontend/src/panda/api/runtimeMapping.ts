import type { RuntimeMetadata, StatusTone } from '../types'

export type ApiTone = StatusTone | string | null | undefined

export type ApiRuntimeMetadata = {
  status?: string
  risk_level?: ApiTone
  risk?: ApiTone
  progress?: number
  owner_agent?: string
  owner?: string
  updated_at?: string
  evidence_refs?: readonly string[]
}

export function toStatusTone(tone: ApiTone): StatusTone {
  return tone === 'success' || tone === 'warning' || tone === 'danger' || tone === 'neutral' ? tone : 'neutral'
}

export function clampProgress(progress: number | null | undefined): number {
  if (typeof progress !== 'number' || Number.isNaN(progress)) {
    return 0
  }
  return Math.min(100, Math.max(0, Math.round(progress)))
}

export function stringValue(value: string | number | null | undefined, fallback: string): string {
  if (value === null || value === undefined || value === '') {
    return fallback
  }
  return String(value)
}

export function mapRuntimeMetadata(item: ApiRuntimeMetadata = {}): RuntimeMetadata {
  return {
    status: stringValue(item.status, '未知'),
    riskLevel: toStatusTone(item.risk_level ?? item.risk),
    progress: clampProgress(item.progress),
    ownerAgent: stringValue(item.owner_agent ?? item.owner, '未分配'),
    updatedAt: stringValue(item.updated_at, '未知'),
    evidenceRefs: Array.isArray(item.evidence_refs) ? [...item.evidence_refs] : [],
  }
}
