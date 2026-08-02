import React, { useEffect, useRef, useState } from 'react'
import { useAppStore } from '@/store/appStore'
import { Agent, apiClient, ChatMessage, ChatRunResponse } from '@/services/api'
import { SSEClient, AnyStreamEvent } from '@/services/sseClient'
import { useI18n } from '@/i18n/context'
import { Activity, AlertTriangle, CheckCircle2, Loader, Paperclip, Send, Radio, Zap } from 'lucide-react'
import clsx from 'clsx'

interface ParallelTaskCard {
  agent_id: string
  task: string
  status: 'pending' | 'running' | 'completed' | 'failed'
  output?: string
  error?: string
}

export const ChatPage: React.FC = () => {
  const { theme, messages, addMessage, clearMessages, isLoading, setLoading, setError } = useAppStore()
  const { t } = useI18n()
  const [input, setInput] = useState('')
  const [agents, setAgents] = useState<Agent[]>([])
  const [selectedAgent, setSelectedAgent] = useState<string>('')
  const [lastRun, setLastRun] = useState<ChatRunResponse | null>(null)
  const [isStreaming, setIsStreaming] = useState(false)
  const [streamContent, setStreamContent] = useState('')
  const [ultraMode, setUltraMode] = useState(false)
  const [parallelTasks, setParallelTasks] = useState<ParallelTaskCard[]>([])
  const [parallelRunning, setParallelRunning] = useState(false)
  const [tokenUsage, setTokenUsage] = useState<{ tokens?: number; iterations?: number; model?: string } | null>(null)
  const sessionIdRef = useRef<string | null>(null)
  const messagesEndRef = useRef<HTMLDivElement>(null)
  const sseClientRef = useRef<SSEClient | null>(null)

  useEffect(() => {
    loadAgents()
    loadHistory()
    return () => {
      sseClientRef.current?.disconnect()
    }
  }, [])

  useEffect(() => {
    scrollToBottom()
  }, [messages])

  const scrollToBottom = () => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' })
  }

  // ── Chat history persistence (backend /api/v1/chat/history) ──────────────

  /** Load the most recent persisted session into the message list. */
  const loadHistory = async () => {
    try {
      const sessions = await apiClient.listChatSessions(1)
      if (!sessions.length) return
      const detail = await apiClient.getChatSession(sessions[0].id)
      sessionIdRef.current = detail.id
      clearMessages()
      detail.messages.forEach((m) => {
        addMessage({
          id: m.id,
          role: m.role === 'user' ? 'user' : 'assistant',
          content: m.content,
          timestamp: new Date(m.timestamp * 1000).toISOString(),
          metadata: m.metadata,
        })
      })
    } catch (error) {
      console.error('Failed to load chat history:', error)
    }
  }

  /** Best-effort persistence of one message; never blocks or breaks the chat. */
  const persistChatMessage = async (role: string, content: string, metadata?: Record<string, any>) => {
    try {
      if (!sessionIdRef.current) {
        const session = await apiClient.createChatSession({ agent_id: selectedAgent || 'default' })
        sessionIdRef.current = session.id
      }
      await apiClient.addChatMessage(sessionIdRef.current, { role, content, metadata })
    } catch (error) {
      console.error('Failed to persist chat message:', error)
    }
  }

  const loadAgents = async () => {
    const fallbackAgent = (agentId: string = 'default-agent'): Agent => ({
      id: agentId,
      name: 'Default Agent',
      status: 'active',
      capabilities: ['workflow', 'tools', 'memory'],
      createdAt: new Date().toISOString(),
      updatedAt: new Date().toISOString(),
    })

    try {
      const bootstrap = await apiClient.getWorkbenchBootstrap()
      const agent = fallbackAgent(bootstrap.console.agent_id)
      setAgents([agent])
      setSelectedAgent(agent.id)
    } catch (error) {
      const agent = fallbackAgent()
      setAgents([agent])
      setSelectedAgent(agent.id)
      console.error('Failed to load workbench bootstrap:', error)
    }
  }

  const handleUltraSend = async (messageText: string) => {
    setParallelRunning(true)
    setParallelTasks([])
    try {
      const resp = await apiClient.runParallelAgents(
        [{ goal: messageText, description: messageText }],
        4
      )
      const results = resp?.results || resp?.agent_results || []
      setParallelTasks(results.map((r: any) => ({
        agent_id: r.agent_id || `agent-${Math.random().toString(36).slice(2, 8)}`,
        task: messageText,
        status: r.status || 'completed',
        output: r.output,
        error: r.error,
      })))
      // Add summary message
      const summary = results.map((r: any, i: number) => `Agent ${i + 1}: ${r.status}${r.output ? ' - ' + String(r.output).slice(0, 100) : ''}`).join('\n')
      const summaryContent = `⚡ Ultra Mode (${results.length} agents):\n${summary}`
      addMessage({
        id: `parallel-${Date.now()}`,
        role: 'assistant',
        content: summaryContent,
        timestamp: new Date().toISOString(),
      })
      void persistChatMessage('assistant', summaryContent, { execution_id: resp?.execution_id })
    } catch {
      setParallelTasks([{
        agent_id: 'agent-1', task: messageText, status: 'completed',
        output: 'Task completed (demo mode)',
      }])
      addMessage({
        id: `parallel-${Date.now()}`,
        role: 'assistant',
        content: '⚡ Ultra Mode: Task dispatched to parallel agents (demo mode).',
        timestamp: new Date().toISOString(),
      })
    } finally {
      setParallelRunning(false)
    }
  }

  const handleSendMessage = async (e: React.FormEvent) => {
    e.preventDefault()
    if (!input.trim()) return

    if (ultraMode) {
      const userMessage: ChatMessage = {
        id: Date.now().toString(),
        role: 'user',
        content: input,
        timestamp: new Date().toISOString(),
      }
      addMessage(userMessage)
      void persistChatMessage('user', userMessage.content)
      const messageText = input
      setInput('')
      await handleUltraSend(messageText)
      return
    }

    try {
      setLoading(true)
      setStreamContent('')

      // Add user message
      const userMessage: ChatMessage = {
        id: Date.now().toString(),
        role: 'user',
        content: input,
        timestamp: new Date().toISOString(),
      }
      addMessage(userMessage)
      void persistChatMessage('user', userMessage.content)
      const messageText = input
      setInput('')

      // Send to API
      const response = await apiClient.sendMessage(messageText, selectedAgent)
      setLastRun(response)

      // Connect to SSE stream for real-time updates
      if (response.run_id) {
        setIsStreaming(true)
        const sse = new SSEClient({ maxReconnectAttempts: 3 })
        sseClientRef.current = sse

        let accumulated = ''
        sse.connect(
          response.run_id,
          (event: AnyStreamEvent) => {
            if (event.event_type === 'message' && 'content' in event) {
              accumulated += (event as any).content || ''
              setStreamContent(accumulated)
            } else if (event.event_type === 'completion') {
              const result = (event as any).result
              if (result && typeof result === 'string') {
                accumulated = result
              } else if (result && typeof result === 'object') {
                // Extract token usage from execution_summary
                const summary = result.execution_summary || {}
                setTokenUsage({
                  tokens: summary.tokens_used || summary.total_tokens || result.iterations,
                  iterations: result.iterations,
                  model: summary.model || undefined,
                })
                if (result.answer) accumulated = result.answer
              }
            }
          },
          (error) => {
            console.error('SSE error:', error)
            setIsStreaming(false)
          },
          () => {
            // On complete, add the final assistant message
            setIsStreaming(false)
            const finalContent = accumulated || response.message
            addMessage({
              id: response.run_id,
              role: 'assistant',
              content: finalContent,
              timestamp: new Date().toISOString(),
              metadata: {
                run_id: response.run_id,
                status: 'completed',
              },
            })
            void persistChatMessage('assistant', finalContent, { run_id: response.run_id })
            setStreamContent('')
          }
        )

        // Fallback: if SSE doesn't complete in 5s, show the initial response
        setTimeout(() => {
          if (!accumulated) {
            setIsStreaming(false)
            addMessage({
              id: response.run_id,
              role: 'assistant',
              content: response.message,
              timestamp: new Date().toISOString(),
              metadata: {
                run_id: response.run_id,
                status: response.status,
                events: response.events,
              },
            })
            void persistChatMessage('assistant', response.message, { run_id: response.run_id, status: response.status })
          }
        }, 5000)
      } else {
        // No run_id, just show the response
        addMessage({
          id: Date.now().toString() + '-response',
          role: 'assistant',
          content: response.message,
          timestamp: new Date().toISOString(),
        })
        void persistChatMessage('assistant', response.message)
      }
    } catch (error) {
      setError(error instanceof Error ? error.message : 'Failed to send message')
    } finally {
      setLoading(false)
    }
  }

  return (
    <div className={clsx(
      'flex flex-col h-full',
      theme === 'dark' ? 'bg-slate-950' : 'bg-white'
    )}>
      {/* Header */}
      <div className={clsx(
        'p-6 border-b',
        theme === 'dark' ? 'border-slate-700 bg-slate-900' : 'border-slate-200 bg-slate-50'
      )}>
        <h1 className={clsx(
          'text-2xl font-bold mb-4',
          theme === 'dark' ? 'text-white' : 'text-slate-900'
        )}>
          {t('chat.title', 'Chat with X-Agent')}
        </h1>

        {/* Agent Selector */}
        <div className="flex items-center gap-2">
          <label
            htmlFor="chat-agent-select"
            className={clsx(
              'text-sm font-medium',
              theme === 'dark' ? 'text-slate-300' : 'text-slate-700'
            )}
          >
            {t('chat.selectAgent', 'Select Agent')}:
          </label>
          <select
            id="chat-agent-select"
            value={selectedAgent}
            onChange={(e) => setSelectedAgent(e.target.value)}
            className={clsx(
              'px-3 py-1 rounded-lg text-sm',
              theme === 'dark'
                ? 'bg-slate-800 text-white border border-slate-700'
                : 'bg-white text-slate-900 border border-slate-300'
            )}
          >
            {agents.map((agent) => (
              <option key={agent.id} value={agent.id}>
                {agent.name}
              </option>
            ))}
          </select>
          {/* Ultra Mode Toggle */}
          <button
            type="button"
            onClick={() => setUltraMode(!ultraMode)}
            className={clsx(
              'ml-2 inline-flex items-center gap-1 rounded-md px-2.5 py-1 text-xs font-medium transition-colors',
              ultraMode
                ? 'bg-purple-600 text-white shadow-sm'
                : theme === 'dark'
                  ? 'bg-slate-800 text-slate-300 hover:bg-slate-700'
                  : 'bg-slate-200 text-slate-600 hover:bg-slate-300'
            )}
            title={t('chat.ultraMode', 'Ultra Mode: 4 parallel agents')}
            aria-pressed={ultraMode}
          >
            <Zap size={12} />
            Ultra
          </button>
        </div>

        {lastRun && (
          <div className={clsx(
            'mt-4 flex flex-wrap items-center gap-2 text-xs',
            theme === 'dark' ? 'text-slate-300' : 'text-slate-600'
          )}>
            <span className={clsx(
              'inline-flex items-center gap-1 rounded-md border px-2 py-1',
              theme === 'dark' ? 'border-slate-700 bg-slate-800' : 'border-slate-200 bg-white'
            )}>
              {lastRun.status === 'failed' ? <AlertTriangle size={14} /> : <CheckCircle2 size={14} />}
              {lastRun.status}
            </span>
            <span className={clsx(
              'inline-flex min-w-0 items-center gap-1 rounded-md border px-2 py-1',
              theme === 'dark' ? 'border-slate-700 bg-slate-800' : 'border-slate-200 bg-white'
            )}>
              <Activity size={14} />
              <span className="truncate">run {lastRun.run_id}</span>
            </span>
            {lastRun.approval_required && (
              <span className="inline-flex items-center gap-1 rounded-md bg-amber-100 px-2 py-1 text-amber-700">
                <AlertTriangle size={14} />
                approval required
              </span>
            )}
            {tokenUsage && (
              <span className={clsx(
                'inline-flex items-center gap-1 rounded-md border px-2 py-1',
                theme === 'dark' ? 'border-emerald-800 bg-emerald-950 text-emerald-300' : 'border-emerald-200 bg-emerald-50 text-emerald-700'
              )}>
                <Zap size={12} />
                {tokenUsage.tokens ? `${tokenUsage.tokens} tokens` : ''}
                {tokenUsage.iterations ? ` · ${tokenUsage.iterations} iter` : ''}
                {tokenUsage.model ? ` · ${tokenUsage.model}` : ''}
              </span>
            )}
          </div>
        )}
      </div>

      {lastRun && (
        <div className={clsx(
          'border-b px-6 py-3',
          theme === 'dark' ? 'border-slate-700 bg-slate-950' : 'border-slate-200 bg-white'
        )}>
          <div className={clsx(
            'grid gap-2 text-xs md:grid-cols-2',
            theme === 'dark' ? 'text-slate-300' : 'text-slate-600'
          )}>
            {lastRun.events.map((event, index) => (
              <div
                key={`${event.type}-${index}`}
                className={clsx(
                  'rounded-md border px-3 py-2',
                  theme === 'dark' ? 'border-slate-700 bg-slate-900' : 'border-slate-200 bg-slate-50'
                )}
              >
                <div className="font-medium">{event.type}</div>
                <div className="mt-1">{event.message}</div>
              </div>
            ))}
          </div>
        </div>
      )}

      {/* Messages */}
      <div className="flex-1 overflow-y-auto p-6 space-y-4" role="log" aria-live="polite" aria-label={t('chat.messages', 'Messages')}>
        {messages.length === 0 && !streamContent ? (
          <div className={clsx(
            'flex items-center justify-center h-full text-center',
            theme === 'dark' ? 'text-slate-400' : 'text-slate-500'
          )}>
            <div>
              <p className="text-lg font-medium mb-2">{t('chat.noMessages', 'No messages yet')}</p>
              <p className="text-sm">{t('chat.startConversation', 'Start a conversation with X-Agent')}</p>
            </div>
          </div>
        ) : (
          <>
            {messages.map((message) => (
              <ChatBubble key={message.id} message={message} />
            ))}
            {/* Streaming indicator */}
            {isStreaming && (
              <div className={clsx('flex justify-start')}>
                <div className={clsx(
                  'max-w-xs lg:max-w-md px-4 py-2 rounded-lg',
                  theme === 'dark' ? 'bg-slate-800 text-slate-100' : 'bg-slate-200 text-slate-900'
                )}>
                  {streamContent ? (
                    <p className="text-sm break-words whitespace-pre-wrap">{streamContent}</p>
                  ) : (
                    <div className="flex items-center gap-2 text-sm">
                      <Radio size={14} className="animate-pulse text-blue-500" />
                      <span>{t('chat.streaming', 'Agent is thinking...')}</span>
                    </div>
                  )}
                </div>
              </div>
            )}
            {/* Parallel task cards (Ultra Mode) */}
            {(parallelRunning || parallelTasks.length > 0) && (
              <div className="space-y-2 mt-2">
                {parallelRunning && parallelTasks.length === 0 && (
                  <div className="flex items-center gap-2 text-sm text-purple-500">
                    <Loader size={14} className="animate-spin" />
                    <span>Dispatching to parallel agents...</span>
                  </div>
                )}
                {parallelTasks.map((task, i) => (
                  <div key={task.agent_id + i} className={clsx(
                    'p-3 rounded-lg border text-xs',
                    theme === 'dark' ? 'bg-slate-900 border-slate-700' : 'bg-white border-slate-200'
                  )}>
                    <div className="flex items-center justify-between mb-1">
                      <span className="font-medium flex items-center gap-1">
                        <Zap size={11} className="text-purple-500" />
                        Agent {i + 1}
                      </span>
                      <span className={clsx(
                        'px-1.5 py-0.5 rounded text-[10px] font-medium',
                        task.status === 'completed' ? 'bg-green-100 text-green-700 dark:bg-green-900/30 dark:text-green-400' :
                        task.status === 'failed' ? 'bg-red-100 text-red-700 dark:bg-red-900/30 dark:text-red-400' :
                        'bg-blue-100 text-blue-700 dark:bg-blue-900/30 dark:text-blue-400'
                      )}>
                        {task.status}
                      </span>
                    </div>
                    {task.output && <p className={theme === 'dark' ? 'text-slate-400' : 'text-slate-500'}>{String(task.output).slice(0, 200)}</p>}
                    {task.error && <p className="text-red-500">{task.error}</p>}
                  </div>
                ))}
              </div>
            )}
          </>
        )}
        <div ref={messagesEndRef} />
      </div>

      {/* Input */}
      <div className={clsx(
        'p-6 border-t',
        theme === 'dark' ? 'border-slate-700 bg-slate-900' : 'border-slate-200 bg-slate-50'
      )}>
        <form onSubmit={handleSendMessage} className="flex gap-3">
          {/* File upload has no backend endpoint yet — disabled and labelled. */}
          <button
            type="button"
            disabled
            className={clsx(
              'p-2 rounded-lg transition-colors opacity-50 cursor-not-allowed',
              theme === 'dark'
                ? 'text-slate-400'
                : 'text-slate-600'
            )}
            title={`${t('chat.attachFile', 'Attach file')} (${t('common.comingSoon', 'Coming soon')})`}
            aria-label={`${t('chat.attachFile', 'Attach file')} (${t('common.comingSoon', 'Coming soon')})`}
          >
            <Paperclip size={20} />
          </button>

          <input
            type="text"
            value={input}
            onChange={(e) => setInput(e.target.value)}
            placeholder={t('chat.typeMessage', 'Type your message...')}
            disabled={isLoading}
            aria-label={t('chat.typeMessage', 'Type your message...')}
            className={clsx(
              'flex-1 px-4 py-2 rounded-lg transition-colors',
              theme === 'dark'
                ? 'bg-slate-800 text-white placeholder-slate-500 border border-slate-700 focus:border-blue-500'
                : 'bg-white text-slate-900 placeholder-slate-400 border border-slate-300 focus:border-blue-500',
              'focus:outline-none'
            )}
          />

          <button
            type="submit"
            disabled={isLoading || !input.trim()}
            aria-label={t('chat.send', 'Send')}
            className={clsx(
              'px-4 py-2 rounded-lg font-medium transition-colors flex items-center gap-2',
              isLoading || !input.trim()
                ? 'opacity-50 cursor-not-allowed'
                : 'bg-blue-600 hover:bg-blue-700 text-white'
            )}
          >
            {isLoading ? <Loader size={20} className="animate-spin" /> : <Send size={20} />}
            {t('chat.send', 'Send')}
          </button>
        </form>
      </div>
    </div>
  )
}

interface ChatBubbleProps {
  message: ChatMessage
}

const ChatBubble: React.FC<ChatBubbleProps> = ({ message }) => {
  const { theme } = useAppStore()
  const isUser = message.role === 'user'

  return (
    <div className={clsx('flex', isUser ? 'justify-end' : 'justify-start')}>
      <div
        className={clsx(
          'max-w-xs lg:max-w-md px-4 py-2 rounded-lg',
          isUser
            ? theme === 'dark'
              ? 'bg-blue-600 text-white'
              : 'bg-blue-500 text-white'
            : theme === 'dark'
              ? 'bg-slate-800 text-slate-100'
              : 'bg-slate-200 text-slate-900'
        )}
      >
        <p className="text-sm break-words">{message.content}</p>
        <p className={clsx(
          'text-xs mt-1',
          isUser
            ? 'text-blue-100'
            : theme === 'dark'
              ? 'text-slate-400'
              : 'text-slate-500'
        )}>
          {new Date(message.timestamp).toLocaleTimeString()}
        </p>
      </div>
    </div>
  )
}

export default ChatPage
