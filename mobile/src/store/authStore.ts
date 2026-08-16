// mobile/src/store/authStore.ts
// 认证状态管理

import { create } from 'zustand';
import { persist, createJSONStorage } from 'zustand/middleware';
import AsyncStorage from '@react-native-async-storage/async-storage';
import { AuthState, User } from '../types';
import * as SecureStore from 'expo-secure-store';
import { loginWithPassword, refreshWithToken } from '../services/authApi';
import {
  ACCESS_TOKEN_KEY,
  REFRESH_TOKEN_KEY,
} from '../services/authCredentials';

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
          const data = await loginWithPassword(email, password);
          const expiresAt = new Date(Date.now() + data.expiresIn * 1000);
          await SecureStore.setItemAsync(ACCESS_TOKEN_KEY, data.accessToken);
          await SecureStore.setItemAsync(REFRESH_TOKEN_KEY, data.refreshToken);

          set({
            isAuthenticated: true,
            user: data.user,
            token: data.accessToken,
            refreshToken: data.refreshToken,
            expiresAt,
            loading: false,
          });
        } catch (error) {
          set({ loading: false });
          throw error;
        }
      },

      logout: async () => {
        try {
          await SecureStore.deleteItemAsync(ACCESS_TOKEN_KEY);
          await SecureStore.deleteItemAsync(REFRESH_TOKEN_KEY);
          set({
            isAuthenticated: false,
            user: undefined,
            token: undefined,
            refreshToken: undefined,
            expiresAt: undefined,
          });
        } catch {
          set({ isAuthenticated: false });
        }
      },

      refreshAccessToken: async () => {
        try {
          const refreshToken = await SecureStore.getItemAsync(REFRESH_TOKEN_KEY);
          if (!refreshToken) throw new Error('No refresh token');

          const data = await refreshWithToken(refreshToken);
          const expiresAt = new Date(Date.now() + data.expiresIn * 1000);
          await SecureStore.setItemAsync(ACCESS_TOKEN_KEY, data.accessToken);

          set({
            token: data.accessToken,
            expiresAt,
          });
        } catch (error) {
          await get().logout();
          throw error;
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
