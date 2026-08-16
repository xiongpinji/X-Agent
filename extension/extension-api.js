(function exposeExtensionApi(root, factory) {
  const api = factory()
  if (typeof module === 'object' && module.exports) module.exports = api
  root.XAgentExtension = api
})(globalThis, function createExtensionApi() {
  const LOCAL_URL_KEY = 'xagent_api_url'
  const ACCESS_TOKEN_KEY = 'xagent_access_token'
  const REFRESH_TOKEN_KEY = 'xagent_refresh_token'
  const MAX_RESPONSE_BYTES = 1_048_576

  class ExtensionApiError extends Error {
    constructor(code, message, status = null) {
      super(message)
      this.name = 'ExtensionApiError'
      this.code = code
      this.status = status
    }
  }

  function normalizeBaseUrl(raw) {
    let url
    try {
      url = new URL(String(raw).trim())
    } catch {
      throw new ExtensionApiError('invalid_backend_url', 'The X-Agent service URL is invalid.')
    }
    const local = ['localhost', '127.0.0.1'].includes(url.hostname)
    if (
      (url.protocol !== 'https:' && !(url.protocol === 'http:' && local))
      || url.username
      || url.password
      || url.search
      || url.hash
      || !['', '/'].includes(url.pathname)
    ) {
      throw new ExtensionApiError(
        'invalid_backend_url',
        'Use HTTPS, or HTTP only for localhost development.',
      )
    }
    return url.origin
  }

  function permissionPattern(baseUrl) {
    const url = new URL(baseUrl)
    const hostname = url.hostname.includes(':') ? `[${url.hostname}]` : url.hostname
    return `${url.protocol}//${hostname}/*`
  }

  function statusError(status) {
    const errors = {
      400: ['validation_failed', 'The request was rejected.'],
      401: ['authentication_failed', 'Authentication failed.'],
      403: ['authorization_failed', 'This account is not allowed to perform the action.'],
      404: ['not_found', 'The requested resource was not found.'],
      409: ['conflict', 'The operation conflicts with the current state.'],
      422: ['validation_failed', 'The request was rejected.'],
      429: ['rate_limited', 'Too many requests. Try again later.'],
    }
    const [code, message] = errors[status] || ['backend_unavailable', 'The X-Agent service is unavailable.']
    return new ExtensionApiError(code, message, status)
  }

  async function readJson(response) {
    const declared = Number(response.headers.get('content-length') || 0)
    if (declared > MAX_RESPONSE_BYTES) {
      throw new ExtensionApiError('invalid_backend_response', 'The X-Agent service returned an invalid response.')
    }
    const reader = response.body?.getReader()
    if (!reader) {
      throw new ExtensionApiError('invalid_backend_response', 'The X-Agent service returned an invalid response.')
    }
    const chunks = []
    let total = 0
    while (true) {
      const { done, value } = await reader.read()
      if (done) break
      total += value.byteLength
      if (total > MAX_RESPONSE_BYTES) {
        await reader.cancel()
        throw new ExtensionApiError('invalid_backend_response', 'The X-Agent service returned an invalid response.')
      }
      chunks.push(value)
    }
    const bytes = new Uint8Array(total)
    let offset = 0
    for (const chunk of chunks) {
      bytes.set(chunk, offset)
      offset += chunk.byteLength
    }
    try {
      return JSON.parse(new TextDecoder().decode(bytes))
    } catch {
      throw new ExtensionApiError('invalid_backend_response', 'The X-Agent service returned an invalid response.')
    }
  }

  function requiredText(value, max, code = 'invalid_request') {
    const normalized = String(value || '').trim()
    if (!normalized || [...normalized].length > max) {
      throw new ExtensionApiError(code, 'The request is invalid.')
    }
    return normalized
  }

  function runId(value) {
    const normalized = String(value || '').trim()
    if (!/^[0-9a-f]{8}-[0-9a-f]{4}-[1-5][0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$/i.test(normalized)) {
      throw new ExtensionApiError('invalid_run_id', 'The run identifier is invalid.')
    }
    return normalized
  }

  class XAgentExtensionApi {
    constructor({ chrome = globalThis.chrome, fetch = globalThis.fetch } = {}) {
      if (!chrome?.storage?.local || !chrome?.storage?.session || !chrome?.permissions) {
        throw new ExtensionApiError('extension_unavailable', 'Extension storage is unavailable.')
      }
      this.chrome = chrome
      this.fetch = fetch
    }

    async configureBackend(raw) {
      const baseUrl = normalizeBaseUrl(raw)
      const granted = await this.chrome.permissions.request({ origins: [permissionPattern(baseUrl)] })
      if (!granted) {
        throw new ExtensionApiError('permission_denied', 'Permission to access the X-Agent service was denied.')
      }
      await this.chrome.storage.local.set({ [LOCAL_URL_KEY]: baseUrl })
      await this.chrome.storage.session.remove([ACCESS_TOKEN_KEY, REFRESH_TOKEN_KEY])
      return baseUrl
    }

    async getConfig() {
      const values = await this.chrome.storage.local.get([LOCAL_URL_KEY])
      return { baseUrl: values[LOCAL_URL_KEY] || '' }
    }

    async getSession() {
      const values = await this.chrome.storage.session.get([ACCESS_TOKEN_KEY])
      return { authenticated: Boolean(values[ACCESS_TOKEN_KEY]) }
    }

    async login(email, password) {
      const normalizedEmail = requiredText(email, 320, 'invalid_credentials')
      const normalizedPassword = requiredText(password, 4096, 'invalid_credentials')
      const response = await this.request('/api/v1/auth/login', {
        method: 'POST',
        body: JSON.stringify({ email: normalizedEmail, password: normalizedPassword }),
      }, false)
      if (
        typeof response.access_token !== 'string'
        || !response.access_token
        || response.access_token.length > 4096
        || typeof response.refresh_token !== 'string'
        || response.refresh_token.length > 4096
      ) {
        throw new ExtensionApiError('invalid_backend_response', 'The X-Agent service returned an invalid response.')
      }
      await this.chrome.storage.session.set({
        [ACCESS_TOKEN_KEY]: response.access_token,
        [REFRESH_TOKEN_KEY]: response.refresh_token,
      })
      return { authenticated: true, user: response.user || {} }
    }

    async logout() {
      let serverRevoked
      try {
        await this.request('/api/v1/auth/logout', { method: 'POST' }, true)
        serverRevoked = true
      } catch {
        serverRevoked = false
      } finally {
        await this.chrome.storage.session.remove([ACCESS_TOKEN_KEY, REFRESH_TOKEN_KEY])
      }
      return { loggedOut: true, serverRevoked }
    }

    async triggerAgent({ agentId, task, operationId }) {
      return this.request('/api/v1/mobile/trigger', {
        method: 'POST',
        body: JSON.stringify({
          agent_id: requiredText(agentId, 128),
          task: requiredText(task, 4096),
          operation_id: requiredText(operationId, 220),
          notify_on_complete: false,
          metadata: { client: 'chrome-extension' },
        }),
      })
    }

    async getRunStatus(value) {
      return this.request(`/api/v1/mobile/runs/${runId(value)}/status`, { method: 'GET' })
    }

    async cancelRun(value) {
      return this.request(`/api/v1/mobile/runs/${runId(value)}/cancel`, { method: 'POST' })
    }

    async request(path, init, authenticated = true) {
      const config = await this.chrome.storage.local.get([LOCAL_URL_KEY])
      const baseUrl = config[LOCAL_URL_KEY]
      if (!baseUrl) throw new ExtensionApiError('backend_not_configured', 'Configure the X-Agent service first.')
      const headers = { 'Content-Type': 'application/json' }
      if (authenticated) {
        const session = await this.chrome.storage.session.get([ACCESS_TOKEN_KEY])
        const token = session[ACCESS_TOKEN_KEY]
        if (!token) throw new ExtensionApiError('authentication_required', 'Sign in before running an Agent.')
        headers.Authorization = `Bearer ${token}`
      }
      let response
      try {
        response = await this.fetch(`${baseUrl}${path}`, { ...init, headers })
      } catch {
        throw new ExtensionApiError('backend_unavailable', 'The X-Agent service is unavailable.')
      }
      if (!response.ok) throw statusError(response.status)
      return readJson(response)
    }
  }

  function safeErrorMessage(error) {
    const messages = {
      invalid_backend_url: '请输入有效的 HTTPS API 地址；本地开发可使用 localhost HTTP。',
      permission_denied: '未授予访问该 API 地址的权限。',
      invalid_credentials: '请输入邮箱和密码。',
      authentication_failed: '登录失败，请检查凭证。',
      authentication_required: '请先登录。',
      authorization_failed: '当前账号无权执行此操作。',
      backend_unavailable: 'X-Agent 服务当前不可用。',
      conflict: '该操作与当前运行状态冲突。',
      invalid_request: '请求内容无效。',
      invalid_run_id: '运行标识无效。',
      not_found: '未找到该资源。',
      rate_limited: '请求过于频繁，请稍后重试。',
      validation_failed: '请求未通过服务端校验。',
    }
    return messages[error?.code] || '操作失败，请稍后重试。'
  }

  return {
    ExtensionApiError,
    XAgentExtensionApi,
    normalizeBaseUrl,
    safeErrorMessage,
  }
})
