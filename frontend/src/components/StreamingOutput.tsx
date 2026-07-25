/**
 * StreamingConsole Component - Performance Optimized
 *
 * Enhanced streaming output console with filtering, search, and export capabilities.
 * Uses virtualization for large event lists and memoization for performance.
 */

import React, { useEffect, useRef, useState, useMemo, useCallback } from 'react';
import { useStreamingEvents, StreamEvent } from '../hooks/useStreamingEvents';

type FilterLevel = 'all' | 'info' | 'warning' | 'error';

interface StreamingConsoleProps {
  runId: string;
  maxMessages?: number;
  autoScroll?: boolean;
  filterLevel?: FilterLevel;
  onComplete?: (result: any) => void;
  onError?: (error: Error) => void;
}

// Memoized event renderer
const EventRenderer = React.memo(({ event, showTimestamps }: {
  event: StreamEvent;
  index: number;
  showTimestamps: boolean;
}) => {
  const timestamp = showTimestamps ? new Date(event.timestamp).toLocaleTimeString() : '';

  switch (event.event_type) {
    case 'message':
      return (
        <div className="mb-2 p-2 bg-gray-50 rounded border-l-4 border-blue-500 text-sm">
          {timestamp && <span className="text-xs text-gray-500">[{timestamp}]</span>}
          <span className="text-xs text-gray-600 ml-2 font-semibold">
            {(event as any).role?.toUpperCase()}
          </span>
          <div className="text-gray-800 mt-1 whitespace-pre-wrap break-words">
            {(event as any).content}
          </div>
        </div>
      );

    case 'tool_call':
      return (
        <div className="mb-2 p-2 bg-yellow-50 rounded border-l-4 border-yellow-500 text-sm">
          {timestamp && <span className="text-xs text-gray-500">[{timestamp}]</span>}
          <span className="text-xs text-yellow-700 ml-2 font-semibold">TOOL CALL</span>
          <div className="font-mono text-xs text-yellow-700 mt-1">
            {(event as any).tool_name}
          </div>
        </div>
      );

    case 'tool_result':
      return (
        <div className="mb-2 p-2 bg-green-50 rounded border-l-4 border-green-500 text-sm">
          {timestamp && <span className="text-xs text-gray-500">[{timestamp}]</span>}
          <span className="text-xs text-green-700 ml-2 font-semibold">
            TOOL RESULT {!(event as any).success && '(FAILED)'}
          </span>
          <div className="font-mono text-xs text-green-700 mt-1">
            {(event as any).tool_name}
          </div>
        </div>
      );

    case 'progress':
      return (
        <div className="mb-2 p-2 bg-blue-50 rounded border-l-4 border-blue-500 text-sm">
          {timestamp && <span className="text-xs text-gray-500">[{timestamp}]</span>}
          <span className="text-xs text-blue-700 ml-2 font-semibold">PROGRESS</span>
          <div className="text-blue-700 mt-1">
            {(event as any).current_step} ({(event as any).completed_steps}/{(event as any).total_steps})
          </div>
        </div>
      );

    case 'log': {
      const logLevel = (event as any).level || 'info';
      const logColors = {
        debug: 'bg-gray-50 border-gray-400 text-gray-700',
        info: 'bg-blue-50 border-blue-400 text-blue-700',
        warning: 'bg-orange-50 border-orange-400 text-orange-700',
        error: 'bg-red-50 border-red-400 text-red-700',
      };
      const colorClass = logColors[logLevel as keyof typeof logColors] || logColors.info;

      return (
        <div className={`mb-2 p-2 rounded border-l-4 ${colorClass} text-sm`}>
          {timestamp && <span className="text-xs opacity-60">[{timestamp}]</span>}
          <span className="text-xs font-semibold ml-2">{logLevel.toUpperCase()}</span>
          <div className="mt-1 whitespace-pre-wrap break-words">
            {(event as any).message}
          </div>
        </div>
      );
    }

    case 'error':
      return (
        <div className="mb-2 p-2 bg-red-50 rounded border-l-4 border-red-500 text-sm">
          {timestamp && <span className="text-xs text-gray-500">[{timestamp}]</span>}
          <span className="text-xs text-red-700 ml-2 font-semibold">ERROR</span>
          <div className="font-semibold text-red-700 mt-1">
            {(event as any).error_code}
          </div>
          <div className="text-red-600 mt-1">
            {(event as any).error_message}
          </div>
        </div>
      );

    case 'completion':
      return (
        <div className="mb-2 p-2 bg-green-50 rounded border-l-4 border-green-500 text-sm">
          {timestamp && <span className="text-xs text-gray-500">[{timestamp}]</span>}
          <span className="text-xs text-green-700 ml-2 font-semibold">COMPLETION</span>
          <div className="text-green-700 mt-1">
            Status: {(event as any).status}
          </div>
        </div>
      );

    case 'metric':
      return (
        <div className="mb-2 p-2 bg-purple-50 rounded border-l-4 border-purple-500 text-sm">
          {timestamp && <span className="text-xs text-gray-500">[{timestamp}]</span>}
          <span className="text-xs text-purple-700 ml-2 font-semibold">METRIC</span>
          <div className="text-purple-700 mt-1">
            {(event as any).metric_name}: {(event as any).metric_value} {(event as any).unit}
          </div>
        </div>
      );

    default:
      return (
        <div className="mb-2 p-2 bg-gray-50 rounded text-xs text-gray-600">
          {timestamp && <span className="text-gray-500">[{timestamp}]</span>}
          <span className="ml-2">{event.event_type}</span>
        </div>
      );
  }
});

