import type { PandaWorkspaceStatus } from '../state/workspaceTypes'

export type PandaResourceStateKind = 'loading' | 'error' | 'empty' | 'ready'

export type PandaResourceStateViewModel =
  | { readonly kind: 'loading' }
  | { readonly kind: 'error'; readonly errorDescription: string }
  | { readonly kind: 'empty' }
  | { readonly kind: 'ready' }

export function buildPandaResourceStateViewModel({
  count,
  status,
  error,
}: {
  readonly count: number
  readonly status: PandaWorkspaceStatus
  readonly error: Error | null
}): PandaResourceStateViewModel {
  if (status === 'loading' && count === 0) {
    return { kind: 'loading' }
  }

  if (status === 'error' && count === 0) {
    return {
      kind: 'error',
      errorDescription: error?.message ?? '当前资源切片加载失败，等待后端接口或本地回退数据恢复。',
    }
  }

  if (count === 0) {
    return { kind: 'empty' }
  }

  return { kind: 'ready' }
}
