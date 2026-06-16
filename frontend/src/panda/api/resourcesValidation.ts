import type { ApiPandaResourceSnapshot } from './adapters'
import { pandaApiResourceKeys, pandaApiResourceKeySet, type PandaApiResourceKey } from './resourceKeys'

export class PandaResourceValidationError extends Error {
  constructor(message: string) {
    super(message)
    this.name = 'PandaResourceValidationError'
  }
}

function isRecord(value: unknown): value is Record<string, unknown> {
  return typeof value === 'object' && value !== null && !Array.isArray(value)
}

export function validatePandaResourceSnapshot(snapshot: unknown): ApiPandaResourceSnapshot {
  if (!isRecord(snapshot)) {
    throw new PandaResourceValidationError('Panda resources BFF must return an object snapshot.')
  }

  for (const key of Object.keys(snapshot)) {
    if (!pandaApiResourceKeySet.has(key)) {
      throw new PandaResourceValidationError(`Panda resources BFF field "${key}" is not a known resource slice.`)
    }
  }

  for (const key of pandaApiResourceKeys) {
    const value = snapshot[key]
    if (value !== undefined && !Array.isArray(value)) {
      throw new PandaResourceValidationError(`Panda resources BFF field "${key}" must be an array when provided.`)
    }
    if (Array.isArray(value)) {
      const invalidIndex = value.findIndex((item) => !isRecord(item))
      if (invalidIndex >= 0) {
        throw new PandaResourceValidationError(`Panda resources BFF field "${key}" item ${invalidIndex} must be an object.`)
      }
    }
  }

  return snapshot as Partial<Record<PandaApiResourceKey, unknown[]>> as ApiPandaResourceSnapshot
}

export const pandaResourceValidationKeys = pandaApiResourceKeys
