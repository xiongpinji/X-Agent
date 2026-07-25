import React, { useEffect, lazy, Suspense } from 'react'
import { BrowserRouter as Router, Routes, Route, Navigate } from 'react-router-dom'
import { useAppStore } from '@/store/appStore'
import { apiClient } from '@/services/api'
import { I18nProvider } from '@/i18n/context'
import Layout from '@/components/Layout'
import ErrorBoundary from '@/components/ErrorBoundary'
import clsx from 'clsx'

// Lazy load pages for code splitting
const Dashboard = lazy(() => import('@/pages/Dashboard'))
const ChatPage = lazy(() => import('@/pages/ChatPage'))
const TasksPage = lazy(() => import('@/pages/TasksPage'))
const ToolsPage = lazy(() => import('@/pages/ToolsPage'))
const MemoryPage = lazy(() => import('@/pages/MemoryPage'))
const LoginPage = lazy(() => import('@/pages/LoginPage'))
const WorkflowsPage = lazy(() => import('@/pages/WorkflowsPage'))
const AgentsPage = lazy(() => import('@/pages/AgentsPage'))
const SettingsPage = lazy(() => import('@/pages/SettingsPage'))
const WorkflowEditorPage = lazy(() => import('@/pages/WorkflowEditorPage'))
const GoalModePage = lazy(() => import('@/pages/GoalModePage'))
const CodeReviewPage = lazy(() => import('@/pages/CodeReviewPage'))
const EvolutionPage = lazy(() => import('@/pages/EvolutionPage'))
const AgentWorkspacePage = lazy(() => import('@/pages/AgentWorkspacePage'))

// Loading fallback component
const PageLoader = () => (
  <div className="flex items-center justify-center h-screen" role="status" aria-label="Loading">
    <div className="animate-spin rounded-full h-12 w-12 border-b-2 border-blue-500"></div>
  </div>
)

export const App: React.FC = () => {
  const { theme, setConnected, setError, isAuthenticated } = useAppStore()

  useEffect(() => {
    initializeApp()
  }, [])

  const initializeApp = async () => {
    try {
      await apiClient.healthCheck()
      setConnected(true)
    } catch (error) {
      console.error('Failed to reach backend health endpoint:', error)
      setConnected(false)
      setError(error instanceof Error ? error.message : 'Failed to initialize')
    }
  }

  return (
    <ErrorBoundary>
    <I18nProvider>
      <Router>
        <div className={clsx(
          'h-screen',
          theme === 'dark' ? 'dark bg-slate-950' : 'bg-white'
        )}>
          <Suspense fallback={<PageLoader />}>
            <Routes>
              <Route path="/login" element={<LoginPage />} />
              <Route path="/*" element={
                isAuthenticated ? (
                  <Layout>
                    <Suspense fallback={<PageLoader />}>
                      <Routes>
                        <Route path="/" element={<Dashboard />} />
                        <Route path="/chat" element={<ChatPage />} />
                        <Route path="/tasks" element={<TasksPage />} />
                        <Route path="/tools" element={<ToolsPage />} />
                        <Route path="/memory" element={<MemoryPage />} />
                        <Route path="/workflows" element={<WorkflowsPage />} />
                        <Route path="/workflows/:id/edit" element={<WorkflowEditorPage />} />
                        <Route path="/agents" element={<AgentsPage />} />
                        <Route path="/settings" element={<SettingsPage />} />
                        <Route path="/goals" element={<GoalModePage />} />
                        <Route path="/review" element={<CodeReviewPage />} />
                        <Route path="/evolution" element={<EvolutionPage />} />
                        <Route path="/agents/:id/workspace" element={<AgentWorkspacePage />} />
                        <Route path="*" element={<Navigate to="/" replace />} />
                      </Routes>
                    </Suspense>
                  </Layout>
                ) : (
                  <Navigate to="/login" replace />
                )
              } />
            </Routes>
          </Suspense>
        </div>
      </Router>
    </I18nProvider>
    </ErrorBoundary>
  )
}

export default App
