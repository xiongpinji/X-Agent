import { StandardModulePageShell } from '../components/common'
import { ProjectWorkspace } from '../components/projectWorkspace'
import { useProjectsPageResources } from '../state/useModulePageResources'

export function ProjectsPage() {
  const resources = useProjectsPageResources()

  return (
    <StandardModulePageShell page="projects" count={resources.count}>
      <ProjectWorkspace projects={resources.projects} />
    </StandardModulePageShell>
  )
}
