import { StandardModulePageShell } from '../components/common'
import { DataSourceGrid } from '../components/dataCenter'
import { useDataPageResources } from '../state/useModulePageResources'

export function DataPage() {
  const resources = useDataPageResources()

  return (
    <StandardModulePageShell page="data" count={resources.count}>
      <DataSourceGrid dataSources={resources.dataSources} />
    </StandardModulePageShell>
  )
}
