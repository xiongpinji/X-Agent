import type { StatusTone } from '../types'

export { KeyValueList, MiniTagList } from './tagListPrimitives'
export type { KeyValueItem } from './tagListPrimitives'
export { RuntimeMetaStrip } from './runtimeMetaPrimitives'

export type MetricStripItem = {
  label: string
  value: import('react').ReactNode
}

export type SummaryMetricItem = {
  label: string
  value: import('react').ReactNode
  tone?: StatusTone
}

export function MetricStrip({ items }: { items: readonly MetricStripItem[] }) {
  return (
    <div className="mt-5 grid grid-cols-3 gap-3 text-sm">
      {items.map((item) => (
        <div key={item.label}>
          <span>{item.label}</span>
          <strong>{item.value}</strong>
        </div>
      ))}
    </div>
  )
}

export function SummaryMetricList({ items }: { items: readonly SummaryMetricItem[] }) {
  return (
    <div className="mt-5 space-y-4 text-sm">
      {items.map((item) => (
        <div key={item.label} className="flex justify-between">
          <span className="text-slate-400">{item.label}</span>
          <strong className={item.tone === 'danger' ? 'text-rose-300' : undefined}>{item.value}</strong>
        </div>
      ))}
    </div>
  )
}
