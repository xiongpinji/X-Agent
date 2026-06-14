import { mockWorkbenchHome } from '../data/mockHome'
import type { PandaWorkbenchHome } from '../types'
import type { PandaWorkbenchHomeResult } from './workbenchClient'

export function buildPandaWorkbenchHomeApiResult(home: PandaWorkbenchHome): PandaWorkbenchHomeResult {
  return {
    home,
    source: 'api',
  }
}

export function normalizePandaWorkbenchHomeError(error: unknown): Error {
  return error instanceof Error ? error : new Error('无法加载工作台数据')
}

export function buildPandaWorkbenchHomeMockResult(error: unknown): PandaWorkbenchHomeResult {
  return {
    home: mockWorkbenchHome,
    source: 'mock',
    error: normalizePandaWorkbenchHomeError(error),
  }
}
