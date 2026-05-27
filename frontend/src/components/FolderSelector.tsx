/**
 * FolderSelector Component
 *
 * Provides a file browser interface for selecting and mounting directories.
 * Features:
 * - Directory browsing
 * - Path input
 * - Permission selection (read-only/read-write)
 * - Mount status display
 * - Unmount operations
 */

import React, { useState, useEffect } from 'react';
import './FolderSelector.css';

interface Mount {
  mount_id: string;
  mount_path: string;
  host_path: string;
  mode: 'ro' | 'rw';
  created_at: string;
}

interface FolderSelectorProps {
  onMountChange?: (mounts: Mount[]) => void;
  onError?: (error: string) => void;
}

export const FolderSelector: React.FC<FolderSelectorProps> = ({
  onMountChange,
  onError,
}) => {
  const [mounts, setMounts] = useState<Mount[]>([]);
  const [hostPath, setHostPath] = useState('');
  const [mountPath, setMountPath] = useState('');
  const [readOnly, setReadOnly] = useState(false);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  // Load mounts on component mount
  useEffect(() => {
    loadMounts();
  }, []);

  // Notify parent of mount changes
  useEffect(() => {
    onMountChange?.(mounts);
  }, [mounts, onMountChange]);

  const loadMounts = async () => {
    try {
      setLoading(true);
      const response = await fetch('/api/v1/workspace/mounts');
      if (!response.ok) {
        throw new Error('Failed to load mounts');
      }
      const data = await response.json();
      setMounts(data);
      setError(null);
    } catch (err) {
      const message = err instanceof Error ? err.message : 'Unknown error';
      setError(message);
      onError?.(message);
    } finally {
      setLoading(false);
    }
  };

  const handleMount = async (e: React.FormEvent) => {
    e.preventDefault();

    if (!hostPath.trim()) {
      setError('Please enter a host path');
      return;
    }

    try {
      setLoading(true);
      const response = await fetch('/api/v1/workspace/mount', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({
          host_path: hostPath,
          mount_path: mountPath || undefined,
          read_only: readOnly,
        }),
      });

      if (!response.ok) {
        const errorData = await response.json();
        throw new Error(errorData.detail || 'Failed to mount directory');
      }

      // Reset form
      setHostPath('');
      setMountPath('');
      setReadOnly(false);
      setError(null);

      // Reload mounts
      await loadMounts();
    } catch (err) {
      const message = err instanceof Error ? err.message : 'Unknown error';
      setError(message);
      onError?.(message);
    } finally {
      setLoading(false);
    }
  };

  const handleUnmount = async (mountId: string) => {
    try {
      setLoading(true);
      const response = await fetch(`/api/v1/workspace/mount/${mountId}`, {
        method: 'DELETE',
      });

      if (!response.ok) {
        throw new Error('Failed to unmount directory');
      }

      setError(null);
      await loadMounts();
    } catch (err) {
      const message = err instanceof Error ? err.message : 'Unknown error';
      setError(message);
      onError?.(message);
    } finally {
      setLoading(false);
    }
  };

  const handleBrowse = async () => {
    // This would typically open a native file picker
    // For now, we'll show a placeholder
    try {
      // In a real implementation, this would use:
      // - Electron's dialog.showOpenDialog() for desktop
      // - File System Access API for web
      // - Or a custom file browser component
      alert('File browser not yet implemented. Please enter path manually.');
    } catch (err) {
      const message = err instanceof Error ? err.message : 'Unknown error';
      setError(message);
    }
  };

  return (
    <div className="folder-selector">
      <div className="folder-selector__container">
        {/* Mount Form */}
        <div className="folder-selector__form-section">
          <h2 className="folder-selector__title">Mount Directory</h2>

          <form onSubmit={handleMount} className="folder-selector__form">
            <div className="folder-selector__form-group">
              <label htmlFor="host-path" className="folder-selector__label">
                Host Path
              </label>
              <div className="folder-selector__input-group">
                <input
                  id="host-path"
                  type="text"
                  value={hostPath}
                  onChange={(e) => setHostPath(e.target.value)}
                  placeholder="/path/to/directory"
                  className="folder-selector__input"
                  disabled={loading}
                />
                <button
                  type="button"
                  onClick={handleBrowse}
                  className="folder-selector__browse-btn"
                  disabled={loading}
                >
                  Browse
                </button>
              </div>
            </div>

            <div className="folder-selector__form-group">
              <label htmlFor="mount-path" className="folder-selector__label">
                Mount Path (optional)
              </label>
              <input
                id="mount-path"
                type="text"
                value={mountPath}
                onChange={(e) => setMountPath(e.target.value)}
                placeholder="/mounts/my-project"
                className="folder-selector__input"
                disabled={loading}
              />
            </div>

            <div className="folder-selector__form-group">
              <label className="folder-selector__checkbox-label">
                <input
                  type="checkbox"
                  checked={readOnly}
                  onChange={(e) => setReadOnly(e.target.checked)}
                  className="folder-selector__checkbox"
                  disabled={loading}
                />
                <span>Read-only</span>
              </label>
            </div>

            {error && (
              <div className="folder-selector__error">
                {error}
              </div>
            )}

            <button
              type="submit"
              className="folder-selector__submit-btn"
              disabled={loading || !hostPath.trim()}
            >
              {loading ? 'Mounting...' : 'Mount Directory'}
            </button>
          </form>
        </div>

        {/* Mounts List */}
        <div className="folder-selector__list-section">
          <h2 className="folder-selector__title">Mounted Directories</h2>

          {mounts.length === 0 ? (
            <div className="folder-selector__empty">
              No directories mounted yet
            </div>
          ) : (
            <div className="folder-selector__list">
              {mounts.map((mount) => (
                <div key={mount.mount_id} className="folder-selector__mount-item">
                  <div className="folder-selector__mount-info">
                    <div className="folder-selector__mount-path">
                      {mount.mount_path}
                    </div>
                    <div className="folder-selector__mount-host">
                      {mount.host_path}
                    </div>
                    <div className="folder-selector__mount-meta">
                      <span className={`folder-selector__mode folder-selector__mode--${mount.mode}`}>
                        {mount.mode === 'ro' ? 'Read-only' : 'Read-write'}
                      </span>
                      <span className="folder-selector__created">
                        {new Date(mount.created_at).toLocaleDateString()}
                      </span>
                    </div>
                  </div>
                  <button
                    onClick={() => handleUnmount(mount.mount_id)}
                    className="folder-selector__unmount-btn"
                    disabled={loading}
                    title="Unmount directory"
                  >
                    ✕
                  </button>
                </div>
              ))}
            </div>
          )}
        </div>
      </div>
    </div>
  );
};

export default FolderSelector;
