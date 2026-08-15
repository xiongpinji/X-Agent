import type { InternalAxiosRequestConfig } from 'axios'

export function applyStoredAuth(
  config: InternalAxiosRequestConfig,
): InternalAxiosRequestConfig {
  const token = localStorage.getItem('auth_token')
  const apiKey = localStorage.getItem('api_key')

  if (token) {
    config.headers.Authorization = `Bearer ${token}`
  }
  if (apiKey) {
    config.headers['x-api-key'] = apiKey
  }

  return config
}
