import axios, { AxiosInstance } from 'axios'

/**
 * Self-evolution console API client — verified against the real backend route
 * table on 2026-07-26 (backend/app/api/evolution.py, prefix /api/v1/evolution).
 *
 * Mounted endpoints (all confirmed via app.routes enumeration):
 *   GET  /evolution/summary
 *   GET  /evolution/stats
 *   GET  /evolution/skills
 *   POST /evolution/trigger
 *   GET  /evolution/reflections | /learnings | /capabilities
 *   POST /evolution/self-evolution/record | /evaluate | /optimize | /distill | /cycle
 *   GET  /evolution/self-evolution/history | /stats | /skills
 *
 * Kept separate from services/api.ts per task boundary (A28).
 */

// ─── Types mirrored from backend response models ────────────────────────────

/** GET /evolution/summary → EvolutionSummaryResponse */
export interface EvolutionSummary {
  reflections: number
  learnings: number
  capabilities: number
}

/** GET /evolution/stats → EvolutionStatsResponse (GEPA engine) */
export interface EvolutionEngineStats {
  total_executions: number
  skill_drafts: number
  promoted_skills: number
  skill_names: string[]
}

/** Item of GET /evolution/skills (promoted GEPA skills) */
export interface PromotedSkillRecord {
  id: string
  name: string
  description: string
  trigger_pattern: string
  tool_sequence: string[]
  usage_count: number
  success_rate: number
}

/** POST /evolution/trigger → reflection outcome or skip */
export interface GepaTriggerResult {
  status: 'completed' | 'skipped' | string
  reason?: string
  should_create_skill?: boolean
  skill_name?: string
  confidence?: number
  key_patterns?: string[]
}

/** GET /evolution/self-evolution/stats → SelfEvolutionEngine.get_stats() */
export interface SelfEvolutionStats {
  total_records: number
  stage_counts: Record<string, number>
  distilled_skills: number
  skill_names: string[]
  average_score: number
  optimizations_applied: number
}

/** Item of GET /evolution/self-evolution/history → EvolutionRecord.to_dict() */
export interface EvolutionRecordItem {
  id: string
  task_id: string
  stage: 'execute' | 'evaluate' | 'optimize' | 'learn' | string
  input_data: Record<string, any>
  output_data: Record<string, any>
  score: number | null
  created_at: string
}

/** Optimization suggestion inside optimize results */
export interface OptimizationSuggestion {
  type: string
  action: string
  detail: string
}

/** POST /evolution/self-evolution/optimize → optimize_strategy() result */
export interface OptimizeResult {
  execution_id?: string
  score?: number
  optimizations: OptimizationSuggestion[]
  should_retry?: boolean
  suggested_approach?: string
  stage?: string
  error?: string
}

/** DistilledSkill.to_dict() — also items of GET /self-evolution/skills */
export interface DistilledSkill {
  id: string
  name: string
  description: string
  pattern: string
  tool_sequence: string[]
  success_rate: number
  source_execution_ids: string[]
  created_at: string
}

/** POST /evolution/self-evolution/distill → distill_skill() result */
export interface DistillResult {
  skill: DistilledSkill | null
  promoted?: boolean
  stage?: string
  error?: string
}

/** POST /evolution/self-evolution/cycle → trigger_evolution_cycle() result */
export interface CycleResult {
  task_id: string
  execution_id?: string
  score?: number
  optimization?: OptimizeResult
  skill_distilled?: boolean
  skill?: DistilledSkill | null
  cycle_complete?: boolean
  error?: string
}

/** POST /evolution/self-evolution/record */
export interface RecordExecutionResult {
  execution_id: string
  task_id: string
  stage: string
}

/** POST /evolution/self-evolution/evaluate */
export interface EvaluateResult {
  execution_id: string
  score: number
  stage: string
}

// ─── Client ─────────────────────────────────────────────────────────────────

class EvolutionOpsClient {
  private client: AxiosInstance

  constructor(baseURL: string = '/api/v1') {
    this.client = axios.create({
      baseURL,
      timeout: 30000,
      headers: { 'Content-Type': 'application/json' },
    })
    this.client.interceptors.request.use((config) => {
      const token = localStorage.getItem('auth_token')
      if (token) {
        config.headers.Authorization = `Bearer ${token}`
      }
      return config
    })
  }

  // ── GEPA engine (evolution_engine) ──

  async getSummary(): Promise<EvolutionSummary> {
    const response = await this.client.get<EvolutionSummary>('/evolution/summary')
    return response.data
  }

  async getStats(): Promise<EvolutionEngineStats> {
    const response = await this.client.get<EvolutionEngineStats>('/evolution/stats')
    return response.data
  }

  async getPromotedSkills(): Promise<PromotedSkillRecord[]> {
    const response = await this.client.get('/evolution/skills')
    const payload = response.data
    return Array.isArray(payload) ? payload : []
  }

  /** POST /evolution/trigger — manual GEPA loop trigger (agent:write scope). */
  async triggerGepa(trajectory: Record<string, any>, result: Record<string, any>): Promise<GepaTriggerResult> {
    const response = await this.client.post<GepaTriggerResult>('/evolution/trigger', { trajectory, result })
    return response.data
  }

  // ── Self-evolution engine (self_evolution_engine) ──

  async getSelfEvolutionStats(): Promise<SelfEvolutionStats> {
    const response = await this.client.get<SelfEvolutionStats>('/evolution/self-evolution/stats')
    return response.data
  }

  async getDistilledSkills(): Promise<DistilledSkill[]> {
    const response = await this.client.get('/evolution/self-evolution/skills')
    const payload = response.data
    return Array.isArray(payload) ? payload : []
  }

  async getHistory(limit: number = 50): Promise<EvolutionRecordItem[]> {
    const response = await this.client.get('/evolution/self-evolution/history', { params: { limit } })
    const payload = response.data
    return Array.isArray(payload) ? payload : []
  }

  /** Stage 1 — record an execution trace. */
  async recordExecution(taskId: string, trace: Record<string, any>): Promise<RecordExecutionResult> {
    const response = await this.client.post<RecordExecutionResult>('/evolution/self-evolution/record', {
      task_id: taskId,
      trace,
    })
    return response.data
  }

  /** Stage 2 — evaluate an execution. */
  async evaluateExecution(executionId: string, feedback?: Record<string, any>): Promise<EvaluateResult> {
    const response = await this.client.post<EvaluateResult>('/evolution/self-evolution/evaluate', {
      execution_id: executionId,
      feedback: feedback ?? null,
    })
    return response.data
  }

  /** Stage 3 — optimize strategy for an execution. */
  async optimizeStrategy(executionId: string, score: number): Promise<OptimizeResult> {
    const response = await this.client.post<OptimizeResult>('/evolution/self-evolution/optimize', {
      execution_id: executionId,
      score,
    })
    return response.data
  }

  /** Stage 4 — distill a reusable skill from successful executions. */
  async distillSkill(executionIds: string[]): Promise<DistillResult> {
    const response = await this.client.post<DistillResult>('/evolution/self-evolution/distill', {
      execution_ids: executionIds,
    })
    return response.data
  }

  /** Full Execute → Evaluate → Optimize → Learn cycle for a task. */
  async triggerCycle(taskId: string): Promise<CycleResult> {
    const response = await this.client.post<CycleResult>('/evolution/self-evolution/cycle', {
      task_id: taskId,
    })
    return response.data
  }
}

export const evolutionOps = new EvolutionOpsClient()
export default evolutionOps
