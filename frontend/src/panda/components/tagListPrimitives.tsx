export type KeyValueItem = {
  label: string
  value: import('react').ReactNode
  valueClassName?: string
}

export function KeyValueList({ items }: { items: readonly KeyValueItem[] }) {
  return (
    <div className="space-y-3 text-sm">
      {items.map((item) => (
        <div key={item.label} className="flex items-center justify-between gap-3">
          <span className="text-slate-400">{item.label}</span>
          <span className={item.valueClassName}>{item.value}</span>
        </div>
      ))}
    </div>
  )
}

export function MiniTagList({ items, prefix = '' }: { items: readonly string[]; prefix?: string }) {
  if (items.length === 0) {
    return null
  }

  return (
    <div className="mt-3 flex flex-wrap gap-2">
      {items.map((item) => (
        <span key={`${prefix}${item}`} className="panda-mini-tag">{prefix}{item}</span>
      ))}
    </div>
  )
}
