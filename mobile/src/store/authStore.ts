// mobile/src/store/authStore.ts
// 认证状态管理

import { create } from 'zustand';
import { persist, createJSONStorage } from 'zustand/middleware';
import AsyncStorage from '@react-native-async-storage/async-storage';
import { AuthState, User } from '../types';
import * as SecureStore from 'expo-secure-store';

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
          // 调用后端API
          const response = await fetch('https://api.xagent.local/auth/login', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ email, password }),
          });

          if (!response.ok) throw new Error('Login failed');

          const data = await response.json();

          // 安全存储token
          await SecureStore.setItemAsync('token', data.token);
          await SecureStore.setItemAsync('refreshToken', data.refreshToken);

          set({
            isAuthenticated: true,
            user: data.user,
            token: data.token,
            refreshToken: data.refreshToken,
            expiresAt: new Date(data.expiresAt),
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

          const response = await fetch('https://api.xagent.local/auth/refresh', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ refreshToken }),
          });

          if (!response.ok) throw new Error('Token refresh failed');

          const data = await response.json();
          await SecureStore.setItemAsync('token', data.token);

          set({
            token: data.token,
            expiresAt: new Date(data.expiresAt),
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
