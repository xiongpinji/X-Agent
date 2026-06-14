import { pandaPageResourceContracts } from '../pageResourceContracts'
import { usePandaWorkspaceLifecycle } from '../state/PandaWorkspaceContext'
import type { PandaPage } from '../types'
import { buildPageContractViewModel } from './pageContractViewModel'

export function PageContractStrip({ page }: { page: PandaPage }) {
  const { status, source, error, refreshedAt } = usePandaWorkspaceLifecycle()
  const contract = pandaPageResourceContracts[page]
  const contractView = buildPageContractViewModel({ page, contract, status, source, error, refreshedAt })

  return (
    <section className="panda-contract-strip" aria-label={contractView.ariaLabel}>
      <div>
        <span>资源</span>
        <strong>{contractView.resourcesLabel}</strong>
      </div>
      <div>
        <span>BFF</span>
        <strong>{contractView.endpointLabel}</strong>
      </div>
      <div>
        <span>状态</span>
        <strong>{contractView.statusLabel}</strong>
      </div>
      <div>
        <span>运行态字段</span>
        <strong className="panda-contract-fields">{contractView.runtimeFieldsLabel}</strong>
      </div>
      <div>
        <span>刷新</span>
        <strong>{contractView.refreshLabel}</strong>
      </div>
      {contractView.errorMessage ? <p>{contractView.errorMessage}</p> : null}
    </section>
  )
}
