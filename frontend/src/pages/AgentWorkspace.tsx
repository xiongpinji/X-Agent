/**
 * AgentWorkspace Component
 *
 * Main workspace layout integrating:
 * - AgentStreamPanel: Real-time POST-based SSE streaming (Codex-style)
 * - TaskList: Task management and tracking
 * - FilePreview: File content viewing
 * - FolderSelector: Directory mounting
 *
 * Responsive layout with desktop, tablet, and mobile support.
 */

import React, { useEffect, useState } from 'react';
import AgentStreamPanel from '../components/AgentStreamPanel';
import FolderSelector from '../components/FolderSelector';
import GitStatusPanel from '../components/GitStatusPanel';
import RunHistoryPanel from '../components/RunHistoryPanel';
import './AgentWorkspace.css';

interface AgentWorkspaceProps {
  onRunComplete?: (result: any) => void;
  onError?: (error: any) => void;
}

export const AgentWorkspace: React.FC<AgentWorkspaceProps> = ({
  onRunComplete,
  onError,
}) => {
  const [layout, setLayout] = useState<'desktop' | 'tablet' | 'mobile'>('desktop');

  // Detect layout based on window size
  useEffect(() => {
    const handleResize = () => {
      const width = window.innerWidth;
      if (width < 768) setLayout('mobile');
      else if (width < 1024) setLayout('tablet');
      else setLayout('desktop');
    };
    handleResize();
    window.addEventListener('resize', handleResize);
    return () => window.removeEventListener('resize', handleResize);
  }, []);

  const renderDesktopLayout = () => (
    <div className="workspace-container">
      {/* Top Bar */}
      <div className="workspace-topbar">
        <div className="workspace-topbar-left">
          <h1 className="workspace-title">Agent Workspace</h1>
          <div className="workspace-status">
            <div className="status-indicator connected" />
            <span className="status-text">Ready</span>
          </div>
        </div>
      </div>

      {/* Main Content */}
      <div className="workspace-main">
        {/* Left Panel - Workspace selector */}
        <div className="workspace-left-panel">
          <div className="panel-section">
            <h2 className="panel-title">Workspace</h2>
            <FolderSelector />
          </div>
        </div>

        {/* Center Panel - Stream */}
        <div className="workspace-center-panel">
          <div className="panel-section full-height">
            <AgentStreamPanel
              onRunComplete={onRunComplete}
              onError={(err) => onError?.(new Error(String(err)))}
            />
          </div>
        </div>

        {/* Right Panel - Git & History */}
        <div className="workspace-right-panel">
          <div className="panel-section">
            <GitStatusPanel />
          </div>
          <div className="panel-section">
            <RunHistoryPanel limit={10} />
          </div>
        </div>
      </div>
    </div>
  );

  const renderTabletLayout = () => (
    <div className="workspace-container workspace-tablet">
      <div className="workspace-topbar">
        <h1 className="workspace-title">Agent Workspace</h1>
      </div>
      <div className="workspace-content">
        <AgentStreamPanel
          onRunComplete={onRunComplete}
          onError={(err) => onError?.(new Error(String(err)))}
        />
      </div>
    </div>
  );

  const renderMobileLayout = () => (
    <div className="workspace-container workspace-mobile">
      <div className="workspace-topbar">
        <h1 className="workspace-title">Agent</h1>
      </div>
      <div className="workspace-content">
        <AgentStreamPanel
          onRunComplete={onRunComplete}
          onError={(err) => onError?.(new Error(String(err)))}
        />
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
