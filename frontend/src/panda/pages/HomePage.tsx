import type { PandaWorkbenchDataSource } from '../api/workbenchClient'
import type { PandaPage, PandaWorkbenchHome } from '../types'
import { ModuleCardGrid, PlatformSnapshot, PromptActionRow, QuickActionGrid, RecentProjects, TaskComposer } from '../components/homeSections'

export function HomePage({
  taskText,
  onTaskTextChange,
  onNavigate,
  home,
  homeSource,
  isLoading,
  error,
}: {
  taskText: string
  onTaskTextChange: (value: string) => void
  onNavigate: (page: PandaPage) => void
  home: PandaWorkbenchHome | null
  homeSource: PandaWorkbenchDataSource
  isLoading: boolean
  error: string | null
}) {
  return (
    <div className="panda-home-grid">
      <section className="panda-hero">
        <h1 className="text-[30px] font-semibold leading-tight">下午好，Panda Agent</h1>
        <p className="mt-2 text-[15px] text-slate-400">今天想用智能体帮你完成什么任务？</p>
        <TaskComposer value={taskText} onChange={onTaskTextChange} />
      </section>

      <PromptActionRow />

      <QuickActionGrid onNavigate={onNavigate} />

      <section className="panda-data-grid">
        <RecentProjects />
        <PlatformSnapshot home={home} source={homeSource} isLoading={isLoading} error={error} />
      </section>

      <ModuleCardGrid onNavigate={onNavigate} />
    </div>
  )
}
