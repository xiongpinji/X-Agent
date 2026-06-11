import { FolderGit2 } from 'lucide-react'
import type { ProjectItem } from '../types'
import { RuntimeMetaStrip, SectionHeader, WorkspacePanel, WorkspaceTable } from './common'

export function ProjectWorkspace({ projects }: { projects: readonly ProjectItem[] }) {
  return (
    <WorkspacePanel>
      <SectionHeader icon={<FolderGit2 className="text-rose-300" size={22} />} title="最近项目" />
      <ProjectTable projects={projects} />
    </WorkspacePanel>
  )
}

export function ProjectTable({ projects }: { projects: readonly ProjectItem[] }) {
  return (
    <WorkspaceTable columns={['名称', '类型', '运行态']}>
      {projects.map((project) => (
        <ProjectTableRow key={project.id} project={project} />
      ))}
    </WorkspaceTable>
  )
}

export function ProjectTableRow({ project }: { project: ProjectItem }) {
  return (
    <tr>
      <td className="font-medium text-slate-100">{project.name}</td>
      <td>{project.type}</td>
      <td>
        <RuntimeMetaStrip
          runtime={project.runtime}
          owner={project.ownerAgent}
          updatedAt={project.updatedAt}
          risk={project.risk}
        />
      </td>
    </tr>
  )
}
