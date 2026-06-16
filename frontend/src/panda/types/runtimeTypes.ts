export type StatusTone = 'success' | 'warning' | 'danger' | 'neutral'

export type RuntimeMetadata = {
  status: string
  riskLevel: StatusTone
  progress: number
  ownerAgent: string
  updatedAt: string
  evidenceRefs: readonly string[]
}

export type WithRuntimeMetadata = {
  runtime?: RuntimeMetadata
}
