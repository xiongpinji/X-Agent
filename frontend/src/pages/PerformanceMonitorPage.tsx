/* Performance Monitor — real-time system metrics dashboard (O). */

import React, { useState, useEffect, useCallback } from 'react';
import {
  AreaChart, Area, BarChart, Bar, RadialBarChart, RadialBar,
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

const MetricCard: React.FC<{ label: string; value: string | number; status?: 'ok' | 'warn' | 'danger' }> = ({ label, value, status = 'ok' }) => (
  <div className={`rounded-lg border p-4 ${status === 'danger' ? 'border-red-300 bg-red-50 dark:bg-red-950' : status === 'warn' ? 'border-yellow-300 bg-yellow-50 dark:bg-yellow-950' : 'border-gray-200 dark:border-gray-700 bg-white dark:bg-gray-800'}`}>
    <p className="text-xs text-gray-500 dark:text-gray-400 uppercase tracking-wide">{label}</p>
    <p className="text-2xl font-bold mt-1 text-gray-900 dark:text-white">{value}</p>
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

  return (
    <div className="p-6 space-y-6 max-w-7xl mx-auto">
      <div className="flex items-center justify-between">
        <h1 className="text-2xl font-bold text-gray-900 dark:text-white">⚡ Performance Monitor</h1>
        <span className="text-xs text-gray-400">Auto-refresh: 5s</span>
      </div>

      {error && <div className="p-3 bg-red-100 dark:bg-red-900 text-red-700 dark:text-red-300 rounded">{error}</div>}

      {/* Top metric cards */}
      <div className="grid grid-cols-2 md:grid-cols-4 lg:grid-cols-6 gap-4">
        <MetricCard label="CPU" value={health ? `${health.cpu_percent}%` : '—'} status={health ? cpuStatus(health.cpu_percent) : 'ok'} />
        <MetricCard label="Memory" value={health ? `${health.memory_percent}%` : '—'} status={health ? memStatus(health.memory_percent) : 'ok'} />
        <MetricCard label="Loop Lag" value={health ? `${health.event_loop_lag_ms}ms` : '—'} />
        <MetricCard label="Active Tasks" value={queue ? queue.pool.active_tasks : '—'} />
        <MetricCard label="Pool Util" value={queue ? `${queue.pool.utilization_percent}%` : '—'} status={queue && queue.pool.utilization_percent > 80 ? 'warn' : 'ok'} />
        <MetricCard label="Success Rate" value={queue ? `${queue.throughput.success_rate}%` : '—'} />
      </div>

      {/* Charts row */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        {/* CPU & Memory trend */}
        <div className="border rounded-lg p-4 dark:border-gray-700">
          <h3 className="text-sm font-medium mb-3 text-gray-700 dark:text-gray-300">CPU / Memory Trend</h3>
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
        </div>

        {/* Concurrency pool radial */}
        <div className="border rounded-lg p-4 dark:border-gray-700">
          <h3 className="text-sm font-medium mb-3 text-gray-700 dark:text-gray-300">Concurrency Pool</h3>
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
        </div>
      </div>

      {/* Bottom info */}
      <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
        <div className="border rounded-lg p-4 dark:border-gray-700">
          <h3 className="text-sm font-medium mb-2 text-gray-700 dark:text-gray-300">🧠 Memory Optimizer</h3>
          {perf?.memory ? (
            <ul className="text-sm space-y-1 text-gray-600 dark:text-gray-400">
              <li>Current: {perf.memory.current_mb} MB</li>
              <li>Target: {perf.memory.target_mb} MB</li>
              <li>Utilization: {perf.memory.utilization_percent}%</li>
            </ul>
          ) : <p className="text-sm text-gray-400">Loading…</p>}
        </div>
        <div className="border rounded-lg p-4 dark:border-gray-700">
          <h3 className="text-sm font-medium mb-2 text-gray-700 dark:text-gray-300">🔄 Parallel Pool</h3>
          {perf?.parallel_pool ? (
            <ul className="text-sm space-y-1 text-gray-600 dark:text-gray-400">
              <li>Max Concurrency: {String(perf.parallel_pool.max_concurrency)}</li>
              <li>Active: {String(perf.parallel_pool.active_tasks)}</li>
              <li>Batches: {String(perf.parallel_pool.total_batches)}</li>
            </ul>
          ) : <p className="text-sm text-gray-400">Loading…</p>}
        </div>
        <div className="border rounded-lg p-4 dark:border-gray-700">
          <h3 className="text-sm font-medium mb-2 text-gray-700 dark:text-gray-300">💡 Recommendation</h3>
          {health ? (
            <p className={`text-lg font-semibold ${health.recommendation === 'scale_down' ? 'text-red-500' : health.recommendation === 'scale_up' ? 'text-green-500' : 'text-blue-500'}`}>
              {health.recommendation === 'scale_down' ? '⚠️ Scale Down' : health.recommendation === 'scale_up' ? '🚀 Scale Up' : '✅ Stable'}
            </p>
          ) : <p className="text-sm text-gray-400">Loading…</p>}
          {queue?.queue.backpressure && (
            <p className="text-xs text-red-500 mt-2">⚠️ Backpressure active</p>
          )}
        </div>
      </div>
    </div>
  );
};

export default PerformanceMonitorPage;
