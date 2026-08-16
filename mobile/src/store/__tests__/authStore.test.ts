import * as SecureStore from 'expo-secure-store';
import { beforeEach, describe, expect, it, jest } from '@jest/globals';
import type { MockedFunction } from 'jest-mock';

import { loginWithPassword, refreshWithToken } from '../../services/authApi';
import {
  ACCESS_TOKEN_KEY,
  REFRESH_TOKEN_KEY,
} from '../../services/authCredentials';
import { useAuthStore } from '../authStore';

jest.mock('../../services/authApi', () => ({
  loginWithPassword: jest.fn(),
  refreshWithToken: jest.fn(),
}));

const mockedLogin = loginWithPassword as MockedFunction<
  typeof loginWithPassword
>;
const mockedRefresh = refreshWithToken as MockedFunction<
  typeof refreshWithToken
>;
const mockedGetItem = SecureStore.getItemAsync as MockedFunction<
  typeof SecureStore.getItemAsync
>;

describe('authStore backend contract', () => {
  beforeEach(() => {
    jest.clearAllMocks();
    useAuthStore.setState({
      isAuthenticated: false,
      biometricEnabled: false,
      loading: false,
      user: undefined,
      token: undefined,
      refreshToken: undefined,
      expiresAt: undefined,
    });
  });

  it('stores validated login tokens under the shared credential keys', async () => {
    mockedLogin.mockResolvedValue({
      accessToken: 'access-1',
      refreshToken: 'refresh-1',
      expiresIn: 900,
      user: {
        id: 'user-1',
        email: 'owner@example.test',
        name: 'Owner',
        roles: ['admin'],
        permissions: [],
      },
    });

    await useAuthStore.getState().login('owner@example.test', 'StrongPass1');

    expect(SecureStore.setItemAsync).toHaveBeenCalledWith(
      ACCESS_TOKEN_KEY,
      'access-1'
    );
    expect(SecureStore.setItemAsync).toHaveBeenCalledWith(
      REFRESH_TOKEN_KEY,
      'refresh-1'
    );
    expect(useAuthStore.getState()).toEqual(
      expect.objectContaining({
        isAuthenticated: true,
        token: 'access-1',
        refreshToken: 'refresh-1',
      })
    );
  });

  it('refreshes through the backend contract without replacing the refresh token', async () => {
    mockedGetItem.mockResolvedValue('refresh-1');
    mockedRefresh.mockResolvedValue({ accessToken: 'access-2', expiresIn: 900 });

    await useAuthStore.getState().refreshAccessToken();

    expect(mockedRefresh).toHaveBeenCalledWith('refresh-1');
    expect(SecureStore.setItemAsync).toHaveBeenCalledWith(
      ACCESS_TOKEN_KEY,
      'access-2'
    );
    expect(useAuthStore.getState().token).toBe('access-2');
  });
});
