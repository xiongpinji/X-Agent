/**
 * SSE Client Tests
 */

import { describe, test, expect, beforeEach, afterEach, vi } from 'vitest'
import { SSEClient } from '@/services/sseClient'

describe('SSEClient', () => {
  let client: SSEClient
  let mockEventSource: any
  let originalEventSource: any

  beforeEach(() => {
    vi.clearAllMocks()
    client = new SSEClient()

    // Mock EventSource (jsdom does not implement it)
    originalEventSource = global.EventSource
    mockEventSource = {
      addEventListener: vi.fn(),
      close: vi.fn(),
      readyState: 1, // OPEN
      onerror: null as ((ev: any) => void) | null,
    }
    global.EventSource = vi.fn(() => mockEventSource) as any
  })

  afterEach(() => {
    client.disconnect()
    global.EventSource = originalEventSource
  })

  test('should connect to SSE stream', () => {
    const onMessage = vi.fn()
    client.connect('test-run-id', onMessage)

    expect(global.EventSource).toHaveBeenCalledWith(
      '/api/v1/agent/stream/test-run-id'
    )
    expect(mockEventSource.addEventListener).toHaveBeenCalled()
  })

  test('should handle incoming messages', () => {
    const onMessage = vi.fn()
    client.connect('test-run-id', onMessage)

    const messageHandler = mockEventSource.addEventListener.mock.calls.find(
      (call: any) => call[0] === 'message'
    )?.[1]

    const event = new MessageEvent('message', {
      data: JSON.stringify({
        event_type: 'message',
        content: 'test',
        role: 'assistant',
        timestamp: new Date().toISOString(),
        run_id: 'test-run-id',
      }),
    })

    messageHandler?.(event)
    expect(onMessage).toHaveBeenCalledWith(
      expect.objectContaining({ event_type: 'message', content: 'test' })
    )
  })

  test('should handle connection errors', () => {
    const onError = vi.fn()
    client.connect('test-run-id', vi.fn(), onError)

    mockEventSource.onerror?.(new Event('error'))

    // Should schedule a reconnection (attempt counter incremented)
    expect(client.getReconnectAttempts()).toBeGreaterThan(0)
  })

  test('should disconnect properly', () => {
    client.connect('test-run-id', vi.fn())
    client.disconnect()

    expect(mockEventSource.close).toHaveBeenCalled()
    expect(client.isConnected()).toBe(false)
  })

  test('should stop reconnecting after max reconnect attempts', () => {
    vi.useFakeTimers()
    try {
      const onError = vi.fn()
      const clientWithLimit = new SSEClient({ maxReconnectAttempts: 2 })

      clientWithLimit.connect('test-run-id', vi.fn(), onError)

      // Simulate repeated connection errors; each call schedules an
      // (exponential backoff) reconnect until the limit is exceeded.
      mockEventSource.onerror?.(new Event('error'))
      mockEventSource.onerror?.(new Event('error'))
      expect(clientWithLimit.getReconnectAttempts()).toBe(2)
      expect(onError).not.toHaveBeenCalled()

      mockEventSource.onerror?.(new Event('error'))
      expect(onError).toHaveBeenCalledWith(
        new Error('Failed to connect after 2 attempts')
      )

      clientWithLimit.disconnect()
    } finally {
      vi.useRealTimers()
    }
  })

  test('should invoke onComplete and close on completion event', () => {
    const onComplete = vi.fn()
    client.connect('test-run-id', vi.fn(), undefined, onComplete)

    const completionHandler = mockEventSource.addEventListener.mock.calls.find(
      (call: any) => call[0] === 'completion'
    )?.[1]

    completionHandler?.(
      new MessageEvent('completion', {
        data: JSON.stringify({
          event_type: 'completion',
          status: 'success',
          result: { answer: 'test' },
          summary: {},
          timestamp: new Date().toISOString(),
          run_id: 'test-run-id',
        }),
      })
    )

    expect(onComplete).toHaveBeenCalled()
    expect(mockEventSource.close).toHaveBeenCalled()
  })
})
