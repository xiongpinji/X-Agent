import axios, { AxiosInstance } from 'axios'

/**
 * Sync / Work-Session operations client — aligned with:
 *  - backend/app/api/sync.py      (prefix /api/v1/sync, 12 endpoints, mounted)
 *  - backend/app/api/work_mode.py (prefix /api/v1/work, 6 endpoints, mounted)
 *  - backend/app/api/sessions.py  (prefix /api/sessions, 10 endpoints, mounted)
 * Re-verified on 2026-07-26 via app.routes enumeration after
 * backend.app.main._register_all_routers().
 *
 * NOTE: /api/sessions/* routes are mounted, but main.py never calls
 * sessions.set_context_manager(), so every /api/sessions endpoint currently
 * responds 500 "Context manager not initialized". Pages must render those
 * features as disabled "coming soon" affordances — do NOT silently call them.
 *
 * sync trigger/offline-enable/offline-disable require the sync:admin scope and
 * the sync client has no cloud connection yet (backend NOTE in sync.py), so
 * manual trigger is surfaced but offline toggles may be treated as coming soon.
 */

// ---------------------------------------------------------------------------
// sync.py types
// ---------------------------------------------------------------------------

export interface SyncEnqueueRequest {
  entity_type: string
  entity_id: string
  operation: string // CREATE | UPDATE | DELETE
  data?: Record<string, unknown>
  priority?: number
}

export interface SyncEnqueueResponse {
  queue_id: string
  status: string
  created_at: string
}

export interface SyncStatusResponse {
  queue_id: string
  entity_type: string
  entity_id: string
  operation: string
  status: string
  created_at: string
  updated_at: string
  retry_count: number
  error_message?: string | null
}

export interface SyncConflict {
  id: string
  entity_type: string
  entity_id: string
  conflict_type: string
  local_version: number
  cloud_version: number
  local_data: Record<string, unknown>
  cloud_data: Record<string, unknown>
  resolved_at?: string | null
  resolution_strategy?: string | null
}

export interface SyncStats {
  pending_syncs: number
  failed_syncs: number
  unresolved_conflicts: number
  offline_operations: number
  last_sync_time?: string | null
  database_size_mb: number
}

export interface SyncHistoryEntry {
  id: string
  sync_batch_id: string
  entity_type: string
  entity_id: string
  operation: string
  direction: string
  status: string
  duration_ms: number
  created_at: string
}

export interface OfflineModeStatus {
  enabled: boolean
  pending_operations: number
  last_sync_time?: string | null
}

export interface SyncHealth {
  status: string // healthy | degraded | unhealthy
  health_score: number
  stats: Record<string, number>
}

// ---------------------------------------------------------------------------
// work_mode.py types
// ---------------------------------------------------------------------------

export interface WorkMilestone {
  index: number
  title: string
  status: string // pending | running | completed | failed | skipped
  output?: string
  duration_seconds?: number
}

export interface WorkArtifact {
  artifact_id: string
  name: string
  type: string
}

export interface WorkSession {
  session_id: string
  goal: string
  status: string // active | paused | completed | failed | timeout
  started_at: string
  completed_at?: string | null
  max_duration_hours: number
  current_milestone_index: number
  milestones: WorkMilestone[]
  artifacts: WorkArtifact[]
  connected_apps: string[]
  total_tokens_used: number
}

export interface StartWorkSessionRequest {
  goal: string
  max_hours?: number
  max_milestones?: number
}

// ---------------------------------------------------------------------------
// sessions.py types (mounted but non-functional until context manager injected)
// ---------------------------------------------------------------------------

export interface SessionListItem {
  session_id?: string
  agent_id?: string
  [key: string]: unknown
}

export interface SessionListResponse {
  sessions: SessionListItem[]
  total_count: number
}

export interface SessionRestoreResponse {
  session_id: string
  agent_id: string
  tenant_id: string
  message_count: number
  total_tokens: number
  created_at: string
  updated_at: string
}

// ---------------------------------------------------------------------------
// client
// ---------------------------------------------------------------------------

class SyncOpsClient {
  private client: AxiosInstance

  constructor() {
    this.client = axios.create({
      baseURL: '/',
      timeout: 30000,
      headers: { 'Content-Type': 'application/json' },
    })
    // Same auth convention as services/api.ts: Bearer token from localStorage.
    this.client.interceptors.request.use((config) => {
      const token = localStorage.getItem('auth_token')
      if (token) {
        config.headers.Authorization = `Bearer ${token}`
      }
      return config
    })
  }

  // --- sync.py (prefix /api/v1/sync) ---

