/**
 * LiveMetrics Component
 *
 * Displays real-time metrics including token usage, tool calls,
 * execution time, and custom metrics.
 */

import React, { useMemo } from 'react';
import { useStreamingEvents, StreamEvent, MetricsData } from '../hooks/useStreamingEvents';

interface MetricCard {
  label: string;
  value: string | number;
  unit?: string;
  trend?: 'up' | 'down' | 'stable';
  color?: 'blue' | 'green' | 'orange' | 'red';
}

interface LiveMetricsProps {
  runId: string;
  metrics?: string[];
  compact?: boolean;
}

export const LiveMetrics: React.FC<LiveMetricsProps> = ({
  runId,
  metrics: customMetrics,
  compact = false,
}) => {
  const { events, metrics: streamMetrics, progress } = useStreamingEvents(runId);

  const calculatedMetrics = useMemo(() => {
    const cards: MetricCard[] = [];
    const startTime = events.length > 0 ? new Date(events[0].timestamp).getTime() : Date.now();
    const endTime = events.length > 0 ? new Date(events[events.length - 1].timestamp).getTime() : Date.now();
    const elapsedSeconds = Math.round((endTime - startTime) / 1000);

    // Execution Time
    cards.push({
      label: 'Execution Time',
      value: elapsedSeconds,
      unit: 's',
      color: 'blue',
    });

    // Tool Calls Count
    const toolCalls = events.filter((e) => e.event_type === 'tool_call').length;
    cards.push({
      label: 'Tool Calls',
      value: toolCalls,
      color: 'green',
    });

    // Tool Results Count
    const toolResults = events.filter((e) => e.event_type === 'tool_result').length;
    const successfulTools = events.filter((e) => e.event_type === 'tool_result' && e.success).length;
    cards.push({
      label: 'Success Rate',
      value: toolCalls > 0 ? Math.round((successfulTools / toolCalls) * 100) : 0,
      unit: '%',
      color: successfulTools === toolCalls ? 'green' : 'orange',
    });

    // Error Count
    const errors = events.filter((e) => e.event_type === 'error').length;
    cards.push({
      label: 'Errors',
      value: errors,
      color: errors > 0 ? 'red' : 'green',
    });

    // Messages Count
    const messages = events.filter((e) => e.event_type === 'message').length;
    cards.push({
      label: 'Messages',
      value: messages,
      color: 'blue',
    });

    // Add custom metrics from stream
    if (customMetrics) {
      for (const metricName of customMetrics) {
        if (streamMetrics[metricName] !== undefined) {
          cards.push({
            label: metricName,
            value: streamMetrics[metricName],
            color: 'blue',
          });
        }
      }
    } else {
      // Show all available metrics
      for (const [key, value] of Object.entries(streamMetrics)) {
        cards.push({
          label: key,
          value,
          color: 'blue',
        });
      }
    }

    return cards;
  }, [events, streamMetrics, customMetrics]);

  const getColorClass = (color?: string) => {
    switch (color) {
      case 'green':
        return 'bg-green-50 border-green-200';
      case 'orange':
        return 'bg-orange-50 border-orange-200';
      case 'red':
        return 'bg-red-50 border-red-200';
      default:
        return 'bg-blue-50 border-blue-200';
    }
  };

  const getTextColorClass = (color?: string) => {
    switch (color) {
      case 'green':
        return 'text-green-700';
      case 'orange':
        return 'text-orange-700';
      case 'red':
        return 'text-red-700';
      default:
        return 'text-blue-700';
    }
  };

  if (compact) {
    return (
      <div className="grid grid-cols-2 gap-2">
        {calculatedMetrics.slice(0, 4).map((metric, index) => (
          <div key={index} className={`p-2 rounded border ${getColorClass(metric.color)}`}>
            <p className="text-xs text-gray-600">{metric.label}</p>
            <p className={`text-lg font-bold ${getTextColorClass(metric.color)}`}>
              {metric.value}
              {metric.unit && <span className="text-sm ml-1">{metric.unit}</span>}
            </p>
          </div>
        ))}
      </div>
    );
  }

  return (
    <div className="w-full bg-white rounded-lg shadow p-4">
      {/* Header */}
      <div className="mb-4">
        <h3 className="text-sm font-semibold text-gray-700">Live Metrics</h3>
      </div>

      {/* Metrics Grid */}
      <div className="grid grid-cols-2 md:grid-cols-3 gap-3">
        {calculatedMetrics.map((metric, index) => (
          <div
            key={index}
            className={`p-3 rounded-lg border-2 transition-all ${getColorClass(metric.color)}`}
          >
            <p className="text-xs text-gray-600 mb-1">{metric.label}</p>
            <div className="flex items-baseline gap-1">
              <p className={`text-2xl font-bold ${getTextColorClass(metric.color)}`}>
                {metric.value}
              </p>
              {metric.unit && (
                <p className={`text-sm font-medium ${getTextColorClass(metric.color)}`}>
                  {metric.unit}
                </p>
              )}
            </div>
            {metric.trend && (
              <p className="text-xs text-gray-500 mt-1">
                {metric.trend === 'up' && '📈'}
                {metric.trend === 'down' && '📉'}
                {metric.trend === 'stable' && '➡️'}
              </p>
            )}
          </div>
        ))}
      </div>

      {/* Progress Summary */}
      {progress && (
        <div className="mt-4 pt-4 border-t border-gray-200">
          <p className="text-xs text-gray-600 mb-2">Progress Summary</p>
          <div className="space-y-1 text-xs text-gray-700">
            <p>
              <span className="font-medium">Current Step:</span> {progress.current_step}
            </p>
            <p>
              <span className="font-medium">Steps:</span> {progress.completed_steps} / {progress.total_steps}
            </p>
            {progress.estimated_time_remaining && (
              <p>
                <span className="font-medium">ETA:</span> ~{progress.estimated_time_remaining}s
              </p>
            )}
          </div>
        </div>
      )}
    </div>
  );
};

export default LiveMetrics;
