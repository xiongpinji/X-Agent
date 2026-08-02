/**
 * RunHistoryPanel Component
 *
 * Displays past agent runs with status, duration, and tool call summary.
 * Fetches from GET /api/v1/agents/runs and supports click-to-expand timeline.
 */

import React, { useCallback, useEffect, useState } from 'react';

interface RunRecord {
  trace_id: string;
  status: string;
  task?: string;
  answer?: string;
  iterations?: number;
  tool_calls?: Array<{ tool_name: string; success: boolean }>;
  created_at?: string;
  started_at?: string;
  finished_at?: string;
  duration_ms?: number;
  [key: string]: any;
}

interface RunHistoryPanelProps {
  limit?: number;
  refreshInterval?: number;
  onSelectRun?: (run: RunRecord) => void;
}

function formatDuration(ms?: number): string {
  if (!ms) return '—';
  if (ms < 1000) return `${ms}ms`;
  return `${(ms / 1000).toFixed(1)}s`;
}

function formatTime(iso?: string): string {
  if (!iso) return '—';
  try {
    return new Date(iso).toLocaleString('zh-CN', { hour12: false });
  } catch {
    return iso;
  }
}

const StatusBadge: React.FC<{ status: string }> = ({ status }) => {
  const colors: Record<string, string> = {
    completed: '#10b981',
    failed: '#ef4444',
    running: '#3b82f6',
    cancelled: '#6b7280',
  };
  return (
    <span
      className="run-history__badge"
      style={{ background: colors[status] || '#6b7280' }}
    >
      {status}
    </span>
  );
};

export const RunHistoryPanel: React.FC<RunHistoryPanelProps> = ({
  limit = 20,
  refreshInterval = 10000,
  onSelectRun,
}) => {
  const [runs, setRuns] = useState<RunRecord[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [expandedId, setExpandedId] = useState<string | null>(null);

  const fetchRuns = useCallback(async () => {
    try {
      const token = localStorage.getItem('auth_token');
      const apiKey = localStorage.getItem('api_key');
      const headers: Record<string, string> = {};
      if (token) headers['Authorization'] = `Bearer ${token}`;
      if (apiKey) headers['X-API-Key'] = apiKey;

      const resp = await fetch(`/api/v1/agents/runs?limit=${limit}`, { headers });
      if (!resp.ok) throw new Error(`HTTP ${resp.status}`);
      const data = await resp.json();
      setRuns(Array.isArray(data) ? data : []);
      setError(null);
    } catch (err: any) {
      setError(err.message || 'Failed to fetch runs');
    } finally {
      setLoading(false);
    }
  }, [limit]);

  useEffect(() => {
    fetchRuns();
    const timer = setInterval(fetchRuns, refreshInterval);
    return () => clearInterval(timer);
  }, [fetchRuns, refreshInterval]);

  return (
    <div className="run-history">
      <div className="run-history__header">
        <h3>📜 运行历史</h3>
        <button className="run-history__refresh" onClick={fetchRuns} title="刷新">
          🔄
        </button>
      </div>

      {error && <div className="run-history__error">{error}</div>}
      {loading && <div className="run-history__loading">加载中...</div>}

      <div className="run-history__list">
        {runs.length === 0 && !loading && (
          <div className="run-history__empty">暂无运行记录</div>
        )}
        {runs.map((run) => (
          <div
            key={run.trace_id}
            className={`run-history__item ${expandedId === run.trace_id ? 'expanded' : ''}`}
            onClick={() => {
              setExpandedId(expandedId === run.trace_id ? null : run.trace_id);
              onSelectRun?.(run);
            }}
          >
            <div className="run-history__item-main">
              <StatusBadge status={run.status || 'unknown'} />
              <span className="run-history__task">
                {(run.task || run.answer || run.trace_id || '').slice(0, 60)}
              </span>
              <span className="run-history__meta">
                {run.iterations ? `${run.iterations} iter` : ''}
                {run.tool_calls ? ` · ${run.tool_calls.length} tools` : ''}
              </span>
            </div>
            <div className="run-history__item-time">
              {formatTime(run.created_at || run.started_at)}
            </div>

            {expandedId === run.trace_id && (
              <div className="run-history__detail">
                {run.tool_calls && run.tool_calls.length > 0 && (
                  <div className="run-history__tools">
                    {run.tool_calls.map((tc, i) => (
                      <span key={i} className={`run-history__tool ${tc.success ? 'ok' : 'fail'}`}>
                        {tc.success ? '✓' : '✗'} {tc.tool_name}
                      </span>
                    ))}
                  </div>
                )}
                {run.duration_ms && (
                  <div className="run-history__duration">
                    ⏱ {formatDuration(run.duration_ms)}
                  </div>
                )}
                <div className="run-history__trace-id">
                  ID: {run.trace_id}
                </div>
              </div>
            )}
          </div>
        ))}
      </div>

      <style>{`
        .run-history { display: flex; flex-direction: column; height: 100%; font-size: 13px; }
        .run-history__header { display: flex; align-items: center; justify-content: space-between; padding: 12px 16px; border-bottom: 1px solid var(--border-color, #e5e7eb); }
        .run-history__header h3 { margin: 0; font-size: 14px; }
        .run-history__refresh { background: none; border: none; cursor: pointer; font-size: 16px; }
        .run-history__error { padding: 8px 16px; color: #b91c1c; background: #fef2f2; font-size: 12px; }
        .run-history__loading, .run-history__empty { padding: 24px; text-align: center; color: #6b7280; }
        .run-history__list { flex: 1; overflow-y: auto; }
        .run-history__item { padding: 10px 16px; border-bottom: 1px solid var(--border-color, #f3f4f6); cursor: pointer; transition: background 0.15s; }
        .run-history__item:hover { background: var(--bg-tertiary, #f9fafb); }
        .run-history__item-main { display: flex; align-items: center; gap: 8px; }
        .run-history__badge { padding: 2px 6px; border-radius: 4px; color: #fff; font-size: 10px; font-weight: 600; text-transform: uppercase; }
        .run-history__task { flex: 1; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
        .run-history__meta { font-size: 11px; color: #6b7280; white-space: nowrap; }
        .run-history__item-time { font-size: 11px; color: #9ca3af; margin-top: 4px; }
        .run-history__detail { margin-top: 8px; padding: 8px; background: var(--bg-tertiary, #f3f4f6); border-radius: 6px; }
        .run-history__tools { display: flex; flex-wrap: wrap; gap: 4px; margin-bottom: 6px; }
        .run-history__tool { padding: 2px 6px; border-radius: 3px; font-size: 11px; font-family: monospace; }
        .run-history__tool.ok { background: #ecfdf5; color: #047857; }
        .run-history__tool.fail { background: #fef2f2; color: #b91c1c; }
        .run-history__duration { font-size: 11px; color: #6b7280; }
        .run-history__trace-id { font-size: 10px; color: #9ca3af; font-family: monospace; margin-top: 4px; }
      `}</style>
    </div>
  );
};

export default RunHistoryPanel;
