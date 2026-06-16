import React from 'react'
import { toneLabel } from '../data/navigation'
import type { RuntimeMetadata, StatusTone } from '../types'
import { RuntimeMetaStrip, StatusDot } from './runtimePrimitives'

export function ActionPanel({ title, items }: { title: string; items: readonly string[] }) {
  return (
    <div className="panda-card p-4">
      <h3 className="font-semibold">{title}</h3>
      <div className="mt-3 grid gap-2">
        {items.map((item) => (
          <PanelActionButton key={item} label={item} group={title} />
        ))}
      </div>
    </div>
  )
}

export function PanelActionButton({ label, group }: { label: string; group: string }) {
  return (
    <button
      className="rounded-lg bg-white/[0.04] px-3 py-2 text-left text-sm text-slate-300"
      type="button"
      aria-label={`${group}：${label}`}
    >
      {label}
    </button>
  )
}

export function ManagementRow({
  tone,
  title,
  description,
  runtime,
  children,
}: {
  tone: StatusTone
  title: string
  description: string
  runtime?: RuntimeMetadata
  children: React.ReactNode
}) {
  return (
    <article className="panda-management-row">
      <div className="min-w-0">
        <div className="flex items-center gap-2">
          <StatusDot tone={tone} label={`${title} 风险等级：${toneLabel[tone]}`} />
          <h3>{title}</h3>
        </div>
        <p>{description}</p>
        <RuntimeMetaStrip runtime={runtime} risk={tone} />
      </div>
      {children}
    </article>
  )
}
