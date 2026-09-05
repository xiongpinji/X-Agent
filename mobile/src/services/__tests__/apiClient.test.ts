// mobile/src/services/__tests__/apiClient.test.ts
// apiClient 契约测试（mock expo-secure-store / fetch）:
//   - 认证头: x-api-key（后端 backend/app/dependencies.py 契约）+ 可选 Bearer token
//   - 端点契约: 断言最终 URL / method / body / headers
//   - 非 2xx 抛 ApiError（可诊断），不静默假成功

import { describe, it, expect, beforeEach, jest } from '@jest/globals';
import * as SecureStore from 'expo-secure-store';

// authStore 依赖 zustand persist + AsyncStorage，此处仅 mock 401 刷新所需接口
const mockRefreshAccessToken = jest.fn(() => Promise.resolve());
const mockLogout = jest.fn(() => Promise.resolve());
jest.mock('../../store/authStore', () => ({
  useAuthStore: {
    getState: () => ({
      refreshAccessToken: mockRefreshAccessToken,
      logout: mockLogout,
    }),
  },
}));

import { apiClient, ApiError } from '../apiClient';
import { API_KEY_STORAGE_KEY, DEFAULT_API_BASE_URL } from '../../config/env';

const mockedGetItem = jest.mocked(SecureStore.getItemAsync);

/** 内存版 SecureStore + mock fetch */
type FetchLike = (url: string, init: Record<string, any>) => Promise<any>;
const mockFetch = jest.fn<FetchLike>();
(global as any).fetch = mockFetch;

function setStore(entries: Record<string, string | null>): void {
  const map = new Map(Object.entries(entries));
  mockedGetItem.mockImplementation(async (key: string) => map.get(key) ?? null);
}

function okResponse(body: unknown, status = 200) {
  return {
    ok: status >= 200 && status < 300,
    status,
    text: async () => (body === undefined ? '' : JSON.stringify(body)),
  };
}

