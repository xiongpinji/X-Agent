import { Database } from 'lucide-react'
import type { DataSource } from '../types'
import { CapabilityMetricCard, ResourceCardGrid } from './common'

export function DataSourceGrid({ dataSources }: { dataSources: readonly DataSource[] }) {
  return (
    <ResourceCardGrid
      items={dataSources}
      className="panda-tools-grid"
      renderItem={(source) => <DataSourceCard key={source.id} source={source} />}
    />
  )
}

export function DataSourceCard({ source }: { source: DataSource }) {
  return (
    <CapabilityMetricCard
      icon={<Database size={18} />}
      title={source.name}
      subtitle={source.source}
      tone={source.tone}
      metrics={[
        { label: '状态', value: source.status },
        { label: '记录', value: source.records },
        { label: '同步', value: source.syncState },
      ]}
    />
  )
}
