import type { LucideIcon } from 'lucide-react'
import { Play } from 'lucide-react'
import type { CapabilityRow, PandaPage } from '../types'
import { ModuleSummaryCard, NavigationCardGrid } from './common'

export { ModuleDeliverySurface } from './moduleDeliverySurface'

export function ModuleFallbackHero({
  title,
  icon: Icon,
  onNavigate,
}: {
  title: string
  icon: LucideIcon
  onNavigate: (page: PandaPage) => void
}) {
  return (
    <section className="panda-card p-5">
      <div className="flex items-start justify-between gap-5">
        <div>
          <div className="flex items-center gap-3">
            <Icon className="text-rose-300" size={24} />
            <h1 className="text-2xl font-semibold">{title}</h1>
          </div>
          <p className="mt-3 max-w-3xl text-sm leading-6 text-slate-400">
            该模块已经纳入完整产品信息架构。第一版会先接入真实聚合数据、空状态、错误状态和执行入口，再逐步替换为对应的细分页面。
          </p>
        </div>
        <button className="panda-command-button" type="button" onClick={() => onNavigate('threads')}>
          <Play size={16} aria-hidden="true" />
          进入执行线程
        </button>
      </div>
    </section>
  )
}

export function ModuleCapabilityGrid({ capabilityRows }: { capabilityRows: readonly CapabilityRow[] }) {
  return (
    <NavigationCardGrid
      items={capabilityRows}
      className="panda-module-grid"
      renderItem={(row) => (
        <div key={row.label} className="panda-card panda-module-card">
          <ModuleSummaryCard title={row.label} summary={row.value} />
        </div>
      )}
    />
  )
}
