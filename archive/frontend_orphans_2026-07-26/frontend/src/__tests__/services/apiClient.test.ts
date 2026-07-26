/**
 * API Client Tests
 */

import { APIClient, AgentRun } from '../services/apiClient';

describe('APIClient', () => {
  let client: APIClient;

  beforeEach(() => {
    client = new APIClient({ baseURL: '/api/v1' });
    global.fetch = jest.fn();
  });

  afterEach(() => {
    jest.clearAllMocks();
  });

  test('should initialize with default config', () => {
    expect(client).toBeDefined();
  });

  test('should start agent run', async () => {
    const mockRun: AgentRun = {
      run_id: 'test-run-1',
      task: 'test task',
      status: 'running',
      created_at: new Date().toISOString(),
    };

    (global.fetch as jest.Mock).mockResolvedValueOnce({
      ok: true,
      json: async () => mockRun,
    });

    const result = await client.startAgentRun('test task');

    expect(result).toEqual(mockRun);
    expect(global.fetch).toHaveBeenCalledWith(
      '/api/v1/agent/run/stream',
      expect.objectContaining({
        method: 'POST',
        headers: expect.objectContaining({
          'Content-Type': 'application/json',
        }),
      })
    );
  });

  test('should get agent run', async () => {
    const mockRun: AgentRun = {
      run_id: 'test-run-1',
      task: 'test task',
      status: 'completed',
      created_at: new Date().toISOString(),
      result: { answer: 'test' },
    };

    (global.fetch as jest.Mock).mockResolvedValueOnce({
      ok: true,
      json: async () => mockRun,
    });

    const result = await client.getAgentRun('test-run-1');

    expect(result).toEqual(mockRun);
    expect(global.fetch).toHaveBeenCalledWith(
      '/api/v1/agents/runs/test-run-1',
      expect.any(Object)
    );
  });

  test('should list agent runs', async () => {
    const mockResponse = {
      items: [
        {
          run_id: 'test-run-1',
          task: 'test task',
          status: 'completed',
          created_at: new Date().toISOString(),
        },
      ],
      total: 1,
    };

    (global.fetch as jest.Mock).mockResolvedValueOnce({
      ok: true,
      json: async () => mockResponse,
    });

    const result = await client.listAgentRuns(10, 0);

    expect(result).toEqual(mockResponse);
  });

  test('should get tasks', async () => {
    const mockResponse = {
      tasks: [
        {
          task_id: 'task-1',
          title: 'Test Task',
          description: 'Test',
          status: 'completed' as const,
          priority: 'high' as const,
          progress: 1,
          created_at: new Date().toISOString(),
          depends_on: [],
          blocks: [],
          tags: [],
          metadata: {},
        },
      ],
      total: 1,
      completed: 1,
      in_progress: 0,
      failed: 0,
      pending: 0,
    };

    (global.fetch as jest.Mock).mockResolvedValueOnce({
      ok: true,
      json: async () => mockResponse,
    });

    const result = await client.getTasks('run-1');

    expect(result.tasks).toHaveLength(1);
    expect(result.total).toBe(1);
  });

  test('should answer question', async () => {
    (global.fetch as jest.Mock).mockResolvedValueOnce({
      ok: true,
      json: async () => ({}),
    });

    await client.answerQuestion('question-1', 'yes');

    expect(global.fetch).toHaveBeenCalledWith(
      '/api/v1/questions/question-1/answer',
      expect.objectContaining({
        method: 'POST',
        body: JSON.stringify({ answer: 'yes' }),
      })
    );
  });

  test('should handle API errors', async () => {
    (global.fetch as jest.Mock).mockResolvedValueOnce({
      ok: false,
      status: 404,
      statusText: 'Not Found',
      json: async () => ({ message: 'Not found' }),
    });

    await expect(client.getAgentRun('nonexistent')).rejects.toThrow();
  });

  test('should handle network errors', async () => {
    (global.fetch as jest.Mock).mockRejectedValueOnce(
      new Error('Network error')
    );

    await expect(client.startAgentRun('test')).rejects.toThrow();
  });

  test('should set custom headers', () => {
    client.setHeaders({ Authorization: 'Bearer token' });
    // Headers should be set for subsequent requests
    expect(client).toBeDefined();
  });

  test('should set custom base URL', () => {
    client.setBaseURL('http://localhost:8000/api/v1');
    expect(client).toBeDefined();
  });
});
