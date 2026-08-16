import { beforeEach, describe, expect, it, vi } from 'vitest'

const { invoke } = vi.hoisted(() => ({ invoke: vi.fn() }))

vi.mock('@tauri-apps/api/core', () => ({ invoke }))

import {
  cancelRun,
  configureBackend,
  getRunStatus,
  login,
  logout,
  safeErrorMessage,
  triggerAgent,
} from './desktopApi'

describe('desktop commercial API', () => {
  beforeEach(() => invoke.mockReset())

  it('uses only dedicated Tauri commands and structured payloads', async () => {
    invoke.mockResolvedValue({ status: 'ok' })

    await configureBackend('https://api.example.test/')
    await login('owner@example.test', 'correct horse battery staple')
    await triggerAgent({
      agentId: 'agent-1',
      task: 'prepare report',
      operationId: 'desktop-op-1',
    })
    await getRunStatus('11111111-1111-4111-8111-111111111111')
    await cancelRun('11111111-1111-4111-8111-111111111111')
    await logout()

    expect(invoke.mock.calls).toEqual([
      ['configure_backend', { baseUrl: 'https://api.example.test/' }],
      ['login', { email: 'owner@example.test', password: 'correct horse battery staple' }],
      ['trigger_agent', {
        agentId: 'agent-1',
        task: 'prepare report',
        operationId: 'desktop-op-1',
      }],
      ['get_run_status', { runId: '11111111-1111-4111-8111-111111111111' }],
      ['cancel_run', { runId: '11111111-1111-4111-8111-111111111111' }],
      ['logout'],
    ])
  })

  it('never passes credentials in a URL', async () => {
    invoke.mockResolvedValue({ authenticated: true })
    await login('owner@example.test', 'private-password')

    const serialized = JSON.stringify(invoke.mock.calls)
    expect(serialized).not.toContain('token=')
    expect(serialized).not.toContain('password=')
  })

  it('shows only allowlisted error messages', () => {
    expect(safeErrorMessage({ code: 'authentication_failed', message: 'PRIVATE_BACKEND_BODY' }))
      .toBe('登录失败，请检查凭证。')
    expect(safeErrorMessage({ message: 'database-password-should-not-leak' }))
      .toBe('操作失败，请稍后重试。')
  })
})
