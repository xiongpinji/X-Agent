/* Performance Monitor — real-time system metrics dashboard (O). */

import React, { useState, useEffect, useCallback } from 'react';
import {
  AreaChart, Area, RadialBarChart, RadialBar,
  XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer, Legend,
} from 'recharts';

interface PerformanceData {
  timestamp: number;
  spawner: Record<string, unknown>;
  sandbox: Record<string, unknown>;
  rate_limiter: Record<string, unknown>;
  runs: Record<string, unknown>;
  cache: Record<string, unknown>;
  memory: { current_mb: number; target_mb: number; utilization_percent: number };
  parallel_pool: { max_concurrency: number; active_tasks: number; total_batches: number };
}

interface QueueStats {
  pool: { max_concurrency: number; active_tasks: number; utilization_percent: number; capacity_remaining: number };
  queue: { backpressure: boolean; total_batches: number };
  throughput: { completed_tasks: number; failed_tasks: number; success_rate: number };
}

interface QueueHealth {
  cpu_percent: number;
  memory_percent: number;
  memory_available_mb: number;
  event_loop_lag_ms: number;
  concurrency: { active: number; max: number };
  recommendation: string;
}

const API_BASE = '/api/v1';
const HEADERS = { 'X-API-Key': localStorage.getItem('api_key') || 'xagent-dev-key-2024' };

const DIVIDER = 'var(--divider)';

/** KPI cell — label 11px uppercase 50% + mono value, hairline vertical divider. */
const StatItem: React.FC<{
  label: string;
  value: string | number;
  status?: 'ok' | 'warn' | 'danger';
  last?: boolean;
}> = ({ label, value, status = 'ok', last }) => (
  <div
    className={`flex flex-col gap-1.5 pr-6 mr-6 ${last ? '' : 'border-r'}`}
    style={last ? undefined : { borderColor: DIVIDER }}
  >
    <dd
      className={`font-data text-[20px] leading-none order-2 ${
        status === 'danger' ? 'text-[#dc2626]' : status === 'warn' ? 'text-[#d97706]' : ''
      }`}
    >
      {value}
    </dd>
    <dt className="text-[11px] uppercase tracking-[0.06em] opacity-50 order-1">{label}</dt>
  </div>
);

