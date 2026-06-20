import { getAuthHeaders, getStoredAuthToken } from '../../services/authHeaders'
import {
  creativeStudioApiEndpoints,
  type ApiCreativeStudioShotVideoRequest,
  type ApiCreativeStudioShotVideoResult,
  type ApiCreativeStudioVideoProviderStatus,
  type ApiCreativeStudioVideoWorkflowRequest,
  type ApiCreativeStudioVideoWorkflowResult,
} from './creativeStudioApiContracts'

export type CreativeStudioFetchClientOptions = {
  baseUrl?: string
  fetchImpl?: typeof fetch
  getToken?: () => string | null
}

export type CreativeStudioClient = {
  getVideoProviderStatus: () => Promise<ApiCreativeStudioVideoProviderStatus>
  generateShotVideo: (request: ApiCreativeStudioShotVideoRequest) => Promise<ApiCreativeStudioShotVideoResult>
  runVideoWorkflow: (request: ApiCreativeStudioVideoWorkflowRequest) => Promise<ApiCreativeStudioVideoWorkflowResult>
}

function endpoint(baseUrl: string, path: string): string {
  return `${baseUrl}${path}`
}

async function readJsonResponse<T>(response: Response, path: string): Promise<T> {
  if (!response.ok) {
    throw new Error(`Creative Studio API failed: ${response.status} ${path}`)
  }
  return response.json() as Promise<T>
}

export function createCreativeStudioFetchClient({
  baseUrl = '',
  fetchImpl = fetch,
  getToken = getStoredAuthToken,
}: CreativeStudioFetchClientOptions = {}): CreativeStudioClient {
  async function request<T>(method: 'GET' | 'POST', path: string, body?: unknown): Promise<T> {
    const headers: HeadersInit = {
      Accept: 'application/json',
      ...getAuthHeaders(getToken),
    }
    if (body !== undefined) {
      headers['Content-Type'] = 'application/json'
    }
    const response = await fetchImpl(endpoint(baseUrl, path), {
      method,
      headers,
      body: body === undefined ? undefined : JSON.stringify(body),
    })
    return readJsonResponse<T>(response, path)
  }

  return {
    getVideoProviderStatus() {
      return request<ApiCreativeStudioVideoProviderStatus>('GET', creativeStudioApiEndpoints.videoProviderStatus)
    },
    generateShotVideo(requestBody) {
      return request<ApiCreativeStudioShotVideoResult>('POST', creativeStudioApiEndpoints.shotVideo, requestBody)
    },
    runVideoWorkflow(requestBody) {
      return request<ApiCreativeStudioVideoWorkflowResult>('POST', creativeStudioApiEndpoints.videoWorkflow, requestBody)
    },
  }
}
