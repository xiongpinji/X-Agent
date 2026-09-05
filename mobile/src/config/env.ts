// mobile/src/config/env.ts
// API 运行时配置解析。
//
// API_BASE_URL 解析优先级（高 → 低）:
//   1. SecureStore 用户覆盖 (key: xagent_base_url) —— Settings 屏保存的运行时设置
//   2. expo-constants 读取的 app.json `expo.extra.apiBaseUrl`
//   3. 环境变量 EXPO_PUBLIC_API_BASE_URL (EAS/CI 注入)
//   4. 默认值 http://localhost:8000 (本地 FastAPI 后端)
//
// API_KEY 始终从 SecureStore 异步读取 (key: xagent_api_key)，不落入 app.json / 环境变量，
// 避免密钥进入版本库。后端通过 `x-api-key` 请求头认证 (backend/app/dependencies.py)。

import Constants from 'expo-constants';
import * as SecureStore from 'expo-secure-store';

/** SecureStore 中 API key 的存储名 */
export const API_KEY_STORAGE_KEY = 'xagent_api_key';

/** SecureStore 中用户覆盖 base URL 的存储名（Settings 屏写入） */
export const BASE_URL_STORAGE_KEY = 'xagent_base_url';

/** EXPO_PUBLIC_ 环境变量名（EAS/CI 注入，babel-preset-expo 编译期内联进 bundle） */
export const API_BASE_URL_ENV_VAR = 'EXPO_PUBLIC_API_BASE_URL';

/** 默认后端地址：本地 FastAPI (backend/app/main.py) */
export const DEFAULT_API_BASE_URL = 'http://localhost:8000';

export interface ApiConfig {
  /** 后端根地址，不含尾斜杠，如 http://localhost:8000。路径需自带 /api/v1 前缀。 */
  baseUrl: string;
  /** x-api-key 认证密钥；未配置时为 undefined（匿名主体，仅当后端 require_api_key=false 时可用） */
  apiKey?: string;
}

function sanitizeBaseUrl(url: string): string {
  return url.trim().replace(/\/+$/, '');
}

function isNonEmptyString(value: unknown): value is string {
  return typeof value === 'string' && value.trim().length > 0;
}

/**
 * 静态解析 base URL（不含 SecureStore 覆盖），优先级:
 * app.json extra.apiBaseUrl → EXPO_PUBLIC_API_BASE_URL → 默认值。
 * 每次调用重新解析（不缓存），保证测试与热更新下的可变性。
 */
export function resolveApiBaseUrl(): string {
  // 1. app.json → expo.extra.apiBaseUrl（经 expo-constants 注入）
  const fromExtra = (Constants.expoConfig as any)?.extra?.apiBaseUrl;
  if (isNonEmptyString(fromExtra)) {
    return sanitizeBaseUrl(fromExtra);
  }

  // 2. 环境变量。分两级读取：
  //    a) 编译期内联引用——Expo 生产构建由 babel-preset-expo 将
  //       process.env.EXPO_PUBLIC_* 替换为构建时字面量；
  //    b) 运行时动态读取（globalThis.process.env）——服务 Node/jest 环境
  //       （babel 在测试转换中会把它内联成 undefined，故运行时再查一次）。
  const inlinedEnvUrl = process.env.EXPO_PUBLIC_API_BASE_URL;
  if (isNonEmptyString(inlinedEnvUrl)) {
    return sanitizeBaseUrl(inlinedEnvUrl);
  }
  const runtimeEnv = (globalThis as { process?: { env?: Record<string, string | undefined> } })
    .process?.env;
  const fromRuntimeEnv = runtimeEnv?.[API_BASE_URL_ENV_VAR];
  if (isNonEmptyString(fromRuntimeEnv)) {
    return sanitizeBaseUrl(fromRuntimeEnv);
  }

  // 3. 默认值
  return DEFAULT_API_BASE_URL;
}

/**
 * 读取完整 API 配置。SecureStore 中的用户覆盖（Settings 屏保存）优先于静态解析结果。
 */
export async function getApiConfig(): Promise<ApiConfig> {
  const [savedBaseUrl, apiKey] = await Promise.all([
    SecureStore.getItemAsync(BASE_URL_STORAGE_KEY).catch(() => null),
    SecureStore.getItemAsync(API_KEY_STORAGE_KEY).catch(() => null),
  ]);

  return {
    baseUrl: isNonEmptyString(savedBaseUrl)
      ? sanitizeBaseUrl(savedBaseUrl)
      : resolveApiBaseUrl(),
    apiKey: isNonEmptyString(apiKey) ? apiKey.trim() : undefined,
  };
}

/**
 * 保存运行时配置到 SecureStore（Settings 屏调用）。
 * 传空字符串/undefined 表示清除对应项（baseUrl=null 清除后回落静态解析；apiKey=null 清除认证）。
 */
export async function saveApiConfig(input: {
  baseUrl?: string | null;
  apiKey?: string | null;
}): Promise<void> {
  const ops: Promise<void>[] = [];

  if (input.baseUrl !== undefined) {
    ops.push(
      isNonEmptyString(input.baseUrl)
        ? SecureStore.setItemAsync(BASE_URL_STORAGE_KEY, sanitizeBaseUrl(input.baseUrl))
        : SecureStore.deleteItemAsync(BASE_URL_STORAGE_KEY)
    );
  }

  if (input.apiKey !== undefined) {
    ops.push(
      isNonEmptyString(input.apiKey)
        ? SecureStore.setItemAsync(API_KEY_STORAGE_KEY, input.apiKey.trim())
        : SecureStore.deleteItemAsync(API_KEY_STORAGE_KEY)
    );
  }

  await Promise.all(ops);
}

/** 清除全部运行时 API 配置 */
export async function clearApiConfig(): Promise<void> {
  await Promise.all([
    SecureStore.deleteItemAsync(BASE_URL_STORAGE_KEY),
    SecureStore.deleteItemAsync(API_KEY_STORAGE_KEY),
  ]);
}

/** 将 HTTP base URL 转为 WebSocket URL（http→ws, https→wss）并拼接 path */
export function buildWebSocketUrl(baseUrl: string, path: string): string {
  const wsBase = baseUrl.replace(/^http:\/\//i, 'ws://').replace(/^https:\/\//i, 'wss://');
  const suffix = path.startsWith('/') ? path : `/${path}`;
  return `${wsBase}${suffix}`;
}
