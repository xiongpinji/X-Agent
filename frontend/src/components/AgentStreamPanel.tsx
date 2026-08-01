/**
 * AgentStreamPanel Component
 *
 * Self-contained panel that handles task input and real-time streaming output
 * via the POST /agents/run/stream SSE endpoint. Replaces the old broken
 * store + EventSource pattern with a fetch-based ReadableStream consumer.
 */

import React, { useCallback, useEffect, useRef, useState } from 'react';
import { useAgentStream, TraceEvent, AgentStreamResult } from '../hooks/useAgentStream';

// ─── Event Renderers ───────────────────────────────────────────────────────────

const ToolCallBadge: React.FC<{ event: TraceEvent }> = ({ event }) => (
  <div className="stream-event stream-event--tool-call">
    <span className="stream-event__icon">🔧</span>
    <div className="stream-event__body">
      <span className="stream-event__label">Tool Call</span>
      <code className="stream-event__tool-name">{event.tool_name || event.data?.tool_name || 'unknown'}</code>
      {event.arguments && (
        <pre className="stream-event__args">{formatArgs(event.arguments)}</pre>
      )}
    </div>
  </div>
);

const ToolResultBadge: React.FC<{ event: TraceEvent }> = ({ event }) => {
  const success = event.success !== false && event.data?.success !== false;
  return (
    <div className={`stream-event ${success ? 'stream-event--success' : 'stream-event--error'}`}>
      <span className="stream-event__icon">{success ? '✅' : '❌'}</span>
      <div className="stream-event__body">
        <span className="stream-event__label">
          {event.tool_name || event.data?.tool_name || 'tool'} {success ? 'succeeded' : 'failed'}
        </span>
        {event.result && (
          <pre className="stream-event__result">{truncate(JSON.stringify(event.result, null, 2), 500)}</pre>
        )}
      </div>
    </div>
  );
};

const MessageBadge: React.FC<{ event: TraceEvent }> = ({ event }) => (
  <div className="stream-event stream-event--message">
    <span className="stream-event__icon">💬</span>
    <div className="stream-event__body">
      <span className="stream-event__label">{(event.role || 'assistant').toUpperCase()}</span>
      <div className="stream-event__content">{event.content || event.message || ''}</div>
    </div>
  </div>
);

const ProgressBadge: React.FC<{ event: TraceEvent }> = ({ event }) => (
  <div className="stream-event stream-event--progress">
    <span className="stream-event__icon">📊</span>
    <div className="stream-event__body">
      <span className="stream-event__label">
        {event.current_step || event.data?.current_step || 'Working...'}
        {event.total_steps ? ` (${event.completed_steps || 0}/${event.total_steps})` : ''}
      </span>
      {typeof event.overall_progress === 'number' && (
        <div className="stream-progress-bar">
          <div className="stream-progress-bar__fill" style={{ width: `${Math.round(event.overall_progress * 100)}%` }} />
        </div>
      )}
    </div>
  </div>
);

const GenericBadge: React.FC<{ event: TraceEvent }> = ({ event }) => (
  <div className="stream-event stream-event--generic">
    <span className="stream-event__icon">📋</span>
    <div className="stream-event__body">
      <span className="stream-event__label">{event.event_type || event.type || 'event'}</span>
      <pre className="stream-event__result">{truncate(JSON.stringify(event, null, 2), 300)}</pre>
    </div>
  </div>
);

function renderEvent(event: TraceEvent, index: number) {
  const type = event.event_type || event.type || '';
  let el: React.ReactNode;
  switch (type) {
    case 'tool_call':
      el = <ToolCallBadge event={event} />;
      break;
    case 'tool_result':
      el = <ToolResultBadge event={event} />;
      break;
    case 'message':
      el = <MessageBadge event={event} />;
      break;
    case 'progress':
      el = <ProgressBadge event={event} />;
      break;
    case 'error':
      el = (
        <div className="stream-event stream-event--error">
          <span className="stream-event__icon">⚠️</span>
          <div className="stream-event__body">
            <span className="stream-event__label">Error</span>
            <div className="stream-event__content">{event.error_message || event.message || JSON.stringify(event)}</div>
          </div>
        </div>
      );
      break;
    default:
      el = <GenericBadge event={event} />;
  }
  return <div key={index}>{el}</div>;
}

// ─── Helpers ───────────────────────────────────────────────────────────────────

function formatArgs(args: Record<string, any>): string {
  const entries = Object.entries(args);
  if (entries.length === 0) return '{}';
  if (entries.length <= 2) {
    return entries.map(([k, v]) => `${k}: ${truncate(String(v), 80)}`).join(', ');
  }
  return JSON.stringify(args, null, 2).slice(0, 200);
}

function truncate(s: string, max: number): string {
  return s.length > max ? s.slice(0, max) + '…' : s;
}

