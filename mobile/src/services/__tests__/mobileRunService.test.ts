// mobile/src/services/__tests__/mobileRunService.test.ts
// P2-08: mobileRunService 端点契约测试 (mock apiClient)

import { describe, it, expect, beforeEach, jest } from '@jest/globals';
import type { Mock } from 'jest-mock';
import {
  triggerAgentRun,
  getRunStatus,
  cancelRun,
  isTerminalStatus,
} from '../mobileRunService';
import { apiClient } from '../apiClient';

jest.mock('../apiClient', () => ({
  apiClient: {
    get: jest.fn(),
    post: jest.fn(),
  },
}));

type AnyAsyncMock = Mock<(...args: any[]) => Promise<any>>;
const mockedGet = apiClient.get as unknown as AnyAsyncMock;
const mockedPost = apiClient.post as unknown as AnyAsyncMock;

describe('mobileRunService', () => {
  beforeEach(() => {
    jest.clearAllMocks();
  });

  it('triggerAgentRun 调用 POST /api/v1/mobile/trigger 并填充默认值', async () => {
    mockedPost.mockResolvedValue({
      run_id: 'mob-abc123',
      trace_id: 'trace-1',
      status: 'pending',
      created_at: '2026-07-26T00:00:00Z',
      estimated_duration_seconds: 60,
      ws_url: '/api/v1/mobile/ws?run_id=mob-abc123',
    });

    const resp = await triggerAgentRun({ task: 'test task', priority: 'high' });

    expect(mockedPost).toHaveBeenCalledWith(
      '/api/v1/mobile/trigger',
      expect.objectContaining({
        task: 'test task',
        agent_id: 'default',
        priority: 'high',
        notify_on_complete: true,
      })
    );
    expect(resp.run_id).toBe('mob-abc123');
  });

  it('getRunStatus 调用 GET /api/v1/mobile/runs/{id}/status', async () => {
    mockedGet.mockResolvedValue({
      run_id: 'mob-abc123',
      trace_id: 'trace-1',
      status: 'running',
      progress_percent: 45,
      current_step: 'step 2',
      started_at: '2026-07-26T00:01:00Z',
      completed_at: null,
      result_summary: '',
      error: null,
      iterations: 2,
      tool_calls_count: 5,
    });

    const status = await getRunStatus('mob-abc123');

    expect(mockedGet).toHaveBeenCalledWith(
      '/api/v1/mobile/runs/mob-abc123/status'
    );
    expect(status.status).toBe('running');
    expect(status.progress_percent).toBe(45);
  });

  it('cancelRun 调用 POST /api/v1/mobile/runs/{id}/cancel', async () => {
    mockedPost.mockResolvedValue({ run_id: 'mob-abc123', status: 'cancelled' });

    const resp = await cancelRun('mob-abc123');

    expect(mockedPost).toHaveBeenCalledWith(
      '/api/v1/mobile/runs/mob-abc123/cancel'
    );
    expect(resp.status).toBe('cancelled');
  });

  it('isTerminalStatus 正确识别终态', () => {
    expect(isTerminalStatus('completed')).toBe(true);
    expect(isTerminalStatus('failed')).toBe(true);
    expect(isTerminalStatus('cancelled')).toBe(true);
    expect(isTerminalStatus('running')).toBe(false);
    expect(isTerminalStatus('pending')).toBe(false);
  });
});
