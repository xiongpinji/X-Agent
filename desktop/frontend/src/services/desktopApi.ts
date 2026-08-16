import { invoke } from '@tauri-apps/api/core'

export interface TriggerAgentInput {
  agentId: string
  task: string
  operationId: string
}

export interface TriggerResponse {
  run_id: string
  trace_id: string
  status: string
  created_at: string
}

export interface RunStatusResponse {
  run_id: string
  trace_id: string
  status: string
  progress_percent: number
  current_step: string
  result_summary: string
  error: string | null
  error_code: string | null
}

export function configureBackend(baseUrl: string) {
  return invoke<{ configured: boolean; base_url: string }>('configure_backend', { baseUrl })
}

export function login(email: string, password: string) {
  return invoke<{ authenticated: boolean; user: Record<string, unknown> }>('login', { email, password })
}

export function logout() {
  return invoke<boolean>('logout')
}

export function triggerAgent(input: TriggerAgentInput) {
  return invoke<TriggerResponse>('trigger_agent', { ...input })
}

export function getRunStatus(runId: string) {
  return invoke<RunStatusResponse>('get_run_status', { runId })
}

export function cancelRun(runId: string) {
  return invoke<{ run_id: string; status: string }>('cancel_run', { runId })
}

export function safeErrorMessage(error: unknown): string {
  const messages: Record<string, string> = {
    invalid_backend_url: '请输入有效的 HTTPS API 地址；本地开发可使用 localhost HTTP。',
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
  if (typeof error === 'object' && error !== null && 'code' in error) {
    const code = (error as { code?: unknown }).code
    if (typeof code === 'string' && messages[code]) return messages[code]
  }
  return '操作失败，请稍后重试。'
}
