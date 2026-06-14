import { getPandaResourceSnapshot } from './resourceFallbackSnapshot'
import type { PandaResourceLoadResult, PandaResourceSnapshot } from './resourceSnapshotTypes'

export function buildPandaApiResourceLoadResult(resources: PandaResourceSnapshot): PandaResourceLoadResult {
  return {
    resources,
    source: 'api',
  }
}

export function buildPandaMockResourceLoadResult(): PandaResourceLoadResult {
  return {
    resources: getPandaResourceSnapshot(),
    source: 'mock',
  }
}

export function normalizePandaResourceLoadError(error: unknown): Error {
  return error instanceof Error ? error : new Error('无法加载 Panda 工作台资源')
}

export function buildPandaMockResourceErrorResult(error: unknown): PandaResourceLoadResult {
  return {
    resources: getPandaResourceSnapshot(),
    source: 'mock',
    error: normalizePandaResourceLoadError(error),
  }
}
