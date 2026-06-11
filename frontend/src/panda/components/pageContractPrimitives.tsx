import { pandaPageResourceContracts } from '../pageResourceContracts'
import { usePandaWorkspaceLifecycle } from '../state/PandaWorkspaceContext'
import type { PandaPage } from '../types'

export function PageContractStrip({ page }: { page: PandaPage }) {
  const { status, source, error, refreshedAt } = usePandaWorkspaceLifecycle()
  const contract = pandaPageResourceContracts[page]
  const readinessLabel = contract.readiness === 'api-wired' ? 'API 已接入' : 'Mock 待对齐'
  const sourceLabel = source === 'api' ? '实时 API' : '本地演示数据'

  return (
    <section className="panda-contract-strip" aria-label={`${page} 页面资源契约状态`}>
      <div>
        <span>资源</span>
        <strong>{contract.resourceKeys.join(' / ')}</strong>
      </div>
      <div>
        <span>BFF</span>
        <strong>{contract.bffEndpoint}</strong>
      </div>
      <div>
        <span>状态</span>
        <strong>{readinessLabel} · {sourceLabel}</strong>
      </div>
      <div>
        <span>运行态字段</span>
        <strong className="panda-contract-fields">{contract.runtimeFields.join(' / ')}</strong>
      </div>
      <div>
        <span>刷新</span>
        <strong>{status === 'loading' ? '同步中' : refreshedAt}</strong>
      </div>
      {error ? <p>{error.message}</p> : null}
    </section>
  )
}
