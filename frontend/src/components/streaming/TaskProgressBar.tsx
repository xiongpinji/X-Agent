/**
 * TaskProgressBar Component
 *
 * Displays real-time task progress with percentage, step information,
 * and estimated time remaining.
 */

import React, { useMemo } from 'react';
import { useStreamingEvents, ProgressData } from '../hooks/useStreamingEvents';

interface TaskProgressBarProps {
  runId: string;
  showEstimate?: boolean;
  showSteps?: boolean;
  compact?: boolean;
}

export const TaskProgressBar: React.FC<TaskProgressBarProps> = ({
  runId,
  showEstimate = true,
  showSteps = true,
  compact = false,
}) => {
  const { progress, isConnected } = useStreamingEvents(runId);

  const formattedTime = useMemo(() => {
    if (!progress?.estimated_time_remaining) return null;
    const seconds = progress.estimated_time_remaining;
    if (seconds < 60) return `${seconds}s`;
    if (seconds < 3600) return `${Math.floor(seconds / 60)}m ${seconds % 60}s`;
    return `${Math.floor(seconds / 3600)}h ${Math.floor((seconds % 3600) / 60)}m`;
  }, [progress?.estimated_time_remaining]);

  const progressPercent = progress?.overall_progress ? Math.round(progress.overall_progress * 100) : 0;

  if (compact) {
    return (
      <div className="flex items-center gap-3">
        <div className="flex-1">
          <div className="w-full bg-gray-200 rounded-full h-2">
            <div
              className="bg-blue-600 h-2 rounded-full transition-all duration-300"
              style={{ width: `${progressPercent}%` }}
            />
          </div>
        </div>
        <span className="text-sm font-semibold text-gray-700 min-w-12">{progressPercent}%</span>
      </div>
    );
  }

  return (
    <div className="w-full bg-white rounded-lg shadow p-4">
      {/* Header */}
      <div className="flex items-center justify-between mb-3">
        <div className="flex items-center gap-2">
          <div className={`w-3 h-3 rounded-full ${isConnected ? 'bg-green-500' : 'bg-gray-400'}`} />
          <h3 className="text-sm font-semibold text-gray-700">Task Progress</h3>
        </div>
        <span className="text-lg font-bold text-blue-600">{progressPercent}%</span>
      </div>

      {/* Current Step */}
      {progress?.current_step && (
        <div className="mb-3">
          <p className="text-xs text-gray-500 mb-1">Current Step</p>
          <p className="text-sm font-medium text-gray-800">{progress.current_step}</p>
        </div>
      )}

      {/* Progress Bar */}
      <div className="mb-3">
        <div className="w-full bg-gray-200 rounded-full h-3 overflow-hidden">
          <div
            className="bg-gradient-to-r from-blue-500 to-blue-600 h-3 rounded-full transition-all duration-300"
            style={{ width: `${progressPercent}%` }}
          />
        </div>
      </div>

      {/* Steps Info */}
      {showSteps && progress && (
        <div className="mb-3 flex items-center justify-between text-xs text-gray-600">
          <span>
            {progress.completed_steps} / {progress.total_steps} steps
          </span>
          {formattedTime && showEstimate && (
            <span className="text-blue-600 font-medium">
              ~{formattedTime} remaining
            </span>
          )}
        </div>
      )}

      {/* Status Indicator */}
      <div className="flex items-center gap-2 text-xs">
        {isConnected ? (
          <>
            <div className="w-2 h-2 bg-green-500 rounded-full animate-pulse" />
            <span className="text-green-600">Live</span>
          </>
        ) : (
          <>
            <div className="w-2 h-2 bg-gray-400 rounded-full" />
            <span className="text-gray-600">Disconnected</span>
          </>
        )}
      </div>
    </div>
  );
};

export default TaskProgressBar;
