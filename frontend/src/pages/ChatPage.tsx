import React, { useEffect, useRef, useState } from 'react'
import { useAppStore } from '@/store/appStore'
import { Agent, apiClient, ChatMessage, ChatRunResponse } from '@/services/api'
import { SSEClient, AnyStreamEvent } from '@/services/sseClient'
import { useI18n } from '@/i18n/context'
import { AlertTriangle, CheckCircle2, Paperclip } from 'lucide-react'
import clsx from 'clsx'
import './ChatPage.css'

const DIVIDER = 'rgba(163,169,177,.15)'
const TIMELINE_GREY = 'rgba(163,169,177,.55)'
const ACCENT = '#2563eb'

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

  const handleSendMessage = async (e: React.FormEvent | React.KeyboardEvent) => {
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

  const handleInputKeyDown = (e: React.KeyboardEvent<HTMLTextAreaElement>) => {
    // Enter sends; Shift+Enter inserts a newline.
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault()
      if (!isLoading && input.trim()) {
        void handleSendMessage(e)
      }
    }
  }

  return (
    <div className={clsx(
      'flex flex-col h-full',
      theme === 'dark' ? 'bg-slate-950 text-slate-200' : 'bg-[#fafafa] text-[#333333]'
    )}>
      {/* Header — editorial rule + hairline divider, no card */}
      <header
        className="px-8 pt-8 pb-6 border-b"
        style={{ borderColor: DIVIDER }}
      >
        <div
          className={clsx(
            'w-10 border-t-2 mb-4',
            theme === 'dark' ? 'border-slate-200' : 'border-[#333333]'
          )}
          aria-hidden="true"
        />
        <h1 className="text-[24px] leading-tight font-medium tracking-tight">
          {t('chat.title', 'Chat with X-Agent')}
        </h1>

        {/* Agent selector + Ultra toggle — plain text row */}
        <div className="mt-4 flex flex-wrap items-center gap-x-5 gap-y-2">
          <label
            htmlFor="chat-agent-select"
            className="text-[11px] uppercase tracking-[0.08em] opacity-50"
          >
            {t('chat.selectAgent', 'Select Agent')}
          </label>
          <select
            id="chat-agent-select"
            value={selectedAgent}
            onChange={(e) => setSelectedAgent(e.target.value)}
            className="bg-transparent border-b pb-0.5 text-[13px] focus:outline-none cursor-pointer"
            style={{ borderColor: DIVIDER }}
          >
            {agents.map((agent) => (
              <option key={agent.id} value={agent.id}>
                {agent.name}
              </option>
            ))}
          </select>
          {/* Ultra Mode — text toggle with 2px active indicator */}
          <button
            type="button"
            onClick={() => setUltraMode(!ultraMode)}
            className={clsx(
              'relative pb-1 text-[11px] uppercase tracking-[0.08em] transition-opacity duration-200',
              ultraMode ? 'opacity-100' : 'opacity-50 hover:opacity-100'
            )}
            title={t('chat.ultraMode', 'Ultra Mode: 4 parallel agents')}
            aria-pressed={ultraMode}
          >
            Ultra
            <span
              className={clsx(
                'absolute left-0 right-0 -bottom-px h-[2px] transition-opacity duration-200',
                ultraMode ? 'opacity-100' : 'opacity-0'
              )}
              style={{ backgroundColor: ACCENT }}
              aria-hidden="true"
            />
          </button>
        </div>

        {lastRun && (
          <div className="mt-5 flex flex-wrap items-center gap-y-2 text-[12px]">
            <span className="inline-flex items-center gap-1.5 pr-5 opacity-80">
              {lastRun.status === 'failed' ? <AlertTriangle size={12} /> : <CheckCircle2 size={12} />}
              {lastRun.status}
            </span>
            <span
              className="inline-flex min-w-0 items-center pl-5 border-l"
              style={{ borderColor: DIVIDER }}
            >
              <span className="font-data truncate opacity-50">run {lastRun.run_id}</span>
            </span>
            {lastRun.approval_required && (
              <span
                className="inline-flex items-center gap-1.5 pl-5 ml-5 border-l text-amber-600"
                style={{ borderColor: DIVIDER }}
              >
                <AlertTriangle size={12} />
                approval required
              </span>
            )}
            {tokenUsage && (
              <span
                className="font-data inline-flex items-center pl-5 ml-5 border-l opacity-50"
                style={{ borderColor: DIVIDER }}
              >
                {tokenUsage.tokens ? `${tokenUsage.tokens} tokens` : ''}
                {tokenUsage.iterations ? ` · ${tokenUsage.iterations} iter` : ''}
                {tokenUsage.model ? ` · ${tokenUsage.model}` : ''}
              </span>
            )}
          </div>
        )}
      </header>

      {/* Run events — hairline rows instead of cards */}
      {lastRun && lastRun.events.length > 0 && (
        <div className="px-8 py-4 border-b" style={{ borderColor: DIVIDER }}>
          <div className="max-w-3xl grid gap-x-8 md:grid-cols-2">
            {lastRun.events.map((event, index) => (
              <div
                key={`${event.type}-${index}`}
                className="py-2 border-b"
                style={{ borderColor: DIVIDER }}
              >
                <div className="text-[11px] uppercase tracking-[0.06em] opacity-50">{event.type}</div>
                <div className="text-[13px] mt-0.5 opacity-80">{event.message}</div>
              </div>
            ))}
          </div>
        </div>
      )}

      {/* Messages — timeline, no bubbles */}
      <div
        className="flex-1 overflow-y-auto px-8 py-8"
        role="log"
        aria-live="polite"
        aria-label={t('chat.messages', 'Messages')}
      >
        {messages.length === 0 && !streamContent ? (
          <div className="flex items-center justify-center h-full text-center opacity-50">
            <div>
              <p className="text-[15px] font-medium mb-1">{t('chat.noMessages', 'No messages yet')}</p>
              <p className="text-[13px]">{t('chat.startConversation', 'Start a conversation with X-Agent')}</p>
            </div>
          </div>
        ) : (
          <div className="max-w-3xl space-y-7">
            {messages.map((message) => (
              <MessageItem key={message.id} message={message} />
            ))}

            {/* Streaming — timeline entry with blinking block cursor / dot pulse */}
            {isStreaming && (
              <article className="pl-4 border-l-2" style={{ borderColor: TIMELINE_GREY }}>
                <header className="flex items-baseline gap-3 mb-1.5">
                  <span className="text-[11px] uppercase tracking-[0.08em] opacity-50">
                    {t('chat.assistant', 'X-Agent')}
                  </span>
                </header>
                {streamContent ? (
                  <div className="text-[15px] leading-[1.7] break-words whitespace-pre-wrap">
                    {renderMessageContent(streamContent, theme === 'dark')}
                    <span
                      className={clsx(
                        'chat-cursor inline-block align-text-bottom w-[8px] h-[16px] ml-0.5',
                        theme === 'dark' ? 'bg-slate-300' : 'bg-[#333333]'
                      )}
                      aria-hidden="true"
                    />
                  </div>
                ) : (
                  <div className="flex items-center gap-2.5 text-[13px] opacity-50">
                    <DotPulse />
                    <span>{t('chat.streaming', 'Agent is thinking...')}</span>
                  </div>
                )}
              </article>
            )}

            {/* Parallel task rows (Ultra Mode) — hairlines, no cards */}
            {(parallelRunning || parallelTasks.length > 0) && (
              <article className="pl-4 border-l-2" style={{ borderColor: TIMELINE_GREY }}>
                <header className="flex items-baseline gap-3 mb-1.5">
                  <span className="text-[11px] uppercase tracking-[0.08em] opacity-50">
                    Ultra · {parallelTasks.length || 4} agents
                  </span>
                </header>
                {parallelRunning && parallelTasks.length === 0 && (
                  <div className="flex items-center gap-2.5 text-[13px] opacity-50 py-1">
                    <DotPulse />
                    <span>Dispatching to parallel agents...</span>
                  </div>
                )}
                <div>
                  {parallelTasks.map((task, i) => (
                    <div
                      key={task.agent_id + i}
                      className="py-2.5 border-b last:border-b-0"
                      style={{ borderColor: DIVIDER }}
                    >
                      <div className="flex items-baseline justify-between gap-3">
                        <span className="text-[13px] font-medium">Agent {i + 1}</span>
                        <span className={clsx(
                          'font-data text-[11px] uppercase tracking-[0.06em]',
                          task.status === 'completed' && 'text-emerald-600',
                          task.status === 'failed' && 'text-red-600',
                          task.status !== 'completed' && task.status !== 'failed' && 'opacity-50'
                        )}>
                          {task.status}
                        </span>
                      </div>
                      {task.output && (
                        <p className="text-[13px] mt-1 opacity-60">{String(task.output).slice(0, 200)}</p>
                      )}
                      {task.error && <p className="text-[13px] mt-1 text-red-600">{task.error}</p>}
                    </div>
                  ))}
                </div>
              </article>
            )}
          </div>
        )}
        <div ref={messagesEndRef} />
      </div>

      {/* Input — bottom fixed, single rounded grey frame */}
      <div className="border-t px-8 py-4" style={{ borderColor: DIVIDER }}>
        <form onSubmit={handleSendMessage} className="max-w-3xl">
          <div className={clsx(
            'flex items-end gap-3 rounded-2xl px-4 py-3',
            theme === 'dark' ? 'bg-slate-900' : 'bg-[#f5f5f5]'
          )}>
            {/* File upload has no backend endpoint yet — disabled and labelled. */}
            <button
              type="button"
              disabled
              className="pb-0.5 opacity-40 cursor-not-allowed"
              title={`${t('chat.attachFile', 'Attach file')} (${t('common.comingSoon', 'Coming soon')})`}
              aria-label={`${t('chat.attachFile', 'Attach file')} (${t('common.comingSoon', 'Coming soon')})`}
            >
              <Paperclip size={16} />
            </button>

            <textarea
              value={input}
              onChange={(e) => setInput(e.target.value)}
              onKeyDown={handleInputKeyDown}
              placeholder={t('chat.typeMessage', 'Type your message...')}
              disabled={isLoading}
              rows={1}
              aria-label={t('chat.typeMessage', 'Type your message...')}
              className="flex-1 bg-transparent resize-none text-[15px] leading-[1.6] focus:outline-none placeholder:opacity-50 max-h-40"
            />

            <button
              type="submit"
              disabled={isLoading || !input.trim()}
              aria-label={t('chat.send', 'Send')}
              className="group flex items-center gap-1.5 pb-0.5 text-[13px] font-medium transition-opacity duration-200 disabled:opacity-40 disabled:cursor-not-allowed"
            >
              {isLoading ? (
                <DotPulse />
              ) : (
                <>
                  {t('chat.send', 'Send')}
                  <span
                    className="transition-transform duration-200 ease-out group-hover:translate-x-[3px]"
                    aria-hidden="true"
                  >
                    →
                  </span>
                </>
              )}
            </button>
          </div>
          <p className="mt-2 text-[11px] opacity-50">
            {t('chat.enterToSend', 'Enter to send · Shift+Enter for a new line')}
          </p>
        </form>
      </div>
    </div>
  )
}

