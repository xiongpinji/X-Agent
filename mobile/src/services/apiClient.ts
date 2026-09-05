// mobile/src/services/apiClient.ts
// API 客户端实现（fetch 版）
//
// 联调契约（对照 backend/app/）:
//   - 认证: `x-api-key` 请求头（backend/app/dependencies.py: get_current_principal
//     从 request.headers.get("x-api-key") 读取）；若本地存在会话 token（/api/v1/auth/login
//     签发）则同时附加 `Authorization: Bearer <token>`。
//   - base URL 来自 src/config/env.ts（app.json extra / EXPO_PUBLIC_API_BASE_URL /
//     默认 http://localhost:8000，Settings 屏可运行时覆盖）。
//   - API 路径自带 `/api/v1` 前缀（与 mobileRunService 等调用方约定一致）。
//   - 非 2xx 一律抛 ApiError（含 status/url/body），不静默假成功。

import * as SecureStore from 'expo-secure-store';
import { getApiConfig, buildWebSocketUrl } from '../config/env';
import { useAuthStore } from '../store/authStore';

export interface RequestOptions {
  body?: unknown;
  /** 追加到 URL 的 query 参数（axios 风格兼容） */
  params?: Record<string, unknown>;
  headers?: Record<string, string>;
}

/** 可诊断的 API 错误：携带 HTTP 状态码、请求 URL 与响应体片段 */
export class ApiError extends Error {
  readonly status?: number;
  readonly url: string;
  readonly body?: string;

  constructor(message: string, url: string, status?: number, body?: string) {
    super(message);
    this.name = 'ApiError';
    this.url = url;
    this.status = status;
    this.body = body;
  }
}

class ApiClient {
  private buildUrl(
    baseUrl: string,
    url: string,
    params?: Record<string, unknown>
  ): string {
    const path = url.startsWith('http')
      ? url
      : `${baseUrl}${url.startsWith('/') ? '' : '/'}${url}`;
    if (!params) return path;
    const qs = Object.entries(params)
      .filter(([, v]) => v !== undefined && v !== null && v !== '')
      .map(
        ([k, v]) =>
          `${encodeURIComponent(k)}=${encodeURIComponent(String(v))}`
      )
      .join('&');
    if (!qs) return path;
    return path.includes('?') ? `${path}&${qs}` : `${path}?${qs}`;
  }

  private async buildHeaders(
    apiKey: string | undefined,
    extra?: Record<string, string>
  ): Promise<Record<string, string>> {
    const headers: Record<string, string> = {
      'Content-Type': 'application/json',
      ...(extra ?? {}),
    };
    if (apiKey) {
      headers['x-api-key'] = apiKey;
    }
    const token = await SecureStore.getItemAsync('token').catch(() => null);
    if (token) {
      headers.Authorization = `Bearer ${token}`;
    }
    return headers;
  }

  async request<T>(
    method: string,
    url: string,
    options: RequestOptions = {},
    allowAuthRefresh = true
  ): Promise<T> {
    const { baseUrl, apiKey } = await getApiConfig();
    const fullUrl = this.buildUrl(baseUrl, url, options.params);
    const headers = await this.buildHeaders(apiKey, options.headers);

    let response: Response;
    try {
      response = await fetch(fullUrl, {
        method,
        headers,
        body: options.body === undefined ? undefined : JSON.stringify(options.body),
      });
    } catch (networkError) {
      // 网络层错误（无法连接后端）也包装为可诊断错误
      throw new ApiError(
        `Network error: ${String(networkError)} (URL: ${fullUrl})`,
        fullUrl
      );
    }

    // 401: 若存在会话 refresh token，尝试刷新后重试一次（后端 /api/v1/auth/refresh）
    if (response.status === 401 && allowAuthRefresh) {
      const refreshToken = await SecureStore.getItemAsync('refreshToken').catch(
        () => null
      );
      if (refreshToken) {
        try {
          await useAuthStore.getState().refreshAccessToken();
          return this.request<T>(method, url, options, false);
        } catch {
          useAuthStore.getState().logout();
          // 刷新失败落入下方统一错误抛出
        }
      }
    }

    if (!response.ok) {
      const bodyText = await response.text().catch(() => undefined);
      throw new ApiError(
        `API ${method} ${url} failed with status ${response.status}`,
        fullUrl,
        response.status,
        bodyText?.slice(0, 2000)
      );
    }

    if (response.status === 204) {
      return undefined as T;
    }
    const text = await response.text();
    if (!text) {
      return undefined as T;
    }
    try {
      return JSON.parse(text) as T;
    } catch {
      throw new ApiError(
        `API ${method} ${url} returned non-JSON body`,
        fullUrl,
        response.status,
        text.slice(0, 2000)
      );
    }
  }

  async get<T>(url: string, config?: RequestOptions): Promise<T> {
    return this.request<T>('GET', url, config);
  }

  async post<T>(url: string, data?: unknown, config?: RequestOptions): Promise<T> {
    return this.request<T>('POST', url, { ...config, body: data });
  }

  async put<T>(url: string, data?: unknown, config?: RequestOptions): Promise<T> {
    return this.request<T>('PUT', url, { ...config, body: data });
  }

  async patch<T>(url: string, data?: unknown, config?: RequestOptions): Promise<T> {
    return this.request<T>('PATCH', url, { ...config, body: data });
  }

  async delete<T>(url: string, config?: RequestOptions): Promise<T> {
    return this.request<T>('DELETE', url, config);
  }

  // WebSocket 连接（后端示例: /api/v1/mobile/ws?run_id=...，见 backend/app/api/mobile.py）
  // 注意: base URL 需异步读取（SecureStore 覆盖），故签名为 Promise<WebSocket>。
  async connectWebSocket(
    path: string,
    onMessage: (data: unknown) => void
  ): Promise<WebSocket> {
    const { baseUrl } = await getApiConfig();
    const ws = new WebSocket(buildWebSocketUrl(baseUrl, path));

    ws.onopen = () => {
      console.log('WebSocket connected');
    };

    ws.onmessage = (event) => {
      try {
        const data = JSON.parse(event.data);
        onMessage(data);
      } catch (error) {
        console.error('WebSocket message parse error:', error);
      }
    };

    ws.onerror = (error) => {
      console.error('WebSocket error:', error);
    };

    ws.onclose = () => {
      console.log('WebSocket disconnected');
    };

    return ws;
  }
}

export const apiClient = new ApiClient();
