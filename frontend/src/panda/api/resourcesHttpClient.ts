import type { ApiPandaResourceSnapshot } from './adapters'
import type { PandaResourcesHttpClient } from './resourcesApiLoader'
import { getAuthHeaders, getStoredAuthToken } from '../../services/authHeaders'

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
  getToken = getStoredAuthToken,
}: PandaResourcesFetchClientOptions = {}): PandaResourcesHttpClient {
  const resolvedEndpoint = resolvePandaResourcesEndpoint(endpoint)

  return {
    async getPandaResources(): Promise<ApiPandaResourceSnapshot> {
      const headers: HeadersInit = {
        Accept: 'application/json',
      }
      Object.assign(headers, getAuthHeaders(getToken))

      const response = await fetch(resolvedEndpoint, { headers })
      if (!response.ok) {
        throw new Error(`无法加载 Panda 资源: ${response.status} ${resolvedEndpoint}`)
      }

      return response.json() as Promise<ApiPandaResourceSnapshot>
    },
  }
}
