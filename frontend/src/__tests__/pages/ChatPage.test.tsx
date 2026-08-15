// @vitest-environment jsdom

import '@testing-library/jest-dom/vitest'
import React from 'react'
import { act, cleanup, render, renderHook, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'

import { I18nProvider } from '@/i18n/context'
import { useAgentStream } from '@/hooks/useAgentStream'
import { ChatPage } from '@/pages/ChatPage'
import { apiClient } from '@/services/api'
import { useAppStore } from '@/store/appStore'


const completedFrame = {
  _final: true,
  result: {
    trace_id: 'trace-123',
    agent_id: 'default-agent',
    status: 'completed',
    answer: 'A real streamed answer',
    iterations: 2,
    memory_hits: 0,
    tool_calls: [],
    events: [],
    plan: [],
    execution_summary: { tokens_used: 42, model: 'mock-provider' },
    error: null,
    snapshot: {},
  },
}

const sensitiveError = 'SENSITIVE_INTERNAL_DETAIL_DO_NOT_LEAK'

const failedFrame = {
  _final: true,
  result: {
    trace_id: 'trace-failed',
    status: 'failed',
    answer: '',
    error: sensitiveError,
    error_code: 'agent_execution_failed',
  },
}


const sseResponse = (frame: object = completedFrame): Response => {
  const bytes = new TextEncoder().encode(`event: completed\ndata: ${JSON.stringify(frame)}\n\n`)
  const read = vi.fn()
    .mockResolvedValueOnce({ done: false, value: bytes })
    .mockResolvedValueOnce({ done: true, value: undefined })
  return {
    ok: true,
    status: 200,
    body: { getReader: () => ({ read }) },
  } as unknown as Response
}


const renderChat = () => render(
  <I18nProvider defaultLanguage="en">
    <ChatPage />
  </I18nProvider>
)


describe('default ChatPage agent stream', () => {
  beforeEach(() => {
    localStorage.clear()
    useAppStore.setState({
      messages: [],
      isLoading: false,
      error: null,
      theme: 'light',
    })
    vi.spyOn(apiClient, 'getWorkbenchBootstrap').mockResolvedValue({
      console: {
        tenant_id: 'tenant-a',
        user_id: 'user-a',
        agent_id: 'default-agent',
        session_id: 'session-a',
        created_at: '2026-08-15T00:00:00Z',
      },
      entries: [{ id: 'chat', label: 'Chat', path: '/chat' }],
    })
    vi.spyOn(apiClient, 'listChatSessions').mockResolvedValue([])
    vi.spyOn(apiClient, 'createChatSession').mockResolvedValue({
      id: 'session-a',
      title: 'Chat',
      created_at: 1,
    })
    vi.spyOn(apiClient, 'addChatMessage').mockResolvedValue({
      id: 'message-a',
      session_id: 'session-a',
      message_count: 1,
    })
    Object.defineProperty(HTMLElement.prototype, 'scrollIntoView', {
      configurable: true,
      value: vi.fn(),
    })
  })

  afterEach(() => {
    cleanup()
    vi.restoreAllMocks()
  })

  it('sends one user message through one authenticated POST-SSE request and records its final trace', async () => {
    localStorage.setItem('auth_token', 'bearer-token')
    const fetchMock = vi.spyOn(globalThis, 'fetch').mockResolvedValue(sseResponse())
    const user = userEvent.setup()
    renderChat()

    await user.type(screen.getByRole('textbox'), 'summarize this workspace')
    await user.click(screen.getByRole('button', { name: 'Send' }))

    await screen.findByText('A real streamed answer')
    expect(fetchMock).toHaveBeenCalledTimes(1)
    expect(fetchMock).toHaveBeenCalledWith('/api/v1/agents/run/stream', expect.objectContaining({
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        Authorization: 'Bearer bearer-token',
      },
    }))
    expect(JSON.parse(String(fetchMock.mock.calls[0][1]?.body))).toMatchObject({
      task: 'summarize this workspace',
    })
    expect(screen.getByText('run trace-123')).toBeInTheDocument()
    const assistantMessages = useAppStore.getState().messages.filter((message) => message.role === 'assistant')
    expect(assistantMessages).toHaveLength(1)
    expect(assistantMessages).toEqual([
      expect.objectContaining({
        role: 'assistant',
        content: 'A real streamed answer',
        metadata: expect.objectContaining({ trace_id: 'trace-123', status: 'completed' }),
      }),
    ])
  })

  it('falls back to X-API-Key when no bearer token is stored', async () => {
    localStorage.setItem('api_key', 'api-key')
    const fetchMock = vi.spyOn(globalThis, 'fetch').mockResolvedValue(sseResponse())
    const { result } = renderHook(() => useAgentStream())

    await act(async () => {
      await result.current.startStream('task')
    })

    expect(fetchMock).toHaveBeenCalledWith('/api/v1/agents/run/stream', expect.objectContaining({
      headers: {
        'Content-Type': 'application/json',
        'X-API-Key': 'api-key',
      },
    }))
  })

  it('sanitizes a terminal failed frame before displaying or persisting it', async () => {
    vi.spyOn(globalThis, 'fetch').mockResolvedValue(sseResponse(failedFrame))
    const user = userEvent.setup()
    renderChat()

    await user.type(screen.getByRole('textbox'), 'fail this task')
    await user.click(screen.getByRole('button', { name: 'Send' }))

    await screen.findByText('Agent run failed: Agent execution failed')
    await waitFor(() => {
      const assistantMessages = useAppStore.getState().messages.filter((message) => message.role === 'assistant')
      expect(assistantMessages).toHaveLength(1)
      expect(assistantMessages[0]).toMatchObject({
        metadata: { trace_id: 'trace-failed', status: 'failed', error_code: 'agent_execution_failed' },
      })
      expect(JSON.stringify(assistantMessages)).not.toContain(sensitiveError)
      expect(assistantMessages.some((message) => message.metadata?.status === 'completed')).toBe(false)
      expect(apiClient.addChatMessage).toHaveBeenCalledWith('session-a', {
        role: 'assistant',
        content: 'Agent run failed: Agent execution failed',
        metadata: { trace_id: 'trace-failed', status: 'failed', error_code: 'agent_execution_failed' },
      })
    })
    expect(document.body.textContent).not.toContain(sensitiveError)
    expect(JSON.stringify(vi.mocked(apiClient.addChatMessage).mock.calls)).not.toContain(sensitiveError)
  })

  it('sanitizes a network failure before displaying or persisting it', async () => {
    vi.spyOn(globalThis, 'fetch').mockRejectedValue(new Error(sensitiveError))
    const user = userEvent.setup()
    renderChat()

    await user.type(screen.getByRole('textbox'), 'network failure')
    await user.click(screen.getByRole('button', { name: 'Send' }))

    await screen.findByText('Agent run failed: Unable to reach the agent service')
    await waitFor(() => {
      const assistantMessages = useAppStore.getState().messages.filter((message) => message.role === 'assistant')
      expect(assistantMessages).toHaveLength(1)
      expect(assistantMessages[0]).toMatchObject({ metadata: { status: 'failed', error_code: 'stream_unavailable' } })
      expect(JSON.stringify(assistantMessages)).not.toContain(sensitiveError)
      expect(assistantMessages.some((message) => message.metadata?.status === 'completed')).toBe(false)
      expect(apiClient.addChatMessage).toHaveBeenCalledWith('session-a', {
        role: 'assistant',
        content: 'Agent run failed: Unable to reach the agent service',
        metadata: { trace_id: undefined, status: 'failed', error_code: 'stream_unavailable' },
      })
    })
    expect(document.body.textContent).not.toContain(sensitiveError)
    expect(JSON.stringify(vi.mocked(apiClient.addChatMessage).mock.calls)).not.toContain(sensitiveError)
  })
})
