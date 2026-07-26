/**
 * StreamingDashboard Component
 *
 * Integrates all streaming components into a unified dashboard for
 * real-time task monitoring and execution visualization.
 */

import React, { useState } from 'react';
import StreamingConsole from './StreamingOutput';
import TaskProgressBar from './streaming/TaskProgressBar';
import TaskTimeline from './streaming/TaskTimeline';
import LiveMetrics from './streaming/LiveMetrics';

interface StreamingDashboardProps {
  runId: string;
  layout?: 'grid' | 'tabs' | 'split';
  showConsole?: boolean;
  showProgress?: boolean;
  showTimeline?: boolean;
  showMetrics?: boolean;
  onComplete?: (result: any) => void;
  onError?: (error: Error) => void;
}

type TabType = 'console' | 'timeline' | 'metrics';

export const StreamingDashboard: React.FC<StreamingDashboardProps> = ({
  runId,
  layout = 'grid',
  showConsole = true,
  showProgress = true,
  showTimeline = true,
  showMetrics = true,
  onComplete,
  onError,
}) => {
  const [activeTab, setActiveTab] = useState<TabType>('console');

  if (layout === 'tabs') {
    return (
      <div className="flex flex-col h-full bg-gray-100 rounded-lg">
        {/* Tab Navigation */}
        <div className="flex gap-2 p-4 bg-white border-b border-gray-200">
          {showConsole && (
            <button
              onClick={() => setActiveTab('console')}
              className={`px-4 py-2 rounded font-medium transition-colors ${
                activeTab === 'console'
                  ? 'bg-blue-500 text-white'
                  : 'bg-gray-200 text-gray-700 hover:bg-gray-300'
              }`}
            >
              Console
            </button>
          )}
          {showTimeline && (
            <button
              onClick={() => setActiveTab('timeline')}
              className={`px-4 py-2 rounded font-medium transition-colors ${
                activeTab === 'timeline'
                  ? 'bg-blue-500 text-white'
                  : 'bg-gray-200 text-gray-700 hover:bg-gray-300'
              }`}
            >
              Timeline
            </button>
          )}
          {showMetrics && (
            <button
              onClick={() => setActiveTab('metrics')}
              className={`px-4 py-2 rounded font-medium transition-colors ${
                activeTab === 'metrics'
                  ? 'bg-blue-500 text-white'
                  : 'bg-gray-200 text-gray-700 hover:bg-gray-300'
              }`}
            >
              Metrics
            </button>
          )}
        </div>

        {/* Progress Bar (always visible) */}
        {showProgress && (
          <div className="p-4 bg-white border-b border-gray-200">
            <TaskProgressBar runId={runId} compact={true} />
          </div>
        )}

        {/* Tab Content */}
        <div className="flex-1 overflow-hidden p-4">
          {activeTab === 'console' && showConsole && (
            <StreamingConsole runId={runId} onComplete={onComplete} onError={onError} />
          )}
          {activeTab === 'timeline' && showTimeline && (
            <TaskTimeline runId={runId} />
          )}
          {activeTab === 'metrics' && showMetrics && (
            <LiveMetrics runId={runId} />
          )}
        </div>
      </div>
    );
  }

  if (layout === 'split') {
    return (
      <div className="flex h-full gap-4 bg-gray-100 p-4 rounded-lg">
        {/* Left Column: Console */}
        <div className="flex-1 flex flex-col gap-4">
          {showProgress && (
            <TaskProgressBar runId={runId} />
          )}
          {showConsole && (
            <div className="flex-1 min-h-0">
              <StreamingConsole runId={runId} onComplete={onComplete} onError={onError} />
            </div>
          )}
        </div>

        {/* Right Column: Timeline and Metrics */}
        <div className="w-96 flex flex-col gap-4">
          {showTimeline && (
            <div className="flex-1 min-h-0">
              <TaskTimeline runId={runId} maxSteps={30} />
            </div>
          )}
          {showMetrics && (
            <div className="flex-1 min-h-0">
              <LiveMetrics runId={runId} compact={false} />
            </div>
          )}
        </div>
      </div>
    );
  }

  // Default: grid layout
  return (
    <div className="flex flex-col h-full gap-4 bg-gray-100 p-4 rounded-lg">
      {/* Top: Progress Bar */}
      {showProgress && (
        <TaskProgressBar runId={runId} />
      )}

      {/* Middle: Console and Timeline */}
      <div className="flex gap-4 flex-1 min-h-0">
        {showConsole && (
          <div className="flex-1 min-h-0">
            <StreamingConsole runId={runId} onComplete={onComplete} onError={onError} />
          </div>
        )}
        {showTimeline && (
          <div className="w-80 min-h-0">
            <TaskTimeline runId={runId} maxSteps={30} />
          </div>
        )}
      </div>

      {/* Bottom: Metrics */}
      {showMetrics && (
        <LiveMetrics runId={runId} />
      )}
    </div>
  );
};

export default StreamingDashboard;
