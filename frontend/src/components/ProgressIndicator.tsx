/**
 * ProgressIndicator Component
 *
 * Displays overall execution progress with step tracking and time estimates.
 */

import React, { useEffect, useState } from 'react';

interface ProgressData {
  overall_progress: number;
  current_step: string;
  total_steps: number;
  completed_steps: number;
  estimated_remaining_seconds?: number;
}

interface ProgressIndicatorProps {
  runId: string;
  onProgressUpdate?: (progress: ProgressData) => void;
  refreshInterval?: number;
}

const formatTime = (seconds: number): string => {
  if (seconds < 60) return `${Math.round(seconds)}s`;
  if (seconds < 3600) return `${Math.round(seconds / 60)}m`;
  return `${Math.round(seconds / 3600)}h`;
};

export const ProgressIndicator: React.FC<ProgressIndicatorProps> = ({
  runId,
  onProgressUpdate,
  refreshInterval = 2000,
}) => {
  const [progress, setProgress] = useState<ProgressData>({
    overall_progress: 0,
    current_step: 'Initializing...',
    total_steps: 0,
    completed_steps: 0,
  });
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    const fetchProgress = async () => {
      try {
        setLoading(true);
        const response = await fetch(`/api/v1/agent/stream/${runId}/events`);
        if (!response.ok) throw new Error('Failed to fetch progress');

        const data = await response.json();
        const events = data.events || [];

        // Find the latest progress event
        const progressEvents = events.filter((e: any) => e.event_type === 'progress');
        if (progressEvents.length > 0) {
          const latestProgress = progressEvents[progressEvents.length - 1];
          const progressData: ProgressData = {
            overall_progress: latestProgress.overall_progress || 0,
            current_step: latestProgress.current_step || 'Processing...',
            total_steps: latestProgress.total_steps || 0,
            completed_steps: latestProgress.completed_steps || 0,
            estimated_remaining_seconds: latestProgress.estimated_remaining_seconds,
          };
          setProgress(progressData);
          onProgressUpdate?.(progressData);
        }

        setError(null);
      } catch (e) {
        setError(e instanceof Error ? e.message : 'Unknown error');
      } finally {
        setLoading(false);
      }
    };

    fetchProgress();
    const interval = setInterval(fetchProgress, refreshInterval);
    return () => clearInterval(interval);
  }, [runId, refreshInterval, onProgressUpdate]);

  const progressPercent = Math.round(progress.overall_progress * 100);
  const stepPercent = progress.total_steps > 0
    ? Math.round((progress.completed_steps / progress.total_steps) * 100)
    : 0;

  return (
    <div className="p-4 bg-white rounded-lg shadow">
      {/* Overall Progress */}
      <div className="mb-6">
        <div className="flex items-center justify-between mb-2">
          <h3 className="font-bold text-gray-900">Overall Progress</h3>
          <span className="text-2xl font-bold text-blue-600">{progressPercent}%</span>
        </div>

        <div className="w-full bg-gray-200 rounded-full h-3 overflow-hidden">
          <div
            className="bg-gradient-to-r from-blue-500 to-blue-600 h-3 rounded-full transition-all duration-300"
            style={{ width: `${progressPercent}%` }}
          />
        </div>

        {progress.estimated_remaining_seconds !== undefined && progress.estimated_remaining_seconds > 0 && (
          <div className="text-xs text-gray-600 mt-2">
            ⏱️ Estimated time remaining: {formatTime(progress.estimated_remaining_seconds)}
          </div>
        )}
      </div>

      {/* Current Step */}
      <div className="mb-6">
        <div className="text-sm font-semibold text-gray-700 mb-2">Current Step</div>
        <div className="p-3 bg-blue-50 rounded border border-blue-200">
          <div className="text-sm text-gray-900">{progress.current_step}</div>
        </div>
      </div>

      {/* Step Progress */}
      {progress.total_steps > 0 && (
        <div className="mb-6">
          <div className="flex items-center justify-between mb-2">
            <h4 className="font-semibold text-gray-900">Steps</h4>
            <span className="text-sm text-gray-600">
              {progress.completed_steps} / {progress.total_steps}
            </span>
          </div>

          <div className="w-full bg-gray-200 rounded-full h-2 overflow-hidden">
            <div
              className="bg-green-500 h-2 rounded-full transition-all duration-300"
              style={{ width: `${stepPercent}%` }}
            />
          </div>

          {/* Step Breakdown */}
          <div className="mt-3 space-y-1">
            {Array.from({ length: progress.total_steps }).map((_, i) => (
              <div key={i} className="flex items-center gap-2 text-xs">
                <div className={`w-4 h-4 rounded-full flex items-center justify-center text-white text-xs font-bold ${
                  i < progress.completed_steps
                    ? 'bg-green-500'
                    : i === progress.completed_steps
                      ? 'bg-blue-500'
                      : 'bg-gray-300'
                }`}>
                  {i < progress.completed_steps ? '✓' : i === progress.completed_steps ? '●' : '○'}
                </div>
                <span className="text-gray-600">Step {i + 1}</span>
              </div>
            ))}
          </div>
        </div>
      )}

      {/* Error */}
      {error && (
        <div className="p-3 bg-red-50 border border-red-200 rounded text-sm text-red-700">
          {error}
        </div>
      )}

      {/* Loading State */}
      {loading && (
        <div className="text-xs text-gray-500 text-center">
          Updating...
        </div>
      )}
    </div>
  );
};

