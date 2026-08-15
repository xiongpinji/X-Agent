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
})
