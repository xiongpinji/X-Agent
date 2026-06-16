import { apiClient } from '@/services/api'
import type { PandaWorkbenchHome } from '../types'
import { mapWorkbenchHome } from './adapters'
import { buildPandaWorkbenchHomeApiResult, buildPandaWorkbenchHomeMockResult } from './workbenchHomeLoadResult'

export type PandaWorkbenchDataSource = 'api' | 'mock'

export type PandaWorkbenchHomeResult = {
  home: PandaWorkbenchHome
  source: PandaWorkbenchDataSource
  error?: Error
}

export async function loadPandaWorkbenchHome(): Promise<PandaWorkbenchHomeResult> {
  try {
    const response = await apiClient.getWorkbenchHome()
    return buildPandaWorkbenchHomeApiResult(mapWorkbenchHome(response))
  } catch (error) {
    return buildPandaWorkbenchHomeMockResult(error)
  }
}
