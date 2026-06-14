import type { PandaResourceSource } from '../api/resourceSnapshotTypes'
import type { PandaWorkspaceStatus } from '../state/workspaceTypes'
import type { PandaPage } from '../types'
import type { PandaPageResourceContract } from '../resourceContractTypes'

export type PageContractViewModel = {
  readonly ariaLabel: string
  readonly resourcesLabel: string
  readonly endpointLabel: string
  readonly statusLabel: string
  readonly runtimeFieldsLabel: string
  readonly refreshLabel: string
  readonly errorMessage: string | null
}

export function buildPageContractViewModel({
  page,
  contract,
  status,
  source,
  error,
  refreshedAt,
}: {
  readonly page: PandaPage
  readonly contract: PandaPageResourceContract
  readonly status: PandaWorkspaceStatus
  readonly source: PandaResourceSource
  readonly error: Error | null
  readonly refreshedAt: string
}): PageContractViewModel {
  const readinessLabel = contract.readiness === 'api-wired' ? 'API 已接入' : 'Mock 待对齐'
  const sourceLabel = source === 'api' ? '实时 API' : '本地演示数据'

  return {
    ariaLabel: `${page} 页面资源契约状态`,
    resourcesLabel: contract.resourceKeys.join(' / '),
    endpointLabel: contract.bffEndpoint,
    statusLabel: `${readinessLabel} · ${sourceLabel}`,
    runtimeFieldsLabel: contract.runtimeFields.join(' / '),
    refreshLabel: status === 'loading' ? '同步中' : refreshedAt,
    errorMessage: error?.message ?? null,
  }
}
