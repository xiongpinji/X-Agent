import type { PandaPage } from '../types'
import { quickActions } from '../data/homeActionContent'
import { moduleCards } from '../data/moduleFallbackContent'
import { ModuleSummaryCard, NavigationCardGrid } from './common'

export function QuickActionGrid({ onNavigate }: { onNavigate: (page: PandaPage) => void }) {
  return (
    <NavigationCardGrid
      items={quickActions}
      className="panda-quick-grid"
      renderItem={(item) => {
        const Icon = item.icon
        return (
          <button key={item.title} className="panda-card panda-quick-card" type="button" onClick={() => onNavigate(item.targetPage)}>
            <div>
              <div className="flex items-center justify-between">
                <h3 className="font-semibold">{item.title}</h3>
                <Icon className="text-slate-500" size={36} />
              </div>
              <p className="mt-2 text-sm leading-6 text-slate-400">{item.description}</p>
            </div>
            <span className="text-sm text-slate-200">+ {item.action}</span>
          </button>
        )
      }}
    />
  )
}

export function ModuleCardGrid({ onNavigate }: { onNavigate: (page: PandaPage) => void }) {
  return (
    <NavigationCardGrid
      items={moduleCards}
      className="panda-module-grid"
      renderItem={(module) => {
        const Icon = module.icon
        return (
          <button key={module.id} className="panda-card panda-module-card text-left" type="button" onClick={() => onNavigate(module.id)}>
            <ModuleSummaryCard
              icon={<Icon className="text-rose-300" size={24} />}
              title={module.title}
              summary={module.summary}
              metric={module.metric}
            />
          </button>
        )
      }}
    />
  )
}
