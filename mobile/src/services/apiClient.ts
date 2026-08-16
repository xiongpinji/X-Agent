// mobile/src/services/apiClient.ts
// API客户端实现

import axios, { AxiosInstance, AxiosError } from 'axios';
import * as SecureStore from 'expo-secure-store';
import { useAuthStore } from '../store/authStore';
import { buildWebSocketUrl, getApiBaseUrl } from './apiConfig';
import { ACCESS_TOKEN_KEY, loadAuthHeaders } from './authCredentials';

class ApiClient {
  private client: AxiosInstance;
  private isRefreshing = false;
  private failedQueue: Array<{
    resolve: (value: any) => void;
    reject: (reason?: any) => void;
  }> = [];

  constructor() {
    this.client = axios.create({
      timeout: 30000,
      headers: {
        'Content-Type': 'application/json',
      },
    });

    // 请求拦截器
    this.client.interceptors.request.use(
      async (config) => {
        config.baseURL = getApiBaseUrl();
        Object.assign(config.headers, await loadAuthHeaders());
        return config;
      },
      (error) => Promise.reject(error)
    );

    // 响应拦截器
    this.client.interceptors.response.use(
      (response) => response.data,
      async (error: AxiosError) => {
        const originalRequest = error.config as any;

        if (error.response?.status === 401 && !originalRequest._retry) {
          if (this.isRefreshing) {
            return new Promise((resolve, reject) => {
              this.failedQueue.push({ resolve, reject });
            })
              .then((token) => {
                originalRequest.headers.Authorization = `Bearer ${token}`;
                return this.client(originalRequest);
              })
              .catch((err) => Promise.reject(err));
          }

          originalRequest._retry = true;
          this.isRefreshing = true;

          try {
            await useAuthStore.getState().refreshAccessToken();
            const token = await SecureStore.getItemAsync(ACCESS_TOKEN_KEY);

            this.failedQueue.forEach((prom) => prom.resolve(token));
            this.failedQueue = [];

            originalRequest.headers.Authorization = `Bearer ${token}`;
            return this.client(originalRequest);
          } catch (err) {
            this.failedQueue.forEach((prom) => prom.reject(err));
            this.failedQueue = [];
            useAuthStore.getState().logout();
            return Promise.reject(err);
          } finally {
            this.isRefreshing = false;
          }
        }

        return Promise.reject(error);
      }
    );
  }

  async get<T>(url: string, config?: any): Promise<T> {
    // 响应拦截器已将 AxiosResponse 解包为 data，这里按解包后的类型返回
    return this.client.get<T>(url, config) as unknown as Promise<T>;
  }

  async post<T>(url: string, data?: any, config?: any): Promise<T> {
    return this.client.post<T>(url, data, config) as unknown as Promise<T>;
  }

  async put<T>(url: string, data?: any, config?: any): Promise<T> {
    return this.client.put<T>(url, data, config) as unknown as Promise<T>;
  }

  async patch<T>(url: string, data?: any, config?: any): Promise<T> {
    return this.client.patch<T>(url, data, config) as unknown as Promise<T>;
  }

  async delete<T>(url: string, config?: any): Promise<T> {
    return this.client.delete<T>(url, config) as unknown as Promise<T>;
  }

  // WebSocket连接
  async connectWebSocket(
    path: string,
    onMessage: (data: any) => void
  ): Promise<WebSocket> {
    const headers = await loadAuthHeaders();
    const NativeWebSocket = WebSocket as unknown as new (
      uri: string,
      protocols: string[],
      options: { headers: Record<string, string> }
    ) => WebSocket;
    const ws = new NativeWebSocket(buildWebSocketUrl(path), [], { headers });

    ws.onmessage = (event) => {
      try {
        const data = JSON.parse(event.data);
        onMessage(data);
      } catch {}
    };

    return ws;
  }
}

export const apiClient = new ApiClient();
