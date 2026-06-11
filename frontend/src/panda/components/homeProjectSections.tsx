import { usePandaWorkspaceResource } from '../state/PandaWorkspaceContext'
import { PandaResourceState, RuntimeMetaStrip, WorkspaceTable } from './common'

export function RecentProjects() {
  const projects = usePandaWorkspaceResource('projects')

  return (
    <section className="panda-card p-3">
      <div className="flex items-center justify-between px-1 pb-2">
        <h2 className="font-semibold">最近项目</h2>
        <button className="text-sm text-slate-400" type="button">查看全部 →</button>
      </div>
      <PandaResourceState
        count={projects.length}
        emptyTitle="暂无最近项目"
        emptyDescription="后续接入项目 BFF 后，这里会展示工作区、智能体应用和工作流的最近更新。"
        loadingTitle="正在同步最近项目"
        loadingDescription="正在读取项目、智能体应用和工作流的最近更新。"
      >
        <WorkspaceTable columns={['名称', '类型', '运行态']}>
          {projects.map((project) => (
            <tr key={project.id}>
              <td className="text-sm text-slate-100">{project.name}</td>
              <td className="text-sm text-slate-400">{project.type}</td>
              <td>
                <RuntimeMetaStrip
                  runtime={project.runtime}
                  owner={project.ownerAgent}
                  updatedAt={project.updatedAt}
                  risk={project.risk}
                />
              </td>
            </tr>
          ))}
        </WorkspaceTable>
      </PandaResourceState>
    </section>
  )
}
