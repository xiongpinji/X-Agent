/**
 * Agent execution resource: one-shot run + SSE streaming.
 *
 * Backend surface (backend/app/api/agents.py + backend/app/api/streaming.py):
 *   POST /api/v1/agents/run             — synchronous agent run
 *   POST /api/v1/agent/run/stream       — start a run, returns run_id/stream_url
 *   GET  /api/v1/agent/stream/{run_id}  — SSE event stream (terminal: completion|error)
 *   GET  /api/v1/agent/stream/{run_id}/events — buffered event history (polling)
 */

import type { XAgentClient, RequestOptions } from "./client.js";
import type {
  AgentRunRequest,
  AgentRunResponse,
  AgentStreamRunRequest,
  StreamEventEnvelope,
  StreamEventsResponse,
  StreamRunStartResponse,
} from "./types.js";

// ---------------------------------------------------------------------------
// SSE parsing (fetch ReadableStream -> AsyncIterable of envelopes)
// ---------------------------------------------------------------------------

/** One parsed SSE frame. */
export interface SseMessage {
  /** Value of the `event:` line, when present. */
  event: string | undefined;
  /** `data:` lines joined with "\n". null when the frame had no data. */
  data: string | null;
  /** Value of the `id:` line, when present. */
  id: string | undefined;
  /** Reconnection hint from `retry:`, in ms. */
  retry: number | undefined;
}

/**
 * Parse a single SSE frame (lines already separated by \n).
 * Returns null for frames that carry no dispatchable content
 * (comments / keep-alives / empty frames).
 */
export function parseSseFrame(frame: string): SseMessage | null {
  let event: string | undefined;
  let id: string | undefined;
  let retry: number | undefined;
  const dataLines: string[] = [];

  for (const rawLine of frame.split("\n")) {
    if (rawLine === "" || rawLine.startsWith(":")) continue; // blank / comment
    const colonIndex = rawLine.indexOf(":");
    const field = colonIndex === -1 ? rawLine : rawLine.slice(0, colonIndex);
    let value = colonIndex === -1 ? "" : rawLine.slice(colonIndex + 1);
    if (value.startsWith(" ")) value = value.slice(1); // strip ONE leading space per spec

    if (field === "data") dataLines.push(value);
    else if (field === "event") event = value;
    else if (field === "id") id = value;
    else if (field === "retry") {
      const parsed = Number.parseInt(value, 10);
      if (!Number.isNaN(parsed)) retry = parsed;
    }
    // Unknown fields are ignored per the SSE spec.
  }

  if (dataLines.length === 0 && event === undefined) return null;
  return {
    event,
    data: dataLines.length ? dataLines.join("\n") : null,
    id,
    retry,
  };
}

/**
 * Incremental SSE parser over a fetch ReadableStream.
 * Handles chunk boundaries splitting frames mid-line, CRLF/LF line endings,
 * multi-line `data:` fields and comment frames. Cancels the underlying reader
 * when the consumer stops early (break/return/throw).
 */
export async function* parseSseStream(
  body: ReadableStream<Uint8Array>,
  options: { signal?: AbortSignal } = {},
): AsyncGenerator<SseMessage, void, unknown> {
  const reader = body.getReader();
  const decoder = new TextDecoder("utf-8");
  let buffer = "";
  try {
    while (true) {
      if (options.signal?.aborted) return;
      const { done, value } = await reader.read();
      if (done) break;
      // Normalize CRLF / CR to LF so frame boundaries are always "\n\n".
      buffer += decoder.decode(value, { stream: true }).replace(/\r\n?/g, "\n");

      let boundary = buffer.indexOf("\n\n");
      while (boundary !== -1) {
        const frame = buffer.slice(0, boundary);
        buffer = buffer.slice(boundary + 2);
        const message = parseSseFrame(frame);
        if (message) {
          if (options.signal?.aborted) return; // responsive cancellation
          yield message;
        }
        boundary = buffer.indexOf("\n\n");
      }
    }
    // Flush the decoder and any trailing frame that lacked a final blank line.
    buffer += decoder.decode();
    const tail = buffer.trim() ? parseSseFrame(buffer) : null;
    if (tail) yield tail;
  } finally {
    try {
      await reader.cancel();
    } catch {
      // Reader already closed/cancelled — nothing to do.
    }
  }
}

/**
 * Convert an SSE frame into the backend StreamEvent envelope.
 * The backend always sends the full envelope JSON on the data line
 * (`{event_type, timestamp, run_id, data, sequence}`); the `event:` line is
 * the fallback/cross-check source for event_type.
 */
export function toStreamEventEnvelope(message: SseMessage): StreamEventEnvelope | null {
  if (message.data === null) return null;
  let parsed: unknown;
  try {
    parsed = JSON.parse(message.data);
  } catch {
    return null;
  }
  if (typeof parsed !== "object" || parsed === null) return null;
  const record = parsed as Record<string, unknown>;
  const eventType =
    typeof record.event_type === "string" ? record.event_type : (message.event ?? "message");
  return {
    event_type: eventType,
    timestamp: typeof record.timestamp === "string" ? record.timestamp : "",
    run_id: typeof record.run_id === "string" ? record.run_id : "",
    data: (typeof record.data === "object" && record.data !== null
      ? (record.data as Record<string, unknown>)
      : {}) as Record<string, unknown>,
    sequence: typeof record.sequence === "number" ? record.sequence : 0,
  };
}