describe('apiClient', () => {
  beforeEach(() => {
    jest.resetAllMocks();
    (global as any).fetch = mockFetch;
    setStore({});
  });
  describe('认证头 (x-api-key 契约)', () => {
    it('SecureStore 存有 xagent_api_key 时附带 x-api-key 头', async () => {
      setStore({ [API_KEY_STORAGE_KEY]: 'sk-test-key' });
      mockFetch.mockResolvedValueOnce(okResponse({ status: 'running' }));

      await apiClient.get('/api/v1/mobile/runs/r1/status');

      expect(mockFetch).toHaveBeenCalledTimes(1);
      const [url, init] = mockFetch.mock.calls[0];
      expect(url).toBe(
        `${DEFAULT_API_BASE_URL}/api/v1/mobile/runs/r1/status`
      );
      expect(init.method).toBe('GET');
      expect(init.headers['x-api-key']).toBe('sk-test-key');
      expect(init.headers['Content-Type']).toBe('application/json');
      expect(init.headers.Authorization).toBeUndefined();
    });

    it('同时存在会话 token 时附带 Authorization Bearer 头', async () => {
      setStore({
        [API_KEY_STORAGE_KEY]: 'sk-test-key',
        token: 'xag-session-token',
      });
      mockFetch.mockResolvedValueOnce(okResponse({}));

      await apiClient.get('/api/v1/agents/stats');

      const [, init] = mockFetch.mock.calls[0];
      expect(init.headers['x-api-key']).toBe('sk-test-key');
      expect(init.headers.Authorization).toBe('Bearer xag-session-token');
    });

    it('无任何凭据时不发送认证头', async () => {
      mockFetch.mockResolvedValueOnce(okResponse({}));
      await apiClient.get('/health');
      const [, init] = mockFetch.mock.calls[0];
      expect(init.headers['x-api-key']).toBeUndefined();
      expect(init.headers.Authorization).toBeUndefined();
    });
  });

  describe('端点契约 (URL/method/body/headers)', () => {
    it('POST /api/v1/agents/run: task 请求体 JSON 序列化（backend/app/api/agents.py 契约）', async () => {
      setStore({ [API_KEY_STORAGE_KEY]: 'sk-agent' });
      mockFetch.mockResolvedValueOnce(
        okResponse({ trace_id: 't-1', status: 'completed' })
      );

      const result = await apiClient.post('/api/v1/agents/run', {
        task: 'Summarize the repo',
        permission_scope: ['tools:read'],
      });

      const [url, init] = mockFetch.mock.calls[0];
      expect(url).toBe(`${DEFAULT_API_BASE_URL}/api/v1/agents/run`);
      expect(init.method).toBe('POST');
      expect(init.headers['x-api-key']).toBe('sk-agent');
      expect(JSON.parse(init.body)).toEqual({
        task: 'Summarize the repo',
        permission_scope: ['tools:read'],
      });
      expect(result).toEqual({ trace_id: 't-1', status: 'completed' });
    });

    it('params 序列化为 query string（limit/offset 分页契约）', async () => {
      mockFetch.mockResolvedValueOnce(okResponse({ tasks: [], total: 0 }));

      await apiClient.get('/api/v1/tasks', {
        params: { limit: 20, offset: 40 },
      });

      const [url] = mockFetch.mock.calls[0];
      expect(url).toBe(`${DEFAULT_API_BASE_URL}/api/v1/tasks?limit=20&offset=40`);
    });

    it('DELETE 204 无内容时返回 undefined', async () => {
      mockFetch.mockResolvedValueOnce({
        ok: true,
        status: 204,
        text: async () => '',
      });

      const result = await apiClient.delete('/api/v1/tasks/t-1');
      expect(result).toBeUndefined();
      const [, init] = mockFetch.mock.calls[0];
      expect(init.method).toBe('DELETE');
    });
  });

  describe('错误处理（可诊断，不静默假成功）', () => {
    it('非 2xx 抛 ApiError，携带 status/url/body', async () => {
      mockFetch.mockResolvedValueOnce({
        ok: false,
        status: 500,
        text: async () => JSON.stringify({ error: { code: 'INTERNAL' } }),
      });

      await expect(
        apiClient.get('/api/v1/workflows/wf-1')
      ).rejects.toMatchObject({
        name: 'ApiError',
        status: 500,
        url: `${DEFAULT_API_BASE_URL}/api/v1/workflows/wf-1`,
        body: expect.stringContaining('INTERNAL'),
      });
    });

    it('网络错误包装为 ApiError 并包含 URL', async () => {
      mockFetch.mockRejectedValue(new Error('connect ECONNREFUSED'));

      let caught: unknown;
      try {
        await apiClient.get('/health');
      } catch (e) {
        caught = e;
      }

      expect(caught).toBeInstanceOf(ApiError);
      expect((caught as ApiError).message).toContain('ECONNREFUSED');
      expect((caught as ApiError).url).toBe(`${DEFAULT_API_BASE_URL}/health`);
      expect((caught as ApiError).status).toBeUndefined();
    });

    it('401 且有 refresh token: 刷新后重试一次', async () => {
      setStore({ token: 'stale-token', refreshToken: 'refresh-1' });
      mockFetch
        .mockResolvedValueOnce({ ok: false, status: 401, text: async () => '' })
        .mockResolvedValueOnce(okResponse({ ok: true }));

      const result = await apiClient.get('/api/v1/agents/runs');

      expect(result).toEqual({ ok: true });
      expect(mockRefreshAccessToken).toHaveBeenCalledTimes(1);
      expect(mockFetch).toHaveBeenCalledTimes(2);
    });

    it('401 且无 refresh token: 直接抛 ApiError(401)', async () => {
      mockFetch.mockResolvedValueOnce({
        ok: false,
        status: 401,
        text: async () => JSON.stringify({ error: { code: 'AUTHENTICATION_FAILED' } }),
      });

      await expect(apiClient.get('/api/v1/agents/stats')).rejects.toMatchObject({
        name: 'ApiError',
        status: 401,
      });
      expect(mockRefreshAccessToken).not.toHaveBeenCalled();
    });
  });
});
