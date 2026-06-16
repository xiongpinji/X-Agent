import type { PandaWorkbenchHomeResult } from '../api/workbenchClient'
import type { PandaWorkbenchHome } from '../types'

export type PandaHomeWorkbenchViewModel = {
  readonly home: PandaWorkbenchHome
  readonly homeSource: PandaWorkbenchHomeResult['source']
  readonly error: string | null
}

export function buildPandaHomeWorkbenchViewModel(result: PandaWorkbenchHomeResult): PandaHomeWorkbenchViewModel {
  return {
    home: result.home,
    homeSource: result.source,
    error: result.source === 'mock' ? result.error?.message ?? '本地演示数据已接管' : null,
  }
}
