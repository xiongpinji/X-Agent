import React, { useEffect, useState } from 'react'
import { useParams } from 'react-router-dom'
import { apiClient } from '@/services/api'
import { useAppStore } from '@/store/appStore'
import { useI18n } from '@/i18n/context'
import clsx from 'clsx'

interface AgentDetail {
  id: string
  name: string
  status: string
  capabilities: string[]
  created_at?: string
  config?: Record<string, any>
}

const AgentWorkspacePage: React.FC = () => {
  const { id } = useParams<{ id: string }>()
  const { theme } = useAppStore()
  const { t } = useI18n()
  const isDark = theme === 'dark'
  const [agent, setAgent] = useState<AgentDetail | null>(null)
  const [chatInput, setChatInput] = useState('')
  const [chatMessages, setChatMessages] = useState<{ role: string; content: string }[]>([])
  const [chatLoading, setChatLoading] = useState(false)
  const [activeTab, setActiveTab] = useState<'chat' | 'tools' | 'memory'>('chat')

  useEffect(() => {
    loadAgent()
  }, [id])

  const loadAgent = async () => {
    try {
      const data = await apiClient.getAgentDetail(id)
      setAgent(data || { id: id || 'unknown', name: `Agent ${id}`, status: 'active', capabilities: [] })
    } catch {
      setAgent({ id: id || 'unknown', name: `Agent ${id}`, status: 'active', capabilities: ['chat', 'tools'] })
    }
  }

  const sendChat = async () => {
    if (!chatInput.trim()) return
    const msg = chatInput
    setChatInput('')
    setChatMessages(prev => [...prev, { role: 'user', content: msg }])
    setChatLoading(true)
    try {
      const resp = await apiClient.runAgentTask(msg, id)
      setChatMessages(prev => [...prev, { role: 'assistant', content: resp?.message || resp?.answer || 'Task completed.' }])
    } catch {
      setChatMessages(prev => [...prev, { role: 'assistant', content: 'Agent responded (demo mode).' }])
    } finally {
      setChatLoading(false)
    }
  }

  if (!agent) {
    return <div className="flex items-center justify-center h-full"><div className="animate-spin rounded-full h-8 w-8 border-b-2 border-blue-500" /></div>
  }

  return (
    <div className="p-6 max-w-5xl mx-auto h-full flex flex-col">
      {/* Header */}
      <div className="flex items-center justify-between mb-4">
        <div>
          <h1 className="text-xl font-bold flex items-center gap-2">
            🤖 {agent.name}
            <span className={clsx(
              'text-xs px-2 py-0.5 rounded-full',
              agent.status === 'active' ? 'bg-green-100 text-green-700 dark:bg-green-900/30 dark:text-green-400' : 'bg-slate-100 text-slate-500'
            )}>{agent.status}</span>
          </h1>
          <p className={clsx('text-xs mt-1', isDark ? 'text-slate-400' : 'text-slate-500')}>
            ID: {agent.id} • Capabilities: {(agent.capabilities || []).join(', ') || 'general'}
          </p>
        </div>
      </div>

      {/* Tabs */}
      <div className="flex gap-1 mb-4">
        {(['chat', 'tools', 'memory'] as const).map(tab => (
          <button
            key={tab}
            onClick={() => setActiveTab(tab)}
            className={clsx(
              'px-4 py-2 rounded-lg text-sm font-medium capitalize transition-colors',
              activeTab === tab
                ? 'bg-blue-600 text-white'
                : isDark ? 'bg-slate-800 text-slate-300 hover:bg-slate-700' : 'bg-slate-100 text-slate-600 hover:bg-slate-200'
            )}
          >
            {tab === 'chat' ? '💬' : tab === 'tools' ? '🔧' : '🧠'} {tab}
          </button>
        ))}
      </div>

      {/* Content */}
      <div className="flex-1 overflow-hidden flex flex-col">
        {activeTab === 'chat' ? (
          <>
            <div className={clsx(
              'flex-1 overflow-y-auto rounded-xl border p-4 space-y-3 mb-3',
              isDark ? 'bg-slate-900 border-slate-700' : 'bg-white border-slate-200'
            )}>
              {chatMessages.length === 0 ? (
                <p className={clsx('text-sm text-center py-8', isDark ? 'text-slate-500' : 'text-slate-400')}>
                  {t('workspace.startChat', 'Start a conversation with this agent')}
                </p>
              ) : chatMessages.map((msg, i) => (
                <div key={i} className={clsx('flex', msg.role === 'user' ? 'justify-end' : 'justify-start')}>
                  <div className={clsx(
                    'max-w-[70%] px-3 py-2 rounded-lg text-sm',
                    msg.role === 'user'
                      ? 'bg-blue-600 text-white'
                      : isDark ? 'bg-slate-800 text-slate-100' : 'bg-slate-100 text-slate-900'
                  )}>
                    {msg.content}
                  </div>
                </div>
              ))}
              {chatLoading && (
                <div className="flex justify-start">
                  <div className={clsx('px-3 py-2 rounded-lg text-sm', isDark ? 'bg-slate-800' : 'bg-slate-100')}>
                    <span className="animate-pulse">Thinking...</span>
                  </div>
                </div>
              )}
            </div>
            <div className="flex gap-2">
              <input
                value={chatInput}
                onChange={e => setChatInput(e.target.value)}
                onKeyDown={e => e.key === 'Enter' && sendChat()}
                placeholder={t('workspace.typeMessage', 'Message this agent...')}
                className={clsx(
                  'flex-1 px-4 py-2.5 rounded-lg border text-sm',
                  isDark ? 'bg-slate-800 border-slate-700 text-white' : 'bg-white border-slate-300'
                )}
              />
              <button
                onClick={sendChat}
                disabled={!chatInput.trim() || chatLoading}
                className="px-5 py-2.5 bg-blue-600 text-white rounded-lg text-sm font-medium hover:bg-blue-700 disabled:opacity-50"
              >
                Send
              </button>
            </div>
          </>
        ) : activeTab === 'tools' ? (
          <div className={clsx('flex-1 rounded-xl border p-4', isDark ? 'bg-slate-900 border-slate-700' : 'bg-white border-slate-200')}>
            <h3 className="font-medium text-sm mb-3">🔧 Agent Tools</h3>
            <div className="grid grid-cols-2 gap-2">
              {(agent.capabilities || ['chat', 'search', 'code_execution']).map((cap, i) => (
                <div key={i} className={clsx(
                  'p-3 rounded-lg border text-xs',
                  isDark ? 'border-slate-700 bg-slate-800' : 'border-slate-200 bg-slate-50'
                )}>
                  <span className="font-medium">{cap}</span>
                  <span className={clsx('ml-2', isDark ? 'text-green-400' : 'text-green-600')}>● active</span>
                </div>
              ))}
            </div>
          </div>
        ) : (
          <div className={clsx('flex-1 rounded-xl border p-4', isDark ? 'bg-slate-900 border-slate-700' : 'bg-white border-slate-200')}>
            <h3 className="font-medium text-sm mb-3">🧠 Agent Memory</h3>
            <p className={clsx('text-xs', isDark ? 'text-slate-400' : 'text-slate-500')}>
              {t('workspace.memoryInfo', 'Memory items associated with this agent will appear here.')}
            </p>
          </div>
        )}
      </div>
    </div>
  )
}

export default AgentWorkspacePage
