import { usePandaWorkspaceResource } from '../state/PandaWorkspaceContext'
import { ThreadListPanel, ThreadWorkPanel } from '../components/threadWorkspace'

export function ThreadsPage() {
  const threads = usePandaWorkspaceResource('threads')
  const activeThread = threads[0]

  return (
    <section className="panda-thread-grid">
      <ThreadListPanel threads={threads} />
      <ThreadWorkPanel threads={threads} activeThread={activeThread} />
    </section>
  )
}
