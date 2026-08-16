const fs = require('node:fs')
const os = require('node:os')
const path = require('node:path')
const { setImmediate } = require('node:timers')
const { TextDecoder, TextEncoder } = require('node:util')

globalThis.setImmediate = setImmediate
globalThis.TextDecoder = TextDecoder
globalThis.TextEncoder = TextEncoder

const {
  ExtensionApiError,
  XAgentExtensionApi,
  normalizeBaseUrl,
  safeErrorMessage,
} = require('../extension-api')
const {
  PACKAGE_FILES,
  createPackage,
  listZipEntries,
} = require('../scripts/package-extension')
const { bindPopup } = require('../popup')

function storageArea(initial = {}) {
  const values = { ...initial }
  return {
    values,
    get: jest.fn(async (keys) => {
      const selected = Array.isArray(keys) ? keys : [keys]
      return Object.fromEntries(selected.filter((key) => key in values).map((key) => [key, values[key]]))
    }),
    set: jest.fn(async (next) => Object.assign(values, next)),
    remove: jest.fn(async (keys) => {
      for (const key of Array.isArray(keys) ? keys : [keys]) delete values[key]
    }),
  }
}

function chromeApi() {
  return {
    permissions: { request: jest.fn(async () => true) },
    storage: {
      local: storageArea(),
      session: storageArea(),
    },
  }
}

function jsonResponse(body, status = 200) {
  const bytes = Uint8Array.from(Buffer.from(JSON.stringify(body)))
  let delivered = false
  return {
    ok: status >= 200 && status < 300,
    status,
    headers: { get: (name) => name.toLowerCase() === 'content-length' ? String(bytes.length) : null },
    body: {
      getReader: () => ({
        read: async () => {
          if (delivered) return { done: true, value: undefined }
          delivered = true
          return { done: false, value: bytes }
        },
        cancel: jest.fn(async () => undefined),
      }),
    },
  }
}

describe('commercial extension API', () => {
  it('allows HTTPS and localhost only, without URL credentials or paths', () => {
    expect(normalizeBaseUrl(' https://api.example.test/ ')).toBe('https://api.example.test')
    expect(normalizeBaseUrl('http://localhost:8000')).toBe('http://localhost:8000')
    for (const invalid of [
      'http://api.example.test',
      'https://user:secret@api.example.test',
      'https://api.example.test/private',
      'javascript:alert(1)',
    ]) {
      expect(() => normalizeBaseUrl(invalid)).toThrow(ExtensionApiError)
    }
  })

  it('requests only the configured origin and stores tokens in session storage', async () => {
    const chrome = chromeApi()
    const fetch = jest.fn(async () => jsonResponse({
      access_token: 'access-secret',
      refresh_token: 'refresh-secret',
      user: { id: 'user-1' },
    }))
    const api = new XAgentExtensionApi({ chrome, fetch })

    await api.configureBackend('https://api.example.test')
    await api.login('owner@example.test', 'private-password')

    expect(chrome.permissions.request).toHaveBeenCalledWith({ origins: ['https://api.example.test/*'] })
    expect(chrome.storage.local.values).toEqual({ xagent_api_url: 'https://api.example.test' })
    expect(chrome.storage.session.values).toEqual({
      xagent_access_token: 'access-secret',
      xagent_refresh_token: 'refresh-secret',
    })
    expect(fetch.mock.calls[0][0]).toBe('https://api.example.test/api/v1/auth/login')
    expect(fetch.mock.calls[0][0]).not.toContain('private-password')
  })

  it('uses Bearer auth for trigger, status, cancel, and server logout', async () => {
    const chrome = chromeApi()
    chrome.storage.local.values.xagent_api_url = 'https://api.example.test'
    chrome.storage.session.values.xagent_access_token = 'access-secret'
    const runId = '11111111-1111-4111-8111-111111111111'
    const fetch = jest
      .fn()
      .mockResolvedValueOnce(jsonResponse({ run_id: runId, trace_id: 'trace-1', status: 'pending', created_at: 'now' }))
      .mockResolvedValueOnce(jsonResponse({ run_id: runId, trace_id: 'trace-1', status: 'completed', result_summary: 'answer' }))
      .mockResolvedValueOnce(jsonResponse({ run_id: runId, status: 'cancelled' }))
      .mockResolvedValueOnce(jsonResponse({ logged_out: true }))
    const api = new XAgentExtensionApi({ chrome, fetch })

    await api.triggerAgent({ agentId: 'agent-1', task: 'prepare report', operationId: 'extension-op-1' })
    await api.getRunStatus(runId)
    await api.cancelRun(runId)
    await api.logout()

    expect(fetch.mock.calls.map(([url]) => url)).toEqual([
      'https://api.example.test/api/v1/mobile/trigger',
      `https://api.example.test/api/v1/mobile/runs/${runId}/status`,
      `https://api.example.test/api/v1/mobile/runs/${runId}/cancel`,
      'https://api.example.test/api/v1/auth/logout',
    ])
    for (const [, init] of fetch.mock.calls) {
      expect(init.headers.Authorization).toBe('Bearer access-secret')
    }
    expect(chrome.storage.session.values).toEqual({})
  })

  it('does not expose backend response bodies in errors', async () => {
    const chrome = chromeApi()
    chrome.storage.local.values.xagent_api_url = 'https://api.example.test'
    const api = new XAgentExtensionApi({
      chrome,
      fetch: jest.fn(async () => jsonResponse({ detail: 'database-password-should-not-leak' }, 500)),
    })

    await expect(api.login('owner@example.test', 'private-password')).rejects.toMatchObject({
      code: 'backend_unavailable',
    })
    expect(safeErrorMessage(new Error('database-password-should-not-leak')))
      .toBe('操作失败，请稍后重试。')
  })

  it('fails closed on permission denial, missing auth, invalid IDs, and oversized bodies', async () => {
    const deniedChrome = chromeApi()
    deniedChrome.permissions.request.mockResolvedValue(false)
    await expect(new XAgentExtensionApi({ chrome: deniedChrome, fetch: jest.fn() })
      .configureBackend('https://api.example.test')).rejects.toMatchObject({ code: 'permission_denied' })

    const chrome = chromeApi()
    chrome.storage.local.values.xagent_api_url = 'https://api.example.test'
    const api = new XAgentExtensionApi({ chrome, fetch: jest.fn() })
    await expect(api.triggerAgent({
      agentId: 'agent-1',
      task: 'task',
      operationId: 'extension-op-1',
    })).rejects.toMatchObject({ code: 'authentication_required' })
    await expect(api.getRunStatus('../private')).rejects.toMatchObject({ code: 'invalid_run_id' })

    const oversized = jsonResponse({ ok: true })
    oversized.headers.get = () => String(1_048_577)
    const oversizedApi = new XAgentExtensionApi({ chrome, fetch: jest.fn(async () => oversized) })
    await expect(oversizedApi.login('owner@example.test', 'private-password'))
      .rejects.toMatchObject({ code: 'invalid_backend_response' })
    expect(safeErrorMessage({ code: 'rate_limited' })).toBe('请求过于频繁，请稍后重试。')
  })
})