/** Options for stream consumption. */
export interface StreamOptions {
  /** Abort the stream (cooperative: iteration ends, connection is released). */
  signal?: AbortSignal;
  /** Resume from a sequence number (GET /agent/stream/{run_id}?since_sequence=N). */
  sinceSequence?: number;
  /** Timeout for the initial POST /agent/run/stream call. Default: client default. */
  startTimeoutMs?: number;
}

/** Handle returned by {@link AgentsResource.runStream}. */
export interface ActiveAgentStream {
  run_id: string;
  trace_id: string;
  stream_url: string;
  status: string;
  /**
   * AsyncIterable of SSE events in order. Ends naturally after a terminal
   * `completion` / `error` event (server closes the stream there) or when
   * the provided AbortSignal fires.
   */
  events: AsyncGenerator<StreamEventEnvelope, void, unknown>;
}

// ---------------------------------------------------------------------------
// Resource
// ---------------------------------------------------------------------------

/** Agent run + streaming resource. */
export class AgentsResource {
  constructor(private readonly client: XAgentClient) {}

  /**
   * POST /api/v1/agents/run — run the agent to completion and return the
   * full result (answer, tool_calls, plan, execution_summary, ...).
   */
  async run(request: AgentRunRequest, options?: { signal?: AbortSignal }): Promise<AgentRunResponse> {
    return this.client.request<AgentRunResponse>("POST", "/api/v1/agents/run", {
      body: request,
      signal: options?.signal,
    });
  }

  /**
   * POST /api/v1/agent/run/stream, then consume GET /api/v1/agent/stream/{run_id}.
   *
   * Usage:
   * ```ts
   * const stream = await client.agents.runStream({ task: "..." });
   * for await (const event of stream.events) {
   *   if (event.event_type === "completion") { /* done *\/ }
   * }
   * ```
   *
   * The events iterable terminates after the terminal event
   * (`completion` or `error`), mirroring the server closing the stream.
   */
  async runStream(
    request: AgentStreamRunRequest,
    options: StreamOptions = {},
  ): Promise<ActiveAgentStream> {
    const start = await this.client.request<StreamRunStartResponse>(
      "POST",
      "/api/v1/agent/run/stream",
      {
        body: {
          task: request.task,
          extra_context: request.extra_context ?? {},
          ...(request.session_id !== undefined ? { session_id: request.session_id } : {}),
        },
        signal: options.signal,
        timeoutMs: options.startTimeoutMs,
      },
    );
    return {
      run_id: start.run_id,
      trace_id: start.trace_id,
      stream_url: start.stream_url,
      status: start.status,
      events: this.iterateRunStream(start.run_id, options),
    };
  }

  /**
   * Subscribe to an already-started run's SSE stream
   * (GET /api/v1/agent/stream/{run_id}). Use `sinceSequence` to re-attach
   * without replaying buffered events.
   */
  subscribeStream(
    runId: string,
    options: StreamOptions = {},
  ): AsyncGenerator<StreamEventEnvelope, void, unknown> {
    return this.iterateRunStream(runId, options);
  }

  /**
   * GET /api/v1/agent/stream/{run_id}/events — buffered event history for a
   * run (polling fallback when SSE is unavailable, e.g. some proxies).
   */
  async streamEvents(
    runId: string,
    options: { sinceSequence?: number; limit?: number; signal?: AbortSignal } = {},
    requestOptions: RequestOptions = {},
  ): Promise<StreamEventsResponse> {
    return this.client.request<StreamEventsResponse>(
      "GET",
      `/api/v1/agent/stream/${encodeURIComponent(runId)}/events`,
      {
        query: {
          since_sequence: options.sinceSequence,
          limit: options.limit,
        },
        signal: options.signal,
        ...requestOptions,
      },
    );
  }

  private async *iterateRunStream(
    runId: string,
    options: StreamOptions,
  ): AsyncGenerator<StreamEventEnvelope, void, unknown> {
    const response = await this.client.requestStream(
      "GET",
      `/api/v1/agent/stream/${encodeURIComponent(runId)}`,
      {
        query: { since_sequence: options.sinceSequence },
        signal: options.signal,
      },
    );
    if (!response.body) {
      return; // Server sent an empty stream — treat as immediately complete.
    }

    for await (const message of parseSseStream(response.body, { signal: options.signal })) {
      const envelope = toStreamEventEnvelope(message);
      if (!envelope) continue;
      yield envelope;
      // Terminal events close the stream server-side (streaming.py
      // TERMINAL_EVENT_TYPES); end the iteration as soon as we see one so
      // consumers get a natural stop even behind buffering proxies.
      if (envelope.event_type === "completion" || envelope.event_type === "error") {
        return;
      }
    }
  }
}