export const PerformanceMonitorPage: React.FC = () => {
  const [perf, setPerf] = useState<PerformanceData | null>(null);
  const [queue, setQueue] = useState<QueueStats | null>(null);
  const [health, setHealth] = useState<QueueHealth | null>(null);
  const [history, setHistory] = useState<Array<{ time: string; cpu: number; mem: number; tasks: number }>>([]);
  const [error, setError] = useState<string | null>(null);

  const fetchData = useCallback(async () => {
    try {
      const [perfRes, queueRes, healthRes] = await Promise.all([
        fetch(`${API_BASE}/agents/performance`, { headers: HEADERS }),
        fetch(`${API_BASE}/agents/parallel/queue/stats`, { headers: HEADERS }),
        fetch(`${API_BASE}/agents/parallel/queue/health`, { headers: HEADERS }),
      ]);
      if (perfRes.ok) setPerf(await perfRes.json());
      if (queueRes.ok) setQueue(await queueRes.json());
      if (healthRes.ok) {
        const h: QueueHealth = await healthRes.json();
        setHealth(h);
        setHistory(prev => [...prev.slice(-29), {
          time: new Date().toLocaleTimeString(),
          cpu: h.cpu_percent,
          mem: h.memory_percent,
          tasks: h.concurrency.active,
        }]);
      }
      setError(null);
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Fetch failed');
    }
  }, []);

  useEffect(() => {
    fetchData();
    const interval = setInterval(fetchData, 5000);
    return () => clearInterval(interval);
  }, [fetchData]);

  const cpuStatus = (v: number) => v > 80 ? 'danger' : v > 60 ? 'warn' : 'ok';
  const memStatus = (v: number) => v > 85 ? 'danger' : v > 70 ? 'warn' : 'ok';

  const sectionTitle = 'text-[11px] uppercase tracking-[0.08em] opacity-50 mb-3';

  return (
    <div className="min-h-full px-8 py-10">
      <div className="max-w-6xl">
        {/* Header — Dashboard-style */}
        <header className="mb-8">
          <div className="w-12 border-t-2 mb-5" style={{ borderColor: 'var(--fg)' }} aria-hidden="true" />
          <div className="flex items-end justify-between gap-4 flex-wrap">
            <h1 className="page-title">⚡ Performance Monitor</h1>
            <span className="cell-data text-xs opacity-50">Auto-refresh: 5s</span>
          </div>
        </header>

        {error && (
          <div className="mb-6 p-3 border border-[#dc2626]/30 text-sm text-[#dc2626]" role="alert">
            {error}
          </div>
        )}

        {/* Top metrics — single-row KPI text, no cards */}
        <dl className="flex flex-wrap gap-y-5 mb-10">
          <StatItem label="CPU" value={health ? `${health.cpu_percent}%` : '—'} status={health ? cpuStatus(health.cpu_percent) : 'ok'} />
          <StatItem label="Memory" value={health ? `${health.memory_percent}%` : '—'} status={health ? memStatus(health.memory_percent) : 'ok'} />
          <StatItem label="Loop Lag" value={health ? `${health.event_loop_lag_ms}ms` : '—'} />
          <StatItem label="Active Tasks" value={queue ? queue.pool.active_tasks : '—'} />
          <StatItem label="Pool Util" value={queue ? `${queue.pool.utilization_percent}%` : '—'} status={queue && queue.pool.utilization_percent > 80 ? 'warn' : 'ok'} />
          <StatItem label="Success Rate" value={queue ? `${queue.throughput.success_rate}%` : '—'} last />
        </dl>

        {/* Charts — transparent containers with hairline top border */}
        <div className="grid grid-cols-1 lg:grid-cols-2 gap-10 mb-10">
          <section className="pt-4 border-t" style={{ borderColor: DIVIDER }}>
            <h3 className={sectionTitle}>CPU / Memory Trend</h3>
            <ResponsiveContainer width="100%" height={200}>
              <AreaChart data={history}>
                <CartesianGrid strokeDasharray="3 3" />
                <XAxis dataKey="time" tick={{ fontSize: 10 }} />
                <YAxis domain={[0, 100]} tick={{ fontSize: 10 }} />
                <Tooltip />
                <Legend />
                <Area type="monotone" dataKey="cpu" stroke="#ef4444" fill="#fecaca" name="CPU %" />
                <Area type="monotone" dataKey="mem" stroke="#3b82f6" fill="#bfdbfe" name="Mem %" />
              </AreaChart>
            </ResponsiveContainer>
          </section>

          <section className="pt-4 border-t" style={{ borderColor: DIVIDER }}>
            <h3 className={sectionTitle}>Concurrency Pool</h3>
            <ResponsiveContainer width="100%" height={200}>
              <RadialBarChart
                cx="50%" cy="50%" innerRadius="40%" outerRadius="90%"
                data={[{
                  name: 'Active',
                  value: queue?.pool.active_tasks ?? 0,
                  fill: '#3b82f6',
                }, {
                  name: 'Capacity',
                  value: queue?.pool.capacity_remaining ?? 0,
                  fill: '#d1d5db',
                }]}
              >
                <RadialBar dataKey="value" cornerRadius={4} />
                <Legend iconSize={10} />
                <Tooltip />
              </RadialBarChart>
            </ResponsiveContainer>
          </section>
        </div>

        {/* Bottom info — mono tabular rows, hairline dividers */}
        <div className="grid grid-cols-1 md:grid-cols-3 gap-10">
          <section className="pt-4 border-t" style={{ borderColor: DIVIDER }}>
            <h3 className={sectionTitle}>🧠 Memory Optimizer</h3>
            {perf?.memory ? (
              <div className="font-data text-[13px]">
                <div className="flex items-baseline justify-between py-2 border-b" style={{ borderColor: DIVIDER }}>
                  <span className="opacity-50">Current</span>
                  <span className="tabular-nums">{perf.memory.current_mb} MB</span>
                </div>
                <div className="flex items-baseline justify-between py-2 border-b" style={{ borderColor: DIVIDER }}>
                  <span className="opacity-50">Target</span>
                  <span className="tabular-nums">{perf.memory.target_mb} MB</span>
                </div>
                <div className="flex items-baseline justify-between py-2 border-b" style={{ borderColor: DIVIDER }}>
                  <span className="opacity-50">Utilization</span>
                  <span className="tabular-nums">{perf.memory.utilization_percent}%</span>
                </div>
              </div>
            ) : <p className="empty-state">Loading…</p>}
          </section>
          <section className="pt-4 border-t" style={{ borderColor: DIVIDER }}>
            <h3 className={sectionTitle}>🔄 Parallel Pool</h3>
            {perf?.parallel_pool ? (
              <div className="font-data text-[13px]">
                <div className="flex items-baseline justify-between py-2 border-b" style={{ borderColor: DIVIDER }}>
                  <span className="opacity-50">Max Concurrency</span>
                  <span className="tabular-nums">{String(perf.parallel_pool.max_concurrency)}</span>
                </div>
                <div className="flex items-baseline justify-between py-2 border-b" style={{ borderColor: DIVIDER }}>
                  <span className="opacity-50">Active</span>
                  <span className="tabular-nums">{String(perf.parallel_pool.active_tasks)}</span>
                </div>
                <div className="flex items-baseline justify-between py-2 border-b" style={{ borderColor: DIVIDER }}>
                  <span className="opacity-50">Batches</span>
                  <span className="tabular-nums">{String(perf.parallel_pool.total_batches)}</span>
                </div>
              </div>
            ) : <p className="empty-state">Loading…</p>}
          </section>
          <section className="pt-4 border-t" style={{ borderColor: DIVIDER }}>
            <h3 className={sectionTitle}>💡 Recommendation</h3>
            {health ? (
              <>
                <p className={`text-base font-medium ${health.recommendation === 'scale_down' ? 'text-[#dc2626]' : health.recommendation === 'scale_up' ? 'text-[#16a34a]' : ''}`}>
                  {health.recommendation === 'scale_down' ? '⚠️ Scale Down' : health.recommendation === 'scale_up' ? '🚀 Scale Up' : '✅ Stable'}
                </p>
                {queue?.queue.backpressure && (
                  <p className="text-xs text-[#dc2626] mt-2">⚠️ Backpressure active</p>
                )}
              </>
            ) : <p className="empty-state">Loading…</p>}
          </section>
        </div>
      </div>
    </div>
  );
};

export default PerformanceMonitorPage;
