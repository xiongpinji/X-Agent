// mobile/src/store/authStore.ts
// 认证状态管理

import { create } from 'zustand';
import { persist, createJSONStorage } from 'zustand/middleware';
import AsyncStorage from '@react-native-async-storage/async-storage';
import { AuthState, User } from '../types';
import * as SecureStore from 'expo-secure-store';
import { getApiConfig } from '../config/env';

// 登录契约对齐 backend/app/api/auth.py:
//   POST /api/v1/auth/login   body {email, password}
//     → AuthTokenResponse {access_token, refresh_token, expires_in, token_type, user}
//   POST /api/v1/auth/refresh (Authorization: Bearer <refresh_token>)
//     → {access_token, token_type, expires_in}

interface AuthStore extends AuthState {
  loading: boolean;

  // Actions
  login: (email: string, password: string) => Promise<void>;
  logout: () => Promise<void>;
  refreshAccessToken: () => Promise<void>;
  enableBiometric: () => Promise<void>;
  disableBiometric: () => Promise<void>;
  setUser: (user: User) => void;
  setToken: (token: string, refreshToken: string, expiresAt: Date) => void;
}

export const useAuthStore = create<AuthStore>()(
  persist(
    (set, get) => ({
      isAuthenticated: false,
      biometricEnabled: false,
      loading: false,

      login: async (email: string, password: string) => {
        set({ loading: true });
        try {
          const { baseUrl } = await getApiConfig();
          const response = await fetch(`${baseUrl}/api/v1/auth/login`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ email, password }),
          });

          if (!response.ok) {
            const detail = await response.text().catch(() => '');
            throw new Error(
              `Login failed with status ${response.status}${detail ? `: ${detail.slice(0, 200)}` : ''}`
            );
          }

          // AuthTokenResponse: {access_token, refresh_token, expires_in, token_type, user}
          const data = await response.json();

          // 安全存储 token
          await SecureStore.setItemAsync('token', data.access_token);
          await SecureStore.setItemAsync('refreshToken', data.refresh_token);

          set({
            isAuthenticated: true,
            user: data.user,
            token: data.access_token,
            refreshToken: data.refresh_token,
            expiresAt: new Date(Date.now() + (data.expires_in ?? 900) * 1000),
            loading: false,
          });
        } catch (error) {
          set({ loading: false });
          console.error('Login error:', error);
          throw error;
        }
      },

      logout: async () => {
        try {
          await SecureStore.deleteItemAsync('token');
          await SecureStore.deleteItemAsync('refreshToken');
          set({
            isAuthenticated: false,
            user: undefined,
            token: undefined,
            refreshToken: undefined,
            expiresAt: undefined,
          });
        } catch (error) {
          console.error('Logout error:', error);
        }
      },

      refreshAccessToken: async () => {
        try {
          const refreshToken = await SecureStore.getItemAsync('refreshToken');
          if (!refreshToken) throw new Error('No refresh token');

          const { baseUrl } = await getApiConfig();
          const response = await fetch(`${baseUrl}/api/v1/auth/refresh`, {
            method: 'POST',
            headers: {
              'Content-Type': 'application/json',
              // 后端 refresh 端点通过认证主体鉴权，refresh token 作为 Bearer 凭证
              Authorization: `Bearer ${refreshToken}`,
            },
          });

          if (!response.ok) {
            const detail = await response.text().catch(() => '');
            throw new Error(
              `Token refresh failed with status ${response.status}${detail ? `: ${detail.slice(0, 200)}` : ''}`
            );
          }

          // {access_token, token_type, expires_in}
          const data = await response.json();
          await SecureStore.setItemAsync('token', data.access_token);

          set({
            token: data.access_token,
            expiresAt: new Date(Date.now() + (data.expires_in ?? 900) * 1000),
          });
        } catch (error) {
          console.error('Token refresh error:', error);
          get().logout();
        }
      },

      enableBiometric: async () => {
        set({ biometricEnabled: true });
      },

      disableBiometric: async () => {
        set({ biometricEnabled: false });
      },

      setUser: (user: User) => {
        set({ user });
      },

      setToken: (token: string, refreshToken: string, expiresAt: Date) => {
        set({ token, refreshToken, expiresAt });
      },
    }),
    {
      name: 'auth-store',
      storage: createJSONStorage(() => AsyncStorage),
      partialize: (state) => ({
        isAuthenticated: state.isAuthenticated,
        user: state.user,
        biometricEnabled: state.biometricEnabled,
      }),
    }
  )
);
