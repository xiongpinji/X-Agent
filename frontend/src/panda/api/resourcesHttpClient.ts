import type { ApiPandaResourceSnapshot } from './adapters'
import type { PandaResourcesHttpClient } from './resourcesApiLoader'

export const PANDA_RESOURCES_BFF_ENDPOINT = '/api/v1/workbench/resources'

export type PandaResourcesFetchClientOptions = {
  endpoint?: string
  getToken?: () => string | null
}

export function resolvePandaResourcesEndpoint(endpoint?: string): string {
  const normalizedEndpoint = endpoint?.trim()
  return normalizedEndpoint || PANDA_RESOURCES_BFF_ENDPOINT
}

export function createPandaResourcesFetchClient({
  endpoint,
  getToken = () => localStorage.getItem('auth_token'),
}: PandaResourcesFetchClientOptions = {}): PandaResourcesHttpClient {
  const resolvedEndpoint = resolvePandaResourcesEndpoint(endpoint)

  return {
    async getPandaResources(): Promise<ApiPandaResourceSnapshot> {
      const headers: HeadersInit = {
        Accept: 'application/json',
      }
      const token = getToken()
      if (token) {
        headers.Authorization = `Bearer ${token}`
      }

      const response = await fetch(resolvedEndpoint, { headers })
      if (!response.ok) {
        throw new Error(`无法加载 Panda 资源: ${response.status} ${resolvedEndpoint}`)
      }

      return response.json() as Promise<ApiPandaResourceSnapshot>
    },
  }
}
