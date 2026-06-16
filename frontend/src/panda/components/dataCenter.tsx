import { Database } from 'lucide-react'
import type { DataSource } from '../types'
import { CapabilityMetricCard, ResourceCardGrid } from './common'
import { buildDataSourceCardViewModel } from './dataCenterViewModel'

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
  const card = buildDataSourceCardViewModel(source)

  return (
    <CapabilityMetricCard
      icon={<Database size={18} />}
      title={card.title}
      subtitle={card.subtitle}
      tone={source.tone}
      metrics={card.metrics}
    />
  )
}