  async enqueueSync(req: SyncEnqueueRequest): Promise<SyncEnqueueResponse> {
    const resp = await this.client.post('/api/v1/sync/enqueue', req)
    return resp.data
  }

  async getSyncStatus(queueId: string): Promise<SyncStatusResponse> {
    const resp = await this.client.get(`/api/v1/sync/status/${encodeURIComponent(queueId)}`)
    return resp.data
  }

  async triggerSync(): Promise<{ batch_id: string; status: string; started_at: string }> {
    const resp = await this.client.post('/api/v1/sync/trigger')
    return resp.data
  }

  async listConflicts(entityType?: string, limit = 100): Promise<SyncConflict[]> {
    const resp = await this.client.get('/api/v1/sync/conflicts', {
      params: { entity_type: entityType || undefined, limit },
    })
    return resp.data
  }

  async getConflict(conflictId: string): Promise<SyncConflict> {
    const resp = await this.client.get(`/api/v1/sync/conflicts/${encodeURIComponent(conflictId)}`)
    return resp.data
  }

  async resolveConflict(
    conflictId: string,
    resolutionStrategy: string,
    resolvedData: Record<string, unknown>,
  ): Promise<{ conflict_id: string; status: string; resolved_at: string }> {
    const resp = await this.client.post(
      `/api/v1/sync/conflicts/${encodeURIComponent(conflictId)}/resolve`,
      { resolution_strategy: resolutionStrategy, resolved_data: resolvedData },
    )
    return resp.data
  }

  async getOfflineStatus(): Promise<OfflineModeStatus> {
    const resp = await this.client.get('/api/v1/sync/offline/status')
    return resp.data
  }

  async setOfflineMode(enabled: boolean): Promise<OfflineModeStatus> {
    const resp = await this.client.post(`/api/v1/sync/offline/${enabled ? 'enable' : 'disable'}`)
    return resp.data
  }

  async getSyncStats(): Promise<SyncStats> {
    const resp = await this.client.get('/api/v1/sync/stats')
    return resp.data
  }

  async getSyncHistory(entityType?: string, limit = 100): Promise<SyncHistoryEntry[]> {
    const resp = await this.client.get('/api/v1/sync/history', {
      params: { entity_type: entityType || undefined, limit },
    })
    return resp.data
  }

  async getSyncHealth(): Promise<SyncHealth> {
    const resp = await this.client.get('/api/v1/sync/health')
    return resp.data
  }

  // --- work_mode.py (prefix /api/v1/work) ---

  async startWorkSession(req: StartWorkSessionRequest): Promise<WorkSession> {
    const resp = await this.client.post('/api/v1/work/sessions', {
      goal: req.goal,
      max_hours: req.max_hours ?? 8.0,
      max_milestones: req.max_milestones ?? 6,
    })
    return resp.data
  }

  async listWorkSessions(): Promise<WorkSession[]> {
    const resp = await this.client.get('/api/v1/work/sessions')
    return resp.data.sessions as WorkSession[]
  }

  async getWorkSession(sessionId: string): Promise<WorkSession> {
    const resp = await this.client.get(`/api/v1/work/sessions/${encodeURIComponent(sessionId)}`)
    return resp.data
  }

  async tickWorkSession(sessionId: string): Promise<WorkSession> {
    const resp = await this.client.post(`/api/v1/work/sessions/${encodeURIComponent(sessionId)}/tick`)
    return resp.data
  }

  async pauseWorkSession(sessionId: string): Promise<WorkSession> {
    const resp = await this.client.post(`/api/v1/work/sessions/${encodeURIComponent(sessionId)}/pause`)
    return resp.data
  }

  async resumeWorkSession(sessionId: string): Promise<WorkSession> {
    const resp = await this.client.post(`/api/v1/work/sessions/${encodeURIComponent(sessionId)}/resume`)
    return resp.data
  }

  // --- sessions.py (prefix /api/sessions) ---
  // Mounted but NOT functional: main.py never calls set_context_manager().
  // Exposed for completeness; pages render these as disabled "coming soon".

  async listContextSessions(limit = 100): Promise<SessionListResponse> {
    const resp = await this.client.get('/api/sessions', { params: { limit } })
    return resp.data
  }

  async restoreContextSession(sessionId: string): Promise<SessionRestoreResponse> {
    const resp = await this.client.post(`/api/sessions/${encodeURIComponent(sessionId)}/restore`)
    return resp.data
  }

  async deleteContextSession(sessionId: string): Promise<{ success: boolean }> {
    const resp = await this.client.delete(`/api/sessions/${encodeURIComponent(sessionId)}`)
    return resp.data
  }
}

export const syncOps = new SyncOpsClient()
export default syncOps
