/**
 * SSE Client Tests
 */

import { afterEach, beforeEach, describe, expect, test, vi } from 'vitest';
import { SSEClient } from '@/services/sseClient';

describe('SSEClient', () => {
  let client: SSEClient;
  let mockEventSource: any;

  beforeEach(() => {
    client = new SSEClient();

    // Mock EventSource
    mockEventSource = {
      addEventListener: vi.fn(),
      close: vi.fn(),
      readyState: 1,
    };

    global.EventSource = vi.fn(() => mockEventSource) as any;
  });

  afterEach(() => {
    client.disconnect();
  });

  test('should connect to SSE stream', () => {
    const onMessage = vi.fn();
    client.connect('test-run-id', onMessage);

    expect(global.EventSource).toHaveBeenCalledWith(
      '/api/v1/agent/stream/test-run-id'
    );
    expect(mockEventSource.addEventListener).toHaveBeenCalled();
  });

  test('should handle incoming messages', () => {
    const onMessage = vi.fn();
    client.connect('test-run-id', onMessage);

    const messageHandler = mockEventSource.addEventListener.mock.calls.find(
      (call: any) => call[0] === 'message'
    )?.[1];

    const event = new MessageEvent('message', {
      data: JSON.stringify({
        event_type: 'message',
        content: 'test',
        role: 'assistant',
        timestamp: new Date().toISOString(),
        run_id: 'test-run-id',
      }),
    });

    messageHandler?.(event);
    expect(onMessage).toHaveBeenCalled();
  });

  test('should handle connection errors', () => {
    const onError = vi.fn();
    client.connect('test-run-id', vi.fn(), onError);

    mockEventSource.onerror?.();

    // Should attempt reconnection
    expect(client.getReconnectAttempts()).toBeGreaterThan(0);
  });

  test('should disconnect properly', () => {
    client.connect('test-run-id', vi.fn());
    client.disconnect();

    expect(mockEventSource.close).toHaveBeenCalled();
    expect(client.isConnected()).toBe(false);
  });

  test('should handle max reconnect attempts', async () => {
    const onError = vi.fn();
    const clientWithLimit = new SSEClient({ maxReconnectAttempts: 2 });

    clientWithLimit.connect('test-run-id', vi.fn(), onError);

    // Simulate multiple connection errors
    for (let i = 0; i < 3; i++) {
      mockEventSource.onerror?.();
      await new Promise(resolve => setTimeout(resolve, 100));
    }

    expect(onError).toHaveBeenCalled();
  });
});
