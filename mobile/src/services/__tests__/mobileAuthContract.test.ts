import * as SecureStore from 'expo-secure-store';
import { afterEach, beforeEach, describe, expect, it, jest } from '@jest/globals';
import type { MockedFunction } from 'jest-mock';

jest.mock('expo-constants', () => ({
  __esModule: true,
  default: {
    expoConfig: { extra: { apiBaseUrl: 'https://mobile.example.test/root/' } },
  },
}));

import {
  ACCESS_TOKEN_KEY,
  API_KEY_KEY,
  REFRESH_TOKEN_KEY,
  loadAuthHeaders,
} from '../authCredentials';
import { loginWithPassword, refreshWithToken } from '../authApi';
import { buildApiUrl, MobileApiConfigurationError } from '../apiConfig';
import { apiClient } from '../apiClient';

const mockedGetItem = SecureStore.getItemAsync as MockedFunction<
  typeof SecureStore.getItemAsync
>;
const originalWebSocket = global.WebSocket;

describe('mobile authentication contract', () => {
  beforeEach(() => {
    jest.clearAllMocks();
    global.fetch = jest.fn() as unknown as typeof fetch;
  });

  afterEach(() => {
    global.WebSocket = originalWebSocket;
  });

  it('fails closed when the API base URL is missing', () => {
    expect(() => buildApiUrl('/api/v1/mobile/trigger', '')).toThrow(
      MobileApiConfigurationError
    );
  });

  it('uses bearer credentials before API-key fallback', async () => {
    mockedGetItem.mockImplementation(async (key) => {
      if (key === ACCESS_TOKEN_KEY) return 'bearer-token';
      if (key === API_KEY_KEY) return 'api-key';
      return null;
    });

    await expect(loadAuthHeaders()).resolves.toEqual({
      Authorization: 'Bearer bearer-token',
    });

    mockedGetItem.mockImplementation(async (key) =>
      key === API_KEY_KEY ? 'api-key' : null
    );
    await expect(loadAuthHeaders()).resolves.toEqual({
      'x-api-key': 'api-key',
    });
  });

  it('authenticates native WebSocket requests with headers', async () => {
    mockedGetItem.mockImplementation(async (key) =>
      key === ACCESS_TOKEN_KEY ? 'bearer-token' : null
    );
    const socket = {} as WebSocket;
    const websocketConstructor = jest.fn(() => socket);
    global.WebSocket = websocketConstructor as unknown as typeof WebSocket;

    await apiClient.connectWebSocket('/api/v1/mobile/ws?run_id=mob-1', jest.fn());

    expect(websocketConstructor).toHaveBeenCalledWith(
      'wss://mobile.example.test/root/api/v1/mobile/ws?run_id=mob-1',
      [],
      { headers: { Authorization: 'Bearer bearer-token' } }
    );
  });

  it('logs in through the mounted v1 endpoint and validates backend fields', async () => {
    (global.fetch as unknown as MockedFunction<typeof fetch>).mockResolvedValue({
      ok: true,
      json: async () => ({
        access_token: 'access-1',
        refresh_token: 'refresh-1',
        expires_in: 900,
        token_type: 'Bearer',
        user: {
          id: 'user-1',
          email: 'owner@example.test',
          display_name: 'Owner',
          role: 'admin',
        },
      }),
    } as Response);

    const response = await loginWithPassword(
      'owner@example.test',
      'StrongPass1'
    );

    expect(global.fetch).toHaveBeenCalledWith(
      'https://mobile.example.test/root/api/v1/auth/login',
      expect.objectContaining({
        method: 'POST',
        body: JSON.stringify({
          email: 'owner@example.test',
          password: 'StrongPass1',
        }),
      })
    );
    expect(response.accessToken).toBe('access-1');
    expect(response.refreshToken).toBe('refresh-1');
    expect(response.user).toEqual(
      expect.objectContaining({ name: 'Owner', roles: ['admin'] })
    );
  });

  it('refreshes with the refresh token as bearer authentication', async () => {
    (global.fetch as unknown as MockedFunction<typeof fetch>).mockResolvedValue({
      ok: true,
      json: async () => ({
        access_token: 'access-2',
        expires_in: 900,
        token_type: 'Bearer',
      }),
    } as Response);

    const response = await refreshWithToken('refresh-1');

    expect(global.fetch).toHaveBeenCalledWith(
      'https://mobile.example.test/root/api/v1/auth/refresh',
      expect.objectContaining({
        method: 'POST',
        headers: expect.objectContaining({
          Authorization: 'Bearer refresh-1',
        }),
      })
    );
    expect(response).toEqual({ accessToken: 'access-2', expiresIn: 900 });
    expect(REFRESH_TOKEN_KEY).toBe('refresh_token');
  });
});