interface LinearProgressProps {
  value: number;
  max?: number;
  label?: string;
  showLabel?: boolean;
  color?: 'blue' | 'green' | 'red' | 'yellow' | 'purple';
  size?: 'sm' | 'md' | 'lg';
}

export const LinearProgress: React.FC<LinearProgressProps> = ({
  value,
  max = 100,
  label,
  showLabel = true,
  color = 'blue',
  size = 'md',
}) => {
  const percent = Math.min(100, Math.max(0, (value / max) * 100));

  const colorClasses: Record<string, string> = {
    blue: 'bg-blue-500',
    green: 'bg-green-500',
    red: 'bg-red-500',
    yellow: 'bg-yellow-500',
    purple: 'bg-purple-500',
  };

  const sizeClasses: Record<string, string> = {
    sm: 'h-1',
    md: 'h-2',
    lg: 'h-3',
  };

  return (
    <div>
      {showLabel && label && (
        <div className="flex items-center justify-between mb-1">
          <span className="text-xs font-medium text-gray-700">{label}</span>
          <span className="text-xs text-gray-600">{Math.round(percent)}%</span>
        </div>
      )}
      <div className={`w-full bg-gray-200 rounded-full overflow-hidden ${sizeClasses[size]}`}>
        <div
          className={`${colorClasses[color]} ${sizeClasses[size]} rounded-full transition-all duration-300`}
          style={{ width: `${percent}%` }}
        />
      </div>
    </div>
  );
};

interface CircularProgressProps {
  value: number;
  max?: number;
  size?: number;
  strokeWidth?: number;
  label?: string;
  color?: string;
}

export const CircularProgress: React.FC<CircularProgressProps> = ({
  value,
  max = 100,
  size = 120,
  strokeWidth = 4,
  label,
  color = '#3b82f6',
}) => {
  const percent = Math.min(100, Math.max(0, (value / max) * 100));
  const radius = (size - strokeWidth) / 2;
  const circumference = 2 * Math.PI * radius;
  const offset = circumference - (percent / 100) * circumference;

  return (
    <div className="flex flex-col items-center">
      <svg width={size} height={size} className="transform -rotate-90">
        {/* Background circle */}
        <circle
          cx={size / 2}
          cy={size / 2}
          r={radius}
          fill="none"
          stroke="#e5e7eb"
          strokeWidth={strokeWidth}
        />
        {/* Progress circle */}
        <circle
          cx={size / 2}
          cy={size / 2}
          r={radius}
          fill="none"
          stroke={color}
          strokeWidth={strokeWidth}
          strokeDasharray={circumference}
          strokeDashoffset={offset}
          strokeLinecap="round"
          className="transition-all duration-300"
        />
      </svg>

      {/* Center text */}
      <div className="absolute flex flex-col items-center justify-center" style={{ width: size, height: size }}>
        <div className="text-2xl font-bold text-gray-900">
          {Math.round(percent)}%
        </div>
        {label && (
          <div className="text-xs text-gray-600 mt-1">{label}</div>
        )}
      </div>
    </div>
  );
};

export default ProgressIndicator;
