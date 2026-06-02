import React, { useEffect, useRef, useState } from 'react'
import { useAppStore } from '@/store/appStore'
import { apiClient, ChatMessage } from '@/services/api'
import { Send, Paperclip, Loader } from 'lucide-react'
import clsx from 'clsx'

export const ChatPage: React.FC = () => {
  const { theme, messages, addMessage, isLoading, setLoading, setError } = useAppStore()
  const [input, setInput] = useState('')
  const [agents, setAgents] = useState<any[]>([])
  const [selectedAgent, setSelectedAgent] = useState<string>('')
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
    try {
      const data = await apiClient.listAgents()
      setAgents(data)
      if (data.length > 0) {
        setSelectedAgent(data[0].id)
      }
    } catch (error) {
      setError(error instanceof Error ? error.message : 'Failed to load agents')
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
      addMessage(response)
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
      </div>

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
