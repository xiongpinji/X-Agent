import { getPandaResourcesBffConfig } from '../api/resourcesBffConfig'
import { KeyValueList, PandaErrorState, RailCard } from './common'

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
  const rows = [
    { label: '页面资源', value: source === 'mock' ? '本地快照' : '后端 API' },
    { label: 'Resources BFF', value: resourcesBffConfig.enabled ? '已启用' : '关闭' },
    { label: 'BFF Endpoint', value: resourcesBffConfig.endpoint, valueClassName: 'truncate text-right' },
    { label: '状态', value: status === 'loading' ? '刷新中' : status === 'error' ? '异常' : '可用' },
    { label: '刷新时间', value: refreshedAt },
  ] as const

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