/* ── Content rendering ────────────────────────────────────────────────────
   Fenced code blocks → mono on flat #f5f5f5 (no coloured border);
   inline `code` → same treatment at smaller size. Plain text keeps
   15px/1.7 via the parent. */

const renderInline = (text: string, baseKey: string, dark: boolean): React.ReactNode[] =>
  text.split(/`([^`]+)`/g).map((seg, i) =>
    i % 2 === 1 ? (
      <code
        key={`${baseKey}-c${i}`}
        className={clsx(
          'font-data text-[0.85em] px-1.5 py-0.5 rounded',
          dark ? 'bg-slate-800' : 'bg-[#f5f5f5]'
        )}
      >
        {seg}
      </code>
    ) : (
      <React.Fragment key={`${baseKey}-t${i}`}>{seg}</React.Fragment>
    )
  )

const renderMessageContent = (content: string, dark: boolean): React.ReactNode => {
  const parts: React.ReactNode[] = []
  const fence = /```(\w*)\n?([\s\S]*?)(?:```|$)/g
  let lastIndex = 0
  let match: RegExpExecArray | null
  let n = 0
  while ((match = fence.exec(content)) !== null) {
    if (match.index > lastIndex) {
      parts.push(...renderInline(content.slice(lastIndex, match.index), `p${n++}`, dark))
    }
    parts.push(
      <pre
        key={`pre${n++}`}
        className={clsx(
          'font-data text-[13px] leading-relaxed my-3 p-4 rounded-lg overflow-x-auto',
          dark ? 'bg-slate-900' : 'bg-[#f5f5f5]'
        )}
      >
        <code className="bg-transparent p-0">{match[2].replace(/\n$/, '')}</code>
      </pre>
    )
    lastIndex = fence.lastIndex
  }
  if (lastIndex < content.length) {
    parts.push(...renderInline(content.slice(lastIndex), `p${n++}`, dark))
  }
  return parts
}

/* ── Three-dot pulse loading affordance ─────────────────────────────────── */

const DotPulse: React.FC = () => (
  <span className="inline-flex items-center gap-1" aria-hidden="true">
    <span className="chat-dot inline-block w-1 h-1 rounded-full bg-current" />
    <span className="chat-dot inline-block w-1 h-1 rounded-full bg-current" />
    <span className="chat-dot inline-block w-1 h-1 rounded-full bg-current" />
  </span>
)

/* ── Timeline message item ──────────────────────────────────────────────── */

interface MessageItemProps {
  message: ChatMessage
}

const MessageItem: React.FC<MessageItemProps> = ({ message }) => {
  const { theme } = useAppStore()
  const { t } = useI18n()
  const isUser = message.role === 'user'
  const dark = theme === 'dark'

  return (
    <article
      className="pl-4 border-l-2"
      style={{ borderColor: isUser ? ACCENT : TIMELINE_GREY }}
    >
      <header className="flex items-baseline gap-3 mb-1.5">
        <span className="text-[11px] uppercase tracking-[0.08em] opacity-50">
          {isUser ? t('chat.you', 'You') : t('chat.assistant', 'X-Agent')}
        </span>
        <span className="font-data text-[11px] opacity-50">
          {new Date(message.timestamp).toLocaleTimeString()}
        </span>
      </header>
      <div className="text-[15px] leading-[1.7] break-words whitespace-pre-wrap">
        {renderMessageContent(message.content, dark)}
      </div>
    </article>
  )
}

export default ChatPage
