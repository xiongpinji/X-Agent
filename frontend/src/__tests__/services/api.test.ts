/**
 * API client request-interceptor tests
 *
 * Covers the fix from commit d102fc0 ("fix(frontend): API key 登录死循环——
 * 请求拦截器补发 x-api-key 头"): when the user signs in with a dev API key
 * (no JWT), requests MUST still carry the x-api-key header, otherwise every
 * request goes out anonymous, the backend answers 401 and the response
 * interceptor bounces the user back to /login in an infinite loop.
 *
 * The interceptor is exercised directly through the axios handler chain, so
 * no network is involved.
 */

import { describe, it, expect, beforeEach } from 'vitest'
import apiClient from '@/services/api'
import type { AxiosInstance, InternalAxiosRequestConfig } from 'axios'

/**
 * Extract the registered request interceptor's fulfillment fn from the
 * underlying axios instance of the singleton client.
 */
// The interceptor under test is synchronous; assert the sync-only signature.
function requestInterceptor(): (config: InternalAxiosRequestConfig) => InternalAxiosRequestConfig {
  const handlers = (
    apiClient as unknown as { client: AxiosInstance }
  ).client.interceptors.request.handlers as unknown as Array<{
    fulfilled: (config: InternalAxiosRequestConfig) => InternalAxiosRequestConfig
  }>
  return handlers[0].fulfilled
}

function runInterceptor() {
  return requestInterceptor()({ headers: {} } as InternalAxiosRequestConfig)
}

describe('apiClient request interceptor', () => {
  beforeEach(() => {
    localStorage.clear()
  })

  it('attaches x-api-key when only the dev API key is stored (d102fc0 regression)', () => {
    localStorage.setItem('api_key', 'xk-dev-secret')

    const config = runInterceptor()

    expect(config.headers['x-api-key']).toBe('xk-dev-secret')
    expect(config.headers.Authorization).toBeUndefined()
  })

  it('attaches BOTH Bearer and x-api-key when both credentials exist', () => {
    localStorage.setItem('auth_token', 'jwt-abc-123')
    localStorage.setItem('api_key', 'xk-dev-secret')

    const config = runInterceptor()

    expect(config.headers.Authorization).toBe('Bearer jwt-abc-123')
    expect(config.headers['x-api-key']).toBe('xk-dev-secret')
  })

  it('attaches only Authorization when only the JWT exists', () => {
    localStorage.setItem('auth_token', 'jwt-abc-123')

    const config = runInterceptor()

    expect(config.headers.Authorization).toBe('Bearer jwt-abc-123')
    expect(config.headers['x-api-key']).toBeUndefined()
  })

  it('adds no auth headers for anonymous requests', () => {
    const config = runInterceptor()

    expect(config.headers.Authorization).toBeUndefined()
    expect(config.headers['x-api-key']).toBeUndefined()
  })

  it('always returns the config so the request proceeds', () => {
    localStorage.setItem('api_key', 'xk-dev-secret')

    const config = { headers: {} } as InternalAxiosRequestConfig
    expect(requestInterceptor()(config)).toBe(config)
  })
})
