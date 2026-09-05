/**
 * Tauri 桌面环境适配层（2026-09-06）。
 *
 * 主 React 前端打包进 Tauri 壳（desktop/tauri.conf.json 的 distDir 指向
 * frontend/dist）后，浏览器语义的相对 API 路径（/api/v1）不再可用——
 * 桌面壳里没有同源后端。本模块检测 Tauri 环境并提供后端地址：
 *
 * 优先级：localStorage 覆盖（用户在设置里改过） > Tauri 桌面配置
 * （Rust 侧 config.rs 的 backend_url，默认 http://localhost:8000）> 相对路径
 * （纯浏览器模式，沿用 vite devServer 代理/反代部署）。
 *
 * Tauri invoke 的调用是异步的，而 axios 实例在模块加载期构造——所以这里
 * 同步返回缓存值，后台异步刷新一次（下次页面加载生效）。桌面首次启动的
 * 默认值与 Rust 侧一致，不需要等待。
 */

const TAURI_BACKEND_KEY = 'xagent_backend_url';

interface TauriBridge {
  __TAURI__?: {
    invoke?: (cmd: string, args?: Record<string, unknown>) => Promise<unknown>;
  };
}

/** 是否运行在 Tauri 桌面壳内。 */
export function isTauri(): boolean {
  const w = globalThis as unknown as TauriBridge;
  return Boolean(w.__TAURI__?.invoke);
}

/**
 * 解析 API base URL。同步、无副作用，任何环境可安全调用。
 */
export function resolveApiBaseUrl(): string {
  if (typeof window === 'undefined') return '/api/v1';
  if (!isTauri()) return '/api/v1';
  try {
    const override = window.localStorage.getItem(TAURI_BACKEND_KEY);
    if (override) return override;
  } catch {
    /* localStorage 不可用（隐私模式等）——回落默认 */
  }
  return 'http://localhost:8000/api/v1';
}

/**
 * Tauri 环境下从桌面配置（Rust 侧 get_backend_config 命令）刷新后端地址，
 * 写入 localStorage 缓存。非 Tauri 环境为无操作。
 */
export async function refreshTauriBackendConfig(): Promise<void> {
  if (!isTauri()) return;
  try {
    const w = globalThis as unknown as TauriBridge;
    const config = (await w.__TAURI__?.invoke?.('get_backend_config')) as
      | { backend_url?: string; backend_port?: number }
      | undefined;
    const url = config?.backend_url?.trim();
    if (url) {
      const base = `${url.replace(/\/+$/, '')}:${config?.backend_port ?? 8000}`;
      window.localStorage.setItem(TAURI_BACKEND_KEY, `${base}/api/v1`);
    }
  } catch {
    /* 桌面命令不可用（旧版本壳）——保持默认，不阻断前端 */
  }
}

// 模块加载时后台刷新一次（下次加载生效），不阻塞当前渲染
void refreshTauriBackendConfig();
