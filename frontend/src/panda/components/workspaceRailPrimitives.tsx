import React from 'react'

export function RailCard({ title, action, children }: { title: string; action?: string; children: React.ReactNode }) {
  return (
    <section className="panda-card p-4" style={{ marginBottom: 12 }}>
      <div className="mb-4 flex items-center justify-between">
        <h2 className="font-semibold">{title}</h2>
        {action ? <button className="text-sm text-slate-400" type="button" aria-label={`${title}：${action}`}>{action}</button> : null}
      </div>
      {children}
    </section>
  )
}
