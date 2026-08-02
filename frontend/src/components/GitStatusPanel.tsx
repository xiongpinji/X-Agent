/**
 * GitStatusPanel Component
 *
 * Displays current git branch, modified/added/deleted files.
 * Fetches from GET /api/v1/agents/git/status with auto-refresh.
 */

import React, { useCallback, useEffect, useState } from 'react';

interface GitFile {
  status: string;
  path: string;
}

interface GitStatusData {
  success: boolean;
  branch: string;
  has_changes: boolean;
  file_count: number;
  files: GitFile[];
}

interface GitStatusPanelProps {
  refreshInterval?: number;
}

const STATUS_MAP: Record<string, { label: string; color: string }> = {
  M: { label: '修改', color: '#f59e0b' },
  A: { label: '新增', color: '#10b981' },
  D: { label: '删除', color: '#ef4444' },
  R: { label: '重命名', color: '#8b5cf6' },
  '?': { label: '未跟踪', color: '#6b7280' },
  '??': { label: '未跟踪', color: '#6b7280' },
};

function getStatusInfo(code: string) {
  return STATUS_MAP[code] || STATUS_MAP['?'];
}

export const GitStatusPanel: React.FC<GitStatusPanelProps> = ({
  refreshInterval = 15000,
}) => {
  const [data, setData] = useState<GitStatusData | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const fetchStatus = useCallback(async () => {
    try {
      const token = localStorage.getItem('auth_token');
      const apiKey = localStorage.getItem('api_key');
      const headers: Record<string, string> = {};
      if (token) headers['Authorization'] = `Bearer ${token}`;
      if (apiKey) headers['X-API-Key'] = apiKey;

      const resp = await fetch('/api/v1/agents/git/status', { headers });
      if (!resp.ok) throw new Error(`HTTP ${resp.status}`);
      const json = await resp.json();
      setData(json);
      setError(null);
    } catch (err: any) {
      setError(err.message || 'Failed to fetch git status');
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    fetchStatus();
    const timer = setInterval(fetchStatus, refreshInterval);
    return () => clearInterval(timer);
  }, [fetchStatus, refreshInterval]);

  return (
    <div className="git-status">
      <div className="git-status__header">
        <h3>🔀 Git 状态</h3>
        <button className="git-status__refresh" onClick={fetchStatus} title="刷新">
          🔄
        </button>
      </div>

      {error && <div className="git-status__error">{error}</div>}
      {loading && <div className="git-status__loading">加载中...</div>}

      {data && (
        <>
          <div className="git-status__branch">
            <span className="git-status__branch-icon">⎇</span>
            <span className="git-status__branch-name">{data.branch || 'unknown'}</span>
            {data.has_changes && (
              <span className="git-status__count">{data.file_count} 变更</span>
            )}
          </div>

          <div className="git-status__files">
            {!data.has_changes && (
              <div className="git-status__clean">✓ 工作区干净</div>
            )}
            {data.files.map((file, i) => {
              const info = getStatusInfo(file.status);
              return (
                <div key={`${file.path}-${i}`} className="git-status__file">
                  <span
                    className="git-status__file-badge"
                    style={{ background: info.color }}
                  >
                    {info.label}
                  </span>
                  <span className="git-status__file-path" title={file.path}>
                    {file.path}
                  </span>
                </div>
              );
            })}
          </div>
        </>
      )}

      <style>{`
        .git-status { display: flex; flex-direction: column; height: 100%; font-size: 13px; }
        .git-status__header { display: flex; align-items: center; justify-content: space-between; padding: 12px 16px; border-bottom: 1px solid var(--border-color, #e5e7eb); }
        .git-status__header h3 { margin: 0; font-size: 14px; }
        .git-status__refresh { background: none; border: none; cursor: pointer; font-size: 16px; }
        .git-status__error { padding: 8px 16px; color: #b91c1c; background: #fef2f2; font-size: 12px; }
        .git-status__loading { padding: 24px; text-align: center; color: #6b7280; }
        .git-status__branch { display: flex; align-items: center; gap: 8px; padding: 10px 16px; background: var(--bg-tertiary, #f9fafb); border-bottom: 1px solid var(--border-color, #f3f4f6); }
        .git-status__branch-icon { font-size: 16px; color: #6b7280; }
        .git-status__branch-name { font-weight: 600; font-family: monospace; font-size: 13px; }
        .git-status__count { margin-left: auto; font-size: 11px; color: #f59e0b; font-weight: 600; }
        .git-status__files { flex: 1; overflow-y: auto; padding: 8px 0; }
        .git-status__clean { padding: 24px; text-align: center; color: #10b981; font-size: 13px; }
        .git-status__file { display: flex; align-items: center; gap: 8px; padding: 5px 16px; }
        .git-status__file:hover { background: var(--bg-tertiary, #f9fafb); }
        .git-status__file-badge { padding: 1px 5px; border-radius: 3px; color: #fff; font-size: 10px; font-weight: 600; white-space: nowrap; }
        .git-status__file-path { flex: 1; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; font-family: monospace; font-size: 12px; color: #374151; }
      `}</style>
    </div>
  );
};

export default GitStatusPanel;