// ─── Main Component ────────────────────────────────────────────────────────────

export interface AgentStreamPanelProps {
  onRunComplete?: (result: AgentStreamResult) => void;
  onError?: (error: string) => void;
}

export const AgentStreamPanel: React.FC<AgentStreamPanelProps> = ({ onRunComplete, onError }) => {
  const [taskInput, setTaskInput] = useState('');
  const [showAdvanced, setShowAdvanced] = useState(false);
  const [extraContextStr, setExtraContextStr] = useState('');
  const scrollRef = useRef<HTMLDivElement>(null);

  const { events, isStreaming, finalResult, error, startStream, stopStream, reset } = useAgentStream({
    onComplete: (result) => onRunComplete?.(result),
    onError: (err) => onError?.(err),
  });

  // Auto-scroll to bottom on new events
  useEffect(() => {
    if (scrollRef.current) {
      scrollRef.current.scrollTop = scrollRef.current.scrollHeight;
    }
  }, [events.length]);

  const handleStart = useCallback(async () => {
    if (!taskInput.trim() || isStreaming) return;
    let extraContext: Record<string, any> | undefined;
    if (showAdvanced && extraContextStr.trim()) {
      try {
        extraContext = JSON.parse(extraContextStr);
      } catch {
        extraContext = { raw_context: extraContextStr };
      }
    }
    await startStream(taskInput.trim(), extraContext);
    setTaskInput('');
  }, [taskInput, isStreaming, showAdvanced, extraContextStr, startStream]);

  const handleKeyDown = useCallback((e: React.KeyboardEvent) => {
    if (e.key === 'Enter' && (e.ctrlKey || e.metaKey)) {
      e.preventDefault();
      handleStart();
    }
  }, [handleStart]);

  return (
    <div className="agent-stream-panel">
      {/* Input Area */}
      <div className="agent-stream-panel__input">
        <textarea
          value={taskInput}
          onChange={(e) => setTaskInput(e.target.value)}
          onKeyDown={handleKeyDown}
          placeholder="描述你的任务... (Ctrl+Enter 发送)"
          className="agent-stream-panel__textarea"
          disabled={isStreaming}
          rows={3}
        />
        <div className="agent-stream-panel__actions">
          <button
            onClick={handleStart}
            disabled={isStreaming || !taskInput.trim()}
            className="btn btn-primary"
          >
            {isStreaming ? '⏳ 执行中...' : '🚀 执行'}
          </button>
          {isStreaming && (
            <button onClick={stopStream} className="btn btn-danger">
              ⏹ 停止
            </button>
          )}
          {!isStreaming && events.length > 0 && (
            <button onClick={reset} className="btn btn-secondary">
              🗑 清空
            </button>
          )}
          <button
            onClick={() => setShowAdvanced(!showAdvanced)}
            className="btn btn-ghost btn-sm"
          >
            {showAdvanced ? '收起' : '高级'}
          </button>
        </div>
        {showAdvanced && (
          <textarea
            value={extraContextStr}
            onChange={(e) => setExtraContextStr(e.target.value)}
            placeholder='额外上下文 (JSON)，如 {"workspace": "backend/"}'
            className="agent-stream-panel__context"
            rows={2}
          />
        )}
      </div>

      {/* Status Bar */}
      {(isStreaming || finalResult || error) && (
        <div className={`agent-stream-panel__status ${error ? 'status--error' : finalResult ? 'status--done' : 'status--running'}`}>
          {isStreaming && <span className="status-spinner" />}
          {isStreaming && <span>Agent 正在工作... ({events.length} events)</span>}
          {finalResult && !error && (
            <span>
              ✅ 完成 — 状态: {finalResult.result?.status || 'completed'}
              {finalResult.result?.iterations ? ` | 迭代: ${finalResult.result.iterations}` : ''}
              {finalResult.result?.tool_calls ? ` | 工具调用: ${finalResult.result.tool_calls.length}` : ''}
            </span>
          )}
          {error && <span>❌ {error}</span>}
        </div>
      )}

      {/* Stream Output */}
      <div className="agent-stream-panel__output" ref={scrollRef}>
        {events.length === 0 && !isStreaming ? (
          <div className="agent-stream-panel__empty">
            <div className="empty-icon">🤖</div>
            <div className="empty-text">输入任务，Agent 将实时展示每一步操作</div>
            <div className="empty-hint">支持：写代码、跑测试、修 Bug、Git 提交</div>
          </div>
        ) : (
          events.map((event, i) => renderEvent(event, i))
        )}
      </div>

      {/* Final Answer */}
      {finalResult?.result?.answer && (
        <div className="agent-stream-panel__answer">
          <h4>📝 Agent 回复</h4>
          <div className="answer-content">{finalResult.result.answer}</div>
        </div>
      )}
    </div>
  );
};

export default AgentStreamPanel;