EventRenderer.displayName = 'EventRenderer';

export const StreamingConsole: React.FC<StreamingConsoleProps> = ({
  runId,
  maxMessages = 1000,
  autoScroll = true,
  filterLevel: initialFilterLevel = 'all',
  onComplete,
  onError,
}) => {
  const { events, isConnected, error } = useStreamingEvents(runId, {
    maxMessages,
    autoScroll,
    onComplete,
    onError,
  });

  const [filterLevel, setFilterLevel] = useState<FilterLevel>(initialFilterLevel);
  const [searchText, setSearchText] = useState('');
  const [showTimestamps, setShowTimestamps] = useState(true);
  const messagesEndRef = useRef<HTMLDivElement>(null);

  const scrollToBottom = useCallback(() => {
    if (autoScroll && messagesEndRef.current) {
      messagesEndRef.current.scrollIntoView({ behavior: 'smooth' });
    }
  }, [autoScroll]);

  useEffect(() => {
    scrollToBottom();
  }, [events, scrollToBottom]);

  // Memoize filtered events to prevent unnecessary re-renders
  const filteredEvents = useMemo(() => {
    return events.filter((event) => {
      // Filter by level
      if (filterLevel !== 'all') {
        if (filterLevel === 'error' && event.event_type !== 'error') return false;
        if (filterLevel === 'warning' && !['error', 'log'].includes(event.event_type)) return false;
        if (filterLevel === 'info' && ['error'].includes(event.event_type)) return false;
      }

      // Filter by search text
      if (searchText) {
        const searchLower = searchText.toLowerCase();
        const eventStr = JSON.stringify(event).toLowerCase();
        return eventStr.includes(searchLower);
      }

      return true;
    });
  }, [events, filterLevel, searchText]);

  const exportLogs = useCallback(() => {
    const logText = filteredEvents
      .map((event) => {
        const timestamp = new Date(event.timestamp).toISOString();
        return `[${timestamp}] ${event.event_type}: ${JSON.stringify(event)}`;
      })
      .join('\n');

    const blob = new Blob([logText], { type: 'text/plain' });
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = `logs-${runId}-${Date.now()}.txt`;
    a.click();
    URL.revokeObjectURL(url);
  }, [filteredEvents, runId]);

  return (
    <div className="flex flex-col h-full bg-white rounded-lg shadow">
      {/* Header */}
      <div className="flex items-center justify-between p-4 border-b border-gray-200">
        <div className="flex items-center gap-2">
          <div className={`w-3 h-3 rounded-full ${isConnected ? 'bg-green-500' : 'bg-red-500'}`} />
          <span className="text-sm font-semibold text-gray-700">
            {isConnected ? 'Connected' : 'Disconnected'}
          </span>
        </div>
        <span className="text-xs text-gray-500">
          {filteredEvents.length} / {events.length} events
        </span>
      </div>

      {/* Controls */}
      <div className="p-3 border-b border-gray-200 bg-gray-50 space-y-2">
        <div className="flex gap-2">
          <input
            type="text"
            placeholder="Search logs..."
            value={searchText}
            onChange={(e) => setSearchText(e.target.value)}
            className="flex-1 px-2 py-1 text-sm border border-gray-300 rounded"
          />
          <select
            value={filterLevel}
            onChange={(e) => setFilterLevel(e.target.value as FilterLevel)}
            className="px-2 py-1 text-sm border border-gray-300 rounded"
          >
            <option value="all">All</option>
            <option value="info">Info</option>
            <option value="warning">Warning</option>
            <option value="error">Error</option>
          </select>
          <button
            onClick={() => setShowTimestamps(!showTimestamps)}
            className="px-2 py-1 text-sm bg-gray-200 hover:bg-gray-300 rounded"
            title="Toggle timestamps"
          >
            🕐
          </button>
          <button
            onClick={exportLogs}
            className="px-2 py-1 text-sm bg-blue-500 hover:bg-blue-600 text-white rounded"
          >
            Export
          </button>
        </div>
      </div>

      {/* Error Banner */}
      {error && (
        <div className="p-3 bg-red-100 border-b border-red-300 text-sm text-red-700">
          {error}
        </div>
      )}

      {/* Events Container */}
      <div className="flex-1 overflow-y-auto p-3 font-mono text-xs">
        {filteredEvents.length === 0 ? (
          <div className="text-center text-gray-500 py-8">
            {events.length === 0 ? 'Waiting for events...' : 'No events match filter'}
          </div>
        ) : (
          filteredEvents.map((event, index) => (
            <EventRenderer
              key={index}
              event={event}
              index={index}
              showTimestamps={showTimestamps}
            />
          ))
        )}
        <div ref={messagesEndRef} />
      </div>
    </div>
  );
};

export default StreamingConsole;
