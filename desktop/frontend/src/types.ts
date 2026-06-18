export interface AgentStatus {
  id: string
  name: string
  status: string
  running: boolean
  created_at: string
}

export interface DesktopSettings {
  backend_url: string
  backend_port: number
  language: string
  theme: 'auto' | 'light' | 'dark' | string
  log_level: 'debug' | 'info' | 'warn' | 'error' | string
  auto_update: boolean
  offline_mode: boolean
}

export interface DirectoryEntry {
  path: string
  name: string
  is_dir: boolean
  size: number
}

export interface RunSummary {
  id: string
  agent_name: string
  status: 'success' | 'failed' | 'running' | string
  created_at: string
  duration?: string
  input?: string
  output?: string
}

export interface BackendHealth {
  status?: string
  service?: string
  [key: string]: unknown
}
