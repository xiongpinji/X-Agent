import { FolderGit2 } from 'lucide-react'
import type { ProjectItem } from '../types'
import { RuntimeMetaStrip, SectionHeader, WorkspacePanel, WorkspaceTable } from './common'
import { buildProjectTableRowViewModel, projectTableColumns, projectWorkspaceHeader } from './projectWorkspaceViewModel'

export function ProjectWorkspace({ projects }: { projects: readonly ProjectItem[] }) {
  return (
    <WorkspacePanel>
      <SectionHeader icon={<FolderGit2 className="text-rose-300" size={22} />} title={projectWorkspaceHeader.title} />
      <ProjectTable projects={projects} />
    </WorkspacePanel>
  )
}

export function ProjectTable({ projects }: { projects: readonly ProjectItem[] }) {
  return (
    <WorkspaceTable columns={projectTableColumns}>
      {projects.map((project) => (
        <ProjectTableRow key={project.id} project={project} />
      ))}
    </WorkspaceTable>
  )
}

export function ProjectTableRow({ project }: { project: ProjectItem }) {
  const row = buildProjectTableRowViewModel(project)

  return (
    <tr>
      <td className="font-medium text-slate-100">{row.name}</td>
      <td>{row.type}</td>
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
