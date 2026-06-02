/**
 * TaskTimeline Component
 *
 * Displays a visual timeline of task execution with steps, tool calls,
 * and their timing information.
 */

import React, { useMemo } from 'react';
import { useStreamingEvents, StreamEvent } from '../hooks/useStreamingEvents';

interface TimelineStep {
  id: string;
  type: 'task' | 'tool' | 'message' | 'error';
  title: string;
  timestamp: string;
  duration?: number;
  status: 'pending' | 'running' | 'completed' | 'failed';
  details?: string;
}

interface TaskTimelineProps {
  runId: string;
  maxSteps?: number;
  showDurations?: boolean;
}

export const TaskTimeline: React.FC<TaskTimelineProps> = ({
  runId,
  maxSteps = 50,
  showDurations = true,
}) => {
  const { events } = useStreamingEvents(runId);

  const timelineSteps = useMemo(() => {
    const steps: TimelineStep[] = [];
    const toolCallMap: Map<string, { startTime: string; toolName: string }> = new Map();
    let lastTimestamp: string | null = null;

    for (const event of events) {
      const timestamp = event.timestamp;

      switch (event.event_type) {
        case 'task_update':
          steps.push({
            id: `task-${event.task_id}`,
            type: 'task',
            title: event.details?.title || `Task: ${event.task_id}`,
            timestamp,
            status: event.status as any,
            details: event.details?.description,
          });
          break;

        case 'tool_call':
          toolCallMap.set(event.tool_id, {
            startTime: timestamp,
            toolName: event.tool_name,
          });
          steps.push({
            id: `tool-call-${event.tool_id}`,
            type: 'tool',
            title: `Calling ${event.tool_name}`,
            timestamp,
            status: 'running',
            details: JSON.stringify(event.arguments).substring(0, 100),
          });
          break;

        case 'tool_result':
          const toolCall = toolCallMap.get(event.tool_id);
          const duration = toolCall
            ? Math.round(
                (new Date(timestamp).getTime() - new Date(toolCall.startTime).getTime()) / 1000
              )
            : undefined;

          steps.push({
            id: `tool-result-${event.tool_id}`,
            type: 'tool',
            title: `${event.tool_name} Result`,
            timestamp,
            duration,
            status: event.success ? 'completed' : 'failed',
            details: event.success ? 'Success' : 'Failed',
          });
          break;

        case 'message':
          steps.push({
            id: `message-${event.sequence}`,
            type: 'message',
            title: `${event.role}: ${event.content.substring(0, 50)}...`,
            timestamp,
            status: 'completed',
          });
          break;

        case 'error':
          steps.push({
            id: `error-${event.sequence}`,
            type: 'error',
            title: `Error: ${event.error_code}`,
            timestamp,
            status: 'failed',
            details: event.error_message,
          });
          break;
      }

      lastTimestamp = timestamp;
    }

    return steps.slice(-maxSteps);
  }, [events, maxSteps]);

  const getStatusColor = (status: string) => {
    switch (status) {
      case 'completed':
        return 'bg-green-500';
      case 'failed':
        return 'bg-red-500';
      case 'running':
        return 'bg-blue-500';
      default:
        return 'bg-gray-400';
    }
  };

  const getTypeIcon = (type: string) => {
    switch (type) {
      case 'task':
        return '📋';
      case 'tool':
        return '🔧';
      case 'message':
        return '💬';
      case 'error':
        return '❌';
      default:
        return '•';
    }
  };

  const formatTime = (timestamp: string) => {
    try {
      const date = new Date(timestamp);
      return date.toLocaleTimeString();
    } catch {
      return timestamp;
    }
  };

  return (
    <div className="w-full bg-white rounded-lg shadow p-4">
      {/* Header */}
      <div className="mb-4">
        <h3 className="text-sm font-semibold text-gray-700">Execution Timeline</h3>
        <p className="text-xs text-gray-500 mt-1">{timelineSteps.length} steps</p>
      </div>

      {/* Timeline */}
      <div className="space-y-3 max-h-96 overflow-y-auto">
        {timelineSteps.length === 0 ? (
          <div className="text-center text-gray-500 py-8">
            <p className="text-sm">No events yet</p>
          </div>
        ) : (
          timelineSteps.map((step, index) => (
            <div key={step.id} className="flex gap-3">
              {/* Timeline Connector */}
              <div className="flex flex-col items-center">
                {/* Dot */}
                <div
                  className={`w-4 h-4 rounded-full ${getStatusColor(step.status)} flex items-center justify-center text-xs text-white font-bold`}
                >
                  {step.status === 'running' && <div className="w-2 h-2 bg-white rounded-full animate-pulse" />}
                </div>

                {/* Line */}
                {index < timelineSteps.length - 1 && (
                  <div className="w-0.5 h-8 bg-gray-300 mt-1" />
                )}
              </div>

              {/* Content */}
              <div className="flex-1 pb-2">
                <div className="flex items-start justify-between">
                  <div className="flex-1">
                    <p className="text-sm font-medium text-gray-800">
                      <span className="mr-2">{getTypeIcon(step.type)}</span>
                      {step.title}
                    </p>
                    {step.details && (
                      <p className="text-xs text-gray-600 mt-1 truncate">{step.details}</p>
                    )}
                  </div>
                  <div className="text-right ml-2">
                    <p className="text-xs text-gray-500">{formatTime(step.timestamp)}</p>
                    {showDurations && step.duration !== undefined && (
                      <p className="text-xs text-blue-600 font-medium">{step.duration}s</p>
                    )}
                  </div>
                </div>
              </div>
            </div>
          ))
        )}
      </div>
    </div>
  );
};

export default TaskTimeline;
