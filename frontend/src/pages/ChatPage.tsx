import React, { useEffect, useRef, useState } from 'react'
import { useAppStore } from '@/store/appStore'
import { Agent, apiClient, ChatMessage, ChatRunResponse } from '@/services/api'
import { Activity, AlertTriangle, CheckCircle2, Loader, Paperclip, Send } from 'lucide-react'
import clsx from 'clsx'

export const ChatPage: React.FC = () => {
  const { theme, messages, addMessage, isLoading, setLoading, setError } = useAppStore()
  const [input, setInput] = useState('')
  const [agents, setAgents] = useState<Agent[]>([])
  const [selectedAgent, setSelectedAgent] = useState<string>('')
  const [lastRun, setLastRun] = useState<ChatRunResponse | null>(null)
  const messagesEndRef = useRef<HTMLDivElement>(null)

  useEffect(() => {
    loadAgents()
    loadChatHistory()
  }, [])

  useEffect(() => {
    scrollToBottom()
  }, [messages])

  const scrollToBottom = () => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' })
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

  const loadChatHistory = async () => {
    try {
      const history = await apiClient.getChatHistory()
      history.forEach((msg) => addMessage(msg))
    } catch (error) {
      console.error('Failed to load chat history:', error)
    }
  }

  const handleSendMessage = async (e: React.FormEvent) => {
    e.preventDefault()
    if (!input.trim()) return

    try {
      setLoading(true)

      // Add user message
      const userMessage: ChatMessage = {
        id: Date.now().toString(),
        role: 'user',
        content: input,
        timestamp: new Date().toISOString(),
      }
      addMessage(userMessage)
      setInput('')

      // Send to API
      const response = await apiClient.sendMessage(input, selectedAgent)
      setLastRun(response)
      addMessage({
        id: response.run_id,
        role: 'assistant',
        content: response.message,
        timestamp: new Date().toISOString(),
        metadata: {
          run_id: response.run_id,
          status: response.status,
          events: response.events,
          approval_required: response.approval_required,
          next_actions: response.next_actions,
        },
      })
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
          Chat with X-Agent
        </h1>

        {/* Agent Selector */}
        <div className="flex gap-2">
          <label className={clsx(
            'text-sm font-medium',
            theme === 'dark' ? 'text-slate-300' : 'text-slate-700'
          )}>
            Select Agent:
          </label>
          <select
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
      <div className="flex-1 overflow-y-auto p-6 space-y-4">
        {messages.length === 0 ? (
          <div className={clsx(
            'flex items-center justify-center h-full text-center',
            theme === 'dark' ? 'text-slate-400' : 'text-slate-500'
          )}>
            <div>
              <p className="text-lg font-medium mb-2">No messages yet</p>
              <p className="text-sm">Start a conversation with X-Agent</p>
            </div>
          </div>
        ) : (
          messages.map((message) => (
            <ChatBubble key={message.id} message={message} />
          ))
        )}
        <div ref={messagesEndRef} />
      </div>

      {/* Input */}
      <div className={clsx(
        'p-6 border-t',
        theme === 'dark' ? 'border-slate-700 bg-slate-900' : 'border-slate-200 bg-slate-50'
      )}>
        <form onSubmit={handleSendMessage} className="flex gap-3">
          <button
            type="button"
            className={clsx(
              'p-2 rounded-lg transition-colors',
              theme === 'dark'
                ? 'hover:bg-slate-800 text-slate-400'
                : 'hover:bg-slate-200 text-slate-600'
            )}
            title="Attach file"
          >
            <Paperclip size={20} />
          </button>

          <input
            type="text"
            value={input}
            onChange={(e) => setInput(e.target.value)}
            placeholder="Type your message..."
            disabled={isLoading}
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
            className={clsx(
              'px-4 py-2 rounded-lg font-medium transition-colors flex items-center gap-2',
              isLoading || !input.trim()
                ? 'opacity-50 cursor-not-allowed'
                : 'bg-blue-600 hover:bg-blue-700 text-white'
            )}
          >
            {isLoading ? <Loader size={20} className="animate-spin" /> : <Send size={20} />}
            Send
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
