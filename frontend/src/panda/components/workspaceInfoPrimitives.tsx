import React from 'react'

export type InfoPairItem = {
  label: string
  value: React.ReactNode
}

export function InfoPairGrid({ items }: { items: readonly InfoPairItem[] }) {
  return (
    <div className="mt-4 grid grid-cols-2 gap-3 text-sm">
      {items.map((item) => (
        <div key={item.label}>
          <span className="text-slate-500">{item.label}</span>
          <strong className="block text-slate-100">{item.value}</strong>
        </div>
      ))}
    </div>
  )
}

export function InsetInfoBlock({ children, dense = false }: { children: React.ReactNode; dense?: boolean }) {
  return (
    <div className={`rounded-lg bg-white/[0.04] ${dense ? 'p-4 text-sm text-slate-300' : 'p-4'}`}>
      {children}
    </div>
  )
}
