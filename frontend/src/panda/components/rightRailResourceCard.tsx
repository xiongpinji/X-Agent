import { getPandaResourcesBffConfig } from '../api/resourcesBffConfig'
import { KeyValueList, PandaErrorState, RailCard } from './common'
import { buildRightRailResourceSnapshotRows } from './rightRailResourceCardViewModel'

export type ResourceSnapshotCardProps = {
  source: 'mock' | 'api'
  status: 'loading' | 'ready' | 'error'
  refreshedAt: string
  resourceError: Error | null
  resourcesBffConfig: ReturnType<typeof getPandaResourcesBffConfig>
  onRefresh: () => Promise<void>
}

export function ResourceSnapshotCard({
  source,
  status,
  refreshedAt,
  resourceError,
  resourcesBffConfig,
  onRefresh,
}: ResourceSnapshotCardProps) {
  const rows = buildRightRailResourceSnapshotRows({ source, status, refreshedAt, resourcesBffConfig })

  return (
    <RailCard title="资源快照">
      <div className="space-y-3 text-sm">
        <KeyValueList items={rows} />
        {resourceError ? <PandaErrorState description={resourceError.message} /> : null}
        <button className="panda-command-button w-full" type="button" aria-label="重新同步 Panda 资源快照" onClick={() => { void onRefresh() }}>刷新快照</button>
      </div>
    </RailCard>
  )
}
