// @vitest-environment jsdom

import '@testing-library/jest-dom/vitest'
import React from 'react'
import { act, cleanup, render, renderHook, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'

import { AgentStreamPanel } from '@/components/AgentStreamPanel'
import { useAgentStream } from '@/hooks/useAgentStream'


const sensitiveError = 'SENSITIVE_INTERNAL_DETAIL_DO_NOT_LEAK'
const safeNetworkError = 'Unable to reach the agent service'

const failedFrame = {
  _final: true,
  result: {
    trace_id: 'trace-failed',
    status: 'failed',
    answer: '',
    error: 'Agent execution failed',
    error_code: 'agent_execution_failed',
  },
}

const sseResponse = (frame: object): Response => {
  return chunkedSseResponse([`event: completed\ndata: ${JSON.stringify(frame)}\n\n`])
}

const chunkedSseResponse = (chunks: string[]): Response => {
  const read = vi.fn()
  chunks.forEach((chunk) => {
    read.mockResolvedValueOnce({ done: false, value: new TextEncoder().encode(chunk) })
  })
  read.mockResolvedValueOnce({ done: true, value: undefined })
  return {
    ok: true,
    status: 200,
    body: { getReader: () => ({ read }) },
  } as unknown as Response
}


describe('shared agent stream failure contract', () => {
  beforeEach(() => {
    localStorage.clear()
  })

  afterEach(() => {
    cleanup()
    vi.restoreAllMocks()
  })

  it('sanitizes the public hook error state and callback for a network failure', async () => {
    vi.spyOn(globalThis, 'fetch').mockRejectedValue(new Error(sensitiveError))
    const onError = vi.fn()
    const { result } = renderHook(() => useAgentStream({ onError }))

    await act(async () => {
      await result.current.startStream('network failure')
    })

    expect(result.current.error).toBe(safeNetworkError)
    expect(onError).toHaveBeenCalledOnce()
    expect(onError).toHaveBeenCalledWith(safeNetworkError)
    expect(JSON.stringify({ error: result.current.error, calls: onError.mock.calls })).not.toContain(sensitiveError)
  })

  it('does not render a raw network failure in the real panel consumer', async () => {
    vi.spyOn(globalThis, 'fetch').mockRejectedValue(new Error(sensitiveError))
    const onError = vi.fn()
    const user = userEvent.setup()
    render(<AgentStreamPanel onError={onError} />)

    await user.type(screen.getByPlaceholderText('描述你的任务... (Ctrl+Enter 发送)'), 'network failure')
    await user.click(screen.getByRole('button', { name: '🚀 执行' }))

    expect(await screen.findByText(`❌ ${safeNetworkError}`)).toBeInTheDocument()
    expect(document.body.textContent).not.toContain(sensitiveError)
    expect(onError).toHaveBeenCalledWith(safeNetworkError)
  })

  it('renders a failed final frame as a failure while retaining onComplete', async () => {
    vi.spyOn(globalThis, 'fetch').mockResolvedValue(sseResponse(failedFrame))
    const onRunComplete = vi.fn()
    const onError = vi.fn()
    const user = userEvent.setup()
    render(<AgentStreamPanel onRunComplete={onRunComplete} onError={onError} />)

    await user.type(screen.getByPlaceholderText('描述你的任务... (Ctrl+Enter 发送)'), 'terminal failure')
    await user.click(screen.getByRole('button', { name: '🚀 执行' }))

    expect(await screen.findByText('❌ Agent execution failed')).toBeInTheDocument()
    expect(screen.queryByText(/✅ 完成/)).not.toBeInTheDocument()
    expect(onRunComplete).toHaveBeenCalledWith(failedFrame)
    expect(onError).not.toHaveBeenCalled()
  })

  it('stops after the first valid final when a duplicate final follows', async () => {
    const firstFinal = {
      _final: true,
      result: { trace_id: 'trace-first', status: 'completed', answer: 'first answer' },
    }
    const duplicateFinal = {
      _final: true,
      result: { trace_id: 'trace-duplicate', status: 'completed', answer: 'duplicate answer' },
    }
    vi.spyOn(globalThis, 'fetch').mockResolvedValue(chunkedSseResponse([
      `event: completed\ndata: ${JSON.stringify(firstFinal)}\n\n`,
      `event: completed\ndata: ${JSON.stringify(duplicateFinal)}\n\n`,
    ]))
    const onComplete = vi.fn()
    const onError = vi.fn()
    const { result } = renderHook(() => useAgentStream({ onComplete, onError }))

    await act(async () => {
      await result.current.startStream('duplicate final')
    })

    expect(onComplete).toHaveBeenCalledOnce()
    expect(onComplete).toHaveBeenCalledWith(firstFinal)
    expect(onError).not.toHaveBeenCalled()
  })

  it('ignores a malformed tail after the first valid final', async () => {
    const firstFinal = {
      _final: true,
      result: { trace_id: 'trace-first', status: 'completed', answer: 'first answer' },
    }
    vi.spyOn(globalThis, 'fetch').mockResolvedValue(chunkedSseResponse([
      `event: completed\ndata: ${JSON.stringify(firstFinal)}\n\n`,
      'event: completed\ndata: {malformed-tail}\n\n',
    ]))
    const onComplete = vi.fn()
    const onError = vi.fn()
    const { result } = renderHook(() => useAgentStream({ onComplete, onError }))

    await act(async () => {
      await result.current.startStream('malformed tail')
    })

    expect(onComplete).toHaveBeenCalledOnce()
    expect(onComplete).toHaveBeenCalledWith(firstFinal)
    expect(onError).not.toHaveBeenCalled()
  })

  it('parses CRLF frame boundaries and joins split multi-line data with a newline', async () => {
    const frameJson = JSON.stringify({
      _final: true,
      result: { trace_id: 'trace-crlf', status: 'completed', answer: 'split answer' },
    })
    const splitAt = frameJson.indexOf('"result"')
    vi.spyOn(globalThis, 'fetch').mockResolvedValue(chunkedSseResponse([
      `event: completed\r\ndata: ${frameJson.slice(0, splitAt)}\r`,
      `\ndata: ${frameJson.slice(splitAt)}\r`,
      '\n\r\n',
    ]))
    const onComplete = vi.fn()
    const onError = vi.fn()
    const { result } = renderHook(() => useAgentStream({ onComplete, onError }))

    await act(async () => {
      await result.current.startStream('split stream')
    })

    expect(result.current.error).toBeNull()
    expect(onError).not.toHaveBeenCalled()
    expect(onComplete).toHaveBeenCalledWith(expect.objectContaining({
      result: expect.objectContaining({ trace_id: 'trace-crlf', answer: 'split answer', status: 'completed' }),
    }))
  })

  it('turns malformed JSON into a safe terminal stream failure', async () => {
    vi.spyOn(globalThis, 'fetch').mockResolvedValue(chunkedSseResponse([
      'event: completed\ndata: {not-json}\n\n',
    ]))
    const onComplete = vi.fn()
    const onError = vi.fn()
    const { result } = renderHook(() => useAgentStream({ onComplete, onError }))

    await act(async () => {
      await result.current.startStream('malformed JSON')
    })

    expect(result.current.error).toBe(safeNetworkError)
    expect(onError).toHaveBeenCalledOnce()
    expect(onError).toHaveBeenCalledWith(safeNetworkError)
    expect(onComplete).not.toHaveBeenCalled()
  })

  it('keeps agent and session top-level while removing client profile fields', async () => {
    const fetchMock = vi.spyOn(globalThis, 'fetch').mockResolvedValue(sseResponse({
      _final: true,
      result: { trace_id: 'trace-binding', status: 'completed', answer: 'bound' },
    }))
    const { result } = renderHook(() => useAgentStream())

    await act(async () => {
      await result.current.startStream('bound task', {
        agent_id: 'custom-agent',
        session_id: 'session-123',
        extra_context: {
          source: 'panel',
          agent_profile: { system_prompt: sensitiveError },
          persona: { system_prompt: sensitiveError },
          profile: { system_prompt: sensitiveError },
        },
      })
    })

    expect(JSON.parse(String(fetchMock.mock.calls[0][1]?.body))).toEqual({
      task: 'bound task',
      agent_id: 'custom-agent',
      session_id: 'session-123',
      extra_context: { source: 'panel' },
    })
  })

  it('turns a malformed final envelope into a safe terminal stream failure', async () => {
    vi.spyOn(globalThis, 'fetch').mockResolvedValue(sseResponse({ _final: true }))
    const onComplete = vi.fn()
    const onError = vi.fn()
    const { result } = renderHook(() => useAgentStream({ onComplete, onError }))

    await act(async () => {
      await result.current.startStream('malformed final')
    })

    expect(result.current.error).toBe(safeNetworkError)
    expect(onError).toHaveBeenCalledWith(safeNetworkError)
    expect(onComplete).not.toHaveBeenCalled()
  })

  it('renders EOF without a final frame as a failure, never as completed', async () => {
    vi.spyOn(globalThis, 'fetch').mockResolvedValue(chunkedSseResponse([
      'event: trace\ndata: {"type":"thinking","content":"working"}\n\n',
    ]))
    const onRunComplete = vi.fn()
    const onError = vi.fn()
    const user = userEvent.setup()
    render(<AgentStreamPanel onRunComplete={onRunComplete} onError={onError} />)

    await user.type(screen.getByPlaceholderText('描述你的任务... (Ctrl+Enter 发送)'), 'missing final')
    await user.click(screen.getByRole('button', { name: '🚀 执行' }))

    expect(await screen.findByText(`❌ ${safeNetworkError}`)).toBeInTheDocument()
    expect(screen.queryByText(/✅ 完成/)).not.toBeInTheDocument()
    expect(onError).toHaveBeenCalledWith(safeNetworkError)
    expect(onRunComplete).not.toHaveBeenCalled()
  })

  it('does not report an intentional abort as a stream failure', async () => {
    vi.spyOn(globalThis, 'fetch').mockImplementation((_input, init) => new Promise((_resolve, reject) => {
      init?.signal?.addEventListener('abort', () => reject(new DOMException('Aborted', 'AbortError')))
    }))
    const onError = vi.fn()
    const { result } = renderHook(() => useAgentStream({ onError }))

    let streamPromise!: Promise<void>
    await act(async () => {
      streamPromise = result.current.startStream('cancel me')
      await Promise.resolve()
    })
    act(() => result.current.stopStream())
    await act(async () => {
      await streamPromise
    })

    expect(result.current.error).toBeNull()
    expect(onError).not.toHaveBeenCalled()
  })
})
