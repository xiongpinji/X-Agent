import { apiClient } from '@/services/api'
import { mockWorkbenchHome } from '../data/mockHome'
import type { PandaWorkbenchHome } from '../types'
import { mapWorkbenchHome } from './adapters'

export type PandaWorkbenchDataSource = 'api' | 'mock'

export type PandaWorkbenchHomeResult = {
  home: PandaWorkbenchHome
  source: PandaWorkbenchDataSource
  error?: Error
}

export async function loadPandaWorkbenchHome(): Promise<PandaWorkbenchHomeResult> {
  try {
    const response = await apiClient.getWorkbenchHome()
    return {
      home: mapWorkbenchHome(response),
      source: 'api',
    }
  } catch (error) {
    return {
      home: mockWorkbenchHome,
      source: 'mock',
      error: error instanceof Error ? error : new Error('无法加载工作台数据'),
    }
  }
}
