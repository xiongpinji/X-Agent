/**
 * AgentWorkspace Component
 *
 * Main workspace layout integrating all 7 components:
 * - StreamingOutput: Real-time event display
 * - TaskList: Task management and tracking
 * - InteractiveQuestion: User interaction prompts
 * - FilePreview: File content viewing
 * - ProgressIndicator: Execution progress
 * - FolderSelector: Directory mounting
 *
 * Responsive layout with desktop, tablet, and mobile support.
 */

import React, { useEffect, useState } from 'react';
import { useAgentStore } from '../store/agentStore';
import StreamingOutput from '../components/StreamingOutput';
import TaskList from '../components/TaskList';
import { InteractiveQuestions } from '../components/InteractiveQuestion';
import FilePreview from '../components/FilePreview';
import ProgressIndicator from '../components/ProgressIndicator';
import FolderSelector from '../components/FolderSelector';
import './AgentWorkspace.css';

interface AgentWorkspaceProps {
  onRunComplete?: (result: any) => void;
  onError?: (error: Error) => void;
}

export const AgentWorkspace: React.FC<AgentWorkspaceProps> = ({
  onRunComplete,
  onError,
}) => {
  const {
    currentRun,
    runId,
    isRunning,
    isConnected,
    error,
    tasks: _tasks,
    messages: _messages,
    pendingQuestions,
    selectedFilePath,
    startRun,
    stopRun,
    fetchTasks,
    fetchPendingQuestions,
    selectFile: _selectFile,
    clearError,
  } = useAgentStore();

  const [taskInput, setTaskInput] = useState('');
  const [showAdvanced, setShowAdvanced] = useState(false);
  const [extraContext, setExtraContext] = useState('');
  const [layout, setLayout] = useState<'desktop' | 'tablet' | 'mobile'>('desktop');

  // Detect layout based on window size
  useEffect(() => {
    const handleResize = () => {
      const width = window.innerWidth;
      if (width < 768) {
        setLayout('mobile');
      } else if (width < 1024) {
        setLayout('tablet');
      } else {
        setLayout('desktop');
      }
    };

    handleResize();
    window.addEventListener('resize', handleResize);
    return () => window.removeEventListener('resize', handleResize);
  }, []);

  // Fetch tasks and questions periodically when running
  useEffect(() => {
    if (!isRunning || !runId) return;

    const taskInterval = setInterval(() => {
      fetchTasks(runId).catch(console.error);
    }, 3000);

    const questionInterval = setInterval(() => {
      fetchPendingQuestions(runId).catch(console.error);
    }, 2000);

    return () => {
      clearInterval(taskInterval);
      clearInterval(questionInterval);
    };
  }, [isRunning, runId, fetchTasks, fetchPendingQuestions]);

  const handleStartRun = async () => {
    try {
      const context = showAdvanced && extraContext ? JSON.parse(extraContext) : undefined;
      await startRun(taskInput, context);
      setTaskInput('');
      setExtraContext('');
    } catch (err) {
      const error = err instanceof Error ? err : new Error(String(err));
      onError?.(error);
    }
  };

  const handleStopRun = async () => {
    try {
      await stopRun();
    } catch (err) {
      const error = err instanceof Error ? err : new Error(String(err));
      onError?.(error);
    }
  };

  const handleRunComplete = (result: any) => {
    onRunComplete?.(result);
  };

  const renderDesktopLayout = () => (
    <div className="workspace-container">
      {/* Top Bar */}
      <div className="workspace-topbar">
        <div className="workspace-topbar-left">
          <h1 className="workspace-title">Agent Workspace</h1>
          <div className="workspace-status">
            <div className={`status-indicator ${isConnected ? 'connected' : 'disconnected'}`} />
            <span className="status-text">
              {isConnected ? 'Connected' : isRunning ? 'Connecting...' : 'Disconnected'}
            </span>
          </div>
        </div>
        <div className="workspace-topbar-right">
          {currentRun && (
            <div className="run-info">
              <span className="run-id">Run: {currentRun.run_id.slice(0, 8)}</span>
              <span className={`run-status ${currentRun.status}`}>{currentRun.status}</span>
            </div>
          )}
        </div>
      </div>

      {/* Error Banner */}
      {error && (
        <div className="workspace-error-banner">
          <div className="error-content">
            <span className="error-icon">⚠️</span>
            <span className="error-message">{error}</span>
            <button
              className="error-close"
              onClick={clearError}
              aria-label="Close error"
            >
              ✕
            </button>
          </div>
        </div>
      )}

      {/* Main Content */}
      <div className="workspace-main">
        {/* Left Panel */}
        <div className="workspace-left-panel">
          <div className="panel-section">
            <h2 className="panel-title">Task Input</h2>
            <div className="task-input-form">
              <textarea
                value={taskInput}
                onChange={(e) => setTaskInput(e.target.value)}
                placeholder="Enter your task here..."
                className="task-input"
                disabled={isRunning}
                rows={4}
              />
              <div className="form-actions">
                <button
                  onClick={handleStartRun}
                  disabled={isRunning || !taskInput.trim()}
                  className="btn btn-primary"
                >
                  {isRunning ? 'Running...' : 'Start'}
                </button>
                {isRunning && (
                  <button
                    onClick={handleStopRun}
                    className="btn btn-danger"
                  >
                    Stop
                  </button>
                )}
              </div>

              {/* Advanced Options */}
              <button
                onClick={() => setShowAdvanced(!showAdvanced)}
                className="btn btn-secondary btn-small"
              >
                {showAdvanced ? 'Hide' : 'Show'} Advanced
              </button>

              {showAdvanced && (
                <div className="advanced-options">
                  <label htmlFor="extra-context" className="form-label">Extra Context (JSON)</label>
                  <textarea
                    id="extra-context"
                    value={extraContext}
                    onChange={(e) => setExtraContext(e.target.value)}
                    placeholder='{"path":"backend/app/core/agent.py"}'
                    className="task-input"
                    rows={3}
                  />
                </div>
              )}
            </div>
          </div>

          {/* Folder Selector */}
          <div className="panel-section">
            <h2 className="panel-title">Workspace</h2>
            <FolderSelector />
          </div>
        </div>

        {/* Center Panel */}
        <div className="workspace-center-panel">
          <div className="panel-section full-height">
            <h2 className="panel-title">Streaming Output</h2>
            {runId ? (
              <StreamingOutput
                runId={runId}
                onComplete={handleRunComplete}
                onError={(err) => onError?.(err)}
                autoScroll={true}
              />
            ) : (
              <div className="empty-state">
                <div className="empty-icon">📡</div>
                <div className="empty-text">No active run</div>
                <div className="empty-hint">Start a task to see streaming output</div>
              </div>
            )}
          </div>
        </div>

        {/* Right Panel */}
        <div className="workspace-right-panel">
          {/* Progress Indicator */}
          {runId && (
            <div className="panel-section">
              <h2 className="panel-title">Progress</h2>
              <ProgressIndicator runId={runId} refreshInterval={2000} />
            </div>
          )}

          {/* Interactive Questions */}
          {runId && pendingQuestions.length > 0 && (
            <div className="panel-section">
              <h2 className="panel-title">Questions ({pendingQuestions.length})</h2>
              <InteractiveQuestions runId={runId} />
            </div>
          )}

          {/* File Preview */}
          {selectedFilePath && (
            <div className="panel-section">
              <h2 className="panel-title">File Preview</h2>
              <FilePreview filePath={selectedFilePath} />
            </div>
          )}
        </div>
      </div>

      {/* Bottom Panel - Tasks */}
      {runId && (
        <div className="workspace-bottom-panel">
          <h2 className="panel-title">Tasks</h2>
          <TaskList runId={runId} onTaskClick={(_task) => {}} />
        </div>
      )}
    </div>
  );

  const renderTabletLayout = () => (
    <div className="workspace-container workspace-tablet">
      {/* Top Bar */}
      <div className="workspace-topbar">
        <h1 className="workspace-title">Agent Workspace</h1>
        <div className={`status-indicator ${isConnected ? 'connected' : 'disconnected'}`} />
      </div>

      {/* Error Banner */}
      {error && (
        <div className="workspace-error-banner">
          <span className="error-message">{error}</span>
          <button className="error-close" onClick={clearError}>✕</button>
        </div>
      )}

      {/* Tabs */}
      <div className="workspace-tabs">
        <button className="tab active">Input</button>
        <button className="tab">Output</button>
        <button className="tab">Tasks</button>
        <button className="tab">Files</button>
      </div>

      {/* Content */}
      <div className="workspace-content">
        <div className="panel-section">
          <textarea
            value={taskInput}
            onChange={(e) => setTaskInput(e.target.value)}
            placeholder="Enter your task..."
            className="task-input"
            disabled={isRunning}
            rows={4}
          />
          <div className="form-actions">
            <button
              onClick={handleStartRun}
              disabled={isRunning || !taskInput.trim()}
              className="btn btn-primary"
            >
              {isRunning ? 'Running...' : 'Start'}
            </button>
            {isRunning && (
              <button onClick={handleStopRun} className="btn btn-danger">
                Stop
              </button>
            )}
          </div>
        </div>

        {runId && (
          <>
            <StreamingOutput runId={runId} onComplete={handleRunComplete} />
            <TaskList runId={runId} />
          </>
        )}
      </div>
    </div>
  );

  const renderMobileLayout = () => (
    <div className="workspace-container workspace-mobile">
      <div className="workspace-topbar">
        <h1 className="workspace-title">Agent</h1>
      </div>

      {error && (
        <div className="workspace-error-banner">
          <span className="error-message">{error}</span>
          <button className="error-close" onClick={clearError}>✕</button>
        </div>
      )}

      <div className="workspace-content">
        <div className="panel-section">
          <textarea
            value={taskInput}
            onChange={(e) => setTaskInput(e.target.value)}
            placeholder="Task..."
            className="task-input"
            disabled={isRunning}
            rows={3}
          />
          <button
            onClick={handleStartRun}
            disabled={isRunning || !taskInput.trim()}
            className="btn btn-primary btn-block"
          >
            {isRunning ? 'Running...' : 'Start'}
          </button>
        </div>

        {runId && (
          <>
            <StreamingOutput runId={runId} onComplete={handleRunComplete} />
            <TaskList runId={runId} />
          </>
        )}
      </div>
    </div>
  );

  return (
    <>
      {layout === 'desktop' && renderDesktopLayout()}
      {layout === 'tablet' && renderTabletLayout()}
      {layout === 'mobile' && renderMobileLayout()}
    </>
  );
};

export default AgentWorkspace;
