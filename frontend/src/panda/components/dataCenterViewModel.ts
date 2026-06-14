import type { DataSource } from '../types'
import type { MetricStripItem } from './common'

export type DataSourceCardViewModel = {
  readonly title: string
  readonly subtitle: string
  readonly metrics: readonly MetricStripItem[]
}

export function buildDataSourceCardViewModel(source: DataSource): DataSourceCardViewModel {
  return {
    title: source.name,
    subtitle: source.source,
    metrics: [
      { label: '状态', value: source.status },
      { label: '记录', value: source.records },
      { label: '同步', value: source.syncState },
    ],
  }
}