describe('deterministic extension package', () => {
  it('contains only the audited allowlist', async () => {
    const directory = fs.mkdtempSync(path.join(os.tmpdir(), 'xagent-extension-'))
    const output = path.join(directory, 'extension.zip')
    try {
      await createPackage(output)
      const entries = listZipEntries(fs.readFileSync(output))
      expect(entries).toEqual(PACKAGE_FILES)
      expect(entries).not.toEqual(expect.arrayContaining(['background.js', 'content.js', 'injected.js']))
    } finally {
      fs.rmSync(directory, { recursive: true, force: true })
    }
  })
})

describe('popup runner', () => {
  it('wires login, trigger, status, cancel, and logout without HTML injection', async () => {
    document.documentElement.innerHTML = fs.readFileSync(path.join(__dirname, '..', 'popup.html'), 'utf8')
    jest.spyOn(globalThis.crypto, 'randomUUID').mockReturnValue('22222222-2222-4222-8222-222222222222')
    const runId = '11111111-1111-4111-8111-111111111111'
    const api = {
      getConfig: jest.fn(async () => ({ baseUrl: 'https://api.example.test' })),
      getSession: jest.fn(async () => ({ authenticated: false })),
      configureBackend: jest.fn(async () => 'https://api.example.test'),
      login: jest.fn(async () => ({ authenticated: true })),
      triggerAgent: jest.fn(async () => ({ run_id: runId, status: 'pending' })),
      getRunStatus: jest.fn(async () => ({ status: 'cancelled', result_summary: 'safe result' })),
      cancelRun: jest.fn(async () => ({ run_id: runId, status: 'cancelled' })),
      logout: jest.fn(async () => ({ loggedOut: true, serverRevoked: true })),
    }
    const tick = () => new Promise((resolve) => setTimeout(resolve, 0))

    await bindPopup(document, api)
    document.getElementById('email').value = 'owner@example.test'
    document.getElementById('password').value = 'private-password'
    document.getElementById('login-form').dispatchEvent(new Event('submit', { bubbles: true, cancelable: true }))
    await tick()
    expect(api.configureBackend).toHaveBeenCalledWith('https://api.example.test')
    expect(api.login).toHaveBeenCalledWith('owner@example.test', 'private-password')
    expect(document.getElementById('password').value).toBe('')

    document.getElementById('task').value = 'prepare report'
    document.getElementById('run-form').dispatchEvent(new Event('submit', { bubbles: true, cancelable: true }))
    await tick()
    expect(api.triggerAgent).toHaveBeenCalledWith({
      agentId: 'default-agent',
      task: 'prepare report',
      operationId: 'extension-22222222-2222-4222-8222-222222222222',
    })
    expect(document.getElementById('run-id').textContent).toBe(runId)

    document.getElementById('cancel').click()
    await tick()
    expect(api.cancelRun).toHaveBeenCalledWith(runId)
    expect(document.getElementById('result').textContent).toBe('safe result')

    document.getElementById('logout').click()
    await tick()
    expect(api.logout).toHaveBeenCalledTimes(1)
    expect(document.getElementById('login-form').classList.contains('hidden')).toBe(false)
  })
})
