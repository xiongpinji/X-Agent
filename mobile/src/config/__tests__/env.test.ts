// mobile/src/config/__tests__/env.test.ts
// 配置解析优先级测试:
//   SecureStore 覆盖 > app.json extra.apiBaseUrl > EXPO_PUBLIC_API_BASE_URL > 默认 http://localhost:8000

import { describe, it, expect, beforeEach, afterEach, jest } from '@jest/globals';
import Constants from 'expo-constants';
import * as SecureStore from 'expo-secure-store';

jest.mock('expo-constants', () => {
  const mod: { expoConfig?: any; __setExpoConfig: (v: any) => void } = {
    expoConfig: undefined,
    __setExpoConfig: (v: any) => {
      mod.expoConfig = v;
    },
  };
  return { __esModule: true, default: mod };
});

import {
  resolveApiBaseUrl,
  getApiConfig,
  saveApiConfig,
  clearApiConfig,
  buildWebSocketUrl,
  API_KEY_STORAGE_KEY,
  BASE_URL_STORAGE_KEY,
  DEFAULT_API_BASE_URL,
} from '../env';

const mockedGetItem = jest.mocked(SecureStore.getItemAsync);
const mockedSetItem = jest.mocked(SecureStore.setItemAsync);
const mockedDeleteItem = jest.mocked(SecureStore.deleteItemAsync);

/**
 * babel-preset-expo 会把 `delete process.env.EXPO_PUBLIC_*` 重写为 `delete undefined;`
 * （点号与方括号形式都会被破坏），必须用 Reflect.deleteProperty 清理测试间状态。
 */
function clearEnvVar(): void {
  Reflect.deleteProperty(process.env, 'EXPO_PUBLIC_API_BASE_URL');
}

/** 内存版 SecureStore */
function setStore(entries: Record<string, string | null>): void {
  const map = new Map(Object.entries(entries));
  mockedGetItem.mockImplementation(async (key: string) => map.get(key) ?? null);
}

describe('env 配置解析', () => {
  beforeEach(() => {
    jest.resetAllMocks();
    (Constants as any).__setExpoConfig(undefined);
    clearEnvVar();
    setStore({});
  });

  afterEach(() => {
    clearEnvVar();
  });

  describe('resolveApiBaseUrl 静态优先级', () => {
    it('无任何配置时回落默认 http://localhost:8000', () => {
      expect(resolveApiBaseUrl()).toBe('http://localhost:8000');
    });

    it('app.json extra.apiBaseUrl (expo-constants) 优先于环境变量与默认值', () => {
      (Constants as any).__setExpoConfig({
        extra: { apiBaseUrl: 'https://extra.example.com' },
      });
      process.env.EXPO_PUBLIC_API_BASE_URL = 'https://env.example.com';
      expect(resolveApiBaseUrl()).toBe('https://extra.example.com');
    });

    it('extra 缺失时使用环境变量 EXPO_PUBLIC_API_BASE_URL', () => {
      process.env.EXPO_PUBLIC_API_BASE_URL = 'https://env.example.com';
      expect(resolveApiBaseUrl()).toBe('https://env.example.com');
    });

    it('extra 为空白字符串时跳过，回落环境变量', () => {
      (Constants as any).__setExpoConfig({ extra: { apiBaseUrl: '   ' } });
      process.env.EXPO_PUBLIC_API_BASE_URL = 'https://env.example.com';
      expect(resolveApiBaseUrl()).toBe('https://env.example.com');
    });

    it('去除尾部斜杠', () => {
      (Constants as any).__setExpoConfig({
        extra: { apiBaseUrl: 'https://extra.example.com/' },
      });
      expect(resolveApiBaseUrl()).toBe('https://extra.example.com');
    });
  });

  describe('getApiConfig 运行时优先级', () => {
    it('SecureStore 用户覆盖 (xagent_base_url) 优先于 app.json extra', async () => {
      (Constants as any).__setExpoConfig({
        extra: { apiBaseUrl: 'https://extra.example.com' },
      });
      setStore({ [BASE_URL_STORAGE_KEY]: 'http://192.168.1.10:8000' });

      const config = await getApiConfig();
      expect(config.baseUrl).toBe('http://192.168.1.10:8000');
    });

    it('无覆盖时回落静态解析（extra）', async () => {
      (Constants as any).__setExpoConfig({
        extra: { apiBaseUrl: 'https://extra.example.com' },
      });
      const config = await getApiConfig();
      expect(config.baseUrl).toBe('https://extra.example.com');
    });

    it('从 SecureStore 读取 API key (xagent_api_key)', async () => {
      setStore({ [API_KEY_STORAGE_KEY]: 'sk-live-123' });
      const config = await getApiConfig();
      expect(config.apiKey).toBe('sk-live-123');
    });

    it('未配置 API key 时为 undefined', async () => {
      const config = await getApiConfig();
      expect(config.apiKey).toBeUndefined();
      expect(config.baseUrl).toBe(DEFAULT_API_BASE_URL);
    });
  });

  describe('saveApiConfig / clearApiConfig', () => {
    it('保存 base URL 与 API key 到 SecureStore', async () => {
      await saveApiConfig({
        baseUrl: 'https://override.example.com',
        apiKey: 'sk-new',
      });

      expect(mockedSetItem).toHaveBeenCalledWith(
        BASE_URL_STORAGE_KEY,
        'https://override.example.com'
      );
      expect(mockedSetItem).toHaveBeenCalledWith(API_KEY_STORAGE_KEY, 'sk-new');
    });

    it('空字符串表示清除对应项', async () => {
      await saveApiConfig({ baseUrl: '', apiKey: '' });
      expect(mockedDeleteItem).toHaveBeenCalledWith(BASE_URL_STORAGE_KEY);
      expect(mockedDeleteItem).toHaveBeenCalledWith(API_KEY_STORAGE_KEY);
    });

    it('clearApiConfig 同时清除两项', async () => {
      await clearApiConfig();
      expect(mockedDeleteItem).toHaveBeenCalledWith(BASE_URL_STORAGE_KEY);
      expect(mockedDeleteItem).toHaveBeenCalledWith(API_KEY_STORAGE_KEY);
    });
  });

  describe('buildWebSocketUrl', () => {
    it('http → ws, https → wss，并拼接 path', () => {
      expect(buildWebSocketUrl('http://localhost:8000', '/api/v1/mobile/ws')).toBe(
        'ws://localhost:8000/api/v1/mobile/ws'
      );
      expect(buildWebSocketUrl('https://api.example.com', 'api/v1/mobile/ws')).toBe(
        'wss://api.example.com/api/v1/mobile/ws'
      );
    });
  });
});
