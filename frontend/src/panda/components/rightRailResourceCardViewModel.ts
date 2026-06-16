import { getPandaResourcesBffConfig } from '../api/resourcesBffConfig'
import type { KeyValueItem } from './common'

export type RightRailResourceSnapshotInput = {
  readonly source: 'mock' | 'api'
  readonly status: 'loading' | 'ready' | 'error'
  readonly refreshedAt: string
  readonly resourcesBffConfig: ReturnType<typeof getPandaResourcesBffConfig>
}

function formatResourceSource(source: RightRailResourceSnapshotInput['source']): string {
  return source === 'mock' ? '本地快照' : '后端 API'
}

function formatResourceStatus(status: RightRailResourceSnapshotInput['status']): string {
  return status === 'loading' ? '刷新中' : status === 'error' ? '异常' : '可用'
}

export function buildRightRailResourceSnapshotRows({
  source,
  status,
  refreshedAt,
  resourcesBffConfig,
}: RightRailResourceSnapshotInput): readonly KeyValueItem[] {
  return [
    { label: '页面资源', value: formatResourceSource(source) },
    { label: 'Resources BFF', value: resourcesBffConfig.enabled ? '已启用' : '关闭' },
    { label: 'BFF Endpoint', value: resourcesBffConfig.endpoint, valueClassName: 'truncate text-right' },
    { label: '状态', value: formatResourceStatus(status) },
    { label: '刷新时间', value: refreshedAt },
  ]
}
