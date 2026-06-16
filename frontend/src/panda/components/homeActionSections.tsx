import { promptActions } from '../data/homeActionContent'

export { TaskComposer } from './homeTaskComposer'
export type { TaskComposerProps } from './homeTaskComposer'
export { ModuleCardGrid, QuickActionGrid } from './homeNavigationSections'

export function PromptActionRow() {
  return (
    <section className="panda-pill-row">
      {promptActions.map(({ label, icon: IconComponent }) => (
        <button key={label} className="panda-pill" type="button">
          <IconComponent size={16} />
          {label}
        </button>
      ))}
    </section>
  )
}
