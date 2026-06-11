import React from 'react'
import './api/bootstrapResources'
import { RightRail } from './components/RightRail'
import { PandaShellFrame } from './components/Shell'
import { navItems } from './data/navigation'
import { HomePage } from './pages/HomePage'
import { ModulePage } from './pages/ModulePage'
import { getPandaPageComponent } from './pageRegistry'
import { usePandaHashRoute } from './state/usePandaHashRoute'
import { usePandaHomeWorkbench } from './state/usePandaHomeWorkbench'
import { PandaWorkspaceProvider } from './state/PandaWorkspaceContext'
import './PandaAgentApp.css'

export default function PandaAgentApp() {
  const { activePage, navigateToPage } = usePandaHashRoute()
  const { home, homeSource, isLoading, error } = usePandaHomeWorkbench()
  const [taskText, setTaskText] = React.useState('')

  const selectedNav = navItems.find((item) => item.id === activePage) ?? navItems[0]
  const ActivePage = getPandaPageComponent(activePage)

  return (
    <div className="panda-agent-app">
      <PandaWorkspaceProvider>
        <PandaShellFrame
          activePage={activePage}
          pageLabel={selectedNav.label}
          isLoading={isLoading}
          error={error}
          onSelectPage={navigateToPage}
          rightRail={<RightRail home={home} isLoading={isLoading} error={error} />}
        >
          {activePage === 'home' ? (
            <HomePage
              taskText={taskText}
              onTaskTextChange={setTaskText}
              onNavigate={navigateToPage}
              home={home}
              homeSource={homeSource}
              isLoading={isLoading}
              error={error}
            />
          ) : ActivePage ? (
            <ActivePage />
          ) : (
            <ModulePage page={activePage} onNavigate={navigateToPage} />
          )}
        </PandaShellFrame>
      </PandaWorkspaceProvider>
    </div>
  )
}
