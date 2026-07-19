import React, { useEffect, lazy, Suspense } from 'react'
import { BrowserRouter as Router, Routes, Route, Navigate } from 'react-router-dom'
import { useAppStore } from '@/store/appStore'
import { wsService } from '@/services/websocket'
import { apiClient } from '@/services/api'
import Layout from '@/components/Layout'
import clsx from 'clsx'

// Lazy load pages for code splitting
const Dashboard = lazy(() => import('@/pages/Dashboard'))
const ChatPage = lazy(() => import('@/pages/ChatPage'))
const TasksPage = lazy(() => import('@/pages/TasksPage'))
const ToolsPage = lazy(() => import('@/pages/ToolsPage'))
const MemoryPage = lazy(() => import('@/pages/MemoryPage'))

// Loading fallback component
const PageLoader = () => (
  <div className="flex items-center justify-center h-screen">
    <div className="animate-spin rounded-full h-12 w-12 border-b-2 border-blue-500"></div>
  </div>
)

export const App: React.FC = () => {
  const { theme, setConnected, setError } = useAppStore()

  useEffect(() => {
    initializeApp()
  }, [])

  const initializeApp = async () => {
    try {
      // Check health
      await apiClient.healthCheck()

      // Connect WebSocket
      await wsService.connect()
      setConnected(true)

      // Subscribe to events with memoization
      wsService.subscribe('task:update', (data) => {
        console.log('Task update:', data)
      })

      wsService.subscribe('agent:status', (data) => {
        console.log('Agent status:', data)
      })
    } catch (error) {
      console.error('Failed to initialize app:', error)
      setError(error instanceof Error ? error.message : 'Failed to initialize')
    }
  }

  return (
    <Router>
      <div className={clsx(
        'h-screen',
        theme === 'dark' ? 'dark bg-slate-950' : 'bg-white'
      )}>
        <Layout>
          <Suspense fallback={<PageLoader />}>
            <Routes>
              <Route path="/" element={<Dashboard />} />
              <Route path="/chat" element={<ChatPage />} />
              <Route path="/tasks" element={<TasksPage />} />
              <Route path="/tools" element={<ToolsPage />} />
              <Route path="/memory" element={<MemoryPage />} />
              <Route path="*" element={<Navigate to="/" replace />} />
            </Routes>
          </Suspense>
        </Layout>
      </div>
    </Router>
  )
}

export default App
