import { usePandaWorkspaceResource } from '../state/PandaWorkspaceContext'
import type { ProjectItem } from '../types'
import { PandaResourceState, RuntimeMetaStrip, WorkspaceTable } from './common'
import {
  buildRecentProjectTableRowViewModel,
  recentProjectsHeader,
  recentProjectsResourceState,
  recentProjectsTableColumns,
} from './homeProjectSectionsViewModel'

export function RecentProjects() {
  const projects = usePandaWorkspaceResource('projects')

  return (
    <section className="panda-card p-3">
      <div className="flex items-center justify-between px-1 pb-2">
        <h2 className="font-semibold">{recentProjectsHeader.title}</h2>
        <button className="text-sm text-slate-400" type="button">{recentProjectsHeader.actionLabel}</button>
      </div>
      <PandaResourceState
        count={projects.length}
        emptyTitle={recentProjectsResourceState.emptyTitle}
        emptyDescription={recentProjectsResourceState.emptyDescription}
        loadingTitle={recentProjectsResourceState.loadingTitle}
        loadingDescription={recentProjectsResourceState.loadingDescription}
      >
        <WorkspaceTable columns={recentProjectsTableColumns}>
          {projects.map((project) => (
            <RecentProjectRow key={project.id} project={project} />
          ))}
        </WorkspaceTable>
      </PandaResourceState>
    </section>
  )
}

export function RecentProjectRow({ project }: { project: ProjectItem }) {
  const row = buildRecentProjectTableRowViewModel(project)

  return (
    <tr>
      <td className="text-sm text-slate-100">{row.name}</td>
      <td className="text-sm text-slate-400">{row.type}</td>
      <td>
        <RuntimeMetaStrip
          runtime={row.runtime}
          owner={row.runtimeOwner}
          updatedAt={row.runtimeUpdatedAt}
          risk={row.runtimeRisk}
        />
      </td>
    </tr>
  )
}
